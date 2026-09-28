"""Local simulated call through the IVR routes (plan.md Phase 7 B3) — runs
the whole ivr.py call flow with no Exotel account, and labels every output
as simulated. — **Niranjan**

What Exotel's dashboard call flow would do (see ivr.py's module docstring),
this script does itself, against the *same* route handlers ivr.mount()
registers — nothing in ivr.py is stubbed or bypassed:

    Gather   -> GET  /ivr/menu.wav                  (saved, not played)
    Record   -> the question WAV (--wav, or --text synthesized via Bhashini
                TTS), downsampled to 8kHz mono 16-bit to match Exotel's
                telephony recordings (ivr.IVR_SAMPLING_RATE), then served
                from a throwaway 127.0.0.1 HTTP server as the RecordingUrl
    Passthru -> POST /ivr/recording                 (CallSid, Digits, RecordingUrl)
    Greeting -> GET  /ivr/answer/{CallSid}.wav      (saved)

By default the routes run in-process on a fresh FastAPI app (IVR_ENABLED is
forced on for that app only, so .env doesn't need it). `--base-url` instead
drives an already-running orchestrator over HTTP — that server must have
IVR_ENABLED set and be on this machine (it has to reach the 127.0.0.1
recording server).

Still needs working Bhashini credentials (ASR + TTS are real calls) — the
only thing simulated is the telephony side. What's simulated is marked
everywhere it lands: the CallSid starts with "SIM-", every file name starts
with "SIMULATED_", every WAV carries a RIFF INFO comment with SIM_LABEL, the
manifest JSON has "simulated": true, and every console line is prefixed.

    cd services/orchestrator
    ../../.venv/bin/python ivr_simulate.py --text "Will it rain in Chennai today?" --lang en
    ../../.venv/bin/python ivr_simulate.py --wav question.wav --lang ta
"""

import argparse
import array
import base64
import http.server
import json
import struct
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bhashini
import config
import httpx
import ivr
from fastapi import FastAPI

SIM_LABEL = "SIMULATED CALL - local IVR simulation, no live Exotel account or phone call"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "ivr-sim-output"
_LANG_TO_DIGIT = {lang: digit for digit, lang in ivr.LANG_DIGITS.items()}


def _say(line: str) -> None:
    print(f"[SIMULATED] {line}")


# ---- WAV helpers ---------------------------------------------------------------

def _parse_pcm16(wav_bytes: bytes) -> tuple[int, int, bytes]:
    """(channels, sample_rate, pcm) for a 16-bit PCM WAV. Raises ValueError
    otherwise — Bhashini's TTS output is already normalized to this, and a
    --wav from anywhere else should be converted first (e.g. `ffmpeg -i in.m4a
    -ac 1 -ar 8000 -sample_fmt s16 out.wav`)."""
    parsed = ivr._wav_data_chunk(wav_bytes)
    if parsed is None:
        raise ValueError("not a RIFF/WAVE file")
    fmt, pcm = parsed
    audio_format, channels, sample_rate, _, _, bits = struct.unpack("<HHIIHH", fmt[:16])
    if audio_format != 1 or bits != 16:
        raise ValueError(f"need 16-bit PCM, got format={audio_format} bits={bits}")
    return channels, sample_rate, pcm


def _pcm16_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, sample_rate * channels * 2,
                      channels * 2, 16)
    return (
        struct.pack("<4sI4s", b"RIFF", 36 + len(pcm), b"WAVE")
        + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
        + struct.pack("<4sI", b"data", len(pcm)) + pcm
    )


def to_telephony_wav(wav_bytes: bytes) -> bytes:
    """Downmix to mono and linearly resample to ivr.IVR_SAMPLING_RATE, so the
    ASR call sees what a real Exotel recording would give it (and the 8kHz
    sampling_rate process_recording declares is actually true)."""
    channels, rate, pcm = _parse_pcm16(wav_bytes)
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    if channels > 1:
        samples = array.array("h", (
            sum(samples[i:i + channels]) // channels
            for i in range(0, len(samples) - channels + 1, channels)
        ))
    target = ivr.IVR_SAMPLING_RATE
    if rate != target and len(samples) > 1:
        n_out = max(1, len(samples) * target // rate)
        step = (len(samples) - 1) / max(1, n_out - 1)
        out = array.array("h")
        for i in range(n_out):
            pos = i * step
            lo = int(pos)
            hi = min(lo + 1, len(samples) - 1)
            frac = pos - lo
            out.append(int(samples[lo] + (samples[hi] - samples[lo]) * frac))
        samples = out
    if sys.byteorder == "big":
        samples.byteswap()
    return _pcm16_wav(samples.tobytes(), target)


def tag_simulated(wav_bytes: bytes, label: str = SIM_LABEL) -> bytes:
    """Appends a RIFF LIST/INFO chunk (ICMT comment + INAM title) carrying
    `label`, so the audio file itself says it's simulated — visible in any
    player/`ffprobe` that shows metadata, and ignored by anything that only
    reads fmt/data. Non-WAV bytes are returned unchanged."""
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return wav_bytes

    def _sub(chunk_id: bytes, text: str) -> bytes:
        body = text.encode("utf-8") + b"\x00"
        if len(body) % 2:
            body += b"\x00"
        return chunk_id + struct.pack("<I", len(body)) + body

    info = b"INFO" + _sub(b"INAM", "SIMULATED") + _sub(b"ICMT", label)
    list_chunk = b"LIST" + struct.pack("<I", len(info)) + info
    body = wav_bytes[12:] + list_chunk
    return struct.pack("<4sI4s", b"RIFF", 4 + len(body), b"WAVE") + body


# ---- the fake RecordingUrl ---------------------------------------------------------

class _RecordingServer:
    """Serves one WAV at http://127.0.0.1:<port>/<name> for the lifetime of the
    `with` block — stands in for Exotel's RecordingUrl."""

    def __init__(self, wav_bytes: bytes, name: str):
        payload, path = wav_bytes, f"/{name}"

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path.split("?")[0] != path:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}{path}"

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


# ---- the call -----------------------------------------------------------------

def build_app(ask_fn, msg_fn) -> FastAPI:
    """A fresh app with only the IVR routes mounted, IVR_ENABLED forced on for
    the mount — the same handlers main.py registers when the flag is set."""
    app = FastAPI(title="WeatherGPT IVR simulation")
    enabled = config.IVR_ENABLED
    config.IVR_ENABLED = True
    try:
        ivr.mount(app, ask_fn, msg_fn)
    finally:
        config.IVR_ENABLED = enabled
    return app


class _Taps:
    """Records what the in-process call sent through Bhashini, without changing
    it — ivr.py looks up bhashini.speech_to_text/text_to_speech at call time,
    so wrapping the module attributes sees every call."""

    def __init__(self):
        self.transcript: str | None = None
        self.tts_texts: list[str] = []

    def __enter__(self):
        self._stt, self._tts = bhashini.speech_to_text, bhashini.text_to_speech

        def stt(*a, **k):
            self.transcript = self._stt(*a, **k)
            return self.transcript

        def tts(text, lang):
            self.tts_texts.append(text)
            return self._tts(text, lang)

        bhashini.speech_to_text, bhashini.text_to_speech = stt, tts
        return self

    def __exit__(self, *exc):
        bhashini.speech_to_text, bhashini.text_to_speech = self._stt, self._tts


def simulate_call(client, question_wav: bytes, lang: str, out_dir: Path,
                  key: str | None = None, tap: bool = True) -> dict:
    """Walks one call through the IVR routes via `client` (a TestClient or an
    httpx.Client with base_url) and writes SIMULATED_* files + a manifest to
    out_dir/<CallSid>/. Returns the manifest."""
    call_sid = f"SIM-{uuid.uuid4().hex[:12]}"
    call_dir = out_dir / call_sid
    call_dir.mkdir(parents=True, exist_ok=True)
    params = {"key": key} if key else {}
    manifest: dict = {
        "simulated": True,
        "label": SIM_LABEL,
        "call_sid": call_sid,
        "lang": lang,
        "digits": _LANG_TO_DIGIT[lang],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
        "files": {},
    }

    def _save(name: str, wav: bytes) -> None:
        path = call_dir / f"SIMULATED_{name}.wav"
        path.write_bytes(tag_simulated(wav))
        manifest["files"][name] = path.name

    def _step(applet: str, route: str, status: int, note: str = "") -> None:
        manifest["steps"].append({"applet": applet, "route": route, "status": status,
                                  **({"note": note} if note else {})})
        _say(f"{applet:<8} {route} -> {status}{f' ({note})' if note else ''}")

    _say(f"call {call_sid} lang={lang} (caller presses {manifest['digits']})")

    resp = client.get("/ivr/menu.wav", params=params)
    _step("Gather", "GET /ivr/menu.wav", resp.status_code)
    if resp.status_code == 200:
        _save("menu", resp.content)

    telephony = to_telephony_wav(question_wav)
    _save("question", telephony)
    _say(f"Record   question: {len(telephony)} bytes, 8kHz mono")

    taps = _Taps() if tap else None
    with _RecordingServer(telephony, f"{call_sid}.wav") as rec:
        if taps:
            taps.__enter__()
        try:
            resp = client.post(
                "/ivr/recording", params=params,
                data={"CallSid": call_sid, "Digits": manifest["digits"], "RecordingUrl": rec.url},
            )
        finally:
            if taps:
                taps.__exit__(None, None, None)
    _step("Passthru", "POST /ivr/recording", resp.status_code)
    if taps:
        manifest["transcript"] = taps.transcript
        manifest["answer_text"] = taps.tts_texts[-1] if taps.tts_texts else None
        _say(f"ASR      transcript: {taps.transcript!r}")
        _say(f"ask()    answer:     {manifest['answer_text']!r}")

    resp = client.get(f"/ivr/answer/{call_sid}.wav", params=params)
    _step("Greeting", f"GET /ivr/answer/{call_sid}.wav", resp.status_code,
          "" if resp.status_code == 200 else "no answer audio cached - TTS unavailable?")
    if resp.status_code == 200:
        _save("answer", resp.content)

    manifest["ok"] = "answer" in manifest["files"]
    manifest_path = call_dir / "SIMULATED_call.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _say(f"wrote {call_dir}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = parser.add_argument_group("question (one of)").add_mutually_exclusive_group(required=True)
    src.add_argument("--wav", type=Path, help="16-bit PCM WAV of the spoken question")
    src.add_argument("--text", help="question text, synthesized via Bhashini TTS in --lang")
    parser.add_argument("--lang", default=ivr.DEFAULT_LANG, choices=sorted(_LANG_TO_DIGIT))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--base-url", help="drive a running orchestrator instead of in-process")
    args = parser.parse_args(argv)

    _say(SIM_LABEL)
    if not bhashini.is_configured():
        _say("Bhashini credentials are not configured - ASR/TTS will fail; see .env.example")
        return 2

    if args.wav:
        question = args.wav.read_bytes()
    else:
        audio_b64 = bhashini.text_to_speech(args.text, args.lang)
        if audio_b64 is None:
            _say("Bhashini TTS failed to synthesize the --text question")
            return 2
        question = base64.b64decode(audio_b64)
    try:
        _parse_pcm16(question)
    except ValueError as exc:
        _say(f"question audio unusable: {exc}")
        return 2

    key = config.IVR_WEBHOOK_SECRET
    if args.base_url:
        with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
            manifest = simulate_call(client, question, args.lang, args.out, key, tap=False)
    else:
        import main as orchestrator  # heavy import; only needed in-process
        from fastapi.testclient import TestClient

        client = TestClient(build_app(orchestrator.ask, orchestrator._msg))
        manifest = simulate_call(client, question, args.lang, args.out, key)
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
