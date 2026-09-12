"""`/ask` FastAPI endpoint: intent parse -> weather lookup -> grounded answer.

Flow (plan.md §4): LLM -> narrate ONLY from the typed object -> validator
(every numeric token must exist in the tool response) -> response + provenance,
with a template fallback on validator failure. Narration is Gemini via
narrate(), which only ever produces English. For lang="ta" the grounded
English sentence is then translated by Bhashini; if narration, grounding, or
translation fails at any step, main.py falls back to the i18n template.
"""

from dataclasses import asdict
from datetime import datetime, timezone

import bhashini
import cities
import guardrail
import nlu
import router
import weather_data
from config import ALLOWED_ORIGINS, GEMINI_API_KEY, GEMINI_MODEL
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google_weather import cache_stats
from i18n import CONDITION_EN, CONDITION_TA, render
from narrate import is_configured as llm_configured
from narrate import narrate
from weather_data import get_weather

app = FastAPI(title="WeatherGPT /ask prototype", version="0.0.1")

# The frontend is served from a different origin (http.server) and calls this
# directly — see prototype/README.md "Integration". GET-only, no credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


_MESSAGES = {
    "unrecognized": {
        "en": "Sorry, I couldn't understand that request.",
        "ta": "மன்னிக்கவும், அந்தக் கோரிக்கை புரியவில்லை.",
    },
    "unsupported_city": {
        "en": "Sorry, I can only answer for Chennai, Madurai and Coimbatore right now.",
        "ta": "மன்னிக்கவும், இப்போது சென்னை, மதுரை, கோயம்புத்தூர் மட்டுமே.",
    },
    "no_city": {
        "en": "Which city? Try Chennai, Madurai or Coimbatore.",
        "ta": "எந்த நகரம்? சென்னை, மதுரை அல்லது கோயம்புத்தூர்.",
    },
    "no_data": {
        "en": "No weather data available for that city yet.",
        "ta": "அந்த நகரத்திற்கான வானிலை தரவு இன்னும் இல்லை.",
    },
    "ungrounded": {
        "en": "Sorry, I couldn't produce a grounded answer for that.",
        "ta": "மன்னிக்கவும், உறுதிப்படுத்தப்பட்ட பதில் தர முடியவில்லை.",
    },
    "out_of_scope": {
        "en": "Sorry, I can only answer current weather, forecasts, rain chances and "
        "rainfall so far — not warnings, alerts or other non-weather questions.",
        "ta": "மன்னிக்கவும், தற்போதைய வானிலை, முன்னறிவிப்பு, மழை வாய்ப்பு, இதுவரை பெய்த "
        "மழை ஆகியவற்றுக்கு மட்டுமே பதிலளிக்க முடியும்.",
    },
    "language_unsupported": {
        "en": "I couldn't recognise that language yet — answering in English.",
        "ta": "அந்த மொழியை இன்னும் அடையாளம் காண முடியவில்லை — ஆங்கிலத்தில் பதிலளிக்கிறேன்.",
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
        "narration": f"gemini:{GEMINI_MODEL}" if llm_configured() else "template",
        "llm": GEMINI_MODEL if GEMINI_API_KEY else "unconfigured",
        "bhashini": "configured" if bhashini.is_configured() else "unconfigured",
        "nlu": "rules+llm" if llm_configured() else "rules",
    }


def _narrate_grounded(intent: str, name: str, data: dict, prompt_facts: dict):
    """Try narration, and once more with feedback if the first answer doesn't
    ground. The guardrail always checks against the FULL facts (`data`), never
    the parameter-trimmed `prompt_facts` sent to the prompt. Returns
    (text|None, report|None, attempted, attempts).
    """
    text = narrate(intent, name, prompt_facts, "en")
    if text is None:  # no provider / all failed — nothing to regenerate from
        return None, None, False, 1
    report = guardrail.check(text, data)
    if report.ok and report.total > 0:
        return text, report, True, 1

    unmatched = [f["reading"] for f in report.figures if not f["matched"]]
    text2 = narrate(intent, name, prompt_facts, "en", feedback=", ".join(unmatched) or None)
    if text2 is not None:
        report2 = guardrail.check(text2, data)
        if report2.ok and report2.total > 0:
            return text2, report2, True, 2

    return None, None, True, 2


def _llm_attempt(intent: str, name: str, data: dict, lang: str, prompt_facts: dict):
    """Try LLM narration (EN, with one regenerate-on-ungrounded retry),
    translating to TA via Bhashini if that's the requested language. Returns
    (candidate, report, attempted, attempts):
    - candidate/report are set only if the *final* text (post-translation for
      ta) grounds cleanly.
    - attempted is True whenever an LLM sentence was produced at all, even if
      it (or its translation) later failed — used for fallback_used.
    """
    english, eng_report, attempted, attempts = _narrate_grounded(intent, name, data, prompt_facts)
    if not english:
        return None, None, attempted, attempts

    if lang != "ta":
        return english, eng_report, attempted, attempts

    tamil = bhashini.translate_to_tamil(english)
    if not tamil:
        return None, None, attempted, attempts  # no credentials / translation failed

    report = guardrail.check(tamil, data)
    ok = report.ok and report.total > 0
    return (tamil, report, attempted, attempts) if ok else (None, None, attempted, attempts)


@app.get("/cities")
def list_cities():
    return {"cities": cities.as_public_list()}


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
    table = CONDITION_TA if lang == "ta" else CONDITION_EN
    return {
        "city": key,
        "city_name": cities.display_name(key, lang),
        "condition_label": table.get(data.get("condition"), data.get("condition")),
        "facts": data,
    }


@app.get("/ask")
def ask(text: str, lang: str = "en", city: str | None = None):
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

    candidate, report, attempted, attempts = _llm_attempt(pq.intent, name, data, lang, prompt_facts)

    if candidate:
        narration = "llm+bhashini" if lang == "ta" else "llm"
        fallback_used = False
    else:  # §4: no LLM answer, ungrounded, or translation failed -> template
        narration = "template"
        fallback_used = attempted
        candidate = render(pq.intent, name, data, lang)
        report = guardrail.check(candidate, data)

    grounding = {**asdict(report), "fallback_used": fallback_used, "narration": narration,
                 "attempts": attempts}

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
    return resp
