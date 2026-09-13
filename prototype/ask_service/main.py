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

from dataclasses import asdict
from datetime import datetime, timezone

import bhashini
import cities
import config
import guardrail
import history
import httpx
import narrate as narrate_module
import nlu
import router
import weather_data
from auth import get_bearer_token, get_current_user
from config import ALLOWED_ORIGINS, REPO_ROOT
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from google_weather import cache_stats
from i18n import condition_table, render
from narrate import is_configured as llm_configured
from narrate import narrate
from pydantic import BaseModel
from weather_data import get_weather

app = FastAPI(title="WeatherGPT /ask prototype", version="0.0.1")

# The frontend is served from a different origin (http.server) and calls this
# directly — see prototype/README.md "Integration". POST is for /asr and /tts
# (JSON bodies too large/binary for query params), no credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# hi/te/mr strings are first-draft machine translations, not reverse-engineered
# from native usage like the ta strings were. Reviewed by a native speaker —
# confirmed accurate (plan.md §13).
_MESSAGES = {
    "unrecognized": {
        "en": "Sorry, I couldn't understand that request.",
        "ta": "மன்னிக்கவும், அந்தக் கோரிக்கை புரியவில்லை.",
        "hi": "माफ़ कीजिए, मुझे वह अनुरोध समझ नहीं आया।",
        "te": "క్షమించండి, ఆ అభ్యర్థన అర్థం కాలేదు.",
        "mr": "माफ करा, ती विनंती समजली नाही.",
    },
    "unsupported_city": {
        "en": "Sorry, I can only answer for Chennai, Madurai and Coimbatore right now.",
        "ta": "மன்னிக்கவும், இப்போது சென்னை, மதுரை, கோயம்புத்தூர் மட்டுமே.",
        "hi": "माफ़ कीजिए, अभी केवल चेन्नई, मदुरै और कोयंबटूर के लिए बता सकता हूँ।",
        "te": "క్షమించండి, ప్రస్తుతం చెన్నై, మదురై, కోయంబత్తూరు గురించి మాత్రమే చెప్పగలను.",
        "mr": "माफ करा, सध्या फक्त चेन्नई, मदुराई आणि कोईम्बतूरबद्दल सांगू शकतो.",
    },
    "no_city": {
        "en": "Which city? Try Chennai, Madurai or Coimbatore.",
        "ta": "எந்த நகரம்? சென்னை, மதுரை அல்லது கோயம்புத்தூர்.",
        "hi": "कौन सा शहर? चेन्नई, मदुरै या कोयंबटूर आज़माएं।",
        "te": "ఏ నగరం? చెన్నై, మదురై లేదా కోయంబత్తూరు ప్రయత్నించండి.",
        "mr": "कोणते शहर? चेन्नई, मदुराई किंवा कोईम्बतूर वापरून पहा.",
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
        "en": "Sorry, I can only answer current weather, forecasts, rain chances and "
        "rainfall so far — not warnings, alerts or other non-weather questions.",
        "ta": "மன்னிக்கவும், தற்போதைய வானிலை, முன்னறிவிப்பு, மழை வாய்ப்பு, இதுவரை பெய்த "
        "மழை ஆகியவற்றுக்கு மட்டுமே பதிலளிக்க முடியும்.",
        "hi": "माफ़ कीजिए, मैं केवल वर्तमान मौसम, पूर्वानुमान, बारिश की संभावना और अब तक हुई "
        "बारिश के बारे में बता सकता हूँ — चेतावनी, अलर्ट या अन्य गैर-मौसम प्रश्नों के बारे में नहीं।",
        "te": "క్షమించండి, నేను ప్రస్తుత వాతావరణం, సూచన, వర్షం అవకాశం మరియు ఇప్పటివరకు కురిసిన "
        "వర్షం గురించి మాత్రమే సమాధానం ఇవ్వగలను — హెచ్చరికలు, అలర్ట్‌లు లేదా ఇతర "
        "వాతావరణేతర ప్రశ్నలకు కాదు.",
        "mr": "माफ करा, मी फक्त सध्याचे हवामान, अंदाज, पावसाची शक्यता आणि आतापर्यंत झालेला "
        "पाऊस याबद्दलच उत्तर देऊ शकतो — इशारे, सूचना किंवा इतर हवामानाशी संबंधित नसलेल्या "
        "प्रश्नांबद्दल नाही.",
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


def _msg(key: str, lang: str) -> str:
    return _MESSAGES[key].get(lang, _MESSAGES[key]["en"])


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


def _narrate_grounded(intent: str, name: str, data: dict, prompt_facts: dict):
    """Try narration, and once more with feedback if the first answer doesn't
    ground. The guardrail always checks against the FULL facts (`data`), never
    the parameter-trimmed `prompt_facts` sent to the prompt. Returns
    (text|None, report|None, attempted, attempts, provider|None).
    """
    text = narrate(intent, name, prompt_facts, "en")
    if text is None:  # no provider / all failed — nothing to regenerate from
        return None, None, False, 1, None
    provider = narrate_module.last_provider or "llm"
    report = guardrail.check(text, data)
    if report.ok and report.total > 0:
        return text, report, True, 1, provider

    unmatched = [f["reading"] for f in report.figures if not f["matched"]]
    text2 = narrate(intent, name, prompt_facts, "en", feedback=", ".join(unmatched) or None)
    if text2 is not None:
        provider = narrate_module.last_provider or "llm"
        report2 = guardrail.check(text2, data)
        if report2.ok and report2.total > 0:
            return text2, report2, True, 2, provider

    return None, None, True, 2, provider


def _llm_attempt(intent: str, name: str, data: dict, lang: str, prompt_facts: dict):
    """Try LLM narration (EN, with one regenerate-on-ungrounded retry),
    translating via Bhashini if the requested language isn't English (plan.md
    §13: ta/hi/te/mr). Returns (candidate, report, attempted, attempts, provider):
    - candidate/report are set only if the *final* text (post-translation for
      lang != "en") grounds cleanly.
    - attempted is True whenever an LLM sentence was produced at all, even if
      it (or its translation) later failed — used for fallback_used.
    - provider names which chain link produced the (English) text, regardless
      of whether translation later failed.
    """
    if lang != "en" and not bhashini.is_configured():
        return None, None, False, 0, None  # English narration would only be thrown away
    english, eng_report, attempted, attempts, provider = \
        _narrate_grounded(intent, name, data, prompt_facts)
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
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        raise HTTPException(
            status_code=status if status in (401, 403) else 502,
            detail="Could not load history",
        ) from e
    return {"history": rows}


@app.get("/cities")
def list_cities():
    return {"cities": cities.as_public_list()}


class ASRRequest(BaseModel):
    audio: str  # base64 mono 16-bit PCM WAV
    lang: str = "en"
    sampling_rate: int = 16000


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"


@app.post("/asr")
def asr(req: ASRRequest):
    """Voice input: transcribe recorded audio via Bhashini ASR (plan.md §14
    voice track). `text: null` (with a message) on no credentials or failure —
    the frontend falls back to letting the user type."""
    text = bhashini.speech_to_text(req.audio, req.lang, req.sampling_rate)
    if text is None:
        return {"text": None, "message": _msg("voice_unavailable", req.lang)}
    return {"text": text}


@app.post("/tts")
def tts(req: TTSRequest):
    """Answer playback: synthesize `req.text` via Bhashini TTS. `audio: null`
    on no credentials or failure — the frontend just skips playback."""
    audio = bhashini.text_to_speech(req.text, req.lang)
    if audio is None:
        return {"audio": None}
    return {"audio": audio, "format": "wav"}


@app.get("/facts")
def facts(city: str, intent: str = "current_weather", day: str = "today", lang: str = "en"):
    """The raw facts dict behind an answer — for UI surfaces (the hero card) that
    need individual fields rather than the narrated sentence."""
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


@app.get("/ask")
def ask(text: str, lang: str = "en", city: str | None = None,
        token: str | None = Depends(get_bearer_token)):
    pq = nlu.parse(text, lang_hint=lang)
    notice = _msg("language_unsupported", lang) if pq.language is None else None

    if pq.intent in ("unrecognized", "unsupported_city", "out_of_scope"):
        resp = {"intent": pq.intent, "message": _msg(pq.intent, lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
        return resp

    # weather intent: resolve the city from the query, else the explicit param
    key = cities.resolve(pq.city) or cities.resolve(city)
    if key is None:  # §2.3: refuse rather than guess
        resp = {"intent": pq.intent, "message": _msg("no_city", lang), "nlu": pq.as_dict()}
        if notice:
            resp["notice"] = notice
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
        _llm_attempt(pq.intent, name, data, lang, prompt_facts)

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

    if not report.ok:  # §2.3
        resp = {
            "intent": pq.intent,
            "city": key,
            "message": _msg("ungrounded", lang),
            "grounding": grounding,
            "nlu": pq.as_dict(),
        }
        if notice:
            resp["notice"] = notice
        return resp

    resp = {
        "intent": pq.intent,
        "city": key,
        "day": router.legacy_day(pq),
        "response": candidate,
        "provenance": {
            "source": data["source"],
            "issued": data.get("issued"),
            "is_live": data["is_live"],
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
            pass  # best-effort — a broken history write must never break the answer

    return resp


# Serves the frontend on the same origin/tunnel as the API (plan.md §14 host
# pin — one stable ngrok URL instead of a second tunnel, which the free tier
# doesn't support running concurrently). Mounted last so it never shadows the
# API routes above.
_FRONTEND_DIR = REPO_ROOT / "prototype" / "frontend"


@app.get("/")
def _frontend_index():
    return RedirectResponse("/WeatherGPT.dc.html")


app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="frontend")
