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
