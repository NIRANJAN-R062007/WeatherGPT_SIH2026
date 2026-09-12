# Internal hackathon prototype (plan.md §14)

Cut-down build. Not the full product — see plan.md §14 for the full scope,
task list, and explicit out-of-scope list.

## What's here

- `ask_service/config.py` — repo paths, API keys (from a gitignored repo-root
  `.env`), CORS origins. Never raises at import; `require()` fails loudly at
  point of use.
- `ask_service/intent.py` — rule-based parser for the two demo intents
  (`current_weather`, `will_it_rain`). Rain/day keywords are matched in both
  English and Tamil (மழை; இன்று/நாளை/இன்றிரவு), so native-language queries
  like "நாளை சென்னையில் மழை பெய்யுமா?" resolve correctly. Full NLU (richer,
  less rigid phrasings) is still a follow-up.
- `ask_service/cities.py` + `data/cities.json` — the demo city registry
  (Chennai, Madurai, Coimbatore): key, lat/lon, EN/TA names, aliases.
  `data/cities.json` is the source of truth; the frontend keeps a copy until
  it fetches `GET /cities`.
- `ask_service/google_weather.py` — fetches currentConditions / forecast/days,
  decodes the enums via `data/decoders/`, caches in memory (15 min / 6 h TTLs),
  and **replays the committed fixtures on any live-call failure** so the demo
  needs no network.
- `ask_service/weather_data.py` — facade over `google_weather`. `get_weather
  (city, intent, day)` returns a flat, intent-aware facts dict.
- `ask_service/narrate.py` — Gemini narration. Returns `None` (→ template) on
  non-English, no key, timeout, or any error; the guardrail still validates
  whatever it returns. Always produces English — Tamil narration goes through
  `bhashini.py` on top of this, not through narrate() itself.
- `ask_service/bhashini.py` — EN→TA translation of the *already-grounded*
  Gemini sentence, via the ULCA two-stage flow (config call resolves a
  pipeline + inference key, then a compute call runs the translation).
  Returns `None` (→ template) on no credentials, timeout, or any error;
  `main.py` re-runs the guardrail on the Tamil output too, since translation
  can itself introduce numeric drift.
- `ask_service/i18n.py` — EN/TA phrase templates (the fallback). `CONDITION_*`
  keys are the canonical decoder targets (lowercased `weatherCondition.type`).
- `ask_service/guardrail.py` — grounding guardrail + numeric validator
  (plan.md §4, "non-negotiable"). Extracts every numeric token from the
  narrated answer and requires each to match a raw field of a compatible unit
  (unit-aware: `"20°C"` cannot pass by matching a `rain_probability_pct` of
  20). On failure `/ask` re-renders from the template, then refuses rather
  than guess (§2.3).
- `ask_service/main.py` — `/ask` (intent → city resolve → weather lookup →
  narration seam → guardrail → typed response + provenance), plus `/health`,
  `/cities`, and `/facts` (raw facts dict for UI surfaces like the hero card
  that need individual fields rather than a narrated sentence).
- `ask_service/snapshot_google_weather.py` — fetches and commits real API
  fixtures; doubles as the Google Weather key verifier.
- `ask_service/verify_gemini.py` — Gemini key verifier + model probe.

### The `grounding` block

Every successful (and refused) `/ask` response carries a `grounding` object
matching what `WeatherGPT.dc.html` renders as the "Validator: n/n matched" chip
and "View source" panel:

```json
"grounding": {
  "ok": true, "matched": 3, "total": 3,
  "figures": [{"reading": "28°C", "value": 28.0, "unit": "celsius",
               "path": "temp_c", "matched": true}, ...],
  "narration": "llm",          // "llm" | "llm+bhashini" | "template"
  "fallback_used": false        // true only if an LLM answer was produced but
}                                //   it (or its Tamil translation) failed to ground
```

## Integration

The frontend calls `ask_service` **directly** (not through `services/gateway`).
The gateway is a Phase-0 skeleton with no `/ask` route and a `/health` that
needs Postgres + PostGIS + Redis — three things that can fail on stage. Direct
means the demo depends on one uvicorn process. Post-hackathon the prototype
moves into `services/orchestrator/` behind the gateway and the frontend's
`apiBase` changes from `http://localhost:8001` to the gateway URL.

CORS on `/ask` is open (`ALLOWED_ORIGINS`, default `*`) — GET-only, no
credentials, and it covers a `file://` origin.

**`WEATHER_MODE`** (`.env`): `auto` (default — live, fixture fallback) |
`live` (no fallback, fail loud in dev) | `fixtures` (never touch the network —
the demo-morning kill switch if venue Wi-Fi is dead). The in-memory weather
cache is per-process; running uvicorn with `--workers > 1` multiplies API
calls.

### `/ask` response contract

| case | HTTP | body keys |
|---|---|---|
| success | 200 | `intent, city, day, response, provenance{source,issued,is_live,retrieved_at}, grounding{ok,matched,total,figures[],narration,fallback_used}` |
| unsupported / unrecognized | 200 | `intent, message` (no `city`) |
| weather query, no city named | 200 | `intent, message` (pass `?city=` to disambiguate) |
| no data for city | 200 | `intent, city, message` |
| guardrail refusal | 200 | `intent, city, message, grounding` |

Frontend mapping: `tokens[]` ← `grounding.figures[].{reading, path}`;
"Validator n/n matched" ← `matched`/`total`; source line ← `provenance`;
error card ← a fetch/network failure; refusal card ← a body with `message`.

## Key status

- **Google Weather API**: verified 2026-09-10. Fixtures committed under
  `data/fixtures/google_weather/`.
- **Gemini**: key verified 2026-09-10, model `gemini-flash-latest`
  (`GEMINI_MODEL` in `.env` / `.env.example`; reachable models in
  `data/fixtures/gemini/models.json`). The key has an `AQ.` prefix (ephemeral-
  token shape, not a standard `AIza...` key) — re-run `verify_gemini.py` at the
  start of each session and on demo morning; if it starts returning 401/403,
  mint a durable key at https://aistudio.google.com/apikey.
- **Bhashini**: `BHASHINI_USER_ID` / `BHASHINI_ULCA_API_KEY` in `.env` are
  currently empty — get one at https://bhashini.gov.in (Login → your name/menu
  → "My Profile" → "Generate New Inference API Key"; the userID + ULCA key are
  shown together there). Until they're filled in, `bhashini.is_configured()`
  is `False` and every Tamil `/ask` call falls straight through to the
  hand-written i18n template — same demo-safe behavior as before this was
  wired in, just now upgradeable without a code change.

## Weather + narration

Weather and English narration are live: `weather_data.get_weather()` pulls
real Google Weather data (cached, with a fixture fallback), and `narrate()`
runs it through Gemini. For Tamil, `main.py` takes that grounded English
sentence and translates it with `bhashini.translate_to_tamil()`; the guardrail
re-checks the Tamil output (translation can shift a number), and `main.py`
falls back to the i18n template on any failure at any step — no Gemini key,
no Bhashini credentials, an ungrounded English draft, or a bad translation.
`data/decoders/` (owned by Deepthi per §12) and the `i18n` condition keys
(Niranjan) both still need a native Tamil QA pass — that now doubles as QA for
Bhashini's raw output too, since a native speaker is the only way to catch a
translation that's grammatically fine but weather-wrong.
Free-tier Gemini is rate-limited (~a few RPM) — fine for a demo, and every
throttle just yields a template answer.

## Run it

```
python -m venv .venv && .venv/bin/pip install -r prototype/ask_service/requirements.txt

# terminal 1 — API
cd prototype/ask_service && ../../.venv/bin/uvicorn main:app --reload --port 8001

# terminal 2 — frontend
cd prototype/frontend && python -m http.server 8777
```

```
curl "http://localhost:8001/health"
curl "http://localhost:8001/ask?text=what's the weather in Chennai&lang=en"
curl "http://localhost:8001/ask?text=will it rain in Madurai tomorrow&lang=ta"
```

## Public URL (stable host pin, plan.md §14 — Niranjan)

Fixed hostname: **`https://plaza-syrup-appetizer.ngrok-free.dev`** → forwards to
`ask_service` on `:8001`. This replaces the old Cloudflare *quick* tunnel,
which minted a new random hostname on every restart and blocked Deepthi's
OAuth redirect URI from being pre-registerable. ngrok's free tier includes
one static/reserved domain that never changes across restarts.

```
# terminal 3 — public tunnel (after ask_service is running on :8001)
./prototype/run_tunnel.sh
```

One-time machine setup (already done on this host, needed on any other):
1. `brew install ngrok/ngrok/ngrok`
2. `ngrok config add-authtoken <token>` — token from
   https://dashboard.ngrok.com/get-started/your-authtoken
3. Static domain is already claimed on the account (dashboard.ngrok.com/domains);
   don't reclaim, it's shared.

Free-tier ngrok domains show an interstitial warning page to plain browser
requests; the frontend's `api()` fetch sends `ngrok-skip-browser-warning: 1`
to skip it (`WeatherGPT.dc.html`). `apiBase` in the canvas now defaults to
the fixed ngrok URL instead of the old Cloudflare one.

## Tests

```
.venv/bin/pytest prototype/ask_service/tests/ -v
```

`tests/conftest.py` blocks real network in every test (the two `live`-marked
smoke tests run only with `-m live`) and defaults `WEATHER_MODE` to `fixtures`
so the suite is deterministic. A repo-root `conftest.py` puts the flat-import
modules on `sys.path`.
