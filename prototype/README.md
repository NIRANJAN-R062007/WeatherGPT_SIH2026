# Internal hackathon prototype (plan.md §14)

Cut-down build. Not the full product — see plan.md §14 for the full scope,
task list, and explicit out-of-scope list.

## What's here

- `ask_service/config.py` — repo paths, API keys (from a gitignored repo-root
  `.env`), CORS origins. Never raises at import; `require()` fails loudly at
  point of use.
- `ask_service/intent.py` — rule-based parser for the two demo intents
  (`current_weather`, `will_it_rain`). Full NLU / Tamil phrasings are a
  follow-up.
- `ask_service/cities.py` + `data/cities.json` — the demo city registry
  (Chennai, Madurai, Coimbatore): key, lat/lon, EN/TA names, aliases.
  `data/cities.json` is the source of truth; the frontend keeps a copy until
  it fetches `GET /cities`.
- `ask_service/weather_data.py` — **stub** for the Google Weather API ingestion
  module. Numbers transcribed from the committed snapshots. Swap `get_weather()`
  for the live module + decoder tables + cache once it lands.
- `ask_service/i18n.py` — EN/TA phrase templates. `CONDITION_*` keys are the
  canonical decoder targets (lowercased Google `weatherCondition.type`).
- `ask_service/guardrail.py` — grounding guardrail + numeric validator
  (plan.md §4, "non-negotiable"). Extracts every numeric token from the
  narrated answer and requires each to match a raw field of a compatible unit
  (unit-aware: `"20°C"` cannot pass by matching a `rain_probability_pct` of
  20). On failure `/ask` re-renders from the template, then refuses rather
  than guess (§2.3).
- `ask_service/main.py` — `/ask` (intent → city resolve → weather lookup →
  narration seam → guardrail → typed response + provenance), plus `/health`
  and `/cities`.
- `ask_service/snapshot_google_weather.py` — fetches and commits real API
  fixtures; doubles as the Google Weather key verifier.
- `ask_service/verify_gemini.py` — Gemini key verifier + model probe.

### The `grounding` block

Every successful (and refused) `/ask` response carries a `grounding` object
matching what `WeatherGPT.dc.html` renders as the "Validator: n/n matched" chip
and "View source" panel:

```json
"grounding": {
  "ok": true, "matched": 1, "total": 1,
  "figures": [{"reading": "28°C", "value": 28.0, "unit": "celsius",
               "path": "temp_c", "matched": true}],
  "fallback_used": false
}
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

### `/ask` response contract

| case | HTTP | body keys |
|---|---|---|
| success | 200 | `intent, city, day, response, provenance{source,retrieved_at}, grounding{ok,matched,total,figures[],fallback_used}` |
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
- **Gemini**: see `data/fixtures/gemini/models.json` and the verifier output.
  Chosen model recorded in `GEMINI_MODEL` (`.env` / `.env.example`).

## Explicitly stubbed — do not treat as done

- **Weather data** (`weather_data.py`): snapshot numbers, not live. The real
  ingestion module (per-endpoint fetch + decoder tables + Redis cache) is the
  next data-layer task.
- **LLM narration**: `main.py`'s narration seam calls `render()`. Real
  narration-from-typed-response drops in there; the guardrail already validates
  whatever it produces.
- **Web UI wiring**: `WeatherGPT.dc.html` still mocks its data with a
  `setTimeout`. Day 2: replace `ask()`'s timeout with a `fetch(apiBase +
  "/ask")`, map the response per the contract above.

## Run it

```
python -m venv .venv && .venv/bin/pip install -r prototype/ask_service/requirements.txt

# terminal 1 — API
cd prototype/ask_service && ../../.venv/bin/uvicorn main:app --reload --port 8001

# terminal 2 — frontend (still mocked)
cd prototype/frontend && python -m http.server 8777
```

```
curl "http://localhost:8001/health"
curl "http://localhost:8001/ask?text=what's the weather in Chennai&lang=en"
curl "http://localhost:8001/ask?text=will it rain in Madurai tomorrow&lang=ta"
```

## Tests

```
.venv/bin/pytest prototype/ask_service/tests/ -v
```

A `conftest.py` shim puts the flat-import modules on `sys.path` so this works
from the repo root.
