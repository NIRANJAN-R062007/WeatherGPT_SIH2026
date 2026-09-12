"""English/Tamil response rendering for the two demo intents.

Hand-written phrase templates, not live Bhashini translation — faster and
safer for a stage demo than translating untested output live.

CONDITION_* keys are the canonical decoder targets: lowercased Google
Weather API weatherCondition.type. data/decoders/ maps raw type -> these.
Tamil strings taken from the frontend's CITIES object where present;
the rest need a native-speaker QA pass (team).
"""

CONDITION_EN = {
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
}
CONDITION_TA = {
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
    return "Sorry, I couldn't understand that." if lang != "ta" else "மன்னிக்கவும், புரியவில்லை."


def _render_current(city: str, data: dict, lang: str) -> str:
    table = CONDITION_TA if lang == "ta" else CONDITION_EN
    cond = table.get(data["condition"], data["condition"])
    feels, humid = data.get("feels_like_c"), data.get("humidity_pct")
    if lang == "ta":
        parts = [f"{city}: {cond}, {data['temp_c']}°C"]
        if feels is not None:
            parts.append(f"உணரப்படுவது {feels}°C")
        if humid is not None:
            parts.append(f"ஈரப்பதம் {humid}%")
        return ", ".join(parts) + "."
    parts = [f"{city}: {cond}, {data['temp_c']}°C right now"]
    if feels is not None:
        parts.append(f"feels like {feels}°C")
    if humid is not None:
        parts.append(f"humidity {humid}%")
    return ", ".join(parts) + "."


def _render_multi_day(city: str, data: dict, lang: str) -> str:
    """N-day outlook. TA text is minimal — needs Syed's native-speaker QA pass."""
    table = CONDITION_TA if lang == "ta" else CONDITION_EN
    segments = []
    for day in data["days"]:
        cond = table.get(day.get("condition"), day.get("condition"))
        pct, high, low = day.get("rain_probability_pct"), day.get("high_c"), day.get("low_c")
        seg = f"{day['label']} {cond}" if cond else day["label"]
        if lang == "ta":
            if pct is not None:
                seg += f", மழை வாய்ப்பு {pct}%"
            if high is not None and low is not None:
                seg += f", அதிகபட்சம் {high}°C, குறைந்தபட்சம் {low}°C"
        else:
            if pct is not None:
                seg += f", {pct}% chance of rain"
            if high is not None and low is not None:
                seg += f", high {high}°C, low {low}°C"
        segments.append(seg)

    counted = data.get("days_counted", len(data["days"]))
    prefix = f"{city}, அடுத்த {counted} நாட்கள்: " if lang == "ta" else f"{city}, next {counted} days: "
    suffix = ""
    if data.get("days_requested") and data["days_requested"] > counted:
        suffix = (" (இதற்கு மேல் முன்னறிவிப்பு இன்னும் இல்லை)" if lang == "ta"
                  else " (forecast beyond that isn't available yet)")
    return prefix + "; ".join(segments) + "." + suffix


def _render_rain_so_far(city: str, data: dict, lang: str) -> str:
    """Rain-so-far-today. TA text is minimal — needs Syed's native-speaker QA pass."""
    table = CONDITION_TA if lang == "ta" else CONDITION_EN
    hours = data.get("hours_counted")
    if "rain_so_far_mm" in data:
        mm = data["rain_so_far_mm"]
        cond = table.get(data.get("condition"), data.get("condition"))
        if lang == "ta":
            return (f"{city}: நள்ளிரவு முதல் {mm} மி.மீ மழை பெய்துள்ளது "
                    f"({hours} மணி நேரத்தில்), தற்போது {cond}.")
        return f"{city}: {mm} mm of rain since midnight (over {hours} hours), currently {cond}."

    mm = data.get("rain_last_24h_mm")
    if lang == "ta":
        return f"{city}: கடந்த {hours} மணி நேரத்தில் {mm} மி.மீ மழை பெய்துள்ளது."
    return f"{city}: {mm} mm of rain in the last {hours} hours."


def _render_forecast(city: str, data: dict, lang: str) -> str:
    pct, high, low = data.get("rain_probability_pct"), data.get("high_c"), data.get("low_c")
    if lang == "ta":
        parts = [f"{city}: மழை வரும் வாய்ப்பு {pct}%" if pct is not None else f"{city}: முன்னறிவிப்பு"]
        if high is not None and low is not None:
            parts.append(f"அதிகபட்சம் {high}°C, குறைந்தபட்சம் {low}°C")
        return ", ".join(parts) + "."
    parts = [f"{city}: {pct}% chance of rain" if pct is not None else f"{city}: forecast"]
    if high is not None and low is not None:
        parts.append(f"high {high}°C, low {low}°C")
    return ", ".join(parts) + "."
