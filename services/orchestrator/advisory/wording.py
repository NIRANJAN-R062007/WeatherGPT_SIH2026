"""The rule-based advisory answer's sentences in all five languages (plan.md §8 TFA-23).

`template.py` and `rubric.py` build every sentence of the template answer, the
override reasons and the caveat through `say()`, so a farmer asking in Tamil gets
the fallback answer in Tamil, not English. English is unchanged from before.

Figures keep their symbols (°C, %, km/h, mm) in every language: the guardrail's
symbol markers are language-neutral, so each translated sentence still grounds.
The Indic sentences put the place first ("{role}: ..."), which keeps them correct
without per-language case endings on "origin" / "destination".

Every non-English string is a first draft for native-speaker review. TODO: native_qa
"""

from __future__ import annotations

import i18n

LANGS = ("en", "hi", "ta", "te", "mr")

MESSAGES: dict[str, dict[str, str]] = {
    # --- travel -------------------------------------------------------------------
    "forecast_unavailable_role": {
        "en": "The forecast for the {role} is not available.",
        "hi": "{role}: मौसम पूर्वानुमान उपलब्ध नहीं है।",
        "ta": "{role}: வானிலை முன்னறிவிப்பு கிடைக்கவில்லை.",
        "te": "{role}: వాతావరణ సూచన అందుబాటులో లేదు.",
        "mr": "{role}: हवामान अंदाज उपलब्ध नाही.",
    },
    "rain_chance_role": {
        "en": "Rain chance at the {role} is {pct}%.",
        "hi": "{role}: बारिश की संभावना {pct}% है।",
        "ta": "{role}: மழை வாய்ப்பு {pct}%.",
        "te": "{role}: వర్షం పడే అవకాశం {pct}%.",
        "mr": "{role}: पावसाची शक्यता {pct}% आहे.",
    },
    "no_wind_role": {
        "en": "No wind forecast for the trip day is available for the {role}.",
        "hi": "{role}: यात्रा के दिन का हवा का पूर्वानुमान उपलब्ध नहीं है।",
        "ta": "{role}: பயண நாளுக்கான காற்று முன்னறிவிப்பு கிடைக்கவில்லை.",
        "te": "{role}: ప్రయాణ రోజుకు గాలి సూచన అందుబాటులో లేదు.",
        "mr": "{role}: प्रवासाच्या दिवसाचा वाऱ्याचा अंदाज उपलब्ध नाही.",
    },
    "wind_role": {
        "en": "Wind at the {role} reaches {wind} km/h.",
        "hi": "{role}: हवा {wind} km/h तक पहुँचती है।",
        "ta": "{role}: காற்று {wind} km/h வரை வீசும்.",
        "te": "{role}: గాలి {wind} km/h వరకు వీస్తుంది.",
        "mr": "{role}: वारा {wind} km/h पर्यंत पोहोचतो.",
    },
    "warning_unavailable_role": {
        "en": "The IMD warning for the {role} is not available.",
        "hi": "{role}: IMD चेतावनी की जानकारी उपलब्ध नहीं है।",
        "ta": "{role}: IMD எச்சரிக்கை தகவல் கிடைக்கவில்லை.",
        "te": "{role}: IMD హెచ్చరిక సమాచారం అందుబాటులో లేదు.",
        "mr": "{role}: IMD इशाऱ्याची माहिती उपलब्ध नाही.",
    },
    "no_warning_role": {
        "en": "No IMD warning is in force at the {role}.",
        "hi": "{role}: कोई IMD चेतावनी लागू नहीं है।",
        "ta": "{role}: IMD எச்சரிக்கை எதுவும் இல்லை.",
        "te": "{role}: ఏ IMD హెచ్చరికా అమలులో లేదు.",
        "mr": "{role}: कोणताही IMD इशारा लागू नाही.",
    },
    "warning_role": {
        "en": "{article} {colour} IMD warning is in force at the {role}.",
        "hi": "{role}: {colour} IMD चेतावनी लागू है।",
        "ta": "{role}: {colour} IMD எச்சரிக்கை நடைமுறையில் உள்ளது.",
        "te": "{role}: {colour} IMD హెచ్చరిక అమలులో ఉంది.",
        "mr": "{role}: {colour} IMD इशारा लागू आहे.",
    },
    "sea_unknown": {
        "en": "Sea conditions are not in the facts, so the crossing cannot be confirmed; "
              "check the ferry operator.",
        "hi": "समुद्र की स्थिति की जानकारी उपलब्ध नहीं है, इसलिए यात्रा की पुष्टि नहीं की जा "
              "सकती; फ़ेरी संचालक से पूछें।",
        "ta": "கடல் நிலை தகவல் இல்லை, எனவே கடல் பயணத்தை உறுதிசெய்ய முடியாது; படகு "
              "இயக்குநரிடம் கேளுங்கள்.",
        "te": "సముద్ర పరిస్థితుల సమాచారం లేదు, కాబట్టి ప్రయాణాన్ని నిర్ధారించలేము; ఫెర్రీ "
              "నిర్వాహకులను అడగండి.",
        "mr": "समुद्राच्या स्थितीची माहिती उपलब्ध नाही, त्यामुळे प्रवासाची खात्री देता येत "
              "नाही; फेरी चालकाकडे चौकशी करा.",
    },
    "storm_metar_role": {
        "en": "The {role} airport report shows a thunderstorm.",
        "hi": "{role}: हवाई अड्डे की रिपोर्ट में आंधी-तूफ़ान दिख रहा है।",
        "ta": "{role}: விமான நிலைய அறிக்கையில் இடியுடன் கூடிய புயல் காட்டப்படுகிறது.",
        "te": "{role}: విమానాశ్రయ నివేదికలో ఉరుములతో కూడిన తుఫాను కనిపిస్తోంది.",
        "mr": "{role}: विमानतळाच्या अहवालात गडगडाटी वादळ दिसत आहे.",
    },
    "storm_taf_role": {
        "en": "The {role} airport forecast (TAF) shows a thunderstorm on the trip day.",
        "hi": "{role}: हवाई अड्डे के पूर्वानुमान (TAF) में यात्रा के दिन आंधी-तूफ़ान है।",
        "ta": "{role}: விமான நிலைய முன்னறிவிப்பில் (TAF) பயண நாளில் இடியுடன் கூடிய புயல் "
              "உள்ளது.",
        "te": "{role}: విమానాశ్రయ సూచనలో (TAF) ప్రయాణ రోజున ఉరుములతో కూడిన తుఫాను ఉంది.",
        "mr": "{role}: विमानतळाच्या अंदाजात (TAF) प्रवासाच्या दिवशी गडगडाटी वादळ आहे.",
    },
    "wind_too_strong_role": {
        "en": "Wind at the {role} reaches {wind} km/h, too strong for a {mode}.",
        "hi": "{role}: हवा {wind} km/h तक पहुँचती है, जो {mode} के लिए बहुत तेज़ है।",
        "ta": "{role}: காற்று {wind} km/h வரை வீசும், இது {mode} பயணத்துக்கு மிக அதிகம்.",
        "te": "{role}: గాలి {wind} km/h వరకు వీస్తుంది, ఇది {mode} కి చాలా ఎక్కువ.",
        "mr": "{role}: वारा {wind} km/h पर्यंत पोहोचतो, जो {mode} साठी खूप जास्त आहे.",
    },
    # --- farming ------------------------------------------------------------------
    "no_crop_entry": {
        "en": "The crop file has no entry for this crop here.",
        "hi": "फ़सल फ़ाइल में यहाँ इस फ़सल की कोई प्रविष्टि नहीं है।",
        "ta": "பயிர் கோப்பில் இங்கு இந்தப் பயிருக்கான பதிவு இல்லை.",
        "te": "పంట ఫైల్‌లో ఇక్కడ ఈ పంటకు నమోదు లేదు.",
        "mr": "पीक फाइलमध्ये येथे या पिकाची नोंद नाही.",
    },
    "no_temp_range": {
        "en": "The crop file gives no temperature range for this crop.",
        "hi": "फ़सल फ़ाइल में इस फ़सल के लिए तापमान सीमा नहीं दी गई है।",
        "ta": "பயிர் கோப்பில் இந்தப் பயிருக்கான வெப்பநிலை வரம்பு இல்லை.",
        "te": "పంట ఫైల్‌లో ఈ పంటకు ఉష్ణోగ్రత పరిధి ఇవ్వలేదు.",
        "mr": "पीक फाइलमध्ये या पिकासाठी तापमान मर्यादा दिलेली नाही.",
    },
    "no_rain_amount": {
        "en": "The forecast gives no rain amount for {day}.",
        "hi": "पूर्वानुमान में {day} के लिए बारिश की मात्रा नहीं दी गई है।",
        "ta": "{day} நாளுக்கான மழை அளவு முன்னறிவிப்பில் இல்லை.",
        "te": "సూచనలో {day} రోజుకు వర్షపాతం మొత్తం లేదు.",
        "mr": "अंदाजात {day} साठी पावसाचे प्रमाण दिलेले नाही.",
    },
    "forecast_unavailable": {
        "en": "The forecast is not available.",
        "hi": "मौसम पूर्वानुमान उपलब्ध नहीं है।",
        "ta": "வானிலை முன்னறிவிப்பு கிடைக்கவில்லை.",
        "te": "వాతావరణ సూచన అందుబాటులో లేదు.",
        "mr": "हवामान अंदाज उपलब्ध नाही.",
    },
    "out_of_season": {
        "en": "The crop file's sowing months are {months}; this forecast is for {month}.",
        "hi": "फ़सल फ़ाइल के अनुसार बुवाई के महीने {months} हैं; यह पूर्वानुमान {month} का है।",
        "ta": "பயிர் கோப்பின்படி விதைப்பு மாதங்கள் {months}; இந்த முன்னறிவிப்பு {month} "
              "மாதத்துக்கானது.",
        "te": "పంట ఫైల్ ప్రకారం విత్తే నెలలు {months}; ఈ సూచన {month} నెలది.",
        "mr": "पीक फाइलनुसार पेरणीचे महिने {months} आहेत; हा अंदाज {month} चा आहे.",
    },
    "in_season": {
        "en": "The forecast falls within the crop file's sowing months ({months}).",
        "hi": "पूर्वानुमान फ़सल फ़ाइल के बुवाई के महीनों ({months}) के भीतर है।",
        "ta": "முன்னறிவிப்பு பயிர் கோப்பின் விதைப்பு மாதங்களுக்குள் ({months}) உள்ளது.",
        "te": "సూచన పంట ఫైల్‌లోని విత్తే నెలల ({months}) లోపలే ఉంది.",
        "mr": "अंदाज पीक फाइलमधील पेरणीच्या महिन्यांत ({months}) येतो.",
    },
    "no_sowing_months": {
        "en": "The crop file gives no sowing months, so the season was not checked.",
        "hi": "फ़सल फ़ाइल में बुवाई के महीने नहीं दिए गए हैं, इसलिए मौसम की जाँच नहीं हुई।",
        "ta": "பயிர் கோப்பில் விதைப்பு மாதங்கள் இல்லை, எனவே பருவம் சரிபார்க்கப்படவில்லை.",
        "te": "పంట ఫైల్‌లో విత్తే నెలలు ఇవ్వలేదు, కాబట్టి సీజన్ తనిఖీ చేయలేదు.",
        "mr": "पीक फाइलमध्ये पेरणीचे महिने दिलेले नाहीत, त्यामुळे हंगाम तपासला गेला नाही.",
    },
    "heavy_rain": {
        "en": "Heavy rain is forecast {when}: {mm} mm. IMD advises postponing sowing in "
              "heavy rain.",
        "hi": "{when} भारी बारिश का पूर्वानुमान है: {mm} mm। IMD भारी बारिश में बुवाई टालने की "
              "सलाह देता है।",
        "ta": "{when} கனமழை முன்னறிவிக்கப்பட்டுள்ளது: {mm} mm. கனமழையின் போது விதைப்பைத் "
              "தள்ளிவைக்க IMD அறிவுறுத்துகிறது.",
        "te": "{when} భారీ వర్షం సూచన ఉంది: {mm} mm. భారీ వర్షంలో విత్తడం వాయిదా వేయమని IMD "
              "సూచిస్తుంది.",
        "mr": "{when} मुसळधार पावसाचा अंदाज आहे: {mm} mm. मुसळधार पावसात पेरणी पुढे ढकलण्याचा "
              "सल्ला IMD देते.",
    },
    "rain_day": {
        "en": "Rain chance {when} is {pct}% ({mm} mm), with a high of {high}°C and a low of "
              "{low}°C.",
        "hi": "{when} बारिश की संभावना {pct}% ({mm} mm) है, अधिकतम तापमान {high}°C और "
              "न्यूनतम {low}°C।",
        "ta": "{when} மழை வாய்ப்பு {pct}% ({mm} mm), அதிகபட்ச வெப்பநிலை {high}°C, "
              "குறைந்தபட்சம் {low}°C.",
        "te": "{when} వర్షం పడే అవకాశం {pct}% ({mm} mm), గరిష్ఠ ఉష్ణోగ్రత {high}°C, "
              "కనిష్ఠం {low}°C.",
        "mr": "{when} पावसाची शक्यता {pct}% ({mm} mm) आहे, कमाल तापमान {high}°C आणि किमान "
              "{low}°C.",
    },
    "crop_not_reviewed": {
        "en": "The crop thresholds have not yet been reviewed by an agronomist.",
        "hi": "फ़सल की सीमाओं की अभी किसी कृषि विशेषज्ञ ने समीक्षा नहीं की है।",
        "ta": "பயிர் வரம்புகள் இன்னும் வேளாண் நிபுணரால் சரிபார்க்கப்படவில்லை.",
        "te": "పంట పరిమితులను ఇంకా వ్యవసాయ నిపుణులు సమీక్షించలేదు.",
        "mr": "पिकाच्या मर्यादांचे अद्याप कृषी तज्ज्ञांकडून पुनरावलोकन झालेले नाही.",
    },
}

# Words put into the sentences above.
ROLES = {
    "origin": {"en": "origin", "hi": "प्रस्थान स्थान", "ta": "புறப்படும் இடம்",
               "te": "బయలుదేరే చోటు", "mr": "प्रस्थान ठिकाण"},
    "destination": {"en": "destination", "hi": "गंतव्य", "ta": "சேருமிடம்",
                    "te": "గమ్యస్థానం", "mr": "गंतव्य"},
}
COLOURS = {
    "red": {"en": "red", "hi": "लाल", "ta": "சிவப்பு", "te": "ఎరుపు", "mr": "लाल"},
    "orange": {"en": "orange", "hi": "नारंगी", "ta": "ஆரஞ்சு", "te": "నారింజ", "mr": "नारंगी"},
    "yellow": {"en": "yellow", "hi": "पीली", "ta": "மஞ்சள்", "te": "పసుపు", "mr": "पिवळा"},
}
MODES = {
    "flight": {"en": "flight", "hi": "उड़ान", "ta": "விமானம்", "te": "విమానం", "mr": "विमान"},
    "road": {"en": "road", "hi": "सड़क यात्रा", "ta": "சாலைப் பயணம்", "te": "రోడ్డు ప్రయాణం",
             "mr": "रस्ता प्रवास"},
    "train": {"en": "train", "hi": "ट्रेन", "ta": "ரயில்", "te": "రైలు", "mr": "रेल्वे"},
    "ferry": {"en": "ferry", "hi": "फ़ेरी", "ta": "படகு", "te": "ఫెర్రీ", "mr": "फेरी"},
    "any": {"en": "trip", "hi": "यात्रा", "ta": "பயணம்", "te": "ప్రయాణం", "mr": "प्रवास"},
}
MONTHS = {  # keyed by the English month name advisory/crops.py writes
    "hi": "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर",
    "ta": "ஜனவரி பிப்ரவரி மார்ச் ஏப்ரல் மே ஜூன் ஜூலை ஆகஸ்ட் செப்டம்பர் அக்டோபர் நவம்பர் டிசம்பர்",
    "te": "జనవరి ఫిబ్రవరి మార్చి ఏప్రిల్ మే జూన్ జూలై ఆగస్టు సెప్టెంబర్ అక్టోబర్ నవంబర్ డిసెంబర్",
    "mr": "जानेवारी फेब्रुवारी मार्च एप्रिल मे जून जुलै ऑगस्ट सप्टेंबर ऑक्टोबर नोव्हेंबर डिसेंबर",
}
_EN_MONTHS = ("January February March April May June July August September October "
              "November December").split()
AND = {"en": " and ", "hi": " और ", "ta": " மற்றும் ", "te": " మరియు ", "mr": " आणि "}


def lang_or_en(lang: str | None) -> str:
    return lang if lang in LANGS else "en"


def say(key: str, lang: str = "en", **fields) -> str:
    return MESSAGES[key][lang_or_en(lang)].format(**fields)


def _word(table: dict, key: str, lang: str) -> str:
    return table.get(key, {}).get(lang_or_en(lang), key)


def role(name: str, lang: str = "en") -> str:
    return _word(ROLES, name, lang)


def colour(name: str, lang: str = "en") -> str:
    return _word(COLOURS, name, lang)


def mode(name: str, lang: str = "en") -> str:
    return _word(MODES, name, lang)


def month(name: str, lang: str = "en") -> str:
    lang = lang_or_en(lang)
    if lang == "en" or name not in _EN_MONTHS:
        return name
    return MONTHS[lang].split()[_EN_MONTHS.index(name)]


def months(names: list[str], lang: str = "en") -> str:
    return AND[lang_or_en(lang)].join(month(n, lang) for n in names)


def day(label: str | None, lang: str = "en") -> str:
    """A forecast day label ("today", "wednesday") as said in `lang`."""
    lang = lang_or_en(lang)
    if not label:
        return {"en": "one day", "hi": "एक दिन", "ta": "ஒரு நாள்", "te": "ఒక రోజు",
                "mr": "एका दिवसा"}[lang]
    return i18n.DAY_LABELS.get(lang, {}).get(label, label)


def when(label: str, lang: str = "en") -> str:
    """"today" / "tomorrow" / "on Wednesday" — the day as the sentence's time phrase."""
    lang = lang_or_en(lang)
    said = day(label, lang)
    if lang == "en":
        return said if label in ("today", "tomorrow") else f"on {said}"
    if lang == "hi" and label not in ("today", "tomorrow"):
        return f"{said} को"
    return said
