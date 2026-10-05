"""`/ask` FastAPI endpoint: intent parse -> weather lookup -> grounded answer.

Flow (plan.md §4): LLM -> narrate ONLY from the typed object -> validator
(every numeric token must exist in the tool response) -> response + provenance,
with a template fallback on validator failure. Narration goes through
narrate.run_chain() (Gemini -> Groq -> Ollama, plan.md §8 Phase 6), which only
ever produces English; the provider that answered is reported via
narrate.last_provider. For any lang != "en" the grounded English sentence is
then translated by Bhashini (plan.md §13: ta/hi/te/mr); if narration,
grounding, or translation fails at any step, main.py falls back to the i18n
template.
"""

import hmac
import math
import re
from dataclasses import asdict
from datetime import datetime, timezone

import alert_engine
import aviation
import bhashini
import cities
import config
import forecast_snapshots
import glossary
import google_weather
import guardrail
import history
import hotlines
import httpx
import i18n
import imd_warnings as warnings_module
import intelligence_cache
import ivr
import limits
import location
import log_redaction
import metar
import metrics
import narrate as narrate_module
import nlu
import occupation as occupation_module
import persona as persona_module
import router
import security_headers
import taf
import weather_data
from advisory import agent as advisory_agent
from advisory import cache as advisory_cache
from advisory import slots as advisory_slots
from auth import get_bearer_token, get_current_user
from config import ALLOWED_ORIGINS, CORS_ALLOW_HEADERS
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from google_weather import FORECAST_DAYS_FETCHED, FORECAST_HOURS, cache_stats
from i18n import SUPPORTED_LANGUAGES, condition_table, render
from narrate import is_configured as llm_configured
from narrate import narrate
from pydantic import BaseModel, Field
from weather_data import daily_forecast, get_weather, hourly_facts, hourly_forecast
from weather_intelligence.change_detector import detect_changes
from weather_intelligence.persona_advisor import CAVEATS, advise, wants_window
from weather_intelligence.scenario_analyzer import compare_scenario
from weather_intelligence.window_analyzer import find_best_window

# Before the app logs anything: scrubs tokens, URLs, phone numbers and
# coordinates from every record in the process, uvicorn's access log
# included (plan.md SEC-N8).
log_redaction.install()

app = FastAPI(title="WeatherGPT Orchestrator", version="0.1.0",
              **security_headers.docs_kwargs())

# The deployed frontend (prototype/frontend on Amplify) calls this from its own
# origin, as does frontend-only local dev — see prototype/README.md
# "Integration". POST is for /asr and /tts (JSON bodies too large/binary for
# query params), no credentials.
config.warn_if_wildcard_cors(ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=CORS_ALLOW_HEADERS,
)
# BodyCap sits inside RequestLimits: the Content-Length check and the rate limit
# answer first, and this counts the body of a request that passed them (a chunked
# upload has no Content-Length to check).
app.add_middleware(limits.BodyCap)
app.add_middleware(limits.RequestLimits)
# Outermost so it also counts the 413s/429s limits.py returns (plan.md §14
# observability track). Route label comes from scope["route"], set once the
# request reaches Starlette's router further in.
app.add_middleware(metrics.HTTPMetrics, service="orchestrator")
# Outermost of all, so the 413s/429s and CORS rejections carry the headers too.
app.add_middleware(security_headers.SecurityHeaders)


# hi/te/mr strings are first-draft machine translations, not reverse-engineered
# from native usage like the ta strings were. The one native-speaker review so
# far (Sep 13, commit fce2ad9; plan.md §13) covered exactly the eight keys this
# dict held then — unrecognized, unsupported_city, no_city, no_data, ungrounded,
# out_of_scope, language_unsupported, voice_unavailable — and their hi/te/mr
# text is unchanged since, so those eight count as reviewed. Any key added or
# any hi/te/mr string edited after fce2ad9 is a first draft and must carry a
# `# TODO: native_qa` marker until a native speaker confirms that exact text
# (same convention as i18n.py and data/i18n/glossary.json's native_qa flags).
_MESSAGES = {
    "unrecognized": {
        "en": "Sorry, I couldn't understand that request.",
        "ta": "மன்னிக்கவும், அந்தக் கோரிக்கை புரியவில்லை.",
        "hi": "माफ़ कीजिए, मुझे वह अनुरोध समझ नहीं आया।",
        "te": "క్షమించండి, ఆ అభ్యర్థన అర్థం కాలేదు.",
        "mr": "माफ करा, ती विनंती समजली नाही.",
    },
    # {cities} is filled in by _msg() from the live cities.CITIES registry
    # (data/cities.json) — was a hardcoded 3-city list (Chennai/Madurai/
    # Coimbatore) that silently went stale once the registry grew to 8; see
    # plan.md. The `and`/`or` before the last name is dropped in favour of a
    # plain comma list so the sentence stays grammatical regardless of how
    # many cities are registered.
    "unsupported_city": {
        "en": "Sorry, I can only answer for {cities} right now.",
        "ta": "மன்னிக்கவும், இப்போது {cities} மட்டுமே.",  # TODO: native_qa
        "hi": "माफ़ कीजिए, अभी केवल {cities} के लिए बता सकता हूँ।",  # TODO: native_qa
        "te": "క్షమించండి, ప్రస్తుతం {cities} గురించి మాత్రమే చెప్పగలను.",  # TODO: native_qa
        "mr": "माफ करा, सध्या फक्त {cities} बद्दल सांगू शकतो.",  # TODO: native_qa
    },
    "no_city": {
        "en": "Which city? Try {cities}.",
        "ta": "எந்த நகரம்? {cities}.",  # TODO: native_qa
        "hi": "कौन सा शहर? {cities} आज़माएं।",  # TODO: native_qa
        "te": "ఏ నగరం? {cities} ప్రయత్నించండి.",  # TODO: native_qa
        "mr": "कोणते शहर? {cities} वापरून पहा.",  # TODO: native_qa
    },
    "no_data": {
        "en": "No weather data available for that city yet.",
        "ta": "அந்த நகரத்திற்கான வானிலை தரவு இன்னும் இல்லை.",
        "hi": "उस शहर के लिए अभी मौसम डेटा उपलब्ध नहीं है।",
        "te": "ఆ నగరానికి ఇంకా వాతావరణ డేటా అందుబాటులో లేదు.",
        "mr": "त्या शहरासाठी अजून हवामान डेटा उपलब्ध नाही.",
    },
    "ungrounded": {
        "en": "Sorry, I couldn't produce a grounded answer for that.",
        "ta": "மன்னிக்கவும், உறுதிப்படுத்தப்பட்ட பதில் தர முடியவில்லை.",
        "hi": "माफ़ कीजिए, इसके लिए पुष्टि किया गया उत्तर नहीं दे सका।",
        "te": "క్షమించండి, దీనికి నిర్ధారించిన సమాధానం ఇవ్వలేకపోయాను.",
        "mr": "माफ करा, यासाठी खात्रीशीर उत्तर देऊ शकलो नाही.",
    },
    "out_of_scope": {
        "en": "Sorry, I can only answer current weather, forecasts, rain chances, rainfall "
        "so far and weather warnings — not cyclone tracks, marine bulletins or other "
        "non-weather questions.",
        "ta": "மன்னிக்கவும், தற்போதைய வானிலை, முன்னறிவிப்பு, மழை வாய்ப்பு, இதுவரை பெய்த "  # TODO: native_qa
        "மழை, வானிலை எச்சரிக்கைகள் ஆகியவற்றுக்கு மட்டுமே பதிலளிக்க முடியும் — புயல் பாதை, "
        "கடல் அறிவிப்புகள் போன்றவற்றுக்கு அல்ல.",
        "hi": "माफ़ कीजिए, मैं केवल वर्तमान मौसम, पूर्वानुमान, बारिश की संभावना, "  # TODO: native_qa
        "अब तक हुई बारिश और मौसम चेतावनियों के बारे में बता सकता हूँ — चक्रवात के मार्ग, "
        "समुद्री बुलेटिन या अन्य गैर-मौसम प्रश्नों के बारे में नहीं।",
        "te": "క్షమించండి, నేను ప్రస్తుత వాతావరణం, సూచన, వర్షం అవకాశం, ఇప్పటివరకు కురిసిన "  # TODO: native_qa
        "వర్షం మరియు వాతావరణ హెచ్చరికల గురించి మాత్రమే సమాధానం ఇవ్వగలను — తుఫాను మార్గం, "
        "సముద్ర బులెటిన్‌లు లేదా ఇతర వాతావరణేతర ప్రశ్నలకు కాదు.",
        "mr": "माफ करा, मी फक्त सध्याचे हवामान, अंदाज, पावसाची शक्यता, आतापर्यंत झालेला "  # TODO: native_qa
        "पाऊस आणि हवामान इशारे याबद्दलच उत्तर देऊ शकतो — चक्रीवादळाचा मार्ग, सागरी बुलेटिन "
        "किंवा इतर हवामानाशी संबंधित नसलेल्या प्रश्नांबद्दल नाही.",
    },
    # Not an all-clear (plan.md §2 principle 3): the feed had no verdict.
    "warnings_unavailable": {
        "en": "Weather warnings aren't available right now — I can't confirm whether an "
        "alert is in force.",
        "ta": "வானிலை எச்சரிக்கைகள் இப்போது கிடைக்கவில்லை — எச்சரிக்கை ஏதும் அமலில் உள்ளதா "  # TODO: native_qa
        "என உறுதிப்படுத்த முடியவில்லை.",
        "hi": "मौसम चेतावनियाँ अभी उपलब्ध नहीं हैं — कोई अलर्ट लागू है या नहीं, यह पुष्टि "  # TODO: native_qa
        "नहीं कर सकता।",
        "te": "వాతావరణ హెచ్చరికలు ప్రస్తుతం అందుబాటులో లేవు — ఏదైనా అలర్ట్ అమలులో ఉందో లేదో "  # TODO: native_qa
        "నిర్ధారించలేను.",
        "mr": "हवामान इशारे सध्या उपलब्ध नाहीत — कोणताही इशारा लागू आहे की नाही "  # TODO: native_qa
        "याची खात्री देऊ शकत नाही.",
    },
    # Not fair weather (plan.md §2 principle 3): no METAR or TAF could be fetched.
    "aviation_unavailable": {
        "en": "Airport weather reports aren't available right now, so I can't give you a "
        "METAR or TAF.",
        "ta": "விமான நிலைய வானிலை அறிக்கைகள் இப்போது கிடைக்கவில்லை.",  # TODO: native_qa
        "hi": "हवाई अड्डे की मौसम रिपोर्ट अभी उपलब्ध नहीं हैं।",  # TODO: native_qa
        "te": "విమానాశ్రయ వాతావరణ నివేదికలు ప్రస్తుతం అందుబాటులో లేవు.",  # TODO: native_qa
        "mr": "विमानतळ हवामान अहवाल सध्या उपलब्ध नाहीत.",  # TODO: native_qa
    },
    # METAR / TAF briefings are English-only (the decoders' fixed templates).
    "aviation_english_only": {
        "en": "Airport reports are shown in English.",
        "ta": "விமான நிலைய அறிக்கைகள் ஆங்கிலத்தில் காட்டப்படுகின்றன.",  # TODO: native_qa
        "hi": "हवाई अड्डे की रिपोर्ट अंग्रेज़ी में दिखाई गई हैं।",  # TODO: native_qa
        "te": "విమానాశ్రయ నివేదికలు ఆంగ్లంలో చూపబడ్డాయి.",  # TODO: native_qa
        "mr": "विमानतळ अहवाल इंग्रजीत दाखवले आहेत.",  # TODO: native_qa
    },
    # WIE-4: no hourly forecast to score at all (the committed snapshots hold 24
    # hours from one fetch, so a fixture-mode "tomorrow" is only its first hours
    # and hourly_facts reports it unavailable; a live fetch holds 48). WIE-8 added the
    # ta/hi/te/mr rows here and the answers themselves in i18n.py.
    "best_window_unavailable": {
        "en": "No hourly forecast is available to find a suitable window right now.",
        "ta": "ஏற்ற நேரத்தைக் கண்டறிய இப்போது மணிநேர முன்னறிவிப்பு கிடைக்கவில்லை.",  # TODO: native_qa
        "hi": "उपयुक्त समय खोजने के लिए अभी घंटेवार पूर्वानुमान उपलब्ध नहीं है।",  # TODO: native_qa
        "te": "అనువైన సమయాన్ని కనుగొనడానికి ప్రస్తుతం గంటవారీ సూచన అందుబాటులో లేదు.",  # TODO: native_qa
        "mr": "योग्य वेळ शोधण्यासाठी सध्या तासावार अंदाज उपलब्ध नाही.",  # TODO: native_qa
    },
    # WIE-11: no earlier forecast stored for these hours (a fresh start, a
    # fixtures-mode demo, a baseline that has aged out).
    "changes_no_baseline": {
        "en": "There is no earlier forecast to compare with yet, so I can't say what has changed.",
        "ta": "ஒப்பிட இன்னும் முந்தைய முன்னறிவிப்பு இல்லை, எனவே என்ன மாறியது என்று சொல்ல "  # TODO: native_qa
        "முடியாது.",
        "hi": "तुलना के लिए अभी कोई पिछला पूर्वानुमान नहीं है, इसलिए क्या बदला है यह नहीं "  # TODO: native_qa
        "बता सकता।",
        "te": "పోల్చడానికి ఇంకా మునుపటి సూచన లేదు, కాబట్టి ఏమి మారిందో చెప్పలేను.",  # TODO: native_qa
        "mr": "तुलना करण्यासाठी अजून आधीचा अंदाज नाही, त्यामुळे काय बदलले ते "  # TODO: native_qa
        "सांगू शकत नाही.",
    },
    "changes_unavailable": {
        "en": "No hourly forecast is available to check for changes right now.",
        "ta": "மாற்றங்களைச் சரிபார்க்க இப்போது மணிநேர முன்னறிவிப்பு கிடைக்கவில்லை.",  # TODO: native_qa
        "hi": "बदलाव जाँचने के लिए अभी घंटेवार पूर्वानुमान उपलब्ध नहीं है।",  # TODO: native_qa
        "te": "మార్పులను తనిఖీ చేయడానికి ప్రస్తుతం గంటవారీ సూచన అందుబాటులో లేదు.",  # TODO: native_qa
        "mr": "बदल तपासण्यासाठी सध्या तासावार अंदाज उपलब्ध नाही.",  # TODO: native_qa
    },
    "language_unsupported": {
        "en": "I couldn't recognise that language yet — answering in English.",
        "ta": "அந்த மொழியை இன்னும் அடையாளம் காண முடியவில்லை — ஆங்கிலத்தில் பதிலளிக்கிறேன்.",
        "hi": "मैं वह भाषा अभी पहचान नहीं पाया — अंग्रेज़ी में उत्तर दे रहा हूँ।",
        "te": "ఆ భాషను ఇంకా గుర్తించలేకపోయాను — ఆంగ్లంలో సమాధానం ఇస్తున్నాను.",
        "mr": "ती भाषा अजून ओळखता आली नाही — इंग्रजीत उत्तर देत आहे.",
    },
    "voice_unavailable": {
        "en": "Voice isn't available right now — try typing your question.",
        "ta": "குரல் இப்போது கிடைக்கவில்லை — தட்டச்சு செய்யவும்.",
        "hi": "आवाज़ अभी उपलब्ध नहीं है — कृपया टाइप करके पूछें।",
        "te": "వాయిస్ ప్రస్తుతం అందుబాటులో లేదు — దయచేసి టైప్ చేయండి.",
        "mr": "आवाज सध्या उपलब्ध नाही — कृपया टाइप करून विचारा.",
    },
}


def _city_list(lang: str) -> str:
    """Plain comma-joined display names, in cities.CITIES registration order
    (== data/cities.json order). Feeds the `{cities}` placeholder in
    _MESSAGES — the single source of truth for which cities are supported,
    so this can't go stale the way the old hardcoded 3-city text did."""
    return ", ".join(
        city.names.get(lang) or city.names["en"] for city in cities.CITIES.values()
    )


def _msg(key: str, lang: str, **fields) -> str:
    if key in i18n.LOCATION_MESSAGES:
        return i18n.location_message(key, lang, **fields)
    template = _MESSAGES[key].get(lang, _MESSAGES[key]["en"])
    return template.format(cities=_city_list(lang), **fields)


_PLACE_ID_RE = re.compile(r"gn:\d{1,12}")


def _checked_point(lat: float | None, lon: float | None) -> None:
    """422 unless the point is both halves, finite and on the globe. A real
    point outside India is not an error: the resolver answers it."""
    if (lat is None) != (lon is None):
        raise HTTPException(status_code=422, detail="give both lat and lon, or neither")
    if lat is None:
        return
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise HTTPException(status_code=422, detail="lat/lon must be finite numbers")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="lat/lon out of range")


def _point(loc: dict) -> dict:
    """All the router, guardrail and provenance ever get of a location."""
    return {"lat": loc["lat"], "lon": loc["lon"], "label": loc["label"]}


def _fetched_place(point: dict) -> dict:
    """The place an answer is for, at the 0.05° point its data was fetched
    for (google_weather.snap) — what provenance and the footer report."""
    return {"label": point["label"], "lat": google_weather.snap(point["lat"]),
            "lon": google_weather.snap(point["lon"])}


def _with_footer(candidate: str, place: dict, lang: str) -> str:
    """Append the provenance footer to an answer the guardrail has ALREADY
    validated. Never call this before guardrail.check(): the footer's
    coordinates are not weather figures and must not be checked as such."""
    return f"{candidate}\n{i18n.place_footer(place['label'], place['lat'], place['lon'], lang)}"


def _public_location(loc: dict) -> dict:
    """The resolved location as /ask reports it: rounded to 2 decimals (~1 km),
    never the raw fix."""
    out = {"label": loc["label"], "source": loc["source"],
           "lat": round(loc["lat"], 2), "lon": round(loc["lon"], 2)}
    if loc.get("place_id"):
        out["place_id"] = loc["place_id"]
    return out


def _location_reply(pq, loc: dict, lang: str, query_place: str | None) -> dict:
    """/ask's answer when the resolver has no single point: which place?,
    not found, India only, or tell me where — never a default city."""
    resp: dict = {"intent": pq.intent, "nlu": pq.as_dict()}
    if loc.get("ambiguous"):
        resp.update(message=_msg("which_place", lang), ambiguous=loc["ambiguous"])
    elif loc.get("outside_india"):
        resp.update(message=_msg("india_only", lang), outside_india=True)
    elif loc.get("not_found"):
        place = query_place or ""
        nearest = loc.get("nearest")
        resp["not_found"] = True
        if nearest:
            resp["nearest"] = nearest
            resp["message"] = _msg("place_not_found", lang, place=place,
                                   nearest=nearest["label"])
        else:
            resp["message"] = _msg("place_not_found_bare", lang, place=place)
    else:
        resp.update(message=_msg("need_location", lang), needs_location=True)
    return resp


def _require_lang(lang: str) -> str:
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"lang must be one of {SUPPORTED_LANGUAGES}")
    return lang


def _provenance(data: dict) -> dict:
    return {
        "source": data["source"],
        "issued": data.get("issued"),
        "is_live": data["is_live"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/livez")
def livez(request: Request):
    """k8s liveness probe: no I/O, just "is the process serving requests".
    Platform-only: a proxied (public) request gets a 404 — see
    security_headers.is_direct()."""
    if not security_headers.is_direct(request):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return {"status": "ok"}


@app.get("/metrics")
def metrics_route(request: Request):
    """Internal only — same contract as the gateway's: `Authorization: Bearer
    $METRICS_TOKEN`, which Prometheus sends via `authorization` in its scrape
    config. With METRICS_TOKEN unset it is disabled (404), never open; the
    orchestrator is public on its own wherever there's no gateway in front
    (Render, the live backend)."""
    if not config.METRICS_TOKEN:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), f"Bearer {config.METRICS_TOKEN}".encode()):
        return JSONResponse({"detail": "unauthorized"}, status_code=401,
                            headers={"WWW-Authenticate": "Bearer"})
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)


@app.get("/health")
def health():
    return {
        "service": "ask",
        "status": "ok",
        "cities": sorted(cities.CITY_KEYS),
        "weather_source": weather_data.source_status(),
        "weather_cache": cache_stats(),
        "narration": "llm" if llm_configured() else "template",
        "llm": {
            "offline_mode": config.OFFLINE_MODE,
            "providers": [name for name, _ in narrate_module.providers()],
            "ollama": narrate_module.ollama_status(),
        },
        "bhashini": "configured" if bhashini.is_configured() else "unconfigured",
        "nlu": "rules+llm" if llm_configured() else "rules",
        "weather_mode": config.WEATHER_MODE,
        "offline_mode": config.OFFLINE_MODE,
    }


def _narrate_grounded(intent: str, name: str, data: dict, prompt_facts: dict,
                       persona: str | None = None):
    """Try narration, and once more with feedback if the first answer doesn't
    ground. The guardrail always checks against the FULL facts (`data`), never
    the parameter-trimmed `prompt_facts` sent to the prompt. Returns
    (text|None, report|None, attempted, attempts, provider|None).
    """
    text = narrate(intent, name, prompt_facts, "en", persona=persona)
    if text is None:  # no provider / all failed — nothing to regenerate from
        return None, None, False, 1, None
    provider = narrate_module.last_provider or "llm"
    report = guardrail.check(text, data)
    if (report.ok and report.total > 0
            and not persona_module.makes_unsafe_claim(persona, text)):
        return text, report, True, 1, provider

    unmatched = [f["reading"] for f in report.figures if not f["matched"]]
    text2 = narrate(intent, name, prompt_facts, "en",
                     feedback=", ".join(unmatched) or None, persona=persona)
    if text2 is not None:
        provider = narrate_module.last_provider or "llm"
        report2 = guardrail.check(text2, data)
        if (report2.ok and report2.total > 0
                and not persona_module.makes_unsafe_claim(persona, text2)):
            return text2, report2, True, 2, provider

    return None, None, True, 2, provider


def _llm_attempt(intent: str, name: str, data: dict, lang: str, prompt_facts: dict,
                  persona: str | None = None):
    """Try LLM narration (EN, with one regenerate-on-ungrounded retry),
    translating via Bhashini if the requested language isn't English (plan.md
    §13: ta/hi/te/mr). Returns (candidate, report, attempted, attempts, provider):
    - candidate/report are set only if the *final* text (post-translation for
      lang != "en") grounds cleanly.
    - attempted is True whenever an LLM sentence was produced at all, even if
      it (or its translation) later failed — used for fallback_used.
    - provider names which chain link produced the (English) text, regardless
      of whether translation later failed.

    `persona` (plan.md §8 Phase 4 P1 item 9) only ever changes narration
    *framing* — passed straight through to narrate()'s prompt, never touches
    `data`/the guardrail, and has no effect on the template fallback below
    (persona.py's docstring: the fallback stays generic by design).
    """
    if lang != "en" and not bhashini.is_configured():
        return None, None, False, 0, None  # English narration would only be thrown away
    english, eng_report, attempted, attempts, provider = \
        _narrate_grounded(intent, name, data, prompt_facts, persona)
    if not english:
        return None, None, attempted, attempts, provider

    if lang == "en":
        return english, eng_report, attempted, attempts, provider

    translated = bhashini.translate(english, lang)
    if not translated:
        return None, None, attempted, attempts, provider  # no credentials / translation failed

    report = guardrail.check(translated, data)
    ok = report.ok and report.total > 0
    return (translated, report, attempted, attempts, provider) if ok \
        else (None, None, attempted, attempts, provider)


@app.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Verifies the Supabase session sent as `Authorization: Bearer <token>`
    and returns the signed-in user. /history below follows the same
    bearer-token pattern, keyed off user["id"] (plan.md §14)."""
    return {"id": user["id"], "email": user.get("email")}


@app.get("/history")
def get_history(token: str | None = Depends(get_bearer_token)):
    """Past /ask queries for the signed-in user, most recent first (plan.md
    §14 Abel track). Reads go straight through Supabase PostgREST with the
    caller's own token — Postgres RLS decides what they can see, so an
    invalid/expired token surfaces as whatever status PostgREST gives it."""
    if token is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        rows = history.list_for_user(token)
    except config.ConfigError as e:
        raise HTTPException(status_code=503, detail="History is not configured") from e
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        raise HTTPException(
            status_code=status if status in (401, 403) else 502,
            detail="Could not load history",
        ) from e
    return {"history": rows}


@app.delete("/history")
async def clear_history(user: dict = Depends(get_current_user),
                        token: str | None = Depends(get_bearer_token)):
    """Erase the signed-in user's history (data-privacy review, plan.md §8
    Phase 6). Verifies the session first so the PostgREST filter is the
    caller's own id; RLS would refuse anything else regardless."""
    try:
        history.clear_for_user(token, user["id"])
    except config.ConfigError as e:
        raise HTTPException(status_code=503, detail="History is not configured") from e
    except httpx.HTTPError as e:  # an error status from Supabase, or no answer from it at all
        raise HTTPException(status_code=502, detail="Could not clear history") from e
    return {"cleared": True}


@app.get("/cities")
def list_cities():
    return {"cities": cities.as_public_list()}


class AlertSubscribeRequest(BaseModel):
    channel: str
    target: str = Field(min_length=1, max_length=2048)
    city_key: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, gt=0)
    lang: str = "en"


@app.post("/alerts/subscribe")
def alerts_subscribe(req: AlertSubscribeRequest):
    """Proactive alerts (plan.md §8 Phase 4): registers a geofence -> push
    subscription for alert_engine.py's poll loop. Exactly one of `city_key`
    or `lat`/`lon`/`radius_km` — see alert_engine.subscribe()'s docstring."""
    _require_lang(req.lang)
    try:
        sub_id, manage_token = alert_engine.subscribe(
            channel=req.channel, target=req.target, city_key=req.city_key,
            lat=req.lat, lon=req.lon, radius_km=req.radius_km, lang=req.lang,
        )
    except alert_engine.SubscriptionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"id": sub_id, "manage_token": manage_token}


@app.delete("/alerts/subscribe/{sub_id}")
def alerts_unsubscribe(sub_id: int, x_manage_token: str | None = Header(default=None)):
    """Needs the manage token returned by POST /alerts/subscribe. A wrong or
    missing token gets the same 404 as an unknown id."""
    if not alert_engine.unsubscribe(sub_id, x_manage_token):
        raise HTTPException(status_code=404, detail="no such subscription")
    return {"deleted": True}


@app.get("/alerts/subscriptions")
def alerts_list(target: str, x_manage_token: str | None = Header(default=None)):
    """Lists the caller's subscriptions for `target`; needs the manage token
    (X-Manage-Token). 404 when nothing matches, so ids can't be probed."""
    subs = alert_engine.list_subscriptions(target, x_manage_token)
    if not subs:
        raise HTTPException(status_code=404, detail="no such subscription")
    return {"subscriptions": subs}


# ~60 s of 16 kHz 16-bit mono PCM is ~1.9 MB raw, ~2.6 MB base64.
MAX_AUDIO_B64_CHARS = 2_800_000
MAX_TTS_CHARS = 500


class ASRRequest(BaseModel):
    audio: str = Field(max_length=MAX_AUDIO_B64_CHARS)  # base64 mono 16-bit PCM WAV
    lang: str = "en"
    sampling_rate: int = Field(default=16000, ge=8000, le=48000)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    lang: str = "en"


@app.post("/asr")
def asr(req: ASRRequest):
    """Voice input: transcribe recorded audio via Bhashini ASR (plan.md §14
    voice track). `text: null` (with a message) on no credentials or failure —
    the frontend falls back to letting the user type."""
    _require_lang(req.lang)
    text = bhashini.speech_to_text(req.audio, req.lang, req.sampling_rate)
    if text is None:
        return {"text": None, "message": _msg("voice_unavailable", req.lang)}
    return {"text": text}


@app.post("/tts")
def tts(req: TTSRequest):
    """Answer playback: synthesize `req.text` via Bhashini TTS. `audio: null`
    on no credentials or failure — the frontend just skips playback."""
    _require_lang(req.lang)
    audio = bhashini.text_to_speech(req.text, req.lang)
    if audio is None:
        return {"audio": None}
    return {"audio": audio, "format": "wav"}


@app.get("/facts")
def facts(city: str, intent: str = "current_weather", day: str = "today", lang: str = "en"):
    """The raw facts dict behind an answer — for UI surfaces (the hero card) that
    need individual fields rather than the narrated sentence. Current
    conditions (current_weather + today) also carry `rain_so_far`: the
    rainfall since local midnight (`rain_so_far_mm`, `since`), or, with no
    hourly history to sum, the last 24 hours' total (`rain_last_24h_mm`),
    each with its IMD `rain_category` and its own provenance. It sits beside
    `facts`, not in it: /ask's guardrail grounds against `facts` alone."""
    _require_lang(lang)
    if intent not in ("current_weather", "will_it_rain") \
            or day not in ("today", "tonight", "tomorrow"):
        raise HTTPException(status_code=422, detail="unknown intent or day")  # §2.3
    key = cities.resolve(city)
    if key is None:
        return {"message": _msg("unsupported_city", lang)}
    data = get_weather(key, intent=intent, day=day)
    if data is None:
        return {"city": key, "message": _msg("no_data", lang)}
    table = condition_table(lang)
    body = {
        "city": key,
        "city_name": cities.display_name(key, lang),
        "condition_label": table.get(data.get("condition"), data.get("condition")),
        "facts": data,
    }
    if intent == "current_weather" and day == "today":
        try:
            rain = weather_data.rain_so_far(key)
        except (KeyError, ValueError, TypeError):  # a malformed history series
            rain = None
        if rain is not None:
            body["rain_so_far"] = rain
    return body


def _series_provenance(data: dict) -> dict:
    return {"source": data["source"], "is_live": data["is_live"], "issued": data["issued"]}


def _known_city(city: str, lang: str) -> str:
    _require_lang(lang)
    key = cities.resolve(city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    return key


@app.get("/forecast/daily")
def forecast_daily(city: str, days: int = FORECAST_DAYS_FETCHED, lang: str = "en"):
    """Up to `days` (1–10) days of the daily forecast as figures, for a day
    list: weather_data.daily_forecast()'s fields plus `condition_label` /
    `night_condition_label` in `lang`. Sunrise and sunset ride on each day.
    `status` is "unavailable" (with `days: []`) when there's no forecast to
    serve. Fixture mode serves the days that were snapshotted (5)."""
    key = _known_city(city, lang)
    if not 1 <= days <= FORECAST_DAYS_FETCHED:
        raise HTTPException(status_code=422, detail=f"days must be 1 to {FORECAST_DAYS_FETCHED}")
    data = daily_forecast(key, days)
    base = {"city": key, "city_name": cities.display_name(key, lang)}
    if data is None:
        return {**base, "status": "unavailable", "days": [], "provenance": None}
    table = condition_table(lang)
    for day in data["days"]:
        for field in ("condition", "night_condition"):
            if field in day:
                day[f"{field}_label"] = table.get(day[field], day[field])
    return {
        **base,
        "status": "ok",
        "days": data["days"],
        "provenance": _series_provenance(data),
    }


@app.get("/forecast/hourly")
def forecast_hourly(city: str, hours: int = FORECAST_HOURS, lang: str = "en"):
    """The next `hours` (1–24) hours of the hourly forecast, for an hourly
    strip: weather_data.hourly_forecast()'s fields plus `condition_label` in
    `lang`. `status` is "unavailable" (with `hours: []`) when there's no
    series to serve."""
    key = _known_city(city, lang)
    if not 1 <= hours <= FORECAST_HOURS:
        raise HTTPException(status_code=422, detail=f"hours must be 1 to {FORECAST_HOURS}")
    data = hourly_forecast(key, hours)
    base = {"city": key, "city_name": cities.display_name(key, lang)}
    if data is None:
        return {**base, "status": "unavailable", "hours": [], "provenance": None}
    table = condition_table(lang)
    for hour in data["hours"]:
        if "condition" in hour:
            hour["condition_label"] = table.get(hour["condition"], hour["condition"])
    return {
        **base,
        "status": "ok",
        "hours": data["hours"],
        "provenance": _series_provenance(data),
    }


@app.get("/hotlines")
def hotlines_route(city: str, lang: str = "en"):
    """Emergency numbers for a city (hotlines.py): 112, then the state's,
    district's and city's own lines, each read off an official page
    (`source_url`) on the `checked` date. Names and notes are English keys
    the apps translate. Unknown city: 404, as /warnings."""
    key = _known_city(city, lang)
    return {"city": key, "city_name": cities.display_name(key, lang), **hotlines.public(key)}


@app.get("/warnings")
def warnings_route(city: str, lang: str = "en"):
    """IMD warning colour code for a city (plan.md §14 Task D) — a stand-in
    fixture feed until the real CAP integration (plan.md §3.3 / Phase 4)
    lands. `status` (imd_warnings.STATUS_*) says whether the feed had a
    verdict at all: with WARNINGS_ENABLED off — the default — it is
    "unavailable" with `warning: null`, which a UI must show as "not
    available", never as an all-clear (plan.md §2 principle 3). Unlike
    /facts, an unknown city is a genuine 404 here: there is no
    partial-answer shape to fall back to for a colour-code banner."""
    _require_lang(lang)
    key = cities.resolve(city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    return {
        "city": key,
        "city_name": cities.display_name(key, lang),
        **warnings_module.public(key, lang),
    }


@app.get("/glossary")
def glossary_route(lang: str = "en"):
    """data/i18n/glossary.json in one language: the warning colour words and
    meanings and the category labels every surface should render from rather
    than carry its own copy (plan.md §3.1). Entries keep their native_qa flag
    so a client can mark unreviewed translations."""
    _require_lang(lang)
    return {"lang": lang, "entries": glossary.entries(lang)}


@app.get("/metar/decode")
def metar_decode(raw: str):
    """Decode a raw METAR/SPECI string into typed fields plus an English
    plain-language briefing (plan.md §6 P2 item 10). Template-rendered, no
    LLM; tokens the decoder doesn't recognise come back in `unparsed`."""
    try:
        decoded = metar.decode(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"decoded": decoded, "briefing": metar.briefing(decoded)}


@app.get("/taf/decode")
def taf_decode(raw: str):
    """The forecast half of /metar/decode: a raw TAF into typed fields (base
    conditions, BECMG / TEMPO / FM / PROB change groups, TX / TN) plus an
    English briefing. Same rules: template-rendered, no LLM, unknown tokens
    come back in `unparsed`."""
    try:
        decoded = taf.decode(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"decoded": decoded, "briefing": taf.briefing(decoded)}


@app.get("/aviation")
def aviation_route(city: str | None = None, station: str | None = None):
    """The current METAR and TAF for a demo city's airport, fetched from
    aviationweather.gov (fixture snapshots when offline), decoded and worded
    by metar.py / taf.py. `status` is "unavailable" when neither report could
    be had — a UI must show that as "not available", never as fair weather
    (plan.md §2 principle 3). Only the demo airports are served: an unknown
    city or station is a 404, and the upstream call is always ours."""
    if not (city or station):
        raise HTTPException(status_code=422, detail="give a city or a station")
    icao = aviation.station_for(station or city)
    if icao is None:
        raise HTTPException(status_code=404, detail="unknown city or station")
    return aviation.public(icao)


def _cached(response: Response, cache_key: str | None, compute) -> dict:
    """WIE-15: an /intelligence/* answer from intelligence_cache, else `compute()`
    — which returns (answer, the hourly facts it used) — stored for the rest of
    that forecast's life. `X-Cache` says which: HIT or MISS."""
    answer = intelligence_cache.get(cache_key)
    if answer is not None:
        response.headers["X-Cache"] = "HIT"
        return answer
    answer, hourly = compute()
    intelligence_cache.put(cache_key, answer, hourly)
    response.headers["X-Cache"] = "MISS"
    return answer


@app.get("/intelligence/best-window")
def intelligence_best_window(response: Response, city: str, day: str = "tomorrow",
                             activity: str = "outdoor"):
    """WIE-3/WIE-13/WIE-14: the best contiguous suitable window in a day's
    hourly forecast, and the values that justify it — deterministic rules
    only (weather_intelligence/rules.py), nothing narrated by an LLM
    (plan.md §2 principle 7). `status`: "ok" (a window exists),
    "no_suitable_window" (every hour was checked and none passed — a real,
    honest negative result, never the least-bad hour), or "unavailable" (no
    hourly forecast to check at all — e.g. "tomorrow" against the committed
    snapshots, whose 24 hours end before tomorrow does; a day is never judged
    from part of its hours)."""
    if day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    key = cities.resolve(city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    return _cached(response, intelligence_cache.key("best-window", key, day, activity=activity),
                   lambda: _best_window_answer(key, day, activity))


def _best_window_answer(key: str, day: str, activity: str) -> tuple[dict, dict | None]:
    hourly = hourly_facts(key, day)
    if hourly is None:
        return {
            "city": key,
            "city_name": cities.display_name(key, "en"),
            "day": day,
            "activity": activity,
            "status": "unavailable",
            "window": None,
            "provenance": None,
        }, None
    window = find_best_window(hourly["hours"], activity)
    return {
        "city": key,
        "city_name": cities.display_name(key, "en"),
        "day": hourly["day"],
        "activity": activity,
        "status": "ok" if window else "no_suitable_window",
        "window": window,
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"]},
    }, hourly


class ScenarioRequest(BaseModel):
    city: str
    day: str = "today"
    times: list[str] = Field(..., min_length=1, max_length=6)
    activity: str = "outdoor"


@app.post("/intelligence/scenario")
def intelligence_scenario(req: ScenarioRequest, response: Response):
    """WIE-6/WIE-13/WIE-14: compares named times of day ("09:00" vs "17:00")
    against the decoded hourly forecast — one hour, or several. Deterministic
    rules only; a time outside the forecast's hours is reported as
    unavailable, never filled in with an invented value."""
    if req.day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    key = cities.resolve(req.city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    cache_key = intelligence_cache.key("scenario", key, req.day, activity=req.activity,
                                       times=req.times)
    return _cached(response, cache_key, lambda: _scenario_answer(key, req))


def _scenario_answer(key: str, req: ScenarioRequest) -> tuple[dict, dict | None]:
    hourly = hourly_facts(key, req.day)
    if hourly is None:
        return {
            "city": key,
            "city_name": cities.display_name(key, "en"),
            "day": req.day,
            "activity": req.activity,
            "status": "unavailable",
            "hours": [{"time": t, "available": False} for t in req.times],
            "better_time": None,
            "provenance": None,
        }, None
    result = compare_scenario(hourly["hours"], req.times, req.activity)
    return {
        "city": key,
        "city_name": cities.display_name(key, "en"),
        "day": hourly["day"],
        "activity": req.activity,
        "status": "ok",
        **result,
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"]},
    }, hourly


class AdvisoryRequest(BaseModel):
    city: str
    persona: str = persona_module.DEFAULT
    day: str = "tomorrow"


@app.post("/intelligence/advisory")
def intelligence_advisory(req: AdvisoryRequest, response: Response):
    """WIE-7: persona-aware framing over the same best-window computation
    (WIE-3) — deterministic rules only, nothing narrated by an LLM, same as
    /intelligence/best-window. farmer, traveller, general and city_official
    get a window verdict (identical numbers across all of them for the same
    facts — only `label` differs, plan.md's WIE-7 done-when); fisherman and
    aviation get the plain hourly forecast and a static caveat instead, no
    window verdict at all (R17: a city forecast has no sea state or
    aerodrome data to back one for either). `status`: "ok" (a window exists,
    or — for fisherman/aviation — the plain forecast exists),
    "no_suitable_window" (every hour was checked and none passed), or
    "unavailable" (no hourly forecast to check at all)."""
    if req.day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    if not persona_module.is_valid(req.persona):
        raise HTTPException(
            status_code=422,
            detail=f"persona must be one of {sorted(persona_module.PERSONAS)}",
        )
    key = cities.resolve(req.city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    return _cached(response, intelligence_cache.key("advisory", key, req.day, persona=req.persona),
                   lambda: _advisory_answer(key, req))


def _advisory_answer(key: str, req: AdvisoryRequest) -> tuple[dict, dict | None]:
    hourly = hourly_facts(key, req.day)
    if hourly is None:
        return {
            "city": key,
            "city_name": cities.display_name(key, "en"),
            "day": req.day,
            "persona": req.persona,
            "status": "unavailable",
            "label": None,
            "window": None,
            "hours": None,
            "caveat": CAVEATS.get(req.persona),
            "provenance": None,
        }, None
    advisory = advise(hourly["hours"], req.persona)
    if wants_window(req.persona):
        status = "ok" if advisory["window"] else "no_suitable_window"
    else:
        status = "ok"
    return {
        "city": key,
        "city_name": cities.display_name(key, "en"),
        "day": hourly["day"],
        "persona": req.persona,
        "status": status,
        "label": advisory["label"],
        "window": advisory["window"],
        "hours": hourly["hours"] if advisory["label"] is None else None,
        "caveat": advisory["caveat"],
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"]},
    }, hourly


def _changes_result(key: str, day: str) -> tuple[dict | None, dict | None, dict | None]:
    """WIE-11: (hourly facts, change result, baseline) for one city/day. The
    baseline is the newest forecast retrieved before the one being compared
    (forecast_snapshots.previous), so the two retrieval times are both known."""
    hourly = hourly_facts(key, day)
    if hourly is None:
        return None, None, None
    cell = google_weather.cell_for(key)
    baseline = (
        forecast_snapshots.previous(cell, hourly["retrieved_at"])
        if cell and hourly.get("retrieved_at") else None
    )
    return hourly, detect_changes(hourly["hours"], baseline), baseline


def _changes_public(key: str, day: str, hourly, result, baseline) -> dict:
    base = {"city": key, "city_name": cities.display_name(key, "en"), "day": day}
    if hourly is None:
        return {**base, "status": "unavailable", "changes": [], "baseline": None,
                "provenance": None}
    return {
        **base,
        "day": hourly["day"],
        "status": result["status"],
        "changes": result["changes"],
        "compared_hours": result["compared_hours"],
        "baseline": (
            {"retrieved_at": baseline["retrieved_at"]}
            if baseline and result["status"] != "no_baseline" else None
        ),
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"],
                       "retrieved_at": hourly["retrieved_at"]},
    }


@app.get("/intelligence/changes")
def intelligence_changes(response: Response, city: str, day: str = "tomorrow"):
    """WIE-11: what changed in a day's hourly forecast since the previous
    retrieval — deterministic rules only (weather_intelligence/
    change_detector.py, thresholds in rules.py), nothing narrated by an LLM.
    `status`: "ok" (one or more figures moved by a reportable amount),
    "no_significant_change" (compared, nothing moved enough), "no_baseline"
    (no earlier forecast for these hours — never reported as "no change"),
    or "unavailable" (no hourly forecast at all)."""
    if day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    key = cities.resolve(city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
    def compute():
        hourly, result, baseline = _changes_result(key, day)
        return _changes_public(key, day, hourly, result, baseline), hourly

    return _cached(response, intelligence_cache.key("changes", key, day), compute)


def _utc_minute(iso: str) -> str:
    return f"{iso[:10]} {iso[11:16]} UTC"


def _changes_text(city_name: str, day: str, result: dict, baseline: dict,
                  current_retrieved_at: str, lang: str = "en") -> str:
    """WIE-11: the forecast_change intent's deterministic sentence (i18n.py,
    WIE-8), built from the detector's structured result — every figure and
    both retrieval times are the engine's own."""
    return i18n.changes_text(
        city_name, day, result, _utc_minute(baseline["retrieved_at"]),
        _utc_minute(forecast_snapshots.normalize_time(current_retrieved_at)), lang,
    )


def _persona_fields(persona, occ: "occupation_module.Resolved | None") -> dict:
    """What an answer echoes about who it was framed for: nothing for the
    default with no occupation given (so existing response shapes don't
    change), else `persona` — "custom" marks unvetted wording — plus the
    occupation as cleaned."""
    if occ is not None:
        return {"persona": occ.key, "occupation": occ.occupation}
    if persona != persona_module.DEFAULT:
        return {"persona": persona}
    return {}


class AdvisoryAsk(BaseModel):
    text: str = Field(default="", max_length=300)
    lang: str = "en"
    slots: dict[str, str] = Field(default_factory=dict, max_length=8)  # from the last turn
    asking: str | None = Field(default=None, max_length=20)


_ADVISORY_DISCLAIMER = {
    "travel": "Awareness only. Check the airline, railway or official source before you travel.",
    "farming": "Check with your local KVK or agriculture office before you sow.",
}


def _carried_slots(kind: str, slots: dict[str, str]) -> dict[str, str]:
    """The slots a client sent back from the last turn, kept only if each is a value we
    could have produced: a registered city key, a known day, a known crop, and for travel
    the optional mode if it is one the slot parser knows. Anything else is dropped and
    asked for again, so no client text reaches the facts or the prompt."""
    keep: dict[str, str] = {}
    for slot in advisory_slots.REQUIRED[kind]:
        value = slots.get(slot)
        if value is None:
            continue
        if slot in ("origin", "destination"):
            ok = cities.resolve(value, travel=True) == value
        elif slot == "district":
            ok = cities.resolve(value) == value
        elif slot == "day":
            ok = value in advisory_slots.DAYS
        else:
            ok = value in advisory_slots.CROPS
        if ok:
            keep[slot] = value
    if kind == advisory_slots.TRAVEL and slots.get("mode") in advisory_slots.MODES:
        keep["mode"] = slots["mode"]  # optional, so not in REQUIRED, but it picks the rule table
    return keep


def _advisory(kind: str, req: AdvisoryAsk, response: Response) -> dict:
    lang = req.lang if req.lang in SUPPORTED_LANGUAGES else "en"
    asking = req.asking if req.asking in advisory_slots.REQUIRED[kind] else None
    parsed = advisory_slots.parse(kind, req.text, have=_carried_slots(kind, req.slots),
                                  asking=asking)
    if not parsed.complete:
        return {"kind": kind, "status": "ask_back",
                "question": advisory_slots.ask_back(parsed, lang), "slots": parsed.slots,
                "asking": parsed.asking, "unsupported": parsed.unsupported}
    asked = {"kind": kind, "status": "ok", "slots": parsed.slots, "assumed": parsed.assumed}
    cache_key = advisory_cache.key(kind, parsed.slots, lang)
    cached = advisory_cache.get(cache_key)  # TFA-20: the same question, already answered
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return {**asked, **cached}
    advice = advisory_agent.advise(kind, parsed.slots, lang)
    answered = {  # what the slots decide; `assumed` is this request's wording, never cached
        "answer": advice.answer,
        "missing": advice.facts.missing(),
        "provenance": advice.facts.provenance(),
        "path": advice.path,
        "fallback_reason": advice.fallback_reason,
        "disclaimer": _ADVISORY_DISCLAIMER[kind],
    }
    advisory_cache.put(cache_key, answered, advice)
    response.headers["X-Cache"] = "MISS"
    return {**asked, **answered}


@app.post("/advisory/travel")
def advisory_travel(req: AdvisoryAsk, response: Response):
    """TFA-17: "can I go from Chennai to Madurai tomorrow". Slots first (a missing one is
    asked for), then the agent, the hard override and the guardrail (advisory/agent.py)."""
    return _advisory("travel", req, response)


@app.post("/advisory/sowing")
def advisory_sowing(req: AdvisoryAsk, response: Response):
    """TFA-17: "when should I sow groundnut in Madurai". Answers `not_available` for every
    crop until the sourced crop file (TFA-9) exists."""
    return _advisory("farming", req, response)


@app.get("/ask")
def ask(text: str, lang: str = "en", city: str | None = None, persona: str = persona_module.DEFAULT,
        occupation: str | None = None, lat: float | None = None,
        lon: float | None = None, place_id: str | None = None,
        token: str | None = Depends(get_bearer_token)):
    """`lat`/`lon`: the device's GPS fix, used when the question names no
    place or says "here". `place_id`: a candidate the user tapped from an
    earlier `ambiguous` reply; it wins over both."""
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    _checked_point(lat, lon)
    if place_id is not None and not _PLACE_ID_RE.fullmatch(place_id):
        raise HTTPException(status_code=422, detail="place_id must look like gn:<digits>")
    if not persona_module.is_valid(persona):
        raise HTTPException(
            status_code=422,
            detail=f"persona must be one of {sorted(persona_module.PERSONAS)}",
        )
    occ = None
    if occupation is not None:
        if persona != persona_module.DEFAULT:
            raise HTTPException(status_code=422, detail="give persona or occupation, not both")
        try:
            occ = occupation_module.resolve(occupation)
        except occupation_module.Rejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        persona = occ.persona
    pq = nlu.parse(text, lang_hint=lang, city_hint=city)
    notice = _msg("language_unsupported", lang) if pq.language is None else None

    if pq.intent in ("unsupported_city", "unrecognized") and place_id:
        # A tapped place: the weather question it was, even if the text alone
        # couldn't say (a name we couldn't place, or just "weather").
        pq.intent = "will_it_rain" if pq.parameter == "rain" else "current_weather"
    if pq.intent in ("unrecognized", "out_of_scope"):
        resp = {"intent": pq.intent, "message": _msg(pq.intent, lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    # One resolver (location.py) for place_id > named place > GPS > ask; the
    # UI's selected city counts as a named place when there is no fix and the
    # question didn't say "here". §2.3: never a default city.
    query_place = None if pq.here else pq.place
    if query_place is None and not pq.here and lat is None:
        query_place = city
    loc = location.resolve_location(query_place, lat, lon, lang, place_id)
    if loc["lat"] is None:
        resp = _location_reply(pq, loc, lang, query_place)
        if notice:
            resp["notice"] = notice
        return resp
    point = _point(loc)
    key = google_weather.point_key(point["lat"], point["lon"])  # a demo key, or "@lat,lon"
    demo_key = key if key in cities.CITY_KEYS else None

    # Offline only the demo cities have saved data (§2 principle 5): a GPS
    # fix is answered for the nearest one, saying so; any other named place
    # is told so rather than answered for a different city (principle 3).
    offline_note = None
    if (config.OFFLINE_MODE or config.WEATHER_MODE == "fixtures") and demo_key is None:
        if loc["source"] != "gps":
            resp = {"intent": pq.intent, "offline": True, "location": _public_location(loc),
                    "message": _msg("offline_demo_only", lang, place=loc["label"],
                                    cities=_city_list(lang)),
                    "nlu": pq.as_dict()}
            if notice:
                resp["notice"] = notice
            return resp
        demo = location.nearest_demo_city(loc["lat"], loc["lon"])
        loc = {"lat": demo.lat, "lon": demo.lon, "label": cities.display_name(demo.key, lang),
               "source": "demo_fixture", "place_id": demo.place_id}
        point, key, demo_key = _point(loc), demo.key, demo.key
        offline_note = _msg("offline_nearest_demo", lang, city=loc["label"])
        notice = f"{notice} {offline_note}" if notice else offline_note

    if pq.intent == "warnings":
        # The /warnings payload (status, warning, legend) inside the /ask
        # envelope. The answer text is the feed's own headline, verbatim
        # (plan.md §2 principle 4): no LLM narration, and no guardrail pass —
        # there are no narrated numbers to check against a facts dict, and the
        # headline is the official category text, not something we generated.
        verdict = warnings_module.public(key, lang)
        warning = verdict["warning"]
        if warning is None:  # feed off or no usable fixture: no verdict, NOT an all-clear
            resp = {"intent": pq.intent, "city": demo_key, "location": _public_location(loc),
                    "message": _msg("warnings_unavailable", lang), **verdict,
                    "nlu": pq.as_dict()}
            if notice:
                resp["notice"] = notice
            return resp

        candidate = warning["headline"]
        # Nothing was narrated or validated, so the report is the empty one a
        # figure-free answer gets; provider/narration say where the text came from.
        grounding = {**asdict(guardrail.Report(ok=True, matched=0, total=0)),
                     "fallback_used": False, "narration": "verbatim", "attempts": 0,
                     "provider": "feed"}
        metrics.observe_ask(intent=pq.intent, lang=lang, provider="feed", narration="verbatim",
                            fallback_used=False, no_llm=True)
        resp = {
            "intent": pq.intent,
            "city": demo_key, "location": _public_location(loc),
            "response": candidate,
            **verdict,
            "provenance": {
                "source": warning["source"],
                "issued_by": warning["issued_by"],
                "valid_from": warning["valid_from"],
                "valid_to": warning["valid_to"],
                "is_live": warning["source"] != "fixture",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice

        if token is not None:
            try:
                history.record(token, query=text, intent=pq.intent, city=demo_key or point["label"],
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as below

        return resp

    if pq.intent == "aviation":
        # The airport's METAR / TAF, worded by metar.py / taf.py's fixed
        # templates: no LLM narration and no guardrail pass, for the same
        # reason as warnings — every figure is a decoded value of the report,
        # nothing is generated. English only; other languages get a notice.
        icao = aviation.station_for(demo_key) if demo_key else None
        result = aviation.public(icao) if icao else None
        want = aviation.want_from_text(text)
        candidate = aviation.answer_text(result, want) if result else None
        if candidate is None:  # no report to show: NOT fair weather
            resp = {"intent": pq.intent, "city": demo_key, "location": _public_location(loc),
                    "message": _msg("aviation_unavailable", lang),
                    "status": "unavailable", "nlu": pq.as_dict()}
            if notice:
                resp["notice"] = notice
            return resp

        parts = [result[k] for k in ("metar", "taf") if result[k] and want in ("both", k)]
        grounding = {**asdict(guardrail.Report(ok=True, matched=0, total=0)),
                     "fallback_used": False, "narration": "verbatim", "attempts": 0,
                     "provider": "feed"}
        metrics.observe_ask(intent=pq.intent, lang=lang, provider="feed", narration="verbatim",
                            fallback_used=False, no_llm=True)
        resp = {
            "intent": pq.intent,
            "city": demo_key, "location": _public_location(loc),
            "response": candidate,
            "status": "ok",
            "aviation": result,
            "provenance": {
                "source": aviation.SOURCE,
                "issued": aviation.issued_iso(parts[0]),
                "is_live": all(p["is_live"] for p in parts),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        elif lang != "en":
            resp["notice"] = _msg("aviation_english_only", lang)
        resp.update(_persona_fields(persona, occ))

        if token is not None:
            try:
                history.record(token, query=text, intent=pq.intent, city=demo_key or point["label"],
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as below

        return resp

    if pq.intent == "best_window":
        # WIE-4: deterministic only, like warnings/aviation above, worded by
        # i18n.py's five-language templates (WIE-8) — no free LLM narration
        # of the window yet; if one is added it must pass
        # guardrail.check(), which grounds clock times and ranges (WIE-5)
        # against `window`. fisherman/aviation personas get no
        # window verdict at all (R17), reusing WIE-7's persona_advisor
        # exactly as GET /intelligence/advisory does — not duplicated here.
        hourly = router.route(pq, point)
        if hourly is None:
            resp = {"intent": pq.intent, "city": demo_key, "location": _public_location(loc),
                    "message": _msg("best_window_unavailable", lang),
                    "status": "unavailable", "nlu": pq.as_dict()}
            if notice:
                resp["notice"] = notice
            return resp

        persona_key = persona_module.key(persona)
        advisory = advise(hourly["hours"], persona_key)
        name = point["label"]  # in the asked language, like every other answer
        if wants_window(persona_key):
            window = advisory["window"]
            status = "ok" if window else "no_suitable_window"
            candidate = (
                i18n.best_window_text(name, hourly["day"], window, lang) if window
                else i18n.no_suitable_window_text(name, hourly["day"], lang)
            )
        else:
            window = None
            status = "ok"
            candidate = i18n.persona_caveat(persona_key, lang)

        grounding = {**asdict(guardrail.Report(ok=True, matched=0, total=0)),
                     "fallback_used": False, "narration": "verbatim", "attempts": 0,
                     "provider": "feed"}
        metrics.observe_ask(intent=pq.intent, lang=lang, provider="feed", narration="verbatim",
                            fallback_used=False, no_llm=True)
        resp = {
            "intent": pq.intent,
            "city": demo_key, "location": _public_location(loc),
            "response": candidate,
            "status": status,
            "label": advisory["label"],
            "window": window,
            "provenance": _provenance(hourly),
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        resp.update(_persona_fields(persona, occ))

        if token is not None:
            try:
                history.record(token, query=text, intent=pq.intent, city=demo_key or point["label"],
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as above

        return resp

    if pq.intent == "forecast_change":
        # WIE-11: deterministic only, like best_window above — the detector's
        # figures and both retrieval times are the whole answer, no LLM
        # narration. "no baseline" is its own honest answer, never "no change".
        key = google_weather.point_key(point["lat"], point["lon"])
        day = "tomorrow" if pq.time_window == "tomorrow" else "today"
        hourly, result, baseline = _changes_result(key, day)
        if hourly is None or result["status"] == "no_baseline":
            resp = {"intent": pq.intent, "city": demo_key, "location": _public_location(loc),
                    "message": _msg("changes_unavailable" if hourly is None
                                    else "changes_no_baseline", lang),
                    "status": "unavailable" if hourly is None else "no_baseline",
                    "nlu": pq.as_dict()}
            if hourly is not None:
                resp["provenance"] = _provenance(hourly)
            if notice:
                resp["notice"] = notice
            return resp

        candidate = _changes_text(point["label"], hourly["day"], result, baseline,
                                  hourly["retrieved_at"], lang)
        grounding = {**asdict(guardrail.Report(ok=True, matched=0, total=0)),
                     "fallback_used": False, "narration": "verbatim", "attempts": 0,
                     "provider": "feed"}
        metrics.observe_ask(intent=pq.intent, lang=lang, provider="feed", narration="verbatim",
                            fallback_used=False, no_llm=True)
        resp = {
            "intent": pq.intent,
            "city": demo_key, "location": _public_location(loc),
            "response": candidate,
            "status": result["status"],
            "changes": result["changes"],
            "baseline": {"retrieved_at": baseline["retrieved_at"]},
            "provenance": _provenance(hourly),
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        resp.update(_persona_fields(persona, occ))

        if token is not None:
            try:
                history.record(token, query=text, intent=pq.intent, city=demo_key or point["label"],
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as above

        return resp

    data = router.route(pq, point)
    if data is None:
        resp = {"intent": pq.intent, "city": demo_key, "location": _public_location(loc),
                "message": _msg("no_data", lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    name = point["label"]
    prompt_facts = router.narration_facts(data, pq.parameter)

    candidate, report, attempted, attempts, provider = \
        _llm_attempt(pq.intent, name, data, lang, prompt_facts, persona)

    if candidate:
        narration = "llm+bhashini" if lang != "en" else "llm"
        fallback_used = False
    else:  # §4: no LLM answer, ungrounded, or translation failed -> template
        narration = "template"
        fallback_used = attempted
        provider = "template"
        candidate = render(pq.intent, name, data, lang)
        report = guardrail.check(candidate, data)

    grounding = {**asdict(report), "fallback_used": fallback_used, "narration": narration,
                 "attempts": attempts, "provider": provider}
    metrics.observe_ask(intent=pq.intent, lang=lang, provider=provider, narration=narration,
                        fallback_used=fallback_used, no_llm=not attempted)

    place = _fetched_place(point)
    if not report.ok:  # §2.3
        resp = {
            "intent": pq.intent,
            "city": demo_key, "location": _public_location(loc),
            "message": _msg("ungrounded", lang),
            "provenance": {**_provenance(data), "place": place},
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        resp.update(_persona_fields(persona, occ))
        return resp

    resp = {
        "intent": pq.intent,
        "city": demo_key, "location": _public_location(loc),
        "day": router.legacy_day(pq),
        # After the guardrail (above): the offline note and the footer are ours,
        # not narrated weather, so neither is validated as figures.
        "response": _with_footer(f"{candidate}\n{offline_note}" if offline_note else candidate,
                                 place, lang),
        "provenance": {**_provenance(data), "place": place},
        "grounding": grounding,
        "nlu": pq.as_dict(),
    }
    if offline_note:
        resp["offline"] = True
    if notice:
        resp["notice"] = notice
    resp.update(_persona_fields(persona, occ))

    if token is not None:
        try:
            history.record(token, query=text, intent=pq.intent, city=demo_key or point["label"],
                            lang=lang, response=resp["response"])
        except Exception:
            pass  # best-effort — a broken history write must never break the answer

    return resp


ivr.mount(app, ask, _msg)
alert_engine.ensure_worker()

# Serves the frontend on the same origin/tunnel as the API (plan.md §14 host
# pin — one stable ngrok URL instead of a second tunnel, which the free tier
# doesn't support running concurrently). Opt-in via FRONTEND_DIR (config.py):
# unset — a bare `uvicorn main:app` — is API-only, and `/` just points at
# /health and /docs. Mounted last so it never shadows the API routes above.
if config.FRONTEND_DIR is None:
    @app.get("/")
    def _api_index():
        return {"service": app.title, "health": "/health",
                "docs": "/docs" if security_headers.DOCS_ENABLED else None}
else:
    @app.get("/")
    def _frontend_index():
        return RedirectResponse("/WeatherGPT.dc.html")

    # check_dir=False: a FRONTEND_DIR missing from the image must still boot —
    # StaticFiles otherwise raises at import and crash-loops the pod.
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, check_dir=False),
              name="frontend")
