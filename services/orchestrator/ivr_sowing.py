"""The sowing advisory over the IVR call (plan.md §8 TFA-14). — **Niranjan**

A recorded question that talks about sowing ("when should I sow groundnut in
Madurai") goes to the same pipeline as POST /advisory/sowing (slots, then
advisory/agent.py with its hard override and guardrail) instead of /ask, and
the answer is read back as a few spoken sentences: the verdict, its reasons,
today's sowing window when there is one, and the KVK line.

A call is turn-based (ivr.py's docstring), so a missing crop or district is
asked for out loud and the slots are kept per CallSid: the caller's next
recording on the same call answers the question. That needs the Exotel flow to
loop from the answer Greeting back to the Record applet; a flow without the
loop just ends after the question.

The advisory's sentences are English (TFA-23 owns the other languages), so for
any other language the spoken text goes through Bhashini translation and the
guardrail re-checks its numbers against the facts, as /ask does. If either
fails, the caller hears a short verdict sentence written for their language,
with no figures, rather than English or nothing.
"""

from __future__ import annotations

import logging
import re
import time

import bhashini
import cities
import config
import guardrail
from advisory import agent as advisory_agent
from advisory import slots as advisory_slots
from advisory import template as advisory_template

_LOG = logging.getLogger("weathergpt.ivr")

KIND = "farming"
MAX_REASONS = 2  # a phone answer has to stay short

# Words that make a question a sowing question. A crop name alone doesn't ("will it
# rain on my paddy?" is a weather question). Prefixes for the Indic verbs, which
# take many endings. TODO: native_qa
_SOWING_CUES = re.compile(
    r"\b(?:sow|sows|sowed|sowing|sown)\b"
    r"|बुवाई|बुआई|बोना|बोने|बोऊँ|बोऊं"       # hi
    r"|விதை"                               # ta: விதைக்க, விதைப்பு
    r"|విత్త"                               # te: విత్తు, విత్తనం
    r"|पेरणी|पेरू|पेरा",                     # mr
    re.I,
)

DISCLAIMER = "Check with your local KVK or agriculture office before you sow."

# The verdict when the full answer can't be said in the caller's language. No
# figures, so there is nothing to ground. TODO: native_qa
_FALLBACK = {
    "suitable": {
        "en": "Conditions look suitable for sowing.",
        "hi": "बुवाई के लिए हालात ठीक दिखते हैं।",
        "ta": "விதைப்பதற்கு சூழ்நிலை ஏற்றதாகத் தெரிகிறது.",
        "te": "విత్తడానికి పరిస్థితులు అనుకూలంగా కనిపిస్తున్నాయి.",
        "mr": "पेरणीसाठी परिस्थिती योग्य दिसते.",
    },
    "not_suitable": {
        "en": "Conditions do not look suitable for sowing now.",
        "hi": "अभी बुवाई के लिए हालात ठीक नहीं दिखते।",
        "ta": "இப்போது விதைப்பதற்கு சூழ்நிலை ஏற்றதாக இல்லை.",
        "te": "ఇప్పుడు విత్తడానికి పరిస్థితులు అనుకూలంగా లేవు.",
        "mr": "आता पेरणीसाठी परिस्थिती योग्य दिसत नाही.",
    },
    "not_available": {
        "en": "I don't have the information to judge sowing for this crop here.",
        "hi": "यहाँ इस फसल की बुवाई आँकने के लिए जानकारी उपलब्ध नहीं है।",
        "ta": "இங்கு இந்தப் பயிரை விதைப்பதை மதிப்பிட தகவல் இல்லை.",
        "te": "ఇక్కడ ఈ పంట విత్తడాన్ని అంచనా వేయడానికి సమాచారం లేదు.",
        "mr": "येथे या पिकाच्या पेरणीचा अंदाज घेण्यासाठी माहिती उपलब्ध नाही.",
    },
}
_FALLBACK_DISCLAIMER = {
    "en": DISCLAIMER,
    "hi": "बुवाई से पहले अपने स्थानीय KVK या कृषि कार्यालय से पूछें।",
    "ta": "விதைப்பதற்கு முன் உங்கள் அருகிலுள்ள KVK அல்லது வேளாண் அலுவலகத்தைக் கேளுங்கள்.",
    "te": "విత్తే ముందు మీ దగ్గరి KVK లేదా వ్యవసాయ కార్యాలయాన్ని సంప్రదించండి.",
    "mr": "पेरणीपूर्वी आपल्या स्थानिक KVK किंवा कृषी कार्यालयाशी संपर्क साधा.",
}

# CallSid -> (expires_at, slots, asking): a sowing conversation waiting for the
# caller's next recording. In memory, like ivr.py's answer cache, for the same reason.
_pending: dict[str, tuple[float, dict, str | None]] = {}


def is_sowing_question(text: str) -> bool:
    return bool(_SOWING_CUES.search(text or ""))


def _remember(call_sid: str, slots: dict, asking: str | None) -> None:
    _pending.pop(call_sid, None)
    _pending[call_sid] = (time.monotonic() + config.IVR_ANSWER_TTL_SECONDS, dict(slots), asking)
    while len(_pending) > config.IVR_ANSWER_CACHE_MAX:
        _pending.pop(next(iter(_pending)))


def _recall(call_sid: str) -> tuple[dict, str | None] | None:
    entry = _pending.get(call_sid)
    if entry is None:
        return None
    expires, slots, asking = entry
    if time.monotonic() >= expires:
        _pending.pop(call_sid, None)
        return None
    return slots, asking


def reply(call_sid: str, transcript: str, lang: str) -> str | None:
    """What to say back for this recording, or None when it isn't a sowing question
    (and no sowing conversation is open on this call), so /ask answers it."""
    open_turn = _recall(call_sid)
    if open_turn is None and not is_sowing_question(transcript):
        return None
    have, asking = open_turn or ({}, None)
    parsed = advisory_slots.parse(KIND, transcript, have=have, asking=asking)
    if not parsed.complete:
        _remember(call_sid, parsed.slots, parsed.asking)
        return advisory_slots.ask_back(parsed, lang)
    _pending.pop(call_sid, None)
    advice = advisory_agent.advise(KIND, parsed.slots, lang)
    return spoken(advice.answer, parsed.slots, advice.facts.raw(), lang)


def english_text(answer: dict, slots: dict) -> str:
    """The answer as a few sentences to say: verdict, reasons, window, KVK line."""
    verdict = answer.get("verdict")
    crop = slots.get("crop", "this crop")
    city = cities.CITIES.get(slots.get("district"))
    place = city.names.get("en") if city else slots.get("district", "here")
    head = {
        "suitable": f"Conditions look suitable for sowing {crop} in {place}.",
        "not_suitable": f"Conditions do not look suitable for sowing {crop} in {place} now.",
    }.get(verdict, f"I can't judge sowing {crop} in {place}.")
    reasons = answer.get("pros" if verdict == "suitable" else "cons") or []
    reasons = [r for r in reasons if r != advisory_template.CROP_NOT_REVIEWED][:MAX_REASONS]
    parts = [head, *reasons]
    window = answer.get("window")
    if verdict == "suitable" and window:
        parts.append(f"Today's best hours are {window['start_local']} to {window['end_local']}.")
    if advisory_template.CROP_NOT_REVIEWED in (answer.get("cons") or []):
        parts.append(advisory_template.CROP_NOT_REVIEWED)
    parts.append(DISCLAIMER)
    return " ".join(parts)


def fallback_text(verdict: str | None, lang: str) -> str:
    lang = lang if lang in _FALLBACK_DISCLAIMER else "en"
    head = _FALLBACK.get(verdict, _FALLBACK["not_available"])[lang]
    return f"{head} {_FALLBACK_DISCLAIMER[lang]}"


def spoken(answer: dict, slots: dict, facts: dict, lang: str) -> str:
    """The text to synthesize in `lang`: the full answer, translated and re-grounded
    when `lang` isn't English, else the short verdict sentence for that language."""
    english = english_text(answer, slots)
    if lang == "en":
        return english
    translated = bhashini.translate(english, lang) if bhashini.is_configured() else None
    if translated and guardrail.check(translated, facts).ok:
        return translated
    _LOG.info("IVR sowing: %s translation unusable, verdict-only answer", lang)
    return fallback_text(answer.get("verdict"), lang)
