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
import weather_data
from config import ALLOWED_ORIGINS, GEMINI_API_KEY, GEMINI_MODEL
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google_weather import cache_stats
from i18n import render
from intent import parse_intent
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
    }


def _llm_attempt(intent: str, name: str, data: dict, lang: str):
    """Try LLM narration (EN), translating to TA via Bhashini if that's the
    requested language. Returns (candidate, report, attempted):
    - candidate/report are set only if the *final* text (post-translation for
      ta) grounds cleanly.
    - attempted is True whenever an LLM sentence was produced at all, even if
      it (or its translation) later failed — used for fallback_used.
    """
    english = narrate(intent, name, data, "en")
    if not english:
        return None, None, False

    if lang != "ta":
        report = guardrail.check(english, data)
        ok = report.ok and report.total > 0
        return (english, report, True) if ok else (None, None, True)

    eng_report = guardrail.check(english, data)
    if not (eng_report.ok and eng_report.total > 0):
        return None, None, True  # ungrounded English answer, don't bother translating

    tamil = bhashini.translate_to_tamil(english)
    if not tamil:
        return None, None, True  # no credentials / translation failed

    report = guardrail.check(tamil, data)
    ok = report.ok and report.total > 0
    return (tamil, report, True) if ok else (None, None, True)


@app.get("/cities")
def list_cities():
    return {"cities": cities.as_public_list()}


@app.get("/ask")
def ask(text: str, lang: str = "en", city: str | None = None):
    parsed = parse_intent(text)
    intent, day = parsed["intent"], parsed["day"]

    if intent == "unrecognized":
        return {"intent": intent, "message": _msg("unrecognized", lang)}
    if intent == "unsupported_city":
        return {"intent": intent, "message": _msg("unsupported_city", lang)}

    # weather intent: resolve the city from the query, else the explicit param
    key = cities.resolve(parsed["city"]) or cities.resolve(city)
    if key is None:  # §2.3: refuse rather than guess
        return {"intent": intent, "message": _msg("no_city", lang)}

    data = get_weather(key, intent=intent, day=day)
    if data is None:
        return {"intent": intent, "city": key, "message": _msg("no_data", lang)}

    name = cities.display_name(key, lang)

    candidate, report, attempted = _llm_attempt(intent, name, data, lang)

    if candidate:
        narration = "llm+bhashini" if lang == "ta" else "llm"
        fallback_used = False
    else:  # §4: no LLM answer, ungrounded, or translation failed -> template
        narration = "template"
        fallback_used = attempted
        candidate = render(intent, name, data, lang)
        report = guardrail.check(candidate, data)

    grounding = {**asdict(report), "fallback_used": fallback_used, "narration": narration}

    if not report.ok:  # §2.3
        return {
            "intent": intent,
            "city": key,
            "message": _msg("ungrounded", lang),
            "grounding": grounding,
        }

    return {
        "intent": intent,
        "city": key,
        "day": day,
        "response": candidate,
        "provenance": {
            "source": data["source"],
            "issued": data.get("issued"),
            "is_live": data["is_live"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "grounding": grounding,
    }
