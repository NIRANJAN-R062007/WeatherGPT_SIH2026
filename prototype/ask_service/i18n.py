"""English/Tamil response rendering for the two §14 demo intents.

Hand-written phrase templates, not live Bhashini translation — per §14 this
is faster and safer for a stage demo than translating untested output live.
"""

CONDITION_EN = {
    "partly_cloudy": "partly cloudy",
}
CONDITION_TA = {
    "partly_cloudy": "பகுதி மேகமூட்டம்",
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
