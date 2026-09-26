"""ivr.py: the IVR channel's ASR->ask->TTS chain and answer-audio cache
(plan.md §8 Phase 4). Unit-tests the module's functions directly rather than
through FastAPI routes, since ivr.mount() registers routes at import time
based on config.IVR_ENABLED — a flag this suite can't retroactively flip
after `main` has already been imported by another test module. Network is
blocked by conftest, so every httpx call here is mocked directly.
"""

import base64
import struct

import config
import httpx
import ivr
import pytest


def _wav_bytes(pcm: bytes = b"\x00\x01\x02\x03", sample_rate: int = 8000) -> bytes:
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16)
    return (
        struct.pack("<4sI4s", b"RIFF", 36 + len(pcm), b"WAVE")
        + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
        + struct.pack("<4sI", b"data", len(pcm)) + pcm
    )


class _Resp:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)


# ---- _check_secret ----------------------------------------------------------

def test_check_secret_noop_when_unset(monkeypatch):
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", None)
    ivr._check_secret(None)  # doesn't raise
    ivr._check_secret("anything")  # doesn't raise


def test_check_secret_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", "s3cr3t")
    with pytest.raises(Exception):
        ivr._check_secret("wrong")
    with pytest.raises(Exception):
        ivr._check_secret(None)


def test_check_secret_accepts_right_key(monkeypatch):
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", "s3cr3t")
    ivr._check_secret("s3cr3t")  # doesn't raise


# ---- _download_recording -----------------------------------------------------

def test_download_recording_rejects_non_wav(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(b"ID3not a wav"))
    assert ivr._download_recording("https://example.test/rec.mp3") is None


def test_download_recording_returns_wav_bytes(monkeypatch):
    wav = _wav_bytes()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(wav))
    assert ivr._download_recording("https://example.test/rec.wav") == wav


def test_download_recording_none_on_http_error(monkeypatch):
    def _raise(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx, "get", _raise)
    assert ivr._download_recording("https://example.test/rec.wav") is None


def test_download_recording_uses_exotel_basic_auth(monkeypatch):
    monkeypatch.setattr(config, "EXOTEL_SID", "sid123")
    monkeypatch.setattr(config, "EXOTEL_TOKEN", "tok456")
    seen = {}

    def _get(url, auth=None, timeout=None, follow_redirects=None):
        seen["auth"] = auth
        return _Resp(_wav_bytes())

    monkeypatch.setattr(httpx, "get", _get)
    ivr._download_recording("https://example.test/rec.wav")
    assert seen["auth"] == ("sid123", "tok456")


# ---- answer cache -------------------------------------------------------------

def test_answer_cache_round_trip():
    ivr._answer_cache.clear()
    ivr._cache_put("CA123", b"wavbytes")
    assert ivr._cache_get("CA123") == b"wavbytes"


def test_answer_cache_expires(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(config, "IVR_ANSWER_TTL_SECONDS", 0)
    ivr._cache_put("CA999", b"wavbytes")
    import time
    time.sleep(0.01)
    assert ivr._cache_get("CA999") is None


def test_answer_cache_missing_call_returns_none():
    ivr._answer_cache.clear()
    assert ivr._cache_get("never-existed") is None


# ---- process_recording ---------------------------------------------------------

def test_process_recording_caches_tts_for_ask_success(monkeypatch):
    ivr._answer_cache.clear()
    wav = _wav_bytes()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: wav)
    monkeypatch.setattr("bhashini.speech_to_text", lambda *a, **k: "will it rain in chennai")
    tts_wav = _wav_bytes(pcm=b"\x09\x08")
    monkeypatch.setattr(
        "bhashini.text_to_speech", lambda text, lang: base64.b64encode(tts_wav).decode(),
    )

    def _ask(text, lang, city, token):
        assert text == "will it rain in chennai"
        return {"response": "It will rain in Chennai today."}

    def _msg(key, lang):
        return f"[{key}:{lang}]"

    ivr.process_recording("CA1", "en", "https://example.test/rec.wav", _ask, _msg)
    assert ivr._cache_get("CA1") == tts_wav


def test_process_recording_falls_back_when_recording_unusable(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: None)
    tts_wav = _wav_bytes(pcm=b"\x0a")
    calls = []

    def _tts(text, lang):
        calls.append(text)
        return base64.b64encode(tts_wav).decode()

    monkeypatch.setattr("bhashini.text_to_speech", _tts)

    def _ask(**kw):
        raise AssertionError("ask() must not be called when there's no transcript")

    msg = lambda key, lg: f"[{key}:{lg}]"  # noqa: E731
    ivr.process_recording("CA2", "hi", "https://example.test/rec.mp3", _ask, msg)
    assert calls == ["[no_data:hi]"]
    assert ivr._cache_get("CA2") == tts_wav


def test_process_recording_falls_back_when_asr_empty(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: _wav_bytes())
    monkeypatch.setattr("bhashini.speech_to_text", lambda *a, **k: None)
    seen_text = []
    monkeypatch.setattr(
        "bhashini.text_to_speech",
        lambda text, lang: (seen_text.append(text), base64.b64encode(_wav_bytes()).decode())[1],
    )

    def _ask(**kw):
        raise AssertionError("ask() must not be called with no transcript")

    msg = lambda key, lg: f"[{key}:{lg}]"  # noqa: E731
    ivr.process_recording("CA3", "ta", "https://example.test/rec.wav", _ask, msg)
    assert seen_text == ["[voice_unavailable:ta]"]


def test_process_recording_survives_ask_raising(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: _wav_bytes())
    monkeypatch.setattr("bhashini.speech_to_text", lambda *a, **k: "some query")
    seen_text = []
    monkeypatch.setattr(
        "bhashini.text_to_speech",
        lambda text, lang: (seen_text.append(text), base64.b64encode(_wav_bytes()).decode())[1],
    )

    def _ask(**kw):
        raise RuntimeError("boom")

    msg = lambda key, lg: f"[{key}:{lg}]"  # noqa: E731
    ivr.process_recording("CA4", "en", "https://example.test/rec.wav", _ask, msg)
    assert seen_text == ["[no_data:en]"]


def test_process_recording_no_cached_audio_when_tts_unavailable(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_download_recording", lambda url: _wav_bytes())
    monkeypatch.setattr("bhashini.speech_to_text", lambda *a, **k: "query")
    monkeypatch.setattr("bhashini.text_to_speech", lambda *a, **k: None)

    msg = lambda key, lg: f"[{key}:{lg}]"  # noqa: E731
    ivr.process_recording(
        "CA5", "en", "https://example.test/rec.wav",
        lambda **kw: {"response": "answer"}, msg,
    )
    assert ivr._cache_get("CA5") is None


# ---- menu audio ---------------------------------------------------------------

def test_build_menu_wav_concatenates_same_format_clips(monkeypatch):
    clip = _wav_bytes(pcm=b"\x01\x02", sample_rate=8000)

    def _synth(text, lang):
        return clip

    monkeypatch.setattr(ivr, "_synthesize", _synth)
    result = ivr._build_menu_wav()
    assert result is not None
    parsed = ivr._wav_data_chunk(result)
    assert parsed is not None
    _, data = parsed
    assert data == b"\x01\x02" * 5  # one clip per LANG_DIGITS entry


def test_build_menu_wav_none_when_all_synthesis_fails(monkeypatch):
    monkeypatch.setattr(ivr, "_synthesize", lambda text, lang: None)
    assert ivr._build_menu_wav() is None


def test_menu_wav_caches_result(monkeypatch):
    ivr._menu_cache = None
    calls = []

    def _synth(text, lang):
        calls.append(lang)
        return _wav_bytes()

    monkeypatch.setattr(ivr, "_synthesize", _synth)
    first = ivr.menu_wav()
    second = ivr.menu_wav()
    assert first is second
    assert len(calls) == 5  # only built once, not once per menu_wav() call
    ivr._menu_cache = None  # don't leak into other tests
