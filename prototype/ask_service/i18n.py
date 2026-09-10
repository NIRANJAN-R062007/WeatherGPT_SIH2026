"""English/Tamil response rendering for the two demo intents.

Hand-written phrase templates, not live Bhashini translation — faster and
safer for a stage demo than translating untested output live.

CONDITION_* keys are the canonical decoder targets: lowercased Google
Weather API weatherCondition.type. data/decoders/ maps raw type -> these.
Tamil strings taken from the frontend's CITIES object where present;
the rest need a native-speaker QA pass (team).
"""

CONDITION_EN = {
    "partly_cloudy": "partly cloudy",
    "cloudy": "cloudy",
    "clear": "clear",
    "mostly_clear": "mostly clear",
    "light_rain": "light rain",
    "thunderstorm_with_rain": "thunderstorm with rain",
    "scattered_thunderstorms": "scattered thunderstorms",
}
CONDITION_TA = {
    "partly_cloudy": "பகுதி மேகமூட்டம்",
    "cloudy": "மேகமூட்டம்",
    "clear": "தெளிவான வானம்",
    "mostly_clear": "பெரும்பாலும் தெளிவு",
    "light_rain": "லேசான மழை",
    "thunderstorm_with_rain": "இடியுடன் கூடிய மழை",
    "scattered_thunderstorms": "சிதறலான இடியுடன் மழை",
}


def render(intent: str, city: str, data: dict, lang: str) -> str:
    if lang == "ta":
        return _render_ta(intent, city, data)
    return _render_en(intent, city, data)


def _render_en(intent: str, city: str, data: dict) -> str:
    condition = CONDITION_EN.get(data["condition"], data["condition"])
    if intent == "current_weather":
        return f"{city}: {condition}, {data['temp_c']}°C right now."
    if intent == "will_it_rain":
        return f"{city}: {data['rain_probability_pct']}% chance of rain."
    return "Sorry, I couldn't understand that."


def _render_ta(intent: str, city: str, data: dict) -> str:
    condition = CONDITION_TA.get(data["condition"], data["condition"])
    if intent == "current_weather":
        return f"{city}: {condition}, {data['temp_c']}°C."
    if intent == "will_it_rain":
        return f"{city}: மழை வரும் வாய்ப்பு {data['rain_probability_pct']}%."
    return "மன்னிக்கவும், புரியவில்லை."
