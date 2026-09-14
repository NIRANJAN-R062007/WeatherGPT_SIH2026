# Internal hackathon prototype (plan.md §14)

Cut-down build. Not the full product — see plan.md §14 for the full scope,
task list, and explicit out-of-scope list.

**Layout (post-hackathon, 2026-09-14):** the backend that started life as
`prototype/ask_service/` now lives at **`services/orchestrator/`** and sits
behind `services/gateway/` (a reverse proxy on `:8000`). Only the frontend
(`prototype/frontend/`) and this README remain under `prototype/`. Module
paths below are relative to `services/orchestrator/`.

## What's here

- `orchestrator/config.py` — repo paths, API keys (from a gitignored repo-root
  `.env`), CORS origins. Never raises at import; `require()` fails loudly at
  point of use.
- `orchestrator/intent.py` — rule-based parser for the two demo intents
  (`current_weather`, `will_it_rain`). Rain/day keywords are matched in both
  English and Tamil (மழை; இன்று/நாளை/இன்றிரவு), so native-language queries
  like "நாளை சென்னையில் மழை பெய்யுமா?" resolve correctly. Full NLU (richer,
  less rigid phrasings) is still a follow-up.
- `orchestrator/cities.py` + `data/cities.json` — the demo city registry
  (Chennai, Madurai, Coimbatore): key, lat/lon, EN/TA names, aliases.
  `data/cities.json` is the source of truth; the frontend keeps a copy until
  it fetches `GET /cities`.
- `orchestrator/google_weather.py` — fetches currentConditions / forecast/days,
  decodes the enums via `data/decoders/`, caches in memory (15 min / 6 h TTLs),
  and **replays the committed fixtures on any live-call failure** so the demo
  needs no network.
- `orchestrator/weather_data.py` — facade over `google_weather`. `get_weather
  (city, intent, day)` returns a flat, intent-aware facts dict.
- `orchestrator/narrate.py` — Gemini → Groq → Ollama behind `narrate.providers()`
  (plan.md §8 Phase 6), one pluggable chain shared by narration and NLU. Returns
  `None` (→ template) on non-English, nothing configured, timeout, or any
  error; the guardrail still validates whatever it returns. Always produces
  English — Tamil narration goes through `bhashini.py` on top of this, not
  through narrate() itself.
- `orchestrator/bhashini.py` — EN→TA translation of the *already-grounded*
  Gemini sentence, via the ULCA two-stage flow (config call resolves a
  pipeline + inference key, then a compute call runs the translation).
  Returns `None` (→ template) on no credentials, timeout, or any error;
  `main.py` re-runs the guardrail on the Tamil output too, since translation
  can itself introduce numeric drift.
- `orchestrator/i18n.py` — EN/TA phrase templates (the fallback). `CONDITION_*`
  keys are the canonical decoder targets (lowercased `weatherCondition.type`).
- `orchestrator/guardrail.py` — grounding guardrail + numeric validator
  (plan.md §4, "non-negotiable"). Extracts every numeric token from the
  narrated answer and requires each to match a raw field of a compatible unit
  (unit-aware: `"20°C"` cannot pass by matching a `rain_probability_pct` of
  20). On failure `/ask` re-renders from the template, then refuses rather
  than guess (§2.3).
- `orchestrator/main.py` — `/ask` (intent → city resolve → weather lookup →
  narration seam → guardrail → typed response + provenance), plus `/health`,
  `/cities`, and `/facts` (raw facts dict for UI surfaces like the hero card
  that need individual fields rather than a narrated sentence).
- `orchestrator/snapshot_google_weather.py` — fetches and commits real API
  fixtures; doubles as the Google Weather key verifier.
- `orchestrator/verify_gemini.py` — Gemini key verifier + model probe.

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
  "fallback_used": false,       // true only if an LLM answer was produced but
                                 //   it (or its Tamil translation) failed to ground
  "provider": "ollama"          // "gemini" | "groq" | "ollama" | "template" —
}                                //   which link of narrate.providers() answered;
                                 //   Chelsea: drive an "answered by local Llama"
                                 //   tag off this in the frontend
```

## Integration

The frontend goes **through `services/gateway`** (`:8000`), which reverse-
proxies every path except its own `/health` to the orchestrator (`:8001`) and
appends the client address to `X-Forwarded-For` so the orchestrator's
per-client rate limit still keys the real caller. The gateway's Postgres/Redis
checks are lazy and only affect `/health`, so the proxy works with neither
running — the demo still depends on two uvicorn processes and nothing else.
Hitting the orchestrator directly on `:8001` keeps working (set
`TUNNEL_PORT=8001` for `run_tunnel.sh`). The frontend's `apiBase` is the
fixed ngrok hostname, so it needed no change — only what the tunnel points at
did. (Before 2026-09-14 the frontend called the prototype directly because the
old gateway had no `/ask` route and a DB-dependent `/health`.)

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
- **Narration/NLU chain**: Gemini → Groq → Ollama behind `narrate.providers()`
  (plan.md §8 Phase 6) — see "Offline mode" below for the Ollama leg.
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

## Offline mode (demo kill switch)

Plan.md §8 Phase 6: a dead venue network shouldn't kill the demo. `OFFLINE_MODE=1`
forces `WEATHER_MODE=fixtures`, drops Gemini/Groq from `narrate.providers()`
(chain becomes Ollama → template only), and disables Bhashini (`is_configured()`
returns `False`, so Tamil narration and voice ASR/TTS fall straight through to
their offline paths) — see config.py and plan.md §5's "one pluggable
abstraction."

**One-time setup** (already done on this machine — 16 CPU / 12 GB RAM / no
GPU, so `llama3.2:3b` (Q4, ~2 GB) is the realistic CPU model; needs Ollama
≥ 0.5 for JSON `format` schemas):

```
curl -fsSL https://ollama.com/install.sh | sh   # needs sudo
ollama pull llama3.2:3b
```

**Night before a demo** — refresh the committed fixtures so they're not
flagged stale:

```
cd services/orchestrator && python snapshot_google_weather.py --city all --force
```

**Demo morning** — run the preflight, then bring the service up in offline mode:

```
cd services/orchestrator
OFFLINE_MODE=1 python offline_check.py       # exit 0 = go; see below on read
OFFLINE_MODE=1 uvicorn main:app --port 8001
```

`offline_check.py` checks every fixture (OK/STALE/MISSING, with the exact
refresh command printed for a STALE row), Ollama reachability + a warm-up
call, and five representative `/ask` queries (EN current/3-day/rain-so-far,
TA rain tomorrow, HI rain tomorrow). It exits 1 only for a real failure — a
missing fixture, an EN/TA query not grounding, or an hi/te/mr query failing
*while Ollama is reachable*; the same failure with Ollama down is a WARN, not
a FAIL, since there's nothing else offline mode can do about it.

`GET /health` in offline mode should show:

```json
{"llm": {"offline_mode": true, "providers": ["ollama"], "ollama": {"reachable": true, ...}},
 "weather_mode": "fixtures", "offline_mode": true}
```

**Expected latency**: one Ollama call per EN/TA query (rules-path NLU, one
narration call), but **two** for hi/te/mr (an NLU parse call, then a
narration call) — on this CPU, several seconds each, more on a cold model
load. The 3B model is noticeably less reliable than Gemini/Groq at following
the NLU JSON schema exactly (e.g. it can omit an optional field like `city`
rather than emitting `null`); this shows up as `grounding.attempts: 2`
(narration regenerated after a guardrail miss) or a hi/te/mr query falling
through to `rules_fallback`/the "which city?" refusal instead of an LLM
answer. That's the tradeoff of the offline path — accept it as a fallback of
last resort, not a like-for-like replacement for Gemini/Groq.

**Docker**: `docker compose --profile offline up` also starts an `ollama`
service (`ollama_models` volume persists pulled models across restarts); set
`OLLAMA_BASE=http://ollama:11434` in `.env` when using it. Without the
`offline` profile, the orchestrator still talks to a host-installed Ollama via
`OLLAMA_BASE` (default `http://localhost:11434`) — `extra_hosts:
host.docker.internal:host-gateway` is wired in case that needs
`http://host.docker.internal:11434` instead on some Docker setups.

## Run it

```
python -m venv .venv && .venv/bin/pip install -r services/orchestrator/requirements.txt -r services/gateway/requirements.txt

# terminal 1 — orchestrator (API + serves the frontend)
cd services/orchestrator && ../../.venv/bin/uvicorn main:app --reload --port 8001

# terminal 2 — gateway (reverse proxy; ORCHESTRATOR_URL defaults to http://localhost:8001)
cd services/gateway && ../../.venv/bin/uvicorn main:app --reload --port 8000
```

Open http://localhost:8000/ (via the gateway) or http://localhost:8001/ (direct).
`python -m http.server 8777` in `prototype/frontend/` still works for
frontend-only dev against either port.

```
curl "http://localhost:8001/health"
curl "http://localhost:8001/ask?text=what's the weather in Chennai&lang=en"
curl "http://localhost:8001/ask?text=will it rain in Madurai tomorrow&lang=ta"
```

## Public-surface limits (security pass)

The ngrok URL is world-reachable and `/ask`, `/asr`, `/tts` have no auth, so
`limits.py` guards them in-process (`main.py` middleware):

- **Body cap** — any request larger than `MAX_BODY_BYTES` (default 2 MiB) is
  rejected with 413 before it reaches Bhashini. `/asr` `audio` and `/tts`
  `text` also carry field-level caps (422).
- **Rate limit** — `RATE_LIMIT_PER_MINUTE` (default 30) requests per client
  per minute on the three expensive routes, keyed by the first
  `X-Forwarded-For` hop (ngrok sets it) → 429 with `Retry-After`. Set it to
  `0` to disable (the test suite does). One uvicorn worker only — this is a
  demo guard, not a gateway.
- **Validation** — `lang` must be one of the five supported codes on `/asr`,
  `/tts`, `/facts` (422); `/ask` falls back to English for anything else.
  `/facts` rejects unknown `intent`/`day` rather than silently answering for
  today (plan.md §2.3).
- **History retention** — `history` rows (query text, answer, city, lang) are
  kept until the user clears them: `DELETE /history` with the session token
  erases the caller's rows (RLS `auth.uid() = user_id`). There is no
  server-side retention job yet; re-run `supabase_schema.sql` to pick up the
  delete policy.

The Playwright end-to-end test lives at `prototype/tests_e2e_frontend.py`,
outside `prototype/frontend/` — that folder is served verbatim by the static
mount, so nothing but the page and its assets belongs there.

## Public URL (stable host pin, plan.md §14 — Niranjan)

Fixed hostname: **`https://plaza-syrup-appetizer.ngrok-free.dev`** → forwards to
the gateway on `:8000` → orchestrator on `:8001`, which also serves the frontend directly
(`prototype/frontend/`, mounted as static files in `main.py`, `/` redirects to
`WeatherGPT.dc.html`) — one tunnel, one URL, for both API and UI. The free
ngrok tier only supports one online tunnel at a time, so the frontend isn't
tunneled separately; it no longer needs its own `python -m http.server 8777`
for the public demo (that's still fine for local-only dev). This replaces the
old Cloudflare *quick* tunnel, which minted a new random hostname on every
restart and blocked Deepthi's OAuth redirect URI from being pre-registerable.
ngrok's free tier includes one static/reserved domain that never changes
across restarts.

```
# terminal 3 — public tunnel (after gateway :8000 and orchestrator :8001 are up)
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
.venv/bin/pytest services/orchestrator/tests/ -v
.venv/bin/pytest services/gateway/tests/ -v
```

`tests/conftest.py` blocks real network in every test (the two `live`-marked
smoke tests run only with `-m live`) and defaults `WEATHER_MODE` to `fixtures`
so the suite is deterministic. A repo-root `conftest.py` puts the flat-import
modules on `sys.path`.

## Monitoring

Prometheus + Grafana (`monitoring/`, plan.md §14 observability track) are an
opt-in compose profile — they don't run with a plain `docker compose up`:

```
docker compose --profile monitoring up -d --build gateway orchestrator prometheus grafana
```

URLs (host machine): Prometheus at `http://localhost:9090`, Grafana at
`http://localhost:3000` (anonymous viewer access — no login needed; admin
password is `admin` if you need to edit something). Grafana comes up with the
Prometheus datasource and the **"WeatherGPT — latency & grounding"**
dashboard already provisioned (`monitoring/grafana/provisioning/`,
`monitoring/grafana/dashboards/weathergpt.json`).

Dashboard panels:

- **p95 latency by service** — `http_request_duration_seconds`, with a red
  threshold line at 2s.
- **requests/sec by service** — `http_requests_total`.
- **error rate (5xx + 429)** — share of requests answered with a server error
  or a rate-limit rejection.
- **/ask answers by provider** — `weathergpt_ask_total`, stacked by which
  narrator (Gemini/Groq/Ollama/template) produced the answer.
- **template-fallback ratio** — `weathergpt_ask_fallback_total` /
  `weathergpt_ask_total`, as a single stat.
- **top routes by p95** — table of the slowest route templates right now.

Both services expose:

- `GET /livez` — `{"status": "ok"}`, no I/O (k8s liveness probe).
- `GET /metrics` — Prometheus text format (`prometheus_client`).

Metric names, all labelled by the *matched route template* (never the raw
path, so a scanner probing random URLs can't blow up cardinality — unmatched
requests get `route="unmatched"`):

- `http_requests_total{service,method,route,status}` (counter)
- `http_request_duration_seconds{service,method,route}` (histogram, buckets
  0.05/0.1/0.25/0.5/1/2/5/10)
- `weathergpt_ask_total{intent,lang,provider,narration}` (counter,
  orchestrator only) — one per `/ask` answer.
- `weathergpt_ask_fallback_total{reason}` (counter, orchestrator only) —
  `reason="guardrail"` when the LLM answer failed grounding,
  `reason="no_llm"` when no LLM narration was attempted at all.
- `gateway_upstream_errors_total` (counter, gateway only) — proxied requests
  that never got a response from the orchestrator.

`docker compose --profile monitoring down` stops just the monitoring
services (and gateway/orchestrator if you started them together); the
`postgres`/`redis` data volumes and the compose network are shared with the
rest of the stack as usual.
