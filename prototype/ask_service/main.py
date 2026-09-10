from datetime import datetime, timezone

from fastapi import FastAPI

from i18n import render
from intent import parse_intent
from weather_data import get_weather

app = FastAPI(title="WeatherGPT /ask prototype", version="0.0.1")


def validate(data: dict) -> bool:
    """STUB grounding guardrail — always passes.

    Owned by Mahesh in plan.md §14 ("non-negotiable, even in minimal form").
    Do not demo without the real guardrail + numeric validator wired in here.
    """
    return True


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
    if data is None or not validate(data):
        return {"intent": intent, "city": city, "message": "No data available."}

    return {
        "intent": intent,
        "city": city,
        "day": day,
        "response": render(intent, city, data, lang),
        "provenance": {
            "source": data["source"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
