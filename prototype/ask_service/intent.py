import re

RAIN_PATTERN = re.compile(r"\brain\b", re.IGNORECASE)
CITY_PATTERN = re.compile(
    r"\bin\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:today|tomorrow|tonight)\b|[?.!]|$)",
    re.IGNORECASE,
)
DAY_PATTERN = re.compile(r"\b(today|tomorrow|tonight)\b", re.IGNORECASE)

DEMO_CITIES = {"chennai"}


def parse_intent(text: str) -> dict:
    """Rule-based parse for the two §14 demo intents. No LLM NLU — time-boxed."""
    city_match = CITY_PATTERN.search(text)
    city = city_match.group(1).strip() if city_match else None

    day_match = DAY_PATTERN.search(text)
    day = day_match.group(1).lower() if day_match else "today"

    if city and city.lower() not in DEMO_CITIES:
        return {"intent": "unsupported_city", "city": city, "day": day}

    if RAIN_PATTERN.search(text):
        return {"intent": "will_it_rain", "city": city, "day": day}

    if city:
        return {"intent": "current_weather", "city": city, "day": day}

    return {"intent": "unrecognized", "city": None, "day": day}
