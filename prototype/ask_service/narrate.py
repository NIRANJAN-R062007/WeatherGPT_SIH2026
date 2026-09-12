"""LLM narration for /ask: turn the facts dict into one grounded sentence.

Gemini is the primary provider; Groq is a second path tried when Gemini
fails, since Gemini's free tier 503s roughly 1 in 3 calls live. The plan
originally named Llama-3 for this slot, but Groq deprecated
llama-3.3-70b-versatile in Aug 2026 — GROQ_MODEL defaults to their
recommended replacement, gpt-oss-120b (see config.py). The guardrail still
validates whatever comes back; on total failure — no key configured for
either provider, non-English, timeout, HTTP error, empty response —
narrate() returns None and main.py falls back to the i18n template (which
covers Tamil). English only for now.
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
    return bool(config.GEMINI_API_KEY or config.GROQ_API_KEY)


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


def generate_groq(prompt: str, *, model: str, key: str, timeout: float = TIMEOUT) -> str | None:
    """Groq's chat-completions endpoint is OpenAI-compatible — plain REST, no
    SDK needed, same httpx call shape as generate() above.

    gpt-oss models are reasoning models: chain-of-thought goes into a separate
    `reasoning` field but still counts against max_tokens, so a low budget
    truncates before `content` gets anything written (finish_reason="length",
    content=""). reasoning_effort="low" + a bigger budget avoids that — the
    Groq equivalent of Gemini's thinkingBudget:0 above.
    """
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
        "reasoning_effort": "low",
    }
    resp = httpx.post(
        f"{config.GROQ_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    choices = resp.json().get("choices") or []
    if not choices or choices[0].get("finish_reason") not in (None, "stop"):
        return None
    text = (choices[0].get("message") or {}).get("content", "").strip()
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
    prompt = build_prompt(intent, city, facts)

    if config.GEMINI_API_KEY:
        try:
            text = _sanitize(generate(prompt, model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY))
            if text:
                return text
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            _LOG.warning("gemini narration failed (%s); trying groq fallback", exc)

    if config.GROQ_API_KEY:
        try:
            text = _sanitize(generate_groq(prompt, model=config.GROQ_MODEL, key=config.GROQ_API_KEY))
            if text:
                return text
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            _LOG.warning("groq narration failed (%s); falling back to template", exc)

    return None
