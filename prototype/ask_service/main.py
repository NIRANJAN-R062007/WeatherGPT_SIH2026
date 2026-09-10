"""`/ask` FastAPI endpoint: intent parse -> weather lookup -> grounded answer.

plan.md §4: LLM -> narrate ONLY from the typed object -> validator (every
numeric token must exist in the tool response) -> response + provenance, with
a template fallback on validator failure. No LLM key exists yet, so the
narration seam below is `render()` itself; real narration drops in without
touching the guardrail wiring.
"""

from dataclasses import asdict
from datetime import datetime, timezone

import guardrail
from fastapi import FastAPI
from i18n import render
from intent import parse_intent
from weather_data import get_weather

app = FastAPI(title="WeatherGPT /ask prototype", version="0.0.1")


@app.get("/ask")
def ask(text: str, lang: str = "en"):
    parsed = parse_intent(text)
    intent, city, day = parsed["intent"], parsed["city"], parsed["day"]

    if intent in ("unrecognized", "unsupported_city"):
        return {
            "intent": intent,
            "message": "Sorry, I can only answer for supported demo cities right now."
            if intent == "unsupported_city"
            else "Sorry, I couldn't understand that request.",
        }

    data = get_weather(city)
    if data is None:
        return {"intent": intent, "city": city, "message": "No data available."}

    # Narration seam: later replaced by llm_narrate(intent, city, data, lang).
    candidate = render(intent, city, data, lang)
    report = guardrail.check(candidate, data)
    fallback_used = False

    if not report.ok:  # §4: fail -> regenerate or fall back to template
        candidate = render(intent, city, data, lang)
        report = guardrail.check(candidate, data)
        fallback_used = True

    grounding = {**asdict(report), "fallback_used": fallback_used}

    if not report.ok:  # §2.3: refuse rather than guess
        return {
            "intent": intent,
            "city": city,
            "message": "Sorry, I couldn't produce a grounded answer for that.",
            "grounding": grounding,
        }

    return {
        "intent": intent,
        "city": city,
        "day": day,
        "response": candidate,
        "provenance": {
            "source": data["source"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "grounding": grounding,
    }
