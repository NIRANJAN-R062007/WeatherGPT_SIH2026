"""LLM narration for /ask: turn the facts dict into one grounded sentence.

Three providers behind one pluggable chain (plan.md §5, §8 Phase 6):
Gemini (primary) -> Groq (Gemini's free tier 503s roughly 1 in 3 calls live)
-> Ollama (local, for a dead venue network). `providers()` lists the ones
configured, in order; `run_chain()` tries each and records which one answered
in `last_provider`. OFFLINE_MODE skips both cloud providers outright.

The plan originally named Llama-3 for the Groq slot, but Groq deprecated
llama-3.3-70b-versatile in Aug 2026 — GROQ_MODEL defaults to their
recommended replacement, gpt-oss-120b (see config.py). The guardrail still
validates whatever comes back; on total failure — nothing configured,
non-English, timeout, HTTP error, empty response — narrate() returns None
and main.py falls back to the i18n template (which covers Tamil). English
only for now.
"""

import json
import logging
import re
from typing import Callable

import config
import httpx

TIMEOUT = 10.0
OLLAMA_TIMEOUT = 30.0
MAX_CHARS = 240
_SKIP = ("source", "issued", "is_live", "day", "since", "days_requested",
         "days_counted", "hours_counted")
_CHAIN_EXC = (httpx.HTTPError, KeyError, IndexError, ValueError)
_LOG = logging.getLogger("weathergpt.narrate")

# Set by run_chain() to the name of whichever provider last produced an
# answer; main.py reads it right after narrate() to report grounding.provider.
# Process-global — fine for a single-user demo, not for concurrent traffic.
last_provider: str | None = None

_PROMPT = (
    "You are WeatherGPT, answering for farmers and fishers in Tamil Nadu. "
    'Write ONE plain-English sentence, max {word_cap} words, starting with "{city}:". '
    "Use ONLY the facts below, and include every number that is present. Each "
    "number must appear verbatim with its unit (°C, %, km/h, mm); do not round or "
    "invent ranges, times, dates or places. Write naturally — never mention the "
    "field names (temp_c, humidity_pct, ...). No markdown, no preamble."
    "{hint}{feedback}\n"
    "Intent: {intent}\nFacts: {facts}"
)

_INTENT_HINTS: dict[str, str] = {
    "rainfall_so_far_today": ' Say "since midnight"; you may say "over N hours" '
    "with N={hours_counted}.",
    "forecast": ' You may say "the next N days" with N={days_counted}.',
    "will_it_rain": ' You may say "the next N days" with N={days_counted}.',
}


def _word_cap(facts: dict) -> int:
    return 25 + 15 * max(0, len(facts.get("days", [])) - 1)


def build_prompt(intent: str, city: str, facts: dict, *, feedback: str | None = None) -> str:
    trimmed = {k: v for k, v in facts.items() if k not in _SKIP}
    hint_template = _INTENT_HINTS.get(intent, "")
    hint = ""
    if hint_template:
        try:
            hint = hint_template.format(**facts)
        except KeyError:
            hint = ""
    feedback_text = ""
    if feedback:
        feedback_text = (
            f"\nYour previous answer contained figures not in the facts: {feedback}. "
            "Rewrite using only the facts' numbers."
        )
    return _PROMPT.format(
        city=city, intent=intent, word_cap=_word_cap(facts), hint=hint,
        feedback=feedback_text,
        facts=json.dumps(trimmed, ensure_ascii=False, sort_keys=True),
    )


def gemini_schema(schema: dict) -> dict:
    """Standard JSON Schema -> Gemini's dialect: uppercase type names,
    `nullable: true` instead of a ["type", "null"] union, and a
    `propertyOrdering` list (Gemini has no guaranteed key order otherwise).
    Recurses into `properties` and `items`.
    """
    type_ = schema.get("type")
    nullable = False
    if isinstance(type_, list):
        types = [t for t in type_ if t != "null"]
        nullable = "null" in type_
        type_ = types[0] if types else "null"

    out: dict = {}
    if type_ is not None:
        out["type"] = type_.upper()
    if nullable:
        out["nullable"] = True
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if "required" in schema:
        out["required"] = schema["required"]
    if "properties" in schema:
        out["properties"] = {k: gemini_schema(v) for k, v in schema["properties"].items()}
        out["propertyOrdering"] = list(schema["properties"].keys())
    if "items" in schema:
        out["items"] = gemini_schema(schema["items"])
    return out


def generate(prompt: str, *, model: str, key: str, timeout: float = TIMEOUT,
             response_schema: dict | None = None) -> str | None:
    generation_config = {
        "temperature": 0.2,
        "maxOutputTokens": 200,
        "candidateCount": 1,
        "thinkingConfig": {"thinkingBudget": 0},  # flash is a thinking model; a
    }                                             # reasoning budget starves the answer
    if response_schema is not None:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = response_schema
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
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


def generate_groq(prompt: str, *, model: str, key: str, timeout: float = TIMEOUT,
                   response_schema: dict | None = None) -> str | None:
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
    if response_schema is not None:
        # Groq's json_object mode has no schema param — the schema is embedded
        # in the prompt text itself (nlu._NLU_PROMPT already does this).
        body["response_format"] = {"type": "json_object"}
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


def generate_ollama(prompt: str, *, model: str, base: str, timeout: float = OLLAMA_TIMEOUT,
                     response_schema: dict | None = None) -> str | None:
    """Local Ollama via its native /api/generate (no chat wrapper needed for a
    single-turn prompt). `keep_alive: 30m` avoids reloading the model between
    the narration and NLU calls a single /ask can make. connect=2.0 means a
    wrong/unreachable OLLAMA_BASE fails fast instead of stalling the demo.
    """
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 200},
        "keep_alive": "30m",
    }
    if response_schema is not None:
        body["format"] = response_schema
    resp = httpx.post(
        f"{base}/api/generate",
        json=body,
        timeout=httpx.Timeout(timeout, connect=2.0),
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("done_reason") not in (None, "stop"):
        _LOG.warning("ollama generation stopped early (%s)", data.get("done_reason"))
        return None
    text = (data.get("response") or "").strip()
    return text or None


def ollama_status(timeout: float = 1.0) -> dict:
    """Never raises — used by /health, which must stay up even offline."""
    base, model = config.OLLAMA_BASE, config.OLLAMA_MODEL
    status = {"base": base, "model": model, "reachable": None, "model_present": None}
    if not model:
        return status
    try:
        resp = httpx.get(f"{base}/api/tags", timeout=timeout)
        resp.raise_for_status()
        names = {m.get("name") for m in resp.json().get("models") or []}
        status["reachable"] = True
        status["model_present"] = model in names
    except (httpx.HTTPError, KeyError, ValueError):
        status["reachable"] = False
        status["model_present"] = None  # unknown — couldn't even ask
    return status


def _gemini(prompt: str, *, response_schema: dict | None = None) -> str | None:
    schema = gemini_schema(response_schema) if response_schema is not None else None
    return generate(prompt, model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY,
                     response_schema=schema)


def _groq(prompt: str, *, response_schema: dict | None = None) -> str | None:
    return generate_groq(prompt, model=config.GROQ_MODEL, key=config.GROQ_API_KEY,
                          response_schema=response_schema)


def _ollama(prompt: str, *, response_schema: dict | None = None) -> str | None:
    return generate_ollama(prompt, model=config.OLLAMA_MODEL, base=config.OLLAMA_BASE,
                            timeout=config.OLLAMA_TIMEOUT, response_schema=response_schema)


def providers() -> list[tuple[str, Callable]]:
    """The configured provider chain, in try-order. OFFLINE_MODE drops both
    cloud providers even if their keys are set.
    """
    chain: list[tuple[str, Callable]] = []
    if not config.OFFLINE_MODE:
        if config.GEMINI_API_KEY:
            chain.append(("gemini", _gemini))
        if config.GROQ_API_KEY:
            chain.append(("groq", _groq))
    if config.OLLAMA_MODEL:
        chain.append(("ollama", _ollama))
    return chain


def is_configured() -> bool:
    return bool(providers())


def run_chain(prompt: str, *, response_schema: dict | None = None,
              task: str = "narration") -> tuple[str | None, str | None]:
    """Try each configured provider in order; return (text, provider_name) for
    the first non-empty answer, or (None, None) if all fail. Sets
    last_provider as a side effect for callers that can't take the tuple
    (main.narrate is stubbed by ~15 tests as a plain lambda).
    """
    global last_provider
    for name, fn in providers():
        try:
            text = fn(prompt, response_schema=response_schema)
        except _CHAIN_EXC as exc:
            _LOG.warning("%s %s failed (%s)", name, task, exc)
            continue
        if text:
            last_provider = name
            return text, name
    last_provider = None
    return None, None


def _sanitize(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"```[a-z]*|`", "", text)
    text = " ".join(text.split())
    text = text.split("\n", 1)[0].strip()
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        ends = [m.end() for m in re.finditer(r"\.(?!\d)", cut)]  # skip decimal points
        text = cut[: ends[-1]] if ends else cut
    return text or None


def narrate(intent: str, city: str, facts: dict, lang: str = "en", *,
            feedback: str | None = None) -> str | None:
    if lang != "en" or not is_configured() or not facts:
        return None
    prompt = build_prompt(intent, city, facts, feedback=feedback)
    text, _ = run_chain(prompt)
    return _sanitize(text)
