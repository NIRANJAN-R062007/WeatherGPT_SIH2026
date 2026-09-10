# Internal hackathon prototype (plan.md §14)

Cut-down, single-night build. Not the full product — see plan.md §14 for the
full scope, task list, and explicit out-of-scope list.

## What's here

This folder currently covers **Niranjan's owned tasks** from §14 only:

- `ask_service/intent.py` — rule-based intent parser for the two demo
  intents (`current_weather`, `will_it_rain`).
- `ask_service/i18n.py` — English/Tamil response rendering. Hand-written
  phrase templates (per §14, faster and safer for a stage demo than live
  translation of untested quality).
- `ask_service/main.py` — `/ask` FastAPI endpoint wiring intent parse →
  weather lookup → typed response → provenance footer.

## Explicitly stubbed, owned by teammates (do not treat as done)

- **Weather data** (`ask_service/weather_data.py`): hardcoded stand-in for
  the real Google Weather API ingestion module — that's Syed + Deepthi's
  task in §14. Swap `get_weather(city)` for their module once it lands.
- **Grounding guardrail / numeric validator**: `main.py` calls a stub
  `validate(...)` that always passes. The real guardrail is Mahesh's task
  in §14 and is "non-negotiable" per the plan — do not demo without it.
- **LLM narration**: not implemented here. §14 assigns narration-from-typed-
  response to Mahesh.
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
