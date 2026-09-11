"""Gemini narration for /ask: turn the facts dict into one grounded sentence.

The guardrail still validates whatever this returns; on any failure — no key,
non-English, timeout, HTTP error, empty response — narrate() returns None and
main.py falls back to the i18n template (which covers Tamil). English only for
now.
"""

import json
import logging
import re

import config
import httpx

TIMEOUT = 10.0
MAX_CHARS = 240
_SKIP = ("source", "issued", "is_live", "day")
_LOG = logging.getLogger("weathergpt.narrate")

_PROMPT = (
    "You are WeatherGPT, answering for farmers and fishers in Tamil Nadu. "
    'Write ONE plain-English sentence, max 25 words, starting with "{city}:". '
    "Use ONLY the facts below, and include every number that is present. Each "
    "number must appear verbatim with its unit (°C, %, km/h); do not round or "
    "invent ranges, times, dates or places. Write naturally — never mention the "
    "field names (temp_c, humidity_pct, ...). No markdown, no preamble.\n"
    "Intent: {intent}\nFacts: {facts}"
)


def is_configured() -> bool:
    return bool(config.GEMINI_API_KEY)


def build_prompt(intent: str, city: str, facts: dict) -> str:
    trimmed = {k: v for k, v in facts.items() if k not in _SKIP}
    return _PROMPT.format(city=city, intent=intent,
                          facts=json.dumps(trimmed, ensure_ascii=False, sort_keys=True))


def generate(prompt: str, *, model: str, key: str, timeout: float = TIMEOUT) -> str | None:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 200,
            "candidateCount": 1,
            "thinkingConfig": {"thinkingBudget": 0},  # flash is a thinking model; a
        },                                            # reasoning budget starves the answer
    }
    resp = httpx.post(
        f"{config.GEMINI_BASE}/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates") or []
    if not candidates or candidates[0].get("finishReason") not in (None, "STOP"):
        return None
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    return text or None


def _sanitize(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"```[a-z]*|`", "", text)
    text = " ".join(text.split())
    text = text.split("\n", 1)[0].strip()
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        text = cut[: cut.rfind(".") + 1] if "." in cut else cut
    return text or None


def narrate(intent: str, city: str, facts: dict, lang: str = "en") -> str | None:
    if lang != "en" or not is_configured() or not facts:
        return None
    try:
        return _sanitize(generate(build_prompt(intent, city, facts),
                                  model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY))
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        _LOG.warning("narration failed (%s); falling back to template", exc)
        return None
