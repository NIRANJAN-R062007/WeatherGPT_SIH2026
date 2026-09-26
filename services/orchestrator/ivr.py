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
import logging
import time

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
    _answer_cache[call_sid] = (time.monotonic() + config.IVR_ANSWER_TTL_SECONDS, wav_bytes)
    _cache_sweep()


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
    audio. If IVR_WEBHOOK_SECRET is unset, this is a no-op — fine for local
    dev against a tunnel nobody else has the URL for, never for a public
    deploy; config.py's docstring says so."""
    if config.IVR_WEBHOOK_SECRET and key != config.IVR_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad or missing key")


def _download_recording(url: str) -> bytes | None:
    """Fetch Exotel's RecordingUrl. Exotel recording URLs need the account's
    own Basic Auth (EXOTEL_SID/EXOTEL_TOKEN) to fetch, same credentials used
    to place calls via their REST API. Only a WAV response (RIFF/WAVE header)
    is usable — see the module docstring's MP3 gap; anything else returns
    None so the caller falls back to the "no data" answer rather than
    silently feeding Bhashini bytes it can't parse."""
    have_creds = config.EXOTEL_SID and config.EXOTEL_TOKEN
    auth = (config.EXOTEL_SID, config.EXOTEL_TOKEN) if have_creds else None
    try:
        resp = httpx.get(url, auth=auth, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        _LOG.warning("IVR: failed to download recording %s (%s)", url, exc)
        return None
    body = resp.content
    if body[:4] != b"RIFF" or body[8:12] != b"WAVE":
        _LOG.warning(
            "IVR: recording at %s is not WAV (got %r) — MP3 transcoding isn't wired up yet",
            url, body[:12],
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
