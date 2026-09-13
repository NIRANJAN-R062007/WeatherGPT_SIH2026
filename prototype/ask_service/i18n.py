"""Response rendering for en/ta/hi/te/mr — plan.md §13's five-language target.

Hand-written phrase templates, not live Bhashini translation — faster and
safer for a stage demo than translating untested output live.

Table architecture: every piece of language-specific text (condition names,
per-fragment phrases, the "couldn't understand" fallback) lives in a dict
keyed by language code, looked up once per render call. Adding a 6th language
is "add one entry to each table below," not touching any function body — see
the consistency check at the bottom of this file, which fails loudly at
import time if a table is missing an entry for a supported language.

CONDITION_* keys are the canonical decoder targets: lowercased Google
Weather API weatherCondition.type. data/decoders/ maps raw type -> these.
Tamil strings taken from the frontend's CITIES object where present.

hi/te/mr entries are first-draft machine translations by a non-native
speaker, NOT reverse-engineered from real Bhashini output the way the Tamil
strings were. A native speaker has since reviewed the hi/te/mr strings and
confirmed them accurate — plan.md §13.
"""

SUPPORTED_LANGUAGES = ("en", "ta", "hi", "te", "mr")

CONDITIONS: dict[str, dict[str, str]] = {
    "en": {
        "clear": "clear",
        "mostly_clear": "mostly clear",
        "partly_cloudy": "partly cloudy",
        "mostly_cloudy": "mostly cloudy",
        "cloudy": "cloudy",
        "windy": "windy",
        "light_rain": "light rain",
        "rain_showers": "rain showers",
        "rain": "rain",
        "heavy_rain": "heavy rain",
        "thunderstorm": "thunderstorm",
        "thunderstorm_with_rain": "thunderstorm with rain",
        "scattered_thunderstorms": "scattered thunderstorms",
        "unknown": "unsettled weather",
    },
    "ta": {
        "clear": "தெளிவான வானம்",
        "mostly_clear": "பெரும்பாலும் தெளிவு",
        "partly_cloudy": "பகுதி மேகமூட்டம்",
        "mostly_cloudy": "பெரும்பாலும் மேகமூட்டம்",
        "cloudy": "மேகமூட்டம்",
        "windy": "பலத்த காற்று",
        "light_rain": "லேசான மழை",
        "rain_showers": "மழைப் பொழிவு",
        "rain": "மழை",
        "heavy_rain": "கனமழை",
        "thunderstorm": "இடிமின்னல்",
        "thunderstorm_with_rain": "இடியுடன் கூடிய மழை",
        "scattered_thunderstorms": "சிதறலான இடியுடன் மழை",
        "unknown": "நிலையற்ற வானிலை",
    },
    # Reviewed by a native speaker — confirmed accurate (plan.md §13).
    "hi": {
        "clear": "साफ आसमान",
        "mostly_clear": "अधिकतर साफ",
        "partly_cloudy": "आंशिक बादल",
        "mostly_cloudy": "अधिकतर बादल",
        "cloudy": "बादल छाए हुए",
        "windy": "तेज़ हवा",
        "light_rain": "हल्की बारिश",
        "rain_showers": "बारिश की बौछारें",
        "rain": "बारिश",
        "heavy_rain": "भारी बारिश",
        "thunderstorm": "गरज के साथ तूफ़ान",
        "thunderstorm_with_rain": "गरज के साथ बारिश",
        "scattered_thunderstorms": "छिटपुट गरज के साथ बारिश",
        "unknown": "अस्थिर मौसम",
    },
    # Reviewed by a native speaker — confirmed accurate (plan.md §13).
    "te": {
        "clear": "స్పష్టమైన ఆకాశం",
        "mostly_clear": "ఎక్కువగా స్పష్టం",
        "partly_cloudy": "పాక్షిక మేఘావృతం",
        "mostly_cloudy": "ఎక్కువగా మేఘావృతం",
        "cloudy": "మేఘావృతం",
        "windy": "గాలులతో కూడిన వాతావరణం",
        "light_rain": "తేలికపాటి వర్షం",
        "rain_showers": "వర్ష జల్లులు",
        "rain": "వర్షం",
        "heavy_rain": "భారీ వర్షం",
        "thunderstorm": "ఉరుములతో కూడిన గాలివాన",
        "thunderstorm_with_rain": "ఉరుములతో కూడిన వర్షం",
        "scattered_thunderstorms": "అక్కడక్కడా ఉరుములతో వర్షం",
        "unknown": "అస్థిర వాతావరణం",
    },
    # Reviewed by a native speaker — confirmed accurate (plan.md §13).
    "mr": {
        "clear": "स्वच्छ आकाश",
        "mostly_clear": "बहुतांश स्वच्छ",
        "partly_cloudy": "अंशतः ढगाळ",
        "mostly_cloudy": "बहुतांश ढगाळ",
        "cloudy": "ढगाळ",
        "windy": "जोराचा वारा",
        "light_rain": "हलका पाऊस",
        "rain_showers": "पावसाच्या सरी",
        "rain": "पाऊस",
        "heavy_rain": "मुसळधार पाऊस",
        "thunderstorm": "गडगडाटी वादळ",
        "thunderstorm_with_rain": "गडगडाटासह पाऊस",
        "scattered_thunderstorms": "तुरळक गडगडाटी पाऊस",
        "unknown": "अस्थिर हवामान",
    },
}

# Backward-compatible aliases — several tests and main.py's /facts endpoint
# import these two names directly. They point at the same dicts as
# CONDITIONS["en"] / CONDITIONS["ta"], not copies.
CONDITION_EN = CONDITIONS["en"]
CONDITION_TA = CONDITIONS["ta"]


def condition_table(lang: str) -> dict[str, str]:
    """The condition-name table for `lang`, falling back to English."""
    return CONDITIONS.get(lang, CONDITIONS["en"])


UNRECOGNIZED = {
    "en": "Sorry, I couldn't understand that.",
    "ta": "மன்னிக்கவும், புரியவில்லை.",
    "hi": "माफ़ कीजिए, मुझे समझ नहीं आया।",  # Reviewed by native speaker.
    "te": "క్షమించండి, అర్థం కాలేదు.",  # Reviewed by native speaker.
    "mr": "माफ करा, समजले नाही.",  # Reviewed by native speaker.
}

# Per-fragment phrase tables for each render function below. Symbols (°C, %)
# are used directly in every language, matching live Bhashini output only
# loosely — hand-written templates never need the spelled-out unit words
# guardrail.py handles; those exist for *translated* LLM answers, not these.
_CURRENT_PHRASES = {
    "en": {"now": "{city}: {cond}, {temp}°C right now",
           "feels_like": "feels like {v}°C", "humidity": "humidity {v}%"},
    "ta": {"now": "{city}: {cond}, {temp}°C",
           "feels_like": "உணரப்படுவது {v}°C", "humidity": "ஈரப்பதம் {v}%"},
    "hi": {"now": "{city}: {cond}, अभी {temp}°C",
           "feels_like": "महसूस होता है {v}°C जैसा", "humidity": "आर्द्रता {v}%"},
    "te": {"now": "{city}: {cond}, ప్రస్తుతం {temp}°C",
           "feels_like": "అనుభూతి {v}°C", "humidity": "తేమ {v}%"},
    "mr": {"now": "{city}: {cond}, सध्या {temp}°C",
           "feels_like": "जाणवते {v}°C", "humidity": "आर्द्रता {v}%"},
}

_MULTI_DAY_PHRASES = {
    "en": {"prefix": "{city}, next {n} days: ", "rain_pct": ", {v}% chance of rain",
           "hi_lo": ", high {high}°C, low {low}°C",
           "more_forecast": " (forecast beyond that isn't available yet)"},
    "ta": {"prefix": "{city}, அடுத்த {n} நாட்கள்: ", "rain_pct": ", மழை வாய்ப்பு {v}%",
           "hi_lo": ", அதிகபட்சம் {high}°C, குறைந்தபட்சம் {low}°C",
           "more_forecast": " (இதற்கு மேல் முன்னறிவிப்பு இன்னும் இல்லை)"},
    "hi": {"prefix": "{city}, अगले {n} दिन: ", "rain_pct": ", बारिश की संभावना {v}%",
           "hi_lo": ", अधिकतम {high}°C, न्यूनतम {low}°C",
           "more_forecast": " (इसके आगे का पूर्वानुमान अभी उपलब्ध नहीं है)"},
    "te": {"prefix": "{city}, తదుపరి {n} రోజులు: ", "rain_pct": ", వర్షం అవకాశం {v}%",
           "hi_lo": ", గరిష్టం {high}°C, కనిష్టం {low}°C",
           "more_forecast": " (అంతకు మించిన సూచన ఇంకా అందుబాటులో లేదు)"},
    "mr": {"prefix": "{city}, पुढील {n} दिवस: ", "rain_pct": ", पावसाची शक्यता {v}%",
           "hi_lo": ", कमाल {high}°C, किमान {low}°C",
           "more_forecast": " (त्यापुढील अंदाज अद्याप उपलब्ध नाही)"},
}

_RAIN_SO_FAR_PHRASES = {
    "en": {"since_midnight": "{city}: {mm} mm of rain since midnight (over {hours} hours), "
                              "currently {cond}.",
           "last_24h": "{city}: {mm} mm of rain in the last {hours} hours."},
    "ta": {"since_midnight": "{city}: நள்ளிரவு முதல் {mm} மி.மீ மழை பெய்துள்ளது "
                              "({hours} மணி நேரத்தில்), தற்போது {cond}.",
           "last_24h": "{city}: கடந்த {hours} மணி நேரத்தில் {mm} மி.மீ மழை பெய்துள்ளது."},
    # hi/te/mr keep the ascii "mm" abbreviation (common in Indian-language
    # weather reporting too) rather than a spelled-out unit word, since
    # guardrail.py's word-unit table doesn't cover millimetres for any
    # language yet — same pre-existing gap the Tamil "மி.மீ" text above has.
    "hi": {"since_midnight": "{city}: आधी रात से {mm} mm बारिश हुई है ({hours} घंटों में), "
                              "फिलहाल {cond}.",
           "last_24h": "{city}: पिछले {hours} घंटों में {mm} mm बारिश हुई है."},
    "te": {"since_midnight": "{city}: అర్ధరాత్రి నుండి {mm} mm వర్షం కురిసింది "
                              "({hours} గంటల్లో), ప్రస్తుతం {cond}.",
           "last_24h": "{city}: గత {hours} గంటల్లో {mm} mm వర్షం కురిసింది."},
    "mr": {"since_midnight": "{city}: मध्यरात्रीपासून {mm} mm पाऊस झाला आहे "
                              "({hours} तासांत), सध्या {cond}.",
           "last_24h": "{city}: गेल्या {hours} तासांत {mm} mm पाऊस झाला आहे."},
}

_FORECAST_PHRASES = {
    "en": {"with_pct": "{city}: {pct}% chance of rain", "no_pct": "{city}: forecast",
           "hi_lo": "high {high}°C, low {low}°C"},
    "ta": {"with_pct": "{city}: மழை வரும் வாய்ப்பு {pct}%", "no_pct": "{city}: முன்னறிவிப்பு",
           "hi_lo": "அதிகபட்சம் {high}°C, குறைந்தபட்சம் {low}°C"},
    "hi": {"with_pct": "{city}: बारिश की {pct}% संभावना", "no_pct": "{city}: पूर्वानुमान",
           "hi_lo": "अधिकतम {high}°C, न्यूनतम {low}°C"},
    "te": {"with_pct": "{city}: వర్షం {pct}% అవకాశం", "no_pct": "{city}: సూచన",
           "hi_lo": "గరిష్టం {high}°C, కనిష్టం {low}°C"},
    "mr": {"with_pct": "{city}: पावसाची {pct}% शक्यता", "no_pct": "{city}: अंदाज",
           "hi_lo": "कमाल {high}°C, किमान {low}°C"},
}


def render(intent: str, city: str, data: dict, lang: str) -> str:
    """Template fallback. Branches on the facts SHAPE, not the intent name —
    "weather tomorrow" is parsed as current_weather but carries forecast facts.
    """
    if "days" in data:
        return _render_multi_day(city, data, lang)
    if "rain_so_far_mm" in data or "rain_last_24h_mm" in data:
        return _render_rain_so_far(city, data, lang)
    if "temp_c" in data:
        return _render_current(city, data, lang)
    if "rain_probability_pct" in data or "high_c" in data:
        return _render_forecast(city, data, lang)
    return UNRECOGNIZED.get(lang, UNRECOGNIZED["en"])


def _render_current(city: str, data: dict, lang: str) -> str:
    table = condition_table(lang)
    phrases = _CURRENT_PHRASES.get(lang, _CURRENT_PHRASES["en"])
    cond = table.get(data["condition"], data["condition"])
    feels, humid = data.get("feels_like_c"), data.get("humidity_pct")
    parts = [phrases["now"].format(city=city, cond=cond, temp=data["temp_c"])]
    if feels is not None:
        parts.append(phrases["feels_like"].format(v=feels))
    if humid is not None:
        parts.append(phrases["humidity"].format(v=humid))
    return ", ".join(parts) + "."


def _render_multi_day(city: str, data: dict, lang: str) -> str:
    """N-day outlook. hi/te/mr text reviewed by a native speaker (plan.md §13)."""
    table = condition_table(lang)
    phrases = _MULTI_DAY_PHRASES.get(lang, _MULTI_DAY_PHRASES["en"])
    segments = []
    for day in data["days"]:
        cond = table.get(day.get("condition"), day.get("condition"))
        pct, high, low = day.get("rain_probability_pct"), day.get("high_c"), day.get("low_c")
        seg = f"{day['label']} {cond}" if cond else day["label"]
        if pct is not None:
            seg += phrases["rain_pct"].format(v=pct)
        if high is not None and low is not None:
            seg += phrases["hi_lo"].format(high=high, low=low)
        segments.append(seg)

    counted = data.get("days_counted", len(data["days"]))
    prefix = phrases["prefix"].format(city=city, n=counted)
    suffix = ""
    if data.get("days_requested") and data["days_requested"] > counted:
        suffix = phrases["more_forecast"]
    return prefix + "; ".join(segments) + "." + suffix


def _render_rain_so_far(city: str, data: dict, lang: str) -> str:
    """Rain-so-far-today. hi/te/mr text reviewed by a native speaker (plan.md §13)."""
    table = condition_table(lang)
    phrases = _RAIN_SO_FAR_PHRASES.get(lang, _RAIN_SO_FAR_PHRASES["en"])
    hours = data.get("hours_counted")
    if "rain_so_far_mm" in data:
        mm = data["rain_so_far_mm"]
        cond = table.get(data.get("condition"), data.get("condition"))
        return phrases["since_midnight"].format(city=city, mm=mm, hours=hours, cond=cond)

    mm = data.get("rain_last_24h_mm")
    return phrases["last_24h"].format(city=city, mm=mm, hours=hours)


def _render_forecast(city: str, data: dict, lang: str) -> str:
    phrases = _FORECAST_PHRASES.get(lang, _FORECAST_PHRASES["en"])
    pct, high, low = data.get("rain_probability_pct"), data.get("high_c"), data.get("low_c")
    parts = [phrases["with_pct"].format(city=city, pct=pct) if pct is not None
             else phrases["no_pct"].format(city=city)]
    if high is not None and low is not None:
        parts.append(phrases["hi_lo"].format(high=high, low=low))
    return ", ".join(parts) + "."


# Fail loudly at import time if a table is missing a supported language,
# rather than silently falling back to English at render time — the whole
# point of the table architecture is that a missing 6th-language entry is
# caught immediately, not discovered live during a demo.
for _name, _table in (
    ("CONDITIONS", CONDITIONS),
    ("UNRECOGNIZED", UNRECOGNIZED),
    ("_CURRENT_PHRASES", _CURRENT_PHRASES),
    ("_MULTI_DAY_PHRASES", _MULTI_DAY_PHRASES),
    ("_RAIN_SO_FAR_PHRASES", _RAIN_SO_FAR_PHRASES),
    ("_FORECAST_PHRASES", _FORECAST_PHRASES),
):
    _missing = set(SUPPORTED_LANGUAGES) - set(_table)
    if _missing:
        raise RuntimeError(f"i18n.{_name} is missing language entries: {sorted(_missing)}")
del _name, _table, _missing
