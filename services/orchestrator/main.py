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
from dataclasses import asdict
from datetime import datetime, timezone

import alert_engine
import aviation
import bhashini
import cities
import config
import glossary
import guardrail
import history
import httpx
import imd_warnings as warnings_module
import ivr
import limits
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
from auth import get_bearer_token, get_current_user
from config import ALLOWED_ORIGINS, CORS_ALLOW_HEADERS
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from google_weather import cache_stats
from i18n import SUPPORTED_LANGUAGES, condition_table, render
from narrate import is_configured as llm_configured
from narrate import narrate
from pydantic import BaseModel, Field
from weather_data import get_weather, hourly_facts
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
    # WIE-4: no hourly forecast to score at all (fixtures hold one day; a
    # fixture-mode "tomorrow" request genuinely has none). English only for
    # now — the five-language versions of best_window's three answer shapes
    # (ok / no_suitable_window / unavailable) are WIE-8's job (plan.md §8
    # Phase 9); _msg() falls back to this "en" entry for every other
    # language until then, same as any key missing a language row.
    "best_window_unavailable": {
        "en": "No hourly forecast is available to find a suitable window right now.",
    },
    # best_window's sentence is a deterministic template built straight from
    # the engine's result (never free LLM narration — see main.py's
    # best_window branch), so it is English-only like aviation's reports.
    "best_window_english_only": {
        "en": "The best-time answer is shown in English.",
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


def _msg(key: str, lang: str) -> str:
    template = _MESSAGES[key].get(lang, _MESSAGES[key]["en"])
    return template.format(cities=_city_list(lang))


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
    except httpx.HTTPStatusError as e:
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
    need individual fields rather than the narrated sentence."""
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
    return {
        "city": key,
        "city_name": cities.display_name(key, lang),
        "condition_label": table.get(data.get("condition"), data.get("condition")),
        "facts": data,
    }


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


@app.get("/intelligence/best-window")
def intelligence_best_window(city: str, day: str = "tomorrow", activity: str = "outdoor"):
    """WIE-3/WIE-13/WIE-14: the best contiguous suitable window in a day's
    hourly forecast, and the values that justify it — deterministic rules
    only (weather_intelligence/rules.py), nothing narrated by an LLM
    (plan.md §2 principle 7). `status`: "ok" (a window exists),
    "no_suitable_window" (every hour was checked and none passed — a real,
    honest negative result, never the least-bad hour), or "unavailable" (no
    hourly forecast to check at all — e.g. "tomorrow" against the committed
    fixtures, which only snapshot a single day's hourly series)."""
    if day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    key = cities.resolve(city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
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
        }
    window = find_best_window(hourly["hours"], activity)
    return {
        "city": key,
        "city_name": cities.display_name(key, "en"),
        "day": hourly["day"],
        "activity": activity,
        "status": "ok" if window else "no_suitable_window",
        "window": window,
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"]},
    }


class ScenarioRequest(BaseModel):
    city: str
    day: str = "today"
    times: list[str] = Field(..., min_length=1, max_length=6)
    activity: str = "outdoor"


@app.post("/intelligence/scenario")
def intelligence_scenario(req: ScenarioRequest):
    """WIE-6/WIE-13/WIE-14: compares named times of day ("09:00" vs "17:00")
    against the decoded hourly forecast — one hour, or several. Deterministic
    rules only; a time outside the forecast's hours is reported as
    unavailable, never filled in with an invented value."""
    if req.day not in ("today", "tomorrow"):
        raise HTTPException(status_code=422, detail="day must be today or tomorrow")
    key = cities.resolve(req.city)
    if key is None:
        raise HTTPException(status_code=404, detail="unknown city")
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
        }
    result = compare_scenario(hourly["hours"], req.times, req.activity)
    return {
        "city": key,
        "city_name": cities.display_name(key, "en"),
        "day": hourly["day"],
        "activity": req.activity,
        "status": "ok",
        **result,
        "provenance": {"source": hourly["source"], "is_live": hourly["is_live"]},
    }


class AdvisoryRequest(BaseModel):
    city: str
    persona: str = persona_module.DEFAULT
    day: str = "tomorrow"


@app.post("/intelligence/advisory")
def intelligence_advisory(req: AdvisoryRequest):
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
        }
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
    }


def _best_window_text(city_name: str, day: str, window: dict) -> str:
    """WIE-4: the best_window intent's deterministic English sentence, built
    straight from the engine's structured result (window_analyzer via
    persona_advisor.advise()) — never from free LLM narration. The guardrail
    does now ground clock times and ranges (WIE-5), and this very sentence
    passes it (tests/test_guardrail.py), but an LLM-worded window waits on the
    five-language templates (WIE-8) and WIE-16's live check; every word and
    figure here is the engine's own, the same choice as warnings' verbatim
    headline and aviation's METAR/TAF templates."""
    day_phrase = "tomorrow" if day == "tomorrow" else "today"
    return (
        f"{city_name}: the most suitable window to be outdoors {day_phrase} is "
        f"{window['start_local']}–{window['end_local']} "
        f"(around {window['avg_temp_c']}°C, up to {window['max_rain_probability_pct']}% "
        f"chance of rain, winds up to {window['max_wind_kmh']} km/h)."
    )


def _no_suitable_window_text(city_name: str, day: str) -> str:
    """WIE-4: "no suitable window" is a valid, honest answer (R17) — never
    replaced by the least-bad hour."""
    day_phrase = "tomorrow" if day == "tomorrow" else "today"
    return (
        f"{city_name}: no suitable window to be outdoors {day_phrase} — every hour had "
        f"too much rain, heat, cold or wind."
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


@app.get("/ask")
def ask(text: str, lang: str = "en", city: str | None = None, persona: str = persona_module.DEFAULT,
        occupation: str | None = None, token: str | None = Depends(get_bearer_token)):
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
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

    if pq.intent in ("unrecognized", "unsupported_city", "out_of_scope"):
        resp = {"intent": pq.intent, "message": _msg(pq.intent, lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    # weather or warnings intent: resolve the city from the query, else the explicit param
    key = cities.resolve(pq.city) or cities.resolve(city)
    if key is None:  # §2.3: refuse rather than guess
        resp = {"intent": pq.intent, "message": _msg("no_city", lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    if pq.intent == "warnings":
        # The /warnings payload (status, warning, legend) inside the /ask
        # envelope. The answer text is the feed's own headline, verbatim
        # (plan.md §2 principle 4): no LLM narration, and no guardrail pass —
        # there are no narrated numbers to check against a facts dict, and the
        # headline is the official category text, not something we generated.
        verdict = warnings_module.public(key, lang)
        warning = verdict["warning"]
        if warning is None:  # feed off or no usable fixture: no verdict, NOT an all-clear
            resp = {"intent": pq.intent, "city": key,
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
            "city": key,
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
                history.record(token, query=text, intent=pq.intent, city=key,
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as below

        return resp

    if pq.intent == "aviation":
        # The airport's METAR / TAF, worded by metar.py / taf.py's fixed
        # templates: no LLM narration and no guardrail pass, for the same
        # reason as warnings — every figure is a decoded value of the report,
        # nothing is generated. English only; other languages get a notice.
        icao = aviation.station_for(key)
        result = aviation.public(icao)
        want = aviation.want_from_text(text)
        candidate = aviation.answer_text(result, want)
        if candidate is None:  # no report to show: NOT fair weather
            resp = {"intent": pq.intent, "city": key,
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
            "city": key,
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
                history.record(token, query=text, intent=pq.intent, city=key,
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as below

        return resp

    if pq.intent == "best_window":
        # WIE-4: deterministic only, like warnings/aviation above — no free
        # LLM narration of the window yet; if one is added it must pass
        # guardrail.check(), which grounds clock times and ranges (WIE-5)
        # against `window`. fisherman/aviation personas get no
        # window verdict at all (R17), reusing WIE-7's persona_advisor
        # exactly as GET /intelligence/advisory does — not duplicated here.
        hourly = router.route(pq, key)
        if hourly is None:
            resp = {"intent": pq.intent, "city": key,
                    "message": _msg("best_window_unavailable", lang),
                    "status": "unavailable", "nlu": pq.as_dict()}
            if notice:
                resp["notice"] = notice
            return resp

        persona_key = persona_module.key(persona)
        advisory = advise(hourly["hours"], persona_key)
        name = cities.display_name(key, "en")
        if wants_window(persona_key):
            window = advisory["window"]
            status = "ok" if window else "no_suitable_window"
            candidate = (
                _best_window_text(name, hourly["day"], window) if window
                else _no_suitable_window_text(name, hourly["day"])
            )
        else:
            window = None
            status = "ok"
            candidate = advisory["caveat"]

        grounding = {**asdict(guardrail.Report(ok=True, matched=0, total=0)),
                     "fallback_used": False, "narration": "verbatim", "attempts": 0,
                     "provider": "feed"}
        metrics.observe_ask(intent=pq.intent, lang=lang, provider="feed", narration="verbatim",
                            fallback_used=False, no_llm=True)
        resp = {
            "intent": pq.intent,
            "city": key,
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
        elif lang != "en":
            resp["notice"] = _msg("best_window_english_only", lang)
        resp.update(_persona_fields(persona, occ))

        if token is not None:
            try:
                history.record(token, query=text, intent=pq.intent, city=key,
                                lang=lang, response=candidate)
            except Exception:
                pass  # best-effort, as above

        return resp

    data = router.route(pq, key)
    if data is None:
        resp = {"intent": pq.intent, "city": key, "message": _msg("no_data", lang),
                "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    name = cities.display_name(key, lang)
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

    if not report.ok:  # §2.3
        resp = {
            "intent": pq.intent,
            "city": key,
            "message": _msg("ungrounded", lang),
            "provenance": _provenance(data),
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        resp.update(_persona_fields(persona, occ))
        return resp

    resp = {
        "intent": pq.intent,
        "city": key,
        "day": router.legacy_day(pq),
        "response": candidate,
        "provenance": _provenance(data),
        "grounding": grounding,
        "nlu": pq.as_dict(),
    }
    if notice:
        resp["notice"] = notice
    resp.update(_persona_fields(persona, occ))

    if token is not None:
        try:
            history.record(token, query=text, intent=pq.intent, city=key,
                            lang=lang, response=candidate)
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
