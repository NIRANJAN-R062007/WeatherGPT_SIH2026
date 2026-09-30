"""ivr.py: the IVR channel's ASR->ask->TTS chain and answer-audio cache
(plan.md §8 Phase 4). Unit-tests the module's functions directly rather than
through FastAPI routes, since ivr.mount() registers routes at import time
based on config.IVR_ENABLED — a flag this suite can't retroactively flip
after `main` has already been imported by another test module. Network is
blocked by conftest, so every httpx call here is mocked directly.
"""

import base64
import socket
import struct

import config
import httpx
import ivr
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def _wav_bytes(pcm: bytes = b"\x00\x01\x02\x03", sample_rate: int = 8000) -> bytes:
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16)
    return (
        struct.pack("<4sI4s", b"RIFF", 36 + len(pcm), b"WAVE")
        + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
        + struct.pack("<4sI", b"data", len(pcm)) + pcm
    )


class _Resp:
    def __init__(self, content: bytes, status: int = 200, headers: dict | None = None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def iter_bytes(self, chunk_size: int = 65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stream(resp_or_fn, seen: dict | None = None):
    """Stand-in for httpx.stream returning a canned _Resp (or calling a fn)."""
    def _s(method, url, **k):
        if seen is not None:
            seen["url"], seen["kwargs"] = url, k
        if isinstance(resp_or_fn, BaseException):
            raise resp_or_fn
        return resp_or_fn
    return _s


def _dns(monkeypatch, *addrs):
    def _gai(host, port, *a, **k):
        return [(socket.AF_INET6 if ":" in ad else socket.AF_INET, 0, 0, "", (ad, 0))
                for ad in addrs]
    monkeypatch.setattr(socket, "getaddrinfo", _gai)


_GOOD_URL = "https://recordings.exotel.com/rec.wav"


@pytest.fixture(autouse=True)
def _public_dns_by_default(monkeypatch):
    _dns(monkeypatch, "93.184.216.34")


# ---- _check_secret ----------------------------------------------------------

def test_check_secret_fails_closed_when_unset(monkeypatch):
    # Behaviour intentionally changed: an unset secret used to be a no-op.
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", None)
    for key in (None, "", "anything"):
        with pytest.raises(HTTPException) as exc:
            ivr._check_secret(key)
        assert exc.value.status_code == 403


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
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(b"ID3not a wav")))
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_returns_wav_bytes(monkeypatch):
    wav = _wav_bytes()
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(wav)))
    assert ivr._download_recording(_GOOD_URL) == wav


def test_download_recording_none_on_http_error(monkeypatch):
    monkeypatch.setattr(httpx, "stream", _stream(httpx.ConnectError("down")))
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_uses_exotel_basic_auth_for_allowlisted_host(monkeypatch):
    monkeypatch.setattr(config, "EXOTEL_API_KEY", "key123")
    monkeypatch.setattr(config, "EXOTEL_API_TOKEN", "tok456")
    seen = {}
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(_wav_bytes()), seen))
    assert ivr._download_recording(_GOOD_URL) is not None
    assert seen["kwargs"]["auth"] == ("key123", "tok456")
    assert seen["kwargs"]["follow_redirects"] is False


def test_download_recording_sends_no_credentials_to_non_allowlisted_host(monkeypatch):
    monkeypatch.setattr(config, "EXOTEL_API_KEY", "key123")
    monkeypatch.setattr(config, "EXOTEL_API_TOKEN", "tok456")
    called = []
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: called.append(k) or _Resp(_wav_bytes()))
    assert ivr._download_recording("https://attacker.example/rec.wav") is None
    assert called == []  # never even contacted


@pytest.mark.parametrize("url", [
    "https://exotel.com.attacker.example/rec.wav",   # allowlisted name as a prefix
    "https://attacker.example/exotel.com/rec.wav",   # ...in the path
    "https://notexotel.com/rec.wav",                 # substring, not dot-suffix
    "https://exotel.com@attacker.example/rec.wav",   # userinfo trick
    "https://exotel.com:pw@exotel.com/rec.wav",      # embedded credentials
])
def test_download_recording_allowlist_is_exact_or_dot_suffix(monkeypatch, url):
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(_wav_bytes())))
    assert ivr._download_recording(url) is None


def test_download_recording_accepts_exact_and_subdomain_hosts(monkeypatch):
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(_wav_bytes())))
    assert ivr._download_recording("https://exotel.com/r.wav") is not None
    assert ivr._download_recording("https://a.b.exotel.com/r.wav") is not None


def test_download_recording_rejects_http(monkeypatch):
    called = []
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: called.append(1) or _Resp(_wav_bytes()))
    assert ivr._download_recording("http://recordings.exotel.com/rec.wav") is None
    assert called == []


@pytest.mark.parametrize("addr", [
    "127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.9", "169.254.169.254",
    "224.0.0.1", "240.0.0.1", "0.0.0.0", "::1", "fe80::1", "fc00::1", "ff02::1",
    "::ffff:127.0.0.1",
])
def test_download_recording_rejects_non_public_resolution(monkeypatch, addr):
    _dns(monkeypatch, addr)
    called = []
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: called.append(1) or _Resp(_wav_bytes()))
    assert ivr._download_recording(_GOOD_URL) is None
    assert called == []


def test_download_recording_rejects_if_any_resolved_address_is_private(monkeypatch):
    _dns(monkeypatch, "93.184.216.34", "10.0.0.1")
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(_wav_bytes())))
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_rejects_unresolvable_host(monkeypatch):
    def _fail(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_does_not_follow_redirects(monkeypatch):
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(b"", status=302)))
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_refuses_oversized_body(monkeypatch):
    monkeypatch.setattr(config, "IVR_MAX_RECORDING_BYTES", 1000)
    big = _wav_bytes(pcm=b"\x00" * 5000)
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(big)))
    assert ivr._download_recording(_GOOD_URL) is None


def test_download_recording_refuses_oversized_declared_length(monkeypatch):
    monkeypatch.setattr(config, "IVR_MAX_RECORDING_BYTES", 1000)
    resp = _Resp(_wav_bytes(), headers={"content-length": "999999"})
    monkeypatch.setattr(httpx, "stream", _stream(resp))
    assert ivr._download_recording(_GOOD_URL) is None


def test_insecure_override_allows_http_loopback_but_never_sends_credentials(monkeypatch):
    monkeypatch.setattr(config, "IVR_ALLOW_INSECURE_RECORDING_URLS", True)
    monkeypatch.setattr(config, "EXOTEL_API_KEY", "key123")
    monkeypatch.setattr(config, "EXOTEL_API_TOKEN", "tok456")
    seen = {}
    monkeypatch.setattr(httpx, "stream", _stream(_Resp(_wav_bytes()), seen))
    assert ivr._download_recording("http://127.0.0.1:9999/rec.wav") is not None
    assert seen["kwargs"]["auth"] is None


def test_insecure_override_is_off_by_default():
    assert config.IVR_ALLOW_INSECURE_RECORDING_URLS is False


def test_download_recording_does_not_log_full_url(monkeypatch, caplog):
    url = "https://attacker.example/secret-path/rec.wav?token=abc123"
    with caplog.at_level("WARNING", logger="weathergpt.ivr"):
        ivr._download_recording(url)
    assert "abc123" not in caplog.text and "secret-path" not in caplog.text
    assert "attacker.example" in caplog.text


# ---- mount / routes -------------------------------------------------------------

def _mounted_app(monkeypatch, enabled=True, secret="s3cr3t"):
    monkeypatch.setattr(config, "IVR_ENABLED", enabled)
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", secret)
    app = FastAPI()
    ivr.mount(app, lambda **k: {}, lambda key, lang: "")
    return app


@pytest.mark.parametrize("secret", [None, ""])
def test_mount_skips_routes_when_enabled_without_secret(monkeypatch, caplog, secret):
    with caplog.at_level("ERROR", logger="weathergpt.ivr"):
        app = _mounted_app(monkeypatch, secret=secret)
    assert not [r for r in app.routes if getattr(r, "path", "").startswith("/ivr")]
    assert "IVR_WEBHOOK_SECRET" in caplog.text


def test_mount_registers_routes_with_secret(monkeypatch):
    app = _mounted_app(monkeypatch)
    assert "/ivr/recording" in {r.path for r in app.routes}


def test_mount_noop_when_disabled(monkeypatch):
    app = _mounted_app(monkeypatch, enabled=False)
    assert not [r for r in app.routes if getattr(r, "path", "").startswith("/ivr")]


def test_routes_return_403_for_wrong_or_missing_key(monkeypatch):
    client = TestClient(_mounted_app(monkeypatch))
    data = {"CallSid": "CA1", "RecordingUrl": _GOOD_URL}
    assert client.post("/ivr/recording", params={"key": "wrong"}, data=data).status_code == 403
    assert client.post("/ivr/recording", data=data).status_code == 403
    assert client.get("/ivr/answer/CA1.wav", params={"key": "wrong"}).status_code == 403
    assert client.get("/ivr/menu.wav").status_code == 403


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


def test_answer_cache_is_bounded_and_evicts_oldest(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(config, "IVR_ANSWER_CACHE_MAX", 3)
    for i in range(6):
        ivr._cache_put(f"CA{i}", b"w")
    assert len(ivr._answer_cache) == 3
    assert list(ivr._answer_cache) == ["CA3", "CA4", "CA5"]
    assert ivr._cache_get("CA0") is None
    assert ivr._cache_get("CA5") == b"w"


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
