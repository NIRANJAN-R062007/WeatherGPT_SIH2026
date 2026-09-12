"""Intent parsing for /ask: a fast EN/TA rule pass, with an LLM (Gemini -> Groq)
path for everything else — romanised/native hi/te/mr, ambiguous phrasing, and a
safety net when the rules don't confidently fit. See plan.md §8.

`intent.py` (untouched, still has its own 6 tests) does the base city/day/rain
extraction; this module layers time-window, next-N-days, day-after-tomorrow,
rainfall-so-far and out-of-scope detection on top, then decides whether that
rule result is trustworthy enough to use directly.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass

import cities
import config
import google_weather
import httpx
import narrate
from intent import parse_intent

INTENTS = ("current_weather", "forecast", "will_it_rain", "rainfall_so_far_today", "out_of_scope")
TIME_WINDOWS = ("today", "tonight", "tomorrow", "day_after_tomorrow", "next_n_days")
PARAMETERS = ("general", "temperature", "rain", "humidity", "wind", "uv")
LANGUAGES = ("en", "hi", "ta", "te", "mr")

_P0_INTENTS = {"current_weather", "forecast", "will_it_rain", "rainfall_so_far_today"}
_LOG = logging.getLogger("weathergpt.nlu")

_OUT_OF_SCOPE_RE = re.compile(
    r"\b(cyclone|storm warning|warning|alert|flood|tsunami|earthquake)\b|புயல்|சூறாவளி|வெள்ள",
    re.IGNORECASE,
)
_RAIN_SO_FAR_RE = re.compile(
    r"(how much|amount of)\s+rain|rain(?:fall)?\s+(?:so far|till now|until now|today so far)"
    r"|has it rained|இதுவரை.*மழை|எவ்வளவு மழை",
    re.IGNORECASE,
)
_NEXT_N_RE = re.compile(
    r"\b(?:next|coming)\s+(\d+)\s*days?\b|\b(\d+)[- ]day\b|\bthis week\b|அடுத்த\s*(\d+)\s*நாட்கள்",
    re.IGNORECASE,
)
_DAY_AFTER_RE = re.compile(r"day after tomorrow|நாளை மறுநாள்", re.IGNORECASE)
_RAIN_WORD_RE = re.compile(r"\brain\b|மழை", re.IGNORECASE)
_KEYWORD_HIT_RE = re.compile(
    r"weather|forecast|temperature|rain|humid|wind|hot|cold|climate|uv"
    r"|வானிலை|மழை|வெப்பநிலை|காற்று|ஈரப்பதம்",
    re.IGNORECASE,
)
_PARAM_PATTERNS = (
    ("temperature", re.compile(r"temperature|temp\b|hot|cold|warm|வெப்பநிலை|சூடு", re.IGNORECASE)),
    ("humidity", re.compile(r"humid|ஈரப்பதம்", re.IGNORECASE)),
    ("wind", re.compile(r"wind|காற்று", re.IGNORECASE)),
    ("rain", re.compile(r"rain|மழை", re.IGNORECASE)),
    ("uv", re.compile(r"\buv\b", re.IGNORECASE)),
)

_NLU_PROMPT = (
    "You are the intent parser for WeatherGPT, a weather assistant for India. Read the "
    "user's message and output ONLY a JSON object with keys intent, city, time_window, "
    "days, parameter, language, confidence.\n"
    "- intent: current_weather = conditions right now / today. forecast = conditions on "
    "a future day or over several days. will_it_rain = chance of rain. "
    "rainfall_so_far_today = how much rain has already fallen today / till now. "
    "out_of_scope = greetings, chit-chat, non-weather, or weather products we do not have "
    "(cyclones, warnings/alerts, floods, tsunami, marine, air quality, past days).\n"
    '- city: exactly "chennai", "madurai" or "coimbatore" when the message names one of '
    "them in ANY language, script or spelling ({city_list}). Any other place: copy the "
    "place name as written. No place named: null. Never invent a city.\n"
    "- time_window: today | tonight | tomorrow | day_after_tomorrow | next_n_days "
    '(default today). For "next 3 days", "3-day forecast", "this week" use next_n_days '
    "and set days to the integer (week = 7); otherwise days = null.\n"
    "- parameter: the single quantity asked about — temperature, rain, humidity, wind, "
    "uv — or general if none or several.\n"
    "- language: the language the message is written in: en, hi, ta, te, mr, or other. "
    'Romanised Indian languages count as that language ("kal baarish hogi?" -> hi).\n'
    "- confidence: 0 to 1.\n"
    "Do not answer the question.\n"
    "Examples:\n"
    '"will it rain in Madurai tomorrow?" -> {{"intent":"will_it_rain","city":"madurai",'
    '"time_window":"tomorrow","days":null,"parameter":"rain","language":"en","confidence":0.95}}\n'
    '"कल चेन्नई में बारिश होगी क्या?" -> {{"intent":"will_it_rain","city":"chennai",'
    '"time_window":"tomorrow","days":null,"parameter":"rain","language":"hi","confidence":0.9}}\n'
    '"చెన్నైలో ఇప్పుడు వాతావరణం ఎలా ఉంది?" -> {{"intent":"current_weather","city":"chennai",'
    '"time_window":"today","days":null,"parameter":"general","language":"te","confidence":0.9}}\n'
    '"पुढील 3 दिवस कोईम्बतूरचे हवामान?" -> {{"intent":"forecast","city":"coimbatore",'
    '"time_window":"next_n_days","days":3,"parameter":"general","language":"mr","confidence":0.9}}\n'
    '"is a cyclone hitting Chennai tomorrow?" -> {{"intent":"out_of_scope","city":"chennai",'
    '"time_window":"tomorrow","days":null,"parameter":"general","language":"en","confidence":0.9}}\n'
    '"weather in Mumbai" -> {{"intent":"current_weather","city":"Mumbai","time_window":"today",'
    '"days":null,"parameter":"general","language":"en","confidence":0.9}}\n'
    "Message: {text}"
)

_GEMINI_SCHEMA = {
    "type": "OBJECT",
    "propertyOrdering": ["intent", "city", "time_window", "days", "parameter",
                         "language", "confidence"],
    "required": ["intent", "time_window", "parameter", "language", "confidence"],
    "properties": {
        "intent": {"type": "STRING", "enum": list(INTENTS)},
        "city": {"type": "STRING", "nullable": True},
        "time_window": {"type": "STRING", "enum": list(TIME_WINDOWS)},
        "days": {"type": "INTEGER", "nullable": True},
        "parameter": {"type": "STRING", "enum": list(PARAMETERS)},
        "language": {"type": "STRING", "enum": [*LANGUAGES, "other"]},
        "confidence": {"type": "NUMBER"},
    },
}


@dataclass
class ParsedQuery:
    intent: str
    city: str | None
    time_window: str
    days: int | None
    parameter: str
    language: str | None
    source: str  # "rules" | "llm" | "rules_fallback"
    confidence: float

    def as_dict(self) -> dict:
        return asdict(self)


def detect_script(text: str) -> str:
    """Indic block with the most letters wins; Latin-only text is "en"; text
    with neither (e.g. Malayalam, which we don't specially support) is "other".
    """
    counts = {"ta": 0, "te": 0, "deva": 0}
    for ch in text:
        cp = ord(ch)
        if 0x0B80 <= cp <= 0x0BFF:
            counts["ta"] += 1
        elif 0x0C00 <= cp <= 0x0C7F:
            counts["te"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["deva"] += 1
    if any(counts.values()):
        return max(counts, key=counts.get)
    if any(ch.isascii() and ch.isalpha() for ch in text):
        return "en"
    return "other"


def _detect_parameter(text: str) -> str:
    for name, pattern in _PARAM_PATTERNS:
        if pattern.search(text):
            return name
    return "general"


def _extract_days(match: re.Match, text: str) -> int | None:
    for group in match.groups():
        if group:
            try:
                return int(group)
            except ValueError:
                continue
    if re.search(r"\bthis week\b", text, re.IGNORECASE):
        return 7
    return None


def parse_rules(text: str, script: str) -> ParsedQuery:
    base = parse_intent(text)
    city, base_intent, time_window = base["city"], base["intent"], base["day"]
    days = None

    next_n_match = _NEXT_N_RE.search(text)
    is_day_after = bool(_DAY_AFTER_RE.search(text))
    is_rain_so_far = bool(_RAIN_SO_FAR_RE.search(text))
    is_out_of_scope = bool(_OUT_OF_SCOPE_RE.search(text))
    has_rain_word = bool(_RAIN_WORD_RE.search(text))

    if next_n_match:
        time_window, days = "next_n_days", _extract_days(next_n_match, text)
    elif is_day_after:
        time_window = "day_after_tomorrow"

    parameter = _detect_parameter(text)

    if is_out_of_scope:
        final_intent = "out_of_scope"
    elif is_rain_so_far:
        final_intent, time_window, parameter = "rainfall_so_far_today", "today", "rain"
    elif next_n_match or is_day_after:
        final_intent = "will_it_rain" if has_rain_word else "forecast"
    else:
        # current_weather | will_it_rain | unsupported_city | unrecognized, from intent.py
        final_intent = base_intent

    return ParsedQuery(
        intent=final_intent, city=city, time_window=time_window, days=days,
        parameter=parameter, language=None, source="rules", confidence=0.9,
    )


def _rule_accepted(pq: ParsedQuery, keyword_hit: bool) -> bool:
    if pq.intent == "out_of_scope" and pq.language in ("en", "ta"):
        return True
    return (
        pq.intent in _P0_INTENTS
        and keyword_hit
        and pq.city is not None
        and cities.resolve(pq.city) is not None
        and pq.language in ("en", "ta")
    )


def _validate_llm_json(raw: str) -> ParsedQuery | None:
    obj = json.loads(raw)  # ValueError/JSONDecodeError bubbles to the caller

    intent = obj.get("intent")
    time_window = obj.get("time_window")
    parameter = obj.get("parameter")
    language = obj.get("language")
    if intent not in INTENTS or time_window not in TIME_WINDOWS or parameter not in PARAMETERS:
        return None
    if language not in (*LANGUAGES, "other"):
        return None

    city_raw = obj.get("city")
    city = None
    if city_raw:
        resolved = cities.resolve(city_raw)
        city = resolved if resolved else city_raw
        if resolved is None:
            intent = "unsupported_city"

    days = obj.get("days")
    if isinstance(days, bool) or not isinstance(days, int) or not (1 <= days <= 7):
        days = google_weather.FORECAST_DAYS if time_window == "next_n_days" else None

    confidence = obj.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5

    return ParsedQuery(
        intent=intent, city=city, time_window=time_window, days=days,
        parameter=parameter, language=None if language == "other" else language,
        source="llm", confidence=confidence,
    )


def _city_list() -> str:
    parts = []
    for key, city in cities.CITIES.items():
        names = {n for n in (city.names.get("en"), city.names.get("ta"), *city.aliases) if n}
        parts.append(f"{key} ({', '.join(sorted(names))})")
    return "; ".join(parts)


def _llm_parse(text: str) -> ParsedQuery | None:
    prompt = _NLU_PROMPT.format(city_list=_city_list(), text=text)
    raw = None

    if config.GEMINI_API_KEY:
        try:
            raw = narrate.generate(prompt, model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY,
                                    response_schema=_GEMINI_SCHEMA)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            _LOG.warning("gemini nlu parse failed (%s); trying groq fallback", exc)

    if not raw and config.GROQ_API_KEY:
        try:
            raw = narrate.generate_groq(prompt, model=config.GROQ_MODEL, key=config.GROQ_API_KEY,
                                        response_schema=_GEMINI_SCHEMA)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            _LOG.warning("groq nlu parse failed (%s)", exc)

    if not raw:
        return None
    return _validate_llm_json(raw)


def _language_from_script(script: str, lang_hint: str | None) -> str | None:
    if script in ("ta", "te", "en"):
        return script
    if script == "deva":
        return lang_hint if lang_hint in ("hi", "mr") else "hi"
    return None


def parse(text: str, lang_hint: str | None = None) -> ParsedQuery:
    script = detect_script(text)
    language = _language_from_script(script, lang_hint)

    pq = parse_rules(text, script)
    pq.language = language

    keyword_hit = bool(_KEYWORD_HIT_RE.search(text))
    if _rule_accepted(pq, keyword_hit):
        pq.source, pq.confidence = "rules", 0.9
        return pq

    if narrate.is_configured():
        try:
            llm_pq = _llm_parse(text)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            _LOG.warning("llm nlu parse failed (%s); using rules fallback", exc)
            llm_pq = None
        if llm_pq is not None:
            if script in ("ta", "te"):  # script is unambiguous; models confuse the two
                llm_pq.language = script
            return llm_pq

    pq.source, pq.confidence = "rules_fallback", (0.5 if script == "deva" else 0.3)
    return pq
