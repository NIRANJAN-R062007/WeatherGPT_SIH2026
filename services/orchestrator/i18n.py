"""Response rendering for en/ta/hi/te/mr — plan.md §13's five-language target.

Hand-written phrase templates, not live Bhashini translation — faster and
safer for a stage demo than translating untested output live.

Table architecture: every piece of language-specific text (condition names,
day labels, per-fragment phrases, the "couldn't understand" fallback) lives in
a dict keyed by language code, looked up once per render call. Adding a 6th
language is "add one entry to each table below," not touching any function
body — see the consistency check at the bottom of this file, which fails
loudly at import time if a table is missing an entry for a supported language
or a language's row lacks a key the English row has.

CONDITION_* keys are the canonical decoder targets: lowercased Google
Weather API weatherCondition.type. data/decoders/ maps raw type -> these.
Tamil strings taken from the frontend's CITIES object where present.

hi/te/mr entries are first-draft machine translations by a non-native
speaker, NOT reverse-engineered from real Bhashini output the way the Tamil
strings were. Native-speaker QA (plan.md §13) happened once, on Sep 13
(commit fce2ad9), and covered exactly the hi/te/mr strings this file held at
that commit: CONDITIONS, UNRECOGNIZED, the now/feels_like/humidity phrases of
_CURRENT_PHRASES, and all of _MULTI_DAY_PHRASES, _RAIN_SO_FAR_PHRASES and
_FORECAST_PHRASES. None of those strings has changed since, so the "Reviewed
by a native speaker" comments below hold for them and for nothing else.
Everything added later is unreviewed in every language and carries a
`# TODO: native_qa` marker: the whole DAY_LABELS table (Sep 21, Tamil row
included) and the "uv" phrase in _CURRENT_PHRASES (Sep 14, Tamil included —
that one is not from Bhashini output either). Keep the marker on any new or
edited hi/te/mr string until a native speaker has confirmed that exact text;
main.py's _MESSAGES and data/i18n/glossary.json track the same thing with a
block comment and per-entry `native_qa` flags respectively.
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
    # Reviewed by a native speaker — confirmed accurate (Sep 13, commit fce2ad9;
    # plan.md §13). Unchanged since; re-add `# TODO: native_qa` if any row is edited.
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
    # Reviewed by a native speaker — confirmed accurate (Sep 13, commit fce2ad9;
    # plan.md §13). Unchanged since; re-add `# TODO: native_qa` if any row is edited.
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
    # Reviewed by a native speaker — confirmed accurate (Sep 13, commit fce2ad9;
    # plan.md §13). Unchanged since; re-add `# TODO: native_qa` if any row is edited.
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


# Keys are weather_data's canonical day labels ("today"/"tomorrow" by position,
# else the weekday, else "later" for an entry whose date can't be read). The
# multi-day template used to interpolate the raw key, so a Tamil outlook read
# "today ..., tomorrow ..., wednesday ..." on exactly the offline path (plan.md
# §11 R5) where no LLM/Bhashini could paper over it.
DAY_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "today": "today",
        "tomorrow": "tomorrow",
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday",
        "saturday": "Saturday",
        "sunday": "Sunday",
        "later": "later",
    },
    # Day names are a first draft by a non-native speaker, NOT reverse-engineered
    # from real Bhashini output like the rest of the Tamil strings.
    "ta": {  # TODO: native_qa
        "today": "இன்று",
        "tomorrow": "நாளை",
        "monday": "திங்கட்கிழமை",
        "tuesday": "செவ்வாய்க்கிழமை",
        "wednesday": "புதன்கிழமை",
        "thursday": "வியாழக்கிழமை",
        "friday": "வெள்ளிக்கிழமை",
        "saturday": "சனிக்கிழமை",
        "sunday": "ஞாயிற்றுக்கிழமை",
        "later": "பின்னர்",
    },
    # Day names are a first-draft machine translation (Sep 21), not native-speaker
    # reviewed — the Sep 13 review predates this table (see the module docstring).
    "hi": {  # TODO: native_qa
        "today": "आज",
        "tomorrow": "कल",
        "monday": "सोमवार",
        "tuesday": "मंगलवार",
        "wednesday": "बुधवार",
        "thursday": "गुरुवार",
        "friday": "शुक्रवार",
        "saturday": "शनिवार",
        "sunday": "रविवार",
        "later": "बाद में",
    },
    # Day names are a first-draft machine translation (Sep 21), not native-speaker
    # reviewed — the Sep 13 review predates this table (see the module docstring).
    "te": {  # TODO: native_qa
        "today": "ఈరోజు",
        "tomorrow": "రేపు",
        "monday": "సోమవారం",
        "tuesday": "మంగళవారం",
        "wednesday": "బుధవారం",
        "thursday": "గురువారం",
        "friday": "శుక్రవారం",
        "saturday": "శనివారం",
        "sunday": "ఆదివారం",
        "later": "తర్వాత",
    },
    # Day names are a first-draft machine translation (Sep 21), not native-speaker
    # reviewed — the Sep 13 review predates this table (see the module docstring).
    "mr": {  # TODO: native_qa
        "today": "आज",
        "tomorrow": "उद्या",
        "monday": "सोमवार",
        "tuesday": "मंगळवार",
        "wednesday": "बुधवार",
        "thursday": "गुरुवार",
        "friday": "शुक्रवार",
        "saturday": "शनिवार",
        "sunday": "रविवार",
        "later": "नंतर",
    },
}


UNRECOGNIZED = {
    "en": "Sorry, I couldn't understand that.",
    "ta": "மன்னிக்கவும், புரியவில்லை.",
    "hi": "माफ़ कीजिए, मुझे समझ नहीं आया।",  # Reviewed by native speaker (Sep 13, fce2ad9).
    "te": "క్షమించండి, అర్థం కాలేదు.",  # Reviewed by native speaker (Sep 13, fce2ad9).
    "mr": "माफ करा, समजले नाही.",  # Reviewed by native speaker (Sep 13, fce2ad9).
}

# Per-fragment phrase tables for each render function below. Symbols (°C, %)
# are used directly in every language, matching live Bhashini output only
# loosely — hand-written templates never need the spelled-out unit words
# guardrail.py handles; those exist for *translated* LLM answers, not these.
_CURRENT_PHRASES = {
    "en": {"now": "{city}: {cond}, {temp}°C right now",
           "feels_like": "feels like {v}°C", "humidity": "humidity {v}%",
           "uv": "UV index {v}"},
    # UV phrase is a first draft by a non-native speaker (Sep 14), NOT
    # reverse-engineered from real Bhashini output like the rest of this row.
    "ta": {"now": "{city}: {cond}, {temp}°C",
           "feels_like": "உணரப்படுவது {v}°C", "humidity": "ஈரப்பதம் {v}%",
           "uv": "UV குறியீடு {v}"},  # TODO: native_qa
    # UV phrase is a first-draft machine translation (Sep 14), not native-speaker
    # reviewed — added after the Sep 13 review that covers the rest of this row.
    "hi": {"now": "{city}: {cond}, अभी {temp}°C",
           "feels_like": "महसूस होता है {v}°C जैसा", "humidity": "आर्द्रता {v}%",
           "uv": "यूवी इंडेक्स {v}"},  # TODO: native_qa
    # UV phrase is a first-draft machine translation (Sep 14), not native-speaker
    # reviewed — added after the Sep 13 review that covers the rest of this row.
    "te": {"now": "{city}: {cond}, ప్రస్తుతం {temp}°C",
           "feels_like": "అనుభూతి {v}°C", "humidity": "తేమ {v}%",
           "uv": "యూవీ సూచిక {v}"},  # TODO: native_qa
    # UV phrase is a first-draft machine translation (Sep 14), not native-speaker
    # reviewed — added after the Sep 13 review that covers the rest of this row.
    "mr": {"now": "{city}: {cond}, सध्या {temp}°C",
           "feels_like": "जाणवते {v}°C", "humidity": "आर्द्रता {v}%",
           "uv": "यूव्ही निर्देशांक {v}"},  # TODO: native_qa
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
    feels, humid, uv = data.get("feels_like_c"), data.get("humidity_pct"), data.get("uv_index")
    parts = [phrases["now"].format(city=city, cond=cond, temp=data["temp_c"])]
    if feels is not None:
        parts.append(phrases["feels_like"].format(v=feels))
    if humid is not None:
        parts.append(phrases["humidity"].format(v=humid))
    if uv is not None:
        parts.append(phrases["uv"].format(v=uv))
    return ", ".join(parts) + "."


def _render_multi_day(city: str, data: dict, lang: str) -> str:
    """N-day outlook. hi/te/mr phrases reviewed by a native speaker (Sep 13,
    fce2ad9; plan.md §13) and unchanged since; the day labels are not reviewed
    in any language (see DAY_LABELS).
    """
    table = condition_table(lang)
    labels = DAY_LABELS.get(lang, DAY_LABELS["en"])
    phrases = _MULTI_DAY_PHRASES.get(lang, _MULTI_DAY_PHRASES["en"])
    segments = []
    for day in data["days"]:
        label = labels.get(day["label"], day["label"])
        cond = table.get(day.get("condition"), day.get("condition"))
        pct, high, low = day.get("rain_probability_pct"), day.get("high_c"), day.get("low_c")
        seg = f"{label} {cond}" if cond else label
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
    """Rain-so-far-today. hi/te/mr text reviewed by a native speaker (Sep 13,
    fce2ad9; plan.md §13) and unchanged since.
    """
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


# --- Weather Intelligence Engine answers (WIE-8) ------------------------------
# The best-window, what-if and forecast-change answers, built straight from the
# engine's structured results (weather_intelligence/) with no LLM, so the
# engine answers in every language offline (R5). Figures keep their symbols
# (°C, %, km/h) and clock times stay "HH:MM", so each sentence grounds the same
# way in every language. English is unchanged from main.py's WIE-4/WIE-11
# sentences. Every ta/hi/te/mr string here is a first draft. TODO: native_qa
_WIE_DAY = {
    "en": {"today": "today", "tomorrow": "tomorrow"},
    "hi": {"today": "आज", "tomorrow": "कल"},
    "ta": {"today": "இன்று", "tomorrow": "நாளை"},
    "te": {"today": "ఈరోజు", "tomorrow": "రేపు"},
    "mr": {"today": "आज", "tomorrow": "उद्या"},
}

_WINDOW_PHRASES = {
    "en": {
        "ok": "{city}: the most suitable window to be outdoors {day} is {start}–{end} "
              "(around {temp}°C, up to {rain}% chance of rain, winds up to {wind} km/h).",
        "none": "{city}: no suitable window to be outdoors {day} — every hour had too much "
                "rain, heat, cold or wind.",
    },
    "hi": {
        "ok": "{city}: {day} बाहर रहने के लिए सबसे उपयुक्त समय {start}–{end} है "
              "(लगभग {temp}°C, बारिश की संभावना {rain}% तक, हवा {wind} km/h तक)।",
        "none": "{city}: {day} बाहर रहने के लिए कोई उपयुक्त समय नहीं है — हर घंटे बारिश, "
                "गर्मी, ठंड या हवा बहुत ज़्यादा है।",
    },
    "ta": {
        "ok": "{city}: {day} வெளியே செல்ல மிகவும் ஏற்ற நேரம் {start}–{end} "
              "(சுமார் {temp}°C, மழை வாய்ப்பு {rain}% வரை, காற்று {wind} km/h வரை).",
        "none": "{city}: {day} வெளியே செல்ல ஏற்ற நேரம் இல்லை — ஒவ்வொரு மணி நேரமும் மழை, "
                "வெப்பம், குளிர் அல்லது காற்று அதிகமாக உள்ளது.",
    },
    "te": {
        "ok": "{city}: {day} బయట ఉండటానికి అత్యంత అనువైన సమయం {start}–{end} "
              "(సుమారు {temp}°C, వర్షం అవకాశం {rain}% వరకు, గాలి {wind} km/h వరకు).",
        "none": "{city}: {day} బయట ఉండటానికి అనువైన సమయం లేదు — ప్రతి గంటలోనూ వర్షం, "
                "వేడి, చలి లేదా గాలి ఎక్కువగా ఉంది.",
    },
    "mr": {
        "ok": "{city}: {day} बाहेर जाण्यासाठी सर्वात योग्य वेळ {start}–{end} आहे "
              "(सुमारे {temp}°C, पावसाची शक्यता {rain}% पर्यंत, वारा {wind} km/h पर्यंत).",
        "none": "{city}: {day} बाहेर जाण्यासाठी योग्य वेळ नाही — प्रत्येक तासाला पाऊस, "
                "उष्णता, थंडी किंवा वारा जास्त आहे.",
    },
}

# {day_of}: "tomorrow's" in English; the Indic rows say "in {day}'s forecast"
# their own way. Hindi and Marathi use a noun for the direction ("an increase
# in ...") so the sentence needs no gender agreement with the metric.
_CHANGE_PHRASES = {
    "en": {
        "rain_probability_pct": "chance of rain", "temp_c": "temperature",
        "wind_kmh": "wind speed",
        "item": "{label} {direction} from {frm} to {to} ({span})",
        "rose": "rose", "fell": "fell",
        "around": "around {t}", "mostly": "mostly {s}–{e}",
        "since": "since the forecast retrieved {then} (now {now})",
        "ok": "{city}: {day}'s {items} {since}.",
        "none": "{city}: no significant change in {day}'s forecast {since}.",
    },
    "hi": {
        "rain_probability_pct": "बारिश की संभावना", "temp_c": "तापमान",
        "wind_kmh": "हवा की गति",
        "item": "{label} में {direction}: {frm} से {to} ({span})",
        "rose": "बढ़ोतरी", "fell": "कमी",
        "around": "लगभग {t}", "mostly": "मुख्यतः {s}–{e}",
        "since": "{then} पर लिए गए पूर्वानुमान की तुलना में (अभी {now})",
        "ok": "{city}: {day} के पूर्वानुमान में, {since}: {items}।",
        "none": "{city}: {day} के पूर्वानुमान में {since} कोई खास बदलाव नहीं है।",
    },
    "ta": {
        "rain_probability_pct": "மழை வாய்ப்பு", "temp_c": "வெப்பநிலை",
        "wind_kmh": "காற்றின் வேகம்",
        "item": "{label} {frm} இலிருந்து {to} ஆக {direction} ({span})",
        "rose": "உயர்ந்தது", "fell": "குறைந்தது",
        "around": "சுமார் {t}", "mostly": "பெரும்பாலும் {s}–{e}",
        "since": "{then} அன்று பெறப்பட்ட முன்னறிவிப்புடன் ஒப்பிடுகையில் (இப்போது {now})",
        "ok": "{city}: {day} முன்னறிவிப்பில், {since}: {items}.",
        "none": "{city}: {day} முன்னறிவிப்பில் {since} குறிப்பிடத்தக்க மாற்றம் இல்லை.",
    },
    "te": {
        "rain_probability_pct": "వర్షం అవకాశం", "temp_c": "ఉష్ణోగ్రత",
        "wind_kmh": "గాలి వేగం",
        "item": "{label} {frm} నుంచి {to}కి {direction} ({span})",
        "rose": "పెరిగింది", "fell": "తగ్గింది",
        "around": "సుమారు {t}", "mostly": "ఎక్కువగా {s}–{e}",
        "since": "{then}న తీసుకున్న సూచనతో పోలిస్తే (ఇప్పుడు {now})",
        "ok": "{city}: {day} సూచనలో, {since}: {items}.",
        "none": "{city}: {day} సూచనలో {since} గణనీయమైన మార్పు లేదు.",
    },
    "mr": {
        "rain_probability_pct": "पावसाची शक्यता", "temp_c": "तापमान",
        "wind_kmh": "वाऱ्याचा वेग",
        "item": "{label} मध्ये {direction}: {frm} वरून {to} ({span})",
        "rose": "वाढ", "fell": "घट",
        "around": "सुमारे {t}", "mostly": "मुख्यतः {s}–{e}",
        "since": "{then} रोजी घेतलेल्या अंदाजाच्या तुलनेत (आता {now})",
        "ok": "{city}: {day}च्या अंदाजात, {since}: {items}.",
        "none": "{city}: {day}च्या अंदाजात {since} लक्षणीय बदल नाही.",
    },
}
_CHANGE_UNITS = {"rain_probability_pct": "%", "temp_c": "°C", "wind_kmh": " km/h"}

_SCENARIO_PHRASES = {
    "en": {"rain": "{v}% chance of rain", "wind": "winds {v} km/h",
           "missing": "{t} — not in the forecast",
           "better": " {t} has the lower chance of rain."},
    "hi": {"rain": "बारिश की संभावना {v}%", "wind": "हवा {v} km/h",
           "missing": "{t} — पूर्वानुमान में नहीं है",
           "better": " {t} पर बारिश की संभावना कम है।"},
    "ta": {"rain": "மழை வாய்ப்பு {v}%", "wind": "காற்று {v} km/h",
           "missing": "{t} — முன்னறிவிப்பில் இல்லை",
           "better": " {t} மணிக்கு மழை வாய்ப்பு குறைவு."},
    "te": {"rain": "వర్షం అవకాశం {v}%", "wind": "గాలి {v} km/h",
           "missing": "{t} — సూచనలో లేదు",
           "better": " {t}కి వర్షం అవకాశం తక్కువ."},
    "mr": {"rain": "पावसाची शक्यता {v}%", "wind": "वारा {v} km/h",
           "missing": "{t} — अंदाजात नाही",
           "better": " {t} ला पावसाची शक्यता कमी आहे."},
}

# fisherman/aviation get this instead of a window verdict (R17). English is
# persona_advisor.CAVEATS verbatim (tests/test_wie_templates.py pins that).
_PERSONA_CAVEATS = {
    "en": {
        "fisherman": "This is a city forecast, not sea conditions — always check the "
                     "official IMD fishermen warning before going out.",
        "aviation": "This is a city forecast, not an airport observation — it has no "
                    "visibility, cloud base or runway data.",
    },
    "hi": {
        "fisherman": "यह शहर का पूर्वानुमान है, समुद्र की स्थिति नहीं — समुद्र में जाने से पहले "
                     "हमेशा IMD की आधिकारिक मछुआरा चेतावनी देखें।",
        "aviation": "यह शहर का पूर्वानुमान है, हवाई अड्डे का अवलोकन नहीं — इसमें दृश्यता, "
                    "बादलों की ऊँचाई या रनवे का डेटा नहीं है।",
    },
    "ta": {
        "fisherman": "இது நகர வானிலை முன்னறிவிப்பு, கடல் நிலை அல்ல — கடலுக்குச் செல்லும் முன் "
                     "எப்போதும் IMD-யின் அதிகாரப்பூர்வ மீனவர் எச்சரிக்கையைப் பாருங்கள்.",
        "aviation": "இது நகர வானிலை முன்னறிவிப்பு, விமான நிலைய அவதானிப்பு அல்ல — இதில் "
                    "தெரிவுநிலை, மேக அடிமட்டம் அல்லது ஓடுபாதை தரவு இல்லை.",
    },
    "te": {
        "fisherman": "ఇది నగర వాతావరణ సూచన, సముద్ర పరిస్థితులు కాదు — వేటకు వెళ్లే ముందు "
                     "ఎల్లప్పుడూ IMD అధికారిక మత్స్యకారుల హెచ్చరికను చూడండి.",
        "aviation": "ఇది నగర వాతావరణ సూచన, విమానాశ్రయ పరిశీలన కాదు — ఇందులో దృశ్యమానత, "
                    "మేఘాల ఎత్తు లేదా రన్‌వే డేటా లేదు.",
    },
    "mr": {
        "fisherman": "हा शहराचा अंदाज आहे, समुद्राची स्थिती नाही — समुद्रात जाण्यापूर्वी नेहमी "
                     "IMD चा अधिकृत मच्छीमार इशारा तपासा.",
        "aviation": "हा शहराचा अंदाज आहे, विमानतळाचे निरीक्षण नाही — यात दृश्यमानता, "
                    "ढगांची उंची किंवा धावपट्टीचा डेटा नाही.",
    },
}


def _wie_day(day: str, lang: str) -> str:
    return _WIE_DAY[lang]["tomorrow" if day == "tomorrow" else "today"]


def _num(value: float) -> str:
    return f"{value:g}"


def best_window_text(city: str, day: str, window: dict, lang: str) -> str:
    """WIE-4's best-window sentence from window_analyzer's result."""
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    return _WINDOW_PHRASES[lang]["ok"].format(
        city=city, day=_wie_day(day, lang), start=window["start_local"],
        end=window["end_local"], temp=window["avg_temp_c"],
        rain=window["max_rain_probability_pct"], wind=window["max_wind_kmh"],
    )


def no_suitable_window_text(city: str, day: str, lang: str) -> str:
    """"No suitable window" is an honest answer (R17), never the least-bad hour."""
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    return _WINDOW_PHRASES[lang]["none"].format(city=city, day=_wie_day(day, lang))


def changes_text(city: str, day: str, result: dict, then: str, now: str, lang: str) -> str:
    """WIE-11's forecast-change sentence from change_detector's result; `then`
    and `now` are the two retrieval times, already formatted."""
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    p = _CHANGE_PHRASES[lang]
    day_word, since = _wie_day(day, lang), p["since"].format(then=then, now=now)
    if result["status"] == "no_significant_change":
        return p["none"].format(city=city, day=day_word, since=since)
    items = []
    for c in result["changes"]:
        unit = _CHANGE_UNITS[c["metric"]]
        span = (p["around"].format(t=c["start_local"]) if c["start_local"] == c["end_local"]
                else p["mostly"].format(s=c["start_local"], e=c["end_local"]))
        items.append(p["item"].format(
            label=p[c["metric"]], direction=p[c["direction"]],
            frm=f"{_num(c['from'])}{unit}", to=f"{_num(c['to'])}{unit}", span=span,
        ))
    return p["ok"].format(city=city, day=day_word, items="; ".join(items), since=since)


def scenario_text(city: str, day: str, result: dict, lang: str) -> str:
    """WIE-6's what-if comparison from scenario_analyzer's result: each asked
    time's figures (or that it isn't in the forecast — never an invented
    value), then the time with the lower rain chance when there is one."""
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    p = _SCENARIO_PHRASES[lang]
    parts = []
    for h in result["hours"]:
        if not h["available"]:
            parts.append(p["missing"].format(t=h["time"]))
            continue
        figures = []
        if h.get("temp_c") is not None:
            figures.append(f"{_num(h['temp_c'])}°C")
        if h.get("rain_probability_pct") is not None:
            figures.append(p["rain"].format(v=_num(h["rain_probability_pct"])))
        if h.get("wind_kmh") is not None:
            figures.append(p["wind"].format(v=_num(h["wind_kmh"])))
        parts.append(f"{h['time']} — " + ", ".join(figures))
    text = f"{city}, {_wie_day(day, lang)}: " + "; ".join(parts) + "."
    if result.get("better_time"):
        text += p["better"].format(t=result["better_time"])
    return text


def persona_caveat(persona: str, lang: str) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    return _PERSONA_CAVEATS[lang][persona]


# Fail loudly at import time if a table is missing a supported language, or a
# language's row is missing a key the English row has, rather than silently
# falling back to English (or the raw key) at render time — the whole point of
# the table architecture is that a missing 6th-language entry or a forgotten
# weekday is caught immediately, not discovered live during a demo.
for _name, _table in (
    ("CONDITIONS", CONDITIONS),
    ("DAY_LABELS", DAY_LABELS),
    ("UNRECOGNIZED", UNRECOGNIZED),
    ("_CURRENT_PHRASES", _CURRENT_PHRASES),
    ("_MULTI_DAY_PHRASES", _MULTI_DAY_PHRASES),
    ("_RAIN_SO_FAR_PHRASES", _RAIN_SO_FAR_PHRASES),
    ("_FORECAST_PHRASES", _FORECAST_PHRASES),
    ("_WIE_DAY", _WIE_DAY),
    ("_WINDOW_PHRASES", _WINDOW_PHRASES),
    ("_CHANGE_PHRASES", _CHANGE_PHRASES),
    ("_SCENARIO_PHRASES", _SCENARIO_PHRASES),
    ("_PERSONA_CAVEATS", _PERSONA_CAVEATS),
):
    _missing = set(SUPPORTED_LANGUAGES) - set(_table)
    if _missing:
        raise RuntimeError(f"i18n.{_name} is missing language entries: {sorted(_missing)}")
    _keyed = isinstance(_table["en"], dict)  # UNRECOGNIZED is a flat lang -> str table
    for _lang in SUPPORTED_LANGUAGES:
        _missing = set(_table["en"]) ^ set(_table[_lang]) if _keyed else set()
        if _missing:
            raise RuntimeError(f"i18n.{_name}[{_lang!r}] keys differ from en: {sorted(_missing)}")
del _name, _table, _keyed, _lang, _missing


# What /ask says instead of an answer when location.resolve_location() has no
# single point (main.py). {place} is the name as the user wrote it; {nearest}
# a gazetteer label. No figures, so nothing here needs grounding.
# Every ta/hi/te/mr string is a first draft (audit 4.2).
LOCATION_MESSAGES = {
    "need_location": {
        "en": "Which place? Name a town or city, or share your location.",
        "ta": "எந்த இடம்? ஒரு ஊர் அல்லது நகரத்தின் பெயரைச் சொல்லுங்கள், அல்லது உங்கள் இருப்பிடத்தைப் பகிருங்கள்.",  # noqa: E501 — TODO: native_qa
        "hi": "कौन सी जगह? किसी कस्बे या शहर का नाम बताइए, या अपनी लोकेशन साझा कीजिए।",  # noqa: E501 — TODO: native_qa
        "te": "ఏ ప్రదేశం? ఒక ఊరు లేదా నగరం పేరు చెప్పండి, లేదా మీ లొకేషన్ పంచుకోండి.",  # noqa: E501 — TODO: native_qa
        "mr": "कोणते ठिकाण? एखाद्या गावाचे किंवा शहराचे नाव सांगा, किंवा तुमचे स्थान शेअर करा.",  # noqa: E501 — TODO: native_qa
    },
    "which_place": {
        "en": "There is more than one place with that name. Which one did you mean?",
        "ta": "அந்தப் பெயரில் ஒன்றுக்கு மேற்பட்ட இடங்கள் உள்ளன. நீங்கள் எதைக் குறிப்பிடுகிறீர்கள்?",  # noqa: E501 — TODO: native_qa
        "hi": "इस नाम की एक से अधिक जगहें हैं। आपका मतलब कौन सी से है?",  # TODO: native_qa
        "te": "ఆ పేరుతో ఒకటి కంటే ఎక్కువ ప్రదేశాలు ఉన్నాయి. మీరు ఏది అనుకుంటున్నారు?",  # noqa: E501 — TODO: native_qa
        "mr": "या नावाची एकापेक्षा जास्त ठिकाणे आहेत. तुम्हाला कोणते म्हणायचे आहे?",  # noqa: E501 — TODO: native_qa
    },
    "place_not_found": {
        "en": "I couldn't find {place} in India. The nearest known place is {nearest}.",
        "ta": "இந்தியாவில் {place} என்ற இடத்தைக் கண்டுபிடிக்க முடியவில்லை. அருகிலுள்ள அறியப்பட்ட இடம் {nearest}.",  # noqa: E501 — TODO: native_qa
        "hi": "भारत में {place} नहीं मिला। सबसे नज़दीकी ज्ञात जगह {nearest} है।",  # TODO: native_qa
        "te": "భారతదేశంలో {place} కనుగొనలేకపోయాను. దగ్గరలో తెలిసిన ప్రదేశం {nearest}.",  # noqa: E501 — TODO: native_qa
        "mr": "भारतात {place} सापडले नाही. सर्वात जवळचे ज्ञात ठिकाण {nearest} आहे.",  # noqa: E501 — TODO: native_qa
    },
    "place_not_found_bare": {
        "en": "I couldn't find {place} in India. Try a nearby town or city.",
        "ta": "இந்தியாவில் {place} என்ற இடத்தைக் கண்டுபிடிக்க முடியவில்லை. அருகிலுள்ள ஊர் அல்லது நகரத்தை முயற்சிக்கவும்.",  # noqa: E501 — TODO: native_qa
        "hi": "भारत में {place} नहीं मिला। पास का कोई कस्बा या शहर आज़माइए।",  # TODO: native_qa
        "te": "భారతదేశంలో {place} కనుగొనలేకపోయాను. దగ్గరలోని ఊరు లేదా నగరాన్ని ప్రయత్నించండి.",  # noqa: E501 — TODO: native_qa
        "mr": "भारतात {place} सापडले नाही. जवळचे गाव किंवा शहर वापरून पहा.",  # TODO: native_qa
    },
    "india_only": {
        "en": "Sorry, I can only answer for places in India.",
        "ta": "மன்னிக்கவும், இந்தியாவில் உள்ள இடங்களுக்கு மட்டுமே பதிலளிக்க முடியும்.",  # noqa: E501 — TODO: native_qa
        "hi": "माफ़ कीजिए, मैं केवल भारत की जगहों के लिए बता सकता हूँ।",  # TODO: native_qa
        "te": "క్షమించండి, నేను భారతదేశంలోని ప్రదేశాలకు మాత్రమే సమాధానం ఇవ్వగలను.",  # noqa: E501 — TODO: native_qa
        "mr": "माफ करा, मी फक्त भारतातील ठिकाणांसाठी उत्तर देऊ शकतो.",  # TODO: native_qa
    },
    # The label a GPS answer carries (location.py): {town} is the nearest
    # gazetteer town, in this language where GeoNames has the name.
    "gps_label": {
        "en": "your location (near {town})",
        "ta": "உங்கள் இருப்பிடம் ({town} அருகில்)",  # TODO: native_qa
        "hi": "आपकी लोकेशन ({town} के पास)",  # TODO: native_qa
        "te": "మీ లొకేషన్ ({town} దగ్గర)",  # TODO: native_qa
        "mr": "तुमचे स्थान ({town} जवळ)",  # TODO: native_qa
    },
    "gps_label_bare": {
        "en": "your location",
        "ta": "உங்கள் இருப்பிடம்",  # TODO: native_qa
        "hi": "आपकी लोकेशन",  # TODO: native_qa
        "te": "మీ లొకేషన్",  # TODO: native_qa
        "mr": "तुमचे स्थान",  # TODO: native_qa
    },
    # Offline (OFFLINE_MODE / WEATHER_MODE=fixtures): only the demo cities
    # have saved data. {city}: the demo city a GPS answer used instead.
    "offline_nearest_demo": {
        "en": "Offline, so this is for {city}, the nearest city with saved data.",
        "ta": "இணைப்பு இல்லை, எனவே இது சேமித்த தரவு உள்ள அருகிலுள்ள நகரமான {city}க்கானது.",  # noqa: E501 — TODO: native_qa
        "hi": "ऑफ़लाइन है, इसलिए यह {city} के लिए है, सहेजे गए डेटा वाला सबसे नज़दीकी शहर।",  # noqa: E501 — TODO: native_qa
        "te": "ఆఫ్‌లైన్‌లో ఉంది, కాబట్టి ఇది సేవ్ చేసిన డేటా ఉన్న దగ్గరి నగరం {city} కోసం.",  # noqa: E501 — TODO: native_qa
        "mr": "ऑफलाइन आहे, म्हणून हे जतन केलेला डेटा असलेल्या सर्वात जवळच्या {city} शहरासाठी आहे.",  # noqa: E501 — TODO: native_qa
    },
    "offline_demo_only": {
        "en": "Offline, I only have saved data for {cities} — not {place}.",
        "ta": "இணைப்பு இல்லை; {cities} ஆகியவற்றுக்கு மட்டுமே சேமித்த தரவு உள்ளது — {place}க்கு இல்லை.",  # noqa: E501 — TODO: native_qa
        "hi": "ऑफ़लाइन मेरे पास केवल {cities} का सहेजा गया डेटा है — {place} का नहीं।",  # noqa: E501 — TODO: native_qa
        "te": "ఆఫ్‌లైన్‌లో నా దగ్గర {cities} కోసం మాత్రమే సేవ్ చేసిన డేటా ఉంది — {place} కోసం లేదు.",  # noqa: E501 — TODO: native_qa
        "mr": "ऑफलाइन माझ्याकडे फक्त {cities} साठी जतन केलेला डेटा आहे — {place} साठी नाही.",  # noqa: E501 — TODO: native_qa
    },
}


def location_message(key: str, lang: str, **fields) -> str:
    table = LOCATION_MESSAGES[key]
    return table.get(lang, table["en"]).format(**fields)


# The provenance footer main.py appends to a weather answer AFTER the
# guardrail has validated it: the place and the rounded point the data was
# fetched for. Its coordinates are never checked as weather figures.
_PLACE_FOOTER = {
    "en": "Forecast for {place} ({coords}).",
    "ta": "{place} ({coords}) பகுதிக்கான முன்னறிவிப்பு.",  # TODO: native_qa
    "hi": "{place} ({coords}) के लिए पूर्वानुमान।",  # TODO: native_qa
    "te": "{place} ({coords}) కోసం వాతావరణ సూచన.",  # TODO: native_qa
    "mr": "{place} ({coords}) साठी अंदाज.",  # TODO: native_qa
}


def place_footer(place: str, lat: float, lon: float, lang: str) -> str:
    coords = (f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, "
              f"{abs(lon):.2f}°{'E' if lon >= 0 else 'W'}")
    return _PLACE_FOOTER.get(lang, _PLACE_FOOTER["en"]).format(place=place, coords=coords)
