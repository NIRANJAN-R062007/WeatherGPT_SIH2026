"""WhatsApp channel (plan.md §8 Phase 5): text questions in any of the five
languages, answered by the same grounded /ask pipeline. — **Mahesh**

The Meta WhatsApp Cloud API calls us, not the other way round:

    GET  /whatsapp/webhook   the one-off handshake when the webhook is
                             registered: echo hub.challenge if hub.verify_token
                             is ours
    POST /whatsapp/webhook   one call per inbound message batch, signed with the
                             app secret (X-Hub-Signature-256). We check the
                             signature over the raw body, answer 200 at once
                             (Meta retries anything slower, and a retry would
                             ask the LLM twice) and do the work in the
                             background: ask() -> a Graph API text message.

Unlike Exotel (ivr.py), Meta signs its requests, so there is no shared ?key=.
Only messages sent to our own number (WHATSAPP_PHONE_NUMBER_ID) are answered.

Language: WhatsApp sends none. Tamil and Telugu script decide themselves;
Devanagari is Hindi unless the sender chose Marathi; Latin text uses the
language the sender last picked (send "hindi", "தமிழ்", "2" ...) and is English
until they pick one.

What the web and app do with taps, the chat does with replies:
- a place name with several matches ("Puttur") lists them numbered, and the
  sender's next message, if it is one of those numbers, asks the same question
  for that place (a number then picks a place, not a language);
- a shared location (attach -> Location) answers a question that was waiting
  for one, and is used for questions that name no place for the next hour;
- a sowing question asks back for a missing crop or district (ivr_sowing.py).

All of this is kept in memory only, keyed by an HMAC of the sender's number
(keyed with the app secret, so a key can't be reversed by hashing every Indian
mobile number), never by the number itself. Expired entries are dropped on the
next write to their table, so nothing outlives its lifetime by more than one
message. A shared location is snapped to 0.05° (~5 km), as the app does, and
this module never logs it; the 5 km cell it falls in is what the weather layer
fetches and caches, and can appear in its failure warnings, tied to no sender.
Webhook tasks run on several threads at once, so every table here is read and
written under one lock.

Not handled: voice notes (OGG/Opus needs ffmpeg and Bhashini ASR), images and
other message types (the sender is told to type), and proactive alerts
(alert_engine.py).
"""

import hashlib
import hmac
import logging
import math
import threading
import time

import config
import httpx
import ivr_sowing
import nlu
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

_LOG = logging.getLogger("weathergpt.whatsapp")

MAX_TEXT_CHARS = 1000  # a question longer than this is not a weather question
MAX_REPLY_CHARS = 4000  # WhatsApp's text body limit is 4096
MAX_CHOICES = 9  # one digit to reply with
_LANG_TTL_SECONDS = 24 * 3600
_GRID_DEGREES = 0.05  # mobile/lib/location.dart snapToGrid

# Words that pick a language. TODO: native_qa (the hi/ta/te/mr words)
_LANG_WORDS = {
    "1": "en", "english": "en", "inglish": "en",
    "2": "hi", "hindi": "hi", "हिन्दी": "hi", "हिंदी": "hi",
    "3": "ta", "tamil": "ta", "தமிழ்": "ta",
    "4": "te", "telugu": "te", "తెలుగు": "te",
    "5": "mr", "marathi": "mr", "मराठी": "mr",
}
_HELP_WORDS = frozenset({
    "hi", "hello", "help", "start", "menu", "namaste", "namaskar",
    "नमस्ते", "नमस्कार", "வணக்கம்", "నమస్కారం",
})

# TODO: native_qa (all hi/ta/te/mr strings below)
_HELP = {
    "en": ("Hello! Ask me about the weather. For example: "
           "\"Will it rain in Chennai today?\" You can also share your location "
           "to ask about where you are.\n\nLanguage: reply 1 English, 2 हिन्दी, "
           "3 தமிழ், 4 తెలుగు, 5 मराठी."),
    "hi": ("नमस्ते! मौसम के बारे में पूछें। जैसे: "
           "\"क्या आज चेन्नई में बारिश होगी?\" आप जहाँ हैं, उसके बारे में पूछने के लिए "
           "अपनी लोकेशन भी भेज सकते हैं।\n\nभाषा: 1 English, 2 हिन्दी, "
           "3 தமிழ், 4 తెలుగు, 5 मराठी भेजें।"),
    "ta": ("வணக்கம்! வானிலை பற்றி கேளுங்கள். "
           "எ.கா: \"இன்று சென்னையில் மழை பெய்யுமா?\" நீங்கள் இருக்கும் இடத்தைப் பற்றிக் "
           "கேட்க உங்கள் இருப்பிடத்தையும் பகிரலாம்.\n\nமொழி: 1 English, 2 हिन्दी, "
           "3 தமிழ், 4 తెలుగు, 5 मराठी என அனுப்பவும்."),
    "te": ("నమస్కారం! వాతావరణం గురించి అడగండి. ఉదా: "
           "\"ఈ రోజు చెన్నైలో వర్షం పడుతుందా?\" మీరు ఉన్న చోటు గురించి అడగడానికి "
           "మీ లొకేషన్‌ను కూడా పంపవచ్చు.\n\nభాష: 1 English, 2 हिन्दी, "
           "3 தமிழ், 4 తెలుగు, 5 मराठी పంపండి."),
    "mr": ("नमस्कार! हवामानाबद्दल विचारा. उदा: "
           "\"आज चेन्नईत पाऊस पडेल का?\" तुम्ही जिथे आहात त्याबद्दल विचारण्यासाठी "
           "तुमचे लोकेशनही पाठवू शकता.\n\nभाषा: 1 English, 2 हिन्दी, "
           "3 தமிழ், 4 తెలుగు, 5 मराठी पाठवा."),
}
_LANG_SET = {
    "en": "Language set to English.",
    "hi": "भाषा हिन्दी पर सेट की गई।",
    "ta": "மொழி தமிழுக்கு மாற்றப்பட்டது.",
    "te": "భాష తెలుగుకు మార్చబడింది.",
    "mr": "भाषा मराठी वर सेट केली.",
}
_UNSUPPORTED = {
    "en": "I can only answer typed questions. Please type your question.",
    "hi": "मैं सिर्फ़ टाइप किए गए सवालों का जवाब दे सकता हूँ। कृपया अपना सवाल टाइप करें।",
    "ta": ("தட்டச்சு செய்த கேள்விகளுக்கு மட்டுமே என்னால் பதிலளிக்க முடியும். "
           "உங்கள் கேள்வியைத் தட்டச்சு செய்யவும்."),
    "te": ("నేను టైప్ చేసిన ప్రశ్నలకు మాత్రమే సమాధానం ఇవ్వగలను. "
           "దయచేసి మీ ప్రశ్నను టైప్ చేయండి."),
    "mr": "मी फक्त टाइप केलेल्या प्रश्नांना उत्तर देऊ शकतो. कृपया तुमचा प्रश्न टाइप करा.",
}
_REPLY_WITH_NUMBER = {
    "en": "Reply with the number.",
    "hi": "नंबर भेजकर जवाब दें।",
    "ta": "எண்ணை அனுப்பி பதிலளிக்கவும்.",
    "te": "సంఖ్యను పంపి జవాబు ఇవ్వండి.",
    "mr": "क्रमांक पाठवून उत्तर द्या.",
}
_HERE_SAVED = {
    "en": ("Got your location. For the next hour I'll use it for questions that "
           "don't name a place, like \"Will it rain here today?\""),
    "hi": ("आपकी लोकेशन मिल गई। अगले एक घंटे तक जिन सवालों में जगह का नाम नहीं होगा, "
           "उनके लिए मैं इसी का उपयोग करूँगा, जैसे \"क्या आज यहाँ बारिश होगी?\""),
    "ta": ("உங்கள் இருப்பிடம் கிடைத்தது. அடுத்த ஒரு மணி நேரத்திற்கு, இடத்தின் பெயர் இல்லாத "
           "கேள்விகளுக்கு இதையே பயன்படுத்துவேன், எ.கா: \"இன்று இங்கே மழை பெய்யுமா?\""),
    "te": ("మీ లొకేషన్ అందింది. తదుపరి ఒక గంట పాటు, ప్రదేశం పేరు లేని ప్రశ్నలకు దీన్నే "
           "ఉపయోగిస్తాను, ఉదా: \"ఈ రోజు ఇక్కడ వర్షం పడుతుందా?\""),
    "mr": ("तुमचे लोकेशन मिळाले. पुढच्या एका तासासाठी ज्या प्रश्नांत ठिकाणाचे नाव नसेल, "
           "त्यांसाठी मी हेच वापरेन, जसे \"आज इथे पाऊस पडेल का?\""),
}
_BAD_LOCATION = {
    "en": "I couldn't read that location. Please share it again, or type a place name.",
    "hi": "वह लोकेशन पढ़ी नहीं जा सकी। कृपया फिर से भेजें, या जगह का नाम टाइप करें।",
    "ta": ("அந்த இருப்பிடத்தைப் படிக்க முடியவில்லை. மீண்டும் பகிரவும், "
           "அல்லது இடத்தின் பெயரைத் தட்டச்சு செய்யவும்."),
    "te": "ఆ లొకేషన్ చదవలేకపోయాను. దయచేసి మళ్ళీ పంపండి, లేదా ప్రదేశం పేరు టైప్ చేయండి.",
    "mr": "ते लोकेशन वाचता आले नाही. कृपया पुन्हा पाठवा, किंवा ठिकाणाचे नाव टाइप करा.",
}

# Every table maps a sender hash (or a message id) to (expires_at, *value).
_lock = threading.Lock()
_lang_prefs: dict[str, tuple] = {}  # -> (expires_at, lang)
_seen: dict[str, tuple] = {}  # message id -> (expires_at,)
_sender_hits: dict[str, list[float]] = {}  # -> send times inside the last minute
# A question waiting on the sender's next message:
# -> (expires_at, "choose", text, lang, [place_id, ...])  a numbered place choice
# -> (expires_at, "location", text, lang, None)            a shared location
_waiting: dict[str, tuple] = {}
_here: dict[str, tuple] = {}  # -> (expires_at, lat, lon), snapped

_monotonic = time.monotonic  # test seam


def sender_key(wa_id: str) -> str:
    """What identifies a sender in memory and in logs. Never the number, and
    not a bare hash of it either: India's ~4 billion mobile numbers can all be
    hashed in hours, so the key is an HMAC with the app secret."""
    secret = (config.WHATSAPP_APP_SECRET or "").encode()
    return hmac.new(secret, wa_id.encode(), hashlib.sha256).hexdigest()[:16]


def _get(table: dict, key: str) -> tuple | None:
    """The live value for `key` (without its expiry), or None."""
    with _lock:
        entry = table.get(key)
        if entry is None:
            return None
        if _monotonic() > entry[0]:
            table.pop(key, None)
            return None
        return entry[1:]


def _put(table: dict, key: str, ttl: float, *value) -> None:
    with _lock:
        now = _monotonic()
        for stale in [k for k, entry in table.items() if now > entry[0]]:
            del table[stale]  # expired entries don't wait for their sender to return
        table.pop(key, None)  # re-insert so it counts as newest
        table[key] = (now + ttl, *value)
        while len(table) > config.WHATSAPP_STATE_MAX:
            table.pop(next(iter(table)), None)  # dicts keep insertion order


def _drop(table: dict, key: str) -> None:
    with _lock:
        table.pop(key, None)


def reset() -> None:
    """Forget all in-memory state (tests)."""
    with _lock:
        for table in (_lang_prefs, _seen, _sender_hits, _waiting, _here):
            table.clear()


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256 is "sha256=" + HMAC-SHA256(app secret, raw body)."""
    secret = config.WHATSAPP_APP_SECRET
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header[len("sha256="):].strip().encode())


def _first_time(message_id: str) -> bool:
    """False for a message id already handled inside the dedupe window. The
    check and the insert are one step, so two deliveries racing on different
    threads can't both get through."""
    with _lock:
        now = _monotonic()
        for mid in [m for m, entry in _seen.items() if now > entry[0]]:
            del _seen[mid]
        if message_id in _seen:
            return False
        _seen[message_id] = (now + config.WHATSAPP_DEDUPE_TTL_SECONDS,)
        while len(_seen) > config.WHATSAPP_STATE_MAX:
            _seen.pop(next(iter(_seen)), None)
        return True


def _within_sender_limit(key: str) -> bool:
    limit = config.WHATSAPP_SENDER_RATE_PER_MIN
    if limit <= 0:
        return True
    with _lock:
        now = _monotonic()
        for idle in [k for k, hits in _sender_hits.items() if not hits or now - hits[-1] > 60.0]:
            del _sender_hits[idle]  # nobody's send times outlive the minute they count for
        # popped and re-inserted, so the active sender is never the one evicted
        window = [t for t in _sender_hits.pop(key, []) if now - t <= 60.0]
        allowed = len(window) < limit
        if allowed:
            window.append(now)
        _sender_hits[key] = window
        while len(_sender_hits) > config.WHATSAPP_STATE_MAX:
            _sender_hits.pop(next(iter(_sender_hits)), None)
        return allowed


def _command_lang(text: str) -> str | None:
    return _LANG_WORDS.get(text.strip().lower().rstrip(".!"))


def _choose_lang(text: str, preferred: str | None) -> str:
    script = nlu.detect_script(text)
    if script in ("ta", "te"):
        return script
    if script == "deva":
        return preferred if preferred in ("hi", "mr") else "hi"
    return preferred or "en"


def _snap(degrees: float) -> float:
    return round(round(degrees / _GRID_DEGREES) * _GRID_DEGREES, 2)


def _point(location) -> tuple[float, float] | None:
    """(lat, lon) from a location message, snapped, or None if unusable."""
    if not isinstance(location, dict):
        return None
    lat, lon = location.get("latitude"), location.get("longitude")
    for value in (lat, lon):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return _snap(lat), _snap(lon)


def _graph_url(path: str) -> str:
    return f"{config.WHATSAPP_GRAPH_BASE}/{config.WHATSAPP_GRAPH_VERSION}/{path}"


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}"}


def send_text(to: str, body: str) -> bool:
    """One Graph API text message. Never raises; False if it was not accepted."""
    try:
        resp = httpx.post(
            _graph_url(f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages"),
            headers=_auth(),
            json={"messaging_product": "whatsapp", "to": to, "type": "text",
                  "text": {"preview_url": False, "body": body[:MAX_REPLY_CHARS]}},
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        # type (and status) only: httpx's message carries the full request URL
        status = getattr(getattr(exc, "response", None), "status_code", None)
        _LOG.warning("WhatsApp: send failed (%s, status=%s)", type(exc).__name__, status)
        return False


def _candidates(outcome: dict) -> list[dict]:
    """ask()'s `ambiguous` list, only the entries a reply can pick."""
    found = outcome.get("ambiguous")
    if not isinstance(found, list):
        return []
    return [c for c in found
            if isinstance(c, dict) and isinstance(c.get("place_id"), str)
            and isinstance(c.get("label"), str)][:MAX_CHOICES]


def _choice_text(message: str, candidates: list[dict], lang: str) -> str:
    lines = [message]
    for n, cand in enumerate(candidates, 1):
        label, district = cand["label"], cand.get("district")
        if isinstance(district, str) and district and district not in label:
            label = f"{label} ({district})"
        lines.append(f"{n}. {label}")
    lines.append(_REPLY_WITH_NUMBER[lang])
    return "\n".join(lines)


def _ask(key: str, text: str, lang: str, ask_fn, msg_fn, **where) -> str:
    """ask() for one question, as reply text. An ambiguous place becomes a
    numbered list and a "which place?" waits for a shared location; either is
    remembered so the sender's next message can answer it. Without a place_id
    or a point of its own, a location the sender shared within the hour is
    passed along (ask() only uses it when the question names no place)."""
    if "place_id" not in where and "lat" not in where:
        here = _get(_here, key)
        if here is not None:
            where = {"lat": here[0], "lon": here[1]}
    try:
        outcome = ask_fn(text=text, lang=lang, city=None, token=None, **where)
    except Exception as exc:  # ask() must never leave a sender without a reply
        _LOG.warning("WhatsApp: ask() raised (%s)", type(exc).__name__)
        return msg_fn("no_data", lang)
    message = outcome.get("response") or outcome.get("message") or msg_fn("no_data", lang)
    candidates = _candidates(outcome)
    if candidates:
        _put(_waiting, key, config.WHATSAPP_CONVERSATION_TTL_SECONDS,
             "choose", text, lang, [c["place_id"] for c in candidates])
        return _choice_text(message, candidates, lang)
    if outcome.get("needs_location"):
        _put(_waiting, key, config.WHATSAPP_CONVERSATION_TTL_SECONDS,
             "location", text, lang, None)
    return message


def _answer(key: str, text: str, lang: str, ask_fn, msg_fn) -> str:
    """The reply text for one question: the sowing advisory when it is one (it
    asks back for a missing crop or district, remembering the slots per
    sender), else /ask. Never raises."""
    try:
        sowing = ivr_sowing.reply(f"wa:{key}", text, lang, channel="whatsapp")
    except Exception as exc:
        _LOG.warning("WhatsApp: sowing advisory raised (%s)", type(exc).__name__)
        return msg_fn("no_data", lang)
    if sowing is not None:
        return sowing
    return _ask(key, text, lang, ask_fn, msg_fn)


def handle_message(message: dict, ask_fn, msg_fn, send_fn=None) -> None:
    """One inbound message -> at most one reply. Never raises. send_fn defaults
    to this module's send_text, looked up at call time so a test or the
    simulator can swap it."""
    try:
        _handle(message, ask_fn, msg_fn, send_fn or send_text)
    except Exception as exc:
        _LOG.warning("WhatsApp: message handling raised (%s)", type(exc).__name__)


def _handle(message: dict, ask_fn, msg_fn, send_fn) -> None:
    sender, message_id = message.get("from"), message.get("id")
    if not isinstance(sender, str) or not sender or not isinstance(message_id, str):
        return
    if not _first_time(message_id):
        return
    key = sender_key(sender)
    if not _within_sender_limit(key):
        _LOG.info("WhatsApp: sender %s over %s messages/min - dropped", key,
                  config.WHATSAPP_SENDER_RATE_PER_MIN)
        return
    preferred = (_get(_lang_prefs, key) or (None,))[0]
    waiting = _get(_waiting, key)
    kind = message.get("type")

    if kind == "text":
        body = ((message.get("text") or {}).get("body") or "").strip()
        if not body:
            return
        # A number answering a place choice picks the place, not a language.
        if waiting is not None and waiting[0] == "choose" and body.isdigit() and len(body) <= 2:
            _, text, lang, place_ids = waiting
            choice = int(body)
            if 1 <= choice <= len(place_ids):
                _drop(_waiting, key)
                send_fn(sender, _ask(key, text, lang, ask_fn, msg_fn,
                                     place_id=place_ids[choice - 1]))
            else:
                send_fn(sender, _REPLY_WITH_NUMBER[lang])
            return
        picked = _command_lang(body)
        if picked is not None:
            _put(_lang_prefs, key, _LANG_TTL_SECONDS, picked)
            send_fn(sender, _LANG_SET[picked])
            return
        lang = _choose_lang(body, preferred)
        if body.lower().rstrip(".!") in _HELP_WORDS:
            send_fn(sender, _HELP[lang])
            return
        _drop(_waiting, key)  # a new question replaces whatever was waiting
        send_fn(sender, _answer(key, body[:MAX_TEXT_CHARS], lang, ask_fn, msg_fn))
        return

    lang = preferred or "en"
    if kind == "location":
        point = _point(message.get("location"))
        if point is None:
            send_fn(sender, _BAD_LOCATION[lang])
            return
        _put(_here, key, config.WHATSAPP_LOCATION_TTL_SECONDS, *point)
        if waiting is not None and waiting[0] == "location":
            _, text, asked_lang, _ = waiting
            _drop(_waiting, key)
            send_fn(sender, _ask(key, text, asked_lang, ask_fn, msg_fn,
                                 lat=point[0], lon=point[1]))
        else:
            send_fn(sender, _HERE_SAVED[lang])
        return

    send_fn(sender, _UNSUPPORTED[lang])


def messages_in(payload, phone_number_id: str | None) -> list[dict]:
    """Every inbound message in a webhook payload that was sent to our number
    (value.metadata.phone_number_id; one Meta app can own several numbers).
    Delivery receipts ("statuses") and anything malformed are skipped."""
    found: list[dict] = []
    if not isinstance(payload, dict) or not phone_number_id:
        return found
    for entry in payload.get("entry") or []:
        for change in (entry.get("changes") or []) if isinstance(entry, dict) else []:
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != phone_number_id:
                continue
            for message in value.get("messages") or []:
                if isinstance(message, dict):
                    found.append(message)
    return found


def mount(app: FastAPI, ask_fn, msg_fn) -> None:
    """Registers the WhatsApp routes on `app`. No-op if WHATSAPP_ENABLED is
    unset, so a clone with no Meta app configured exposes nothing."""
    if not config.WHATSAPP_ENABLED:
        return
    missing = [name for name in ("WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN",
                                 "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")
               if not getattr(config, name)]
    if missing:
        _LOG.error("WHATSAPP_ENABLED is set but %s empty - WhatsApp routes NOT mounted.",
                   ", ".join(missing) + (" is" if len(missing) == 1 else " are"))
        return

    @app.get("/whatsapp/webhook")
    def whatsapp_verify(
        mode: str | None = Query(None, alias="hub.mode"),
        token: str | None = Query(None, alias="hub.verify_token"),
        challenge: str | None = Query(None, alias="hub.challenge"),
    ):
        expected = config.WHATSAPP_VERIFY_TOKEN or ""
        if (mode != "subscribe" or challenge is None or not token
                or not hmac.compare_digest(token.encode(), expected.encode())):
            raise HTTPException(status_code=403, detail="verification failed")
        return PlainTextResponse(challenge)

    @app.post("/whatsapp/webhook")
    async def whatsapp_inbound(request: Request, background: BackgroundTasks):
        raw = await request.body()
        if not verify_signature(raw, request.headers.get("x-hub-signature-256")):
            raise HTTPException(status_code=403, detail="bad signature")
        try:
            payload = await request.json()
        except ValueError:
            return {"status": "ignored"}
        for message in messages_in(payload, config.WHATSAPP_PHONE_NUMBER_ID):
            background.add_task(handle_message, message, ask_fn, msg_fn)
        return {"status": "ok"}
