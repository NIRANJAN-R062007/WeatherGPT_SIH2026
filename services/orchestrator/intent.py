import re

from cities import resolve as resolve_city

RAIN_PATTERN = re.compile(r"\brain\b", re.IGNORECASE)
RAIN_WORDS_TA = ("மழை",)  # "rain" — covers மழை பெய்யுமா, மழை வருமா, etc.
CITY_PATTERN = re.compile(
    r"\bin\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:today|tomorrow|tonight)\b|[?.!]|$)",
    re.IGNORECASE,
)
DAY_PATTERN = re.compile(r"\b(today|tomorrow|tonight)\b", re.IGNORECASE)

# Longest/most specific first: "இன்றிரவு"/"இன்று இரவு" (tonight) must be checked
# before "இன்று" (today), which is a substring of both.
DAY_WORDS_TA = (
    ("இன்றிரவு", "tonight"),
    ("இன்று இரவு", "tonight"),
    ("நாளை", "tomorrow"),
    ("இன்று", "today"),
)


def _day_from_ta(text: str) -> str | None:
    for word, day in DAY_WORDS_TA:
        if word in text:
            return day
    return None


def parse_intent(text: str) -> dict:
    """Rule-based parse for the two demo intents. No LLM NLU — time-boxed.

    City is taken from an English "in <city>" phrase, falling back to scanning
    the whole text against the registry (catches "Madurai today", Tamil names).
    Rain/day keywords are matched in both English and Tamil so a query like
    "நாளை சென்னையில் மழை பெய்யுமா?" resolves to will_it_rain/tomorrow instead
    of unrecognized.
    """
    city_match = CITY_PATTERN.search(text)
    raw_city = city_match.group(1).strip() if city_match else None
    if raw_city is None:
        key = resolve_city(text)
        raw_city = key if key else None

    day_match = DAY_PATTERN.search(text)
    day = day_match.group(1).lower() if day_match else (_day_from_ta(text) or "today")

    is_rain = bool(RAIN_PATTERN.search(text)) or any(w in text for w in RAIN_WORDS_TA)

    if raw_city and resolve_city(raw_city) is None:
        return {"intent": "unsupported_city", "city": raw_city, "day": day}

    if is_rain:
        return {"intent": "will_it_rain", "city": raw_city, "day": day}

    if raw_city:
        return {"intent": "current_weather", "city": raw_city, "day": day}

    return {"intent": "unrecognized", "city": None, "day": day}
