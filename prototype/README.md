# Internal hackathon prototype (plan.md §14)

Cut-down, single-night build. Not the full product — see plan.md §14 for the
full scope, task list, and explicit out-of-scope list.

## What's here

This folder currently covers **Niranjan's owned tasks** from §14, plus
Mahesh's grounding guardrail:

- `ask_service/intent.py` — rule-based intent parser for the two demo
  intents (`current_weather`, `will_it_rain`).
- `ask_service/i18n.py` — English/Tamil response rendering. Hand-written
  phrase templates (per §14, faster and safer for a stage demo than live
  translation of untested quality).
- `ask_service/main.py` — `/ask` FastAPI endpoint wiring intent parse →
  weather lookup → narration → grounding guardrail → typed response →
  provenance footer.
- `ask_service/guardrail.py` — the grounding guardrail + numeric validator
  (plan.md §14, "non-negotiable, even in minimal form"; see §4). Extracts
  every numeric token from the narrated answer and requires each to match a
  raw field of a compatible unit (unit-aware: `"20°C"` cannot pass by
  matching a `rain_probability_pct` of 20). If the check fails, `/ask`
  re-renders from the template and, if that also fails, refuses instead of
  guessing (§2.3). Tests in `ask_service/tests/test_guardrail.py`.

### The `grounding` block

Every successful (and refused) `/ask` response carries a `grounding` object
matching what `prototype/frontend/WeatherGPT.dc.html` renders as the
"Validator: n/n matched" chip and "View source" panel:

```json
"grounding": {
  "ok": true, "matched": 1, "total": 1,
  "figures": [{"reading": "31°C", "value": 31.0, "unit": "celsius",
               "path": "temp_c", "matched": true}],
  "fallback_used": false
}
```

## Explicitly stubbed, owned by teammates (do not treat as done)

- **Weather data** (`ask_service/weather_data.py`): hardcoded stand-in for
  the real Google Weather API ingestion module — that's Syed + Deepthi's
  task in §14. Swap `get_weather(city)` for their module once it lands.
- **LLM narration**: not implemented here. `main.py`'s narration seam
  currently just calls `render()`; §14 assigns narration-from-typed-response
  to Mahesh as a follow-up (needs an API key nobody has yet). The guardrail
  is already wired to validate whatever that seam produces.
- **Web UI**: not implemented here. §14 assigns the single-page UI to
  Mahesh + Chelsea.

## Run it

```
cd prototype/ask_service
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

```
curl "http://localhost:8001/ask?text=what's the weather in Chennai&lang=en"
curl "http://localhost:8001/ask?text=will it rain in Chennai tomorrow&lang=ta"
```

## Run the tests

```
cd prototype/ask_service
pytest tests/ -v
```

(or `pytest prototype/ask_service/tests/ -v` from the repo root — a
`conftest.py` shim puts the flat-import modules on `sys.path`.)
