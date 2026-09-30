"""IVR channel (plan.md §8 Phase 4): dial a number, speak a question in any
of the five languages, hear the grounded /ask answer read back. — **Niranjan**

Exotel's call-flow builder (configured in their web dashboard, not via this
repo — there is no "call flow as code" step here) has no single applet that
both accepts a caller's recording and plays back audio we generate in
response to it. Two applet types matter (support.exotel.com/.../35431-applets):

- **Passthru**: fires an HTTP request at a URL with the call's details and
  moves on immediately — it does not wait for our response to decide what
  happens next in the call.
- **Greeting**: fetches a URL and expects the response body to *be* a WAV
  file, which it then plays to the caller. This is the only applet whose
  response Exotel actually plays back.

So the flow is two Exotel-dashboard nodes chained one after another, not one
request/response turn:

    Incoming call
      -> Gather applet: caller presses 1-5 for a language (or defaults to
         English if the Gather times out) — its own prompt is played from
         GET /ivr/menu.wav (a Greeting node)
      -> Record applet: records the caller's spoken question
      -> Passthru applet -> POST /ivr/recording?key=IVR_WEBHOOK_SECRET
         (CallSid, Digits, RecordingUrl as form fields) — this is where the
         real work happens: download the recording, Bhashini ASR, ask() for
         a grounded answer, Bhashini TTS, cache the resulting WAV by CallSid
      -> Greeting applet -> GET /ivr/answer/{CallSid}.wav?key=... — plays
         back whatever process_recording() cached for that call

Because Passthru doesn't block the flow on our response, the Record+Passthru
step's whole ASR->ask->TTS chain has to finish (or fail) *before* the flow
reaches the following Greeting node — Exotel's own inter-applet latency is
the only thing giving us that window, so this is a turn-based IVR, not a
real-time conversation. A duplex, mid-call voicebot would need Exotel's
separate Voicebot Applet (a websocket audio stream), which is a materially
bigger build than this first pass.

**Known gap, not yet handled**: Exotel's default RecordingUrl serves MP3, not
the WAV Bhashini's ASR endpoint wants (same contract main.py's POST /asr
uses). This module only accepts a RecordingUrl that resolves to a WAV file
and answers with `_msg("no_data", lang)`'s audio otherwise — see
_download_recording's docstring. Transcoding (ffmpeg/pydub) is the fix,
scoped out of this pass.
"""

import base64
import hmac
import ipaddress
import logging
import socket
import time
from urllib.parse import urlsplit

import bhashini
import config
import httpx
from fastapi import FastAPI, Form, HTTPException, Response

_LOG = logging.getLogger("weathergpt.ivr")

LANG_DIGITS = {"1": "en", "2": "hi", "3": "ta", "4": "te", "5": "mr"}
DEFAULT_LANG = "en"

# Exotel's own recordings are telephony audio: 8kHz mono, not the 16kHz the
# app's mic capture (main.py's ASRRequest) uses — same Bhashini ASR endpoint,
# different sampling_rate.
IVR_SAMPLING_RATE = 8000

# CallSid -> (expires_at, wav_bytes). In-memory only: a call is seconds long
# end to end, so this doesn't need to survive a restart, and multiple
# orchestrator replicas would need a shared cache (Redis) before this scales
# past one instance — noted, not built, since the rest of the IVR flow is a
# single-instance-first pass too.
_answer_cache: dict[str, tuple[float, bytes]] = {}


def _cache_put(call_sid: str, wav_bytes: bytes) -> None:
    _answer_cache.pop(call_sid, None)  # re-insert so it counts as newest
    _answer_cache[call_sid] = (time.monotonic() + config.IVR_ANSWER_TTL_SECONDS, wav_bytes)
    _cache_sweep()
    while len(_answer_cache) > config.IVR_ANSWER_CACHE_MAX:
        _answer_cache.pop(next(iter(_answer_cache)), None)  # dicts keep insertion order


def _cache_get(call_sid: str) -> bytes | None:
    entry = _answer_cache.get(call_sid)
    if entry is None:
        return None
    expires_at, wav_bytes = entry
    if time.monotonic() > expires_at:
        _answer_cache.pop(call_sid, None)
        return None
    return wav_bytes


def _cache_sweep() -> None:
    now = time.monotonic()
    expired = [sid for sid, (expires_at, _) in _answer_cache.items() if now > expires_at]
    for sid in expired:
        _answer_cache.pop(sid, None)


def _check_secret(key: str | None) -> None:
    """Exotel has no request-signing (no X-Twilio-Signature equivalent), so a
    shared ?key= query param is the only thing stopping a stranger who finds
    the webhook URL from injecting fake calls or scraping cached answer
    audio. mount() refuses to register the routes without a secret; this
    check also fails closed if it is somehow empty."""
    secret = config.IVR_WEBHOOK_SECRET
    if not secret or not key or not hmac.compare_digest(key.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="bad or missing key")


def _host_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in config.IVR_RECORDING_HOSTS)


def _host_is_public(host: str) -> bool:
    """True only if every address the host resolves to is a public one."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            return False
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified or not ip.is_global):
            return False
    return True


def _download_recording(url: str) -> bytes | None:
    """Fetch Exotel's RecordingUrl. Needs Basic Auth with the account's API
    Key/API Token (EXOTEL_API_KEY/EXOTEL_API_TOKEN). The URL is caller
    supplied, so: https only, host must be on IVR_RECORDING_HOSTS and resolve
    to public addresses only, credentials go to allowlisted hosts only,
    redirects are not followed, and the body is capped. Only a WAV response
    (RIFF/WAVE header) is usable — see the module docstring's MP3 gap;
    anything else returns None so the caller falls back to the "no data"
    answer. config.IVR_ALLOW_INSECURE_RECORDING_URLS (simulator/tests only)
    relaxes the scheme/host/IP checks but never the credential rule."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError:
        _LOG.warning("IVR: recording URL rejected (unparseable)")
        return None
    allowed = _host_allowed(host) if host else False
    if not config.IVR_ALLOW_INSECURE_RECORDING_URLS:
        if parts.scheme != "https" or not allowed or parts.username or parts.password:
            _LOG.warning("IVR: recording URL rejected (scheme/host not allowed): host=%s", host)
            return None
        if not _host_is_public(host):
            _LOG.warning("IVR: recording host rejected (non-public address): host=%s", host)
            return None
    elif parts.scheme not in ("http", "https") or not host:
        _LOG.warning("IVR: recording URL rejected (bad scheme): host=%s", host)
        return None
    have_creds = config.EXOTEL_API_KEY and config.EXOTEL_API_TOKEN
    auth = (config.EXOTEL_API_KEY, config.EXOTEL_API_TOKEN) \
        if have_creds and allowed and parts.scheme == "https" else None
    limit = config.IVR_MAX_RECORDING_BYTES
    try:
        with httpx.stream("GET", url, auth=auth, timeout=15.0, follow_redirects=False) as resp:
            resp.raise_for_status()
            if resp.status_code != 200:
                _LOG.warning("IVR: recording download refused (status %s) host=%s",
                             resp.status_code, host)
                return None
            declared = resp.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit:
                _LOG.warning("IVR: recording too large (declared) host=%s", host)
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > limit:
                    _LOG.warning("IVR: recording too large host=%s", host)
                    return None
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        # type only: httpx exception text includes the full URL
        _LOG.warning("IVR: failed to download recording from %s (%s)", host, type(exc).__name__)
        return None
    body = b"".join(chunks)
    if body[:4] != b"RIFF" or body[8:12] != b"WAVE":
        _LOG.warning(
            "IVR: recording from %s is not WAV (got %r) — MP3 transcoding isn't wired up yet",
            host, body[:12],
        )
        return None
    return body


def _synthesize(text: str, lang: str) -> bytes | None:
    audio_b64 = bhashini.text_to_speech(text, lang)
    if audio_b64 is None:
        return None
    try:
        return base64.b64decode(audio_b64)
    except (ValueError, TypeError) as exc:
        _LOG.warning("IVR: TTS audio for lang=%s wasn't valid base64 (%s)", lang, exc)
        return None


def process_recording(call_sid: str, lang: str, recording_url: str, ask_fn, msg_fn) -> None:
    """Runs the ASR->ask->TTS chain for one call and caches the resulting
    answer audio under `call_sid` for /ivr/answer to serve. Never raises —
    every failure path still caches *some* audio (a spoken fallback message)
    so the caller always hears something instead of dead air or a hangup.
    `ask_fn`/`msg_fn` are main.ask/main._msg, passed in rather than imported
    at module scope to avoid a circular import (main.py imports this module
    to register the routes below).
    """
    def _finish(text: str) -> None:
        wav = _synthesize(text, lang)
        if wav is not None:
            _cache_put(call_sid, wav)
        else:
            _LOG.warning(
                "IVR: TTS unavailable for call %s (lang=%s) — no answer to play", call_sid, lang,
            )

    audio = _download_recording(recording_url)
    if audio is None:
        _finish(msg_fn("no_data", lang))
        return

    audio_b64 = base64.b64encode(audio).decode("ascii")
    transcript = bhashini.speech_to_text(audio_b64, lang, IVR_SAMPLING_RATE)
    if not transcript:
        _finish(msg_fn("voice_unavailable", lang))
        return

    try:
        outcome = ask_fn(text=transcript, lang=lang, city=None, token=None)
    except Exception as exc:  # ask() must never take the call down with it
        _LOG.warning("IVR: ask() raised for call %s (%s)", call_sid, exc)
        _finish(msg_fn("no_data", lang))
        return

    answer_text = outcome.get("response") or outcome.get("message") or msg_fn("no_data", lang)
    _finish(answer_text)


_MENU_TEXT = {
    "en": "For English, press 1.",
    "hi": "हिन्दी के लिए 2 दबाएँ।",  # TODO: native_qa
    "ta": "தமிழுக்கு 3-ஐ அழுத்தவும்.",  # TODO: native_qa
    "te": "తెలుగు కోసం 4 నొక్కండి.",  # TODO: native_qa
    "mr": "मराठीसाठी 5 दाबा.",  # TODO: native_qa
}
_menu_cache: bytes | None = None


def _wav_data_chunk(wav_bytes: bytes) -> tuple[bytes, bytes] | None:
    """Returns (fmt_chunk_bytes, data_chunk_bytes) for a well-formed RIFF/WAVE
    file, else None. Used to concatenate the five per-language menu clips
    into one file without re-encoding."""
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return None
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = int.from_bytes(wav_bytes[pos + 4:pos + 8], "little")
        body_start = pos + 8
        if chunk_id == b"fmt ":
            fmt = wav_bytes[body_start:body_start + chunk_size]
        elif chunk_id == b"data":
            data = wav_bytes[body_start:body_start + chunk_size]
        pos = body_start + chunk_size + (chunk_size % 2)
    if fmt is None or data is None:
        return None
    return fmt, data


def _build_menu_wav() -> bytes | None:
    """Synthesizes and concatenates the five-language menu prompt. Bhashini's
    TTS is called once per language every time this needs (re)building, not
    per request — the result is cached in `_menu_cache` for the process
    lifetime once it succeeds. Assumes every language's clip shares the same
    PCM format (bhashini.text_to_speech already normalizes to 16-bit PCM);
    a mismatched one is skipped with a warning rather than corrupting the mix."""
    import struct

    fmt_ref: bytes | None = None
    data_parts: list[bytes] = []
    for lang in ("en", "hi", "ta", "te", "mr"):
        wav = _synthesize(_MENU_TEXT[lang], lang)
        if wav is None:
            _LOG.warning("IVR: menu TTS failed for lang=%s — omitted from the prompt", lang)
            continue
        parsed = _wav_data_chunk(wav)
        if parsed is None:
            continue
        fmt, data = parsed
        if fmt_ref is None:
            fmt_ref = fmt
        elif fmt != fmt_ref:
            _LOG.warning("IVR: menu clip for lang=%s has a different format — omitted", lang)
            continue
        data_parts.append(data)

    if fmt_ref is None or not data_parts:
        return None

    pcm = b"".join(data_parts)
    header = struct.pack("<4sI4s", b"RIFF", 36 + len(pcm), b"WAVE") \
        + struct.pack("<4sI", b"fmt ", len(fmt_ref)) + fmt_ref \
        + struct.pack("<4sI", b"data", len(pcm))
    return header + pcm


def menu_wav() -> bytes | None:
    global _menu_cache
    if _menu_cache is None:
        _menu_cache = _build_menu_wav()
    return _menu_cache


def mount(app: FastAPI, ask_fn, msg_fn) -> None:
    """Registers the IVR routes on `app`. No-op if IVR_ENABLED is unset, so a
    repo clone with no Exotel account configured doesn't expose them."""
    if not config.IVR_ENABLED:
        return
    if not config.IVR_WEBHOOK_SECRET:
        _LOG.error(
            "IVR_ENABLED is set but IVR_WEBHOOK_SECRET is empty - IVR routes NOT mounted. "
            "Set IVR_WEBHOOK_SECRET to enable the IVR channel."
        )
        return

    @app.get("/ivr/menu.wav")
    def ivr_menu(key: str | None = None):
        _check_secret(key)
        wav = menu_wav()
        if wav is None:
            raise HTTPException(status_code=503, detail="menu audio unavailable")
        return Response(content=wav, media_type="audio/wav")

    @app.post("/ivr/recording")
    def ivr_recording(
        CallSid: str = Form(...),
        RecordingUrl: str = Form(...),
        Digits: str = Form(""),
        key: str | None = None,
    ):
        _check_secret(key)
        lang = LANG_DIGITS.get(Digits.strip(), DEFAULT_LANG)
        process_recording(CallSid, lang, RecordingUrl, ask_fn, msg_fn)
        return {"status": "ok"}

    @app.get("/ivr/answer/{call_sid}.wav")
    def ivr_answer(call_sid: str, key: str | None = None):
        _check_secret(key)
        wav = _cache_get(call_sid)
        if wav is None:
            raise HTTPException(status_code=404, detail="no answer cached for this call yet")
        return Response(content=wav, media_type="audio/wav")
