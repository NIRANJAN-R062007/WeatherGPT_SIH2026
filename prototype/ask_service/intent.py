import re

from cities import resolve as resolve_city

RAIN_PATTERN = re.compile(r"\brain\b", re.IGNORECASE)
CITY_PATTERN = re.compile(
    r"\bin\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:today|tomorrow|tonight)\b|[?.!]|$)",
    re.IGNORECASE,
)
DAY_PATTERN = re.compile(r"\b(today|tomorrow|tonight)\b", re.IGNORECASE)


def parse_intent(text: str) -> dict:
    """Rule-based parse for the two demo intents. No LLM NLU — time-boxed.

    Full NLU (Tamil queries, richer phrasings) is a follow-up task; for now the
    city is taken from an English "in <city>" phrase, falling back to scanning
    the whole text against the registry (catches "Madurai today", Tamil names).
    """
    city_match = CITY_PATTERN.search(text)
    raw_city = city_match.group(1).strip() if city_match else None
    if raw_city is None:
        key = resolve_city(text)
        raw_city = key if key else None

    day_match = DAY_PATTERN.search(text)
    day = day_match.group(1).lower() if day_match else "today"

    if raw_city and resolve_city(raw_city) is None:
        return {"intent": "unsupported_city", "city": raw_city, "day": day}

    if RAIN_PATTERN.search(text):
        return {"intent": "will_it_rain", "city": raw_city, "day": day}

    if raw_city:
        return {"intent": "current_weather", "city": raw_city, "day": day}

    return {"intent": "unrecognized", "city": None, "day": day}
