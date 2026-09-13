"""translate_to_tamil(): returns the translated string on success, None on
anything else, and never raises. Network is blocked by conftest, so every
"success" path here mocks httpx.post directly.
"""

import base64
import struct

import bhashini
import config
import httpx
import pytest


def _pipeline_response():
    return {
        "pipelineInferenceAPIEndPoint": {
            "inferenceApiKey": {"name": "Authorization", "value": "Bearer xyz"},
        },
        "pipelineResponseConfig": [{"config": [{"serviceId": "ai4bharat/x"}]}],
    }


def _compute_response(text: str):
    return {"pipelineResponse": [{"output": [{"target": text}]}]}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_offline_mode_disables_bhashini_even_with_credentials(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(config, "OFFLINE_MODE", True)

    def _boom(*a, **k):
        raise AssertionError("httpx.post was called while OFFLINE_MODE")

    monkeypatch.setattr(httpx, "post", _boom)
    assert bhashini.is_configured() is False
    assert bhashini.translate_to_tamil("x") is None


def test_no_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", None)
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", None)
    assert bhashini.translate_to_tamil("hello") is None


def test_empty_text_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    assert bhashini.translate_to_tamil("") is None


def test_happy_path(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    calls = []

    def _post(url, **kw):
        calls.append(url)
        if url == bhashini.CONFIG_URL:
            return _Resp(_pipeline_response())
        return _Resp(_compute_response("சென்னை: 28°C."))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.translate_to_tamil("Chennai: 28°C.") == "சென்னை: 28°C."
    assert calls == [bhashini.CONFIG_URL, bhashini.COMPUTE_URL]


def test_pipeline_is_cached_across_calls(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    config_calls = []

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            config_calls.append(1)
            return _Resp(_pipeline_response())
        return _Resp(_compute_response("x"))

    monkeypatch.setattr(httpx, "post", _post)
    bhashini.translate_to_tamil("a")
    bhashini.translate_to_tamil("b")
    assert len(config_calls) == 1


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("t"), httpx.ConnectError("c")])
def test_http_error_returns_none(monkeypatch, caplog, exc):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(exc))
    with caplog.at_level("WARNING"):
        assert bhashini.translate_to_tamil("hello") is None
    assert any("bhashini translation failed" in r.message for r in caplog.records)


def test_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp({"unexpected": True}))
    assert bhashini.translate_to_tamil("hello") is None


def test_empty_target_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_pipeline_response())
        return _Resp(_compute_response(""))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.translate_to_tamil("hello") is None


# --- Udyat credential shape: ulcaApiKey alone on config, inference key on compute ---

def _udyat_pipeline_response():
    # no pipelineInferenceAPIEndPoint block at all — matches the real response
    return {"pipelineResponseConfig": [{"config": [{"serviceId": "ai4bharat/x"}]}]}


def _udyat_creds(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", None)
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "udyat-key")
    monkeypatch.setattr(config, "BHASHINI_INFERENCE_KEY", "inference-key")
    bhashini.cache_clear()


def test_udyat_is_configured_without_user_id(monkeypatch):
    _udyat_creds(monkeypatch)
    assert bhashini.is_configured()
    monkeypatch.setattr(config, "BHASHINI_INFERENCE_KEY", None)
    assert not bhashini.is_configured()  # ulcaApiKey alone is not enough


def test_udyat_uses_inference_key_as_authorization(monkeypatch):
    _udyat_creds(monkeypatch)
    seen = []

    def _post(url, **kw):
        seen.append((url, kw["headers"]))
        if url == bhashini.CONFIG_URL:
            return _Resp(_udyat_pipeline_response())
        return _Resp(_compute_response("சென்னை: 28 டிகிரி செல்சியஸ்."))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.translate_to_tamil("Chennai: 28°C.") == "சென்னை: 28 டிகிரி செல்சியஸ்."
    cfg_headers, compute_headers = seen[0][1], seen[1][1]
    assert "userID" not in cfg_headers and cfg_headers["ulcaApiKey"] == "udyat-key"
    assert compute_headers["Authorization"] == "inference-key"


def test_config_without_inference_key_and_no_udyat_key_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(config, "BHASHINI_INFERENCE_KEY", None)
    bhashini.cache_clear()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(_udyat_pipeline_response()))
    assert bhashini.translate_to_tamil("Chennai: 28°C.") is None  # no key anywhere -> fallback


# --- speech_to_text (ASR) ---

def _asr_pipeline_response():
    return {
        "pipelineInferenceAPIEndPoint": {
            "inferenceApiKey": {"name": "Authorization", "value": "Bearer xyz"},
        },
        "pipelineResponseConfig": [{"config": [{"serviceId": "ai4bharat/asr"}]}],
    }


def _asr_compute_response(transcript: str):
    return {"pipelineResponse": [{"output": [{"source": transcript}]}]}


def test_asr_no_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", None)
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", None)
    assert bhashini.speech_to_text("base64audio", "en") is None


def test_asr_no_audio_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    assert bhashini.speech_to_text("", "en") is None


def test_asr_happy_path(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    seen = []

    def _post(url, **kw):
        seen.append((url, kw.get("json")))
        if url == bhashini.CONFIG_URL:
            return _Resp(_asr_pipeline_response())
        return _Resp(_asr_compute_response("what's the weather in chennai"))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.speech_to_text("base64wav", "en") == "what's the weather in chennai"
    compute_body = seen[1][1]
    assert compute_body["inputData"]["audio"][0]["audioContent"] == "base64wav"
    assert compute_body["inputData"]["config"]["samplingRate"] == 16000


def test_asr_pipeline_is_cached_per_language(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    config_calls = []

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            config_calls.append(1)
            return _Resp(_asr_pipeline_response())
        return _Resp(_asr_compute_response("x"))

    monkeypatch.setattr(httpx, "post", _post)
    bhashini.speech_to_text("a", "en")
    bhashini.speech_to_text("b", "en")
    bhashini.speech_to_text("c", "ta")  # different language -> separate cache slot
    assert len(config_calls) == 2


def test_asr_http_error_returns_none(monkeypatch, caplog):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("t")))
    with caplog.at_level("WARNING"):
        assert bhashini.speech_to_text("base64wav", "en") is None
    assert any("bhashini ASR failed" in r.message for r in caplog.records)


def test_asr_empty_transcript_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_asr_pipeline_response())
        return _Resp(_asr_compute_response(""))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.speech_to_text("base64wav", "en") is None


# --- text_to_speech (TTS) ---

def _tts_pipeline_response():
    return {
        "pipelineInferenceAPIEndPoint": {
            "inferenceApiKey": {"name": "Authorization", "value": "Bearer xyz"},
        },
        "pipelineResponseConfig": [{"config": [{"serviceId": "ai4bharat/tts"}]}],
    }


def _tts_compute_response(audio_b64: str):
    return {"pipelineResponse": [{"audio": [{"audioContent": audio_b64}]}]}


def test_tts_no_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", None)
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", None)
    assert bhashini.text_to_speech("hello", "en") is None


def test_tts_no_text_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    assert bhashini.text_to_speech("", "en") is None


def test_tts_happy_path(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_tts_pipeline_response())
        return _Resp(_tts_compute_response("UklGRi4="))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.text_to_speech("Chennai: 28°C.", "en") == "UklGRi4="


def test_tts_pipeline_is_cached_per_language(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    config_calls = []

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            config_calls.append(1)
            return _Resp(_tts_pipeline_response())
        return _Resp(_tts_compute_response("x"))

    monkeypatch.setattr(httpx, "post", _post)
    bhashini.text_to_speech("a", "en")
    bhashini.text_to_speech("b", "en")
    assert len(config_calls) == 1


def test_tts_http_error_returns_none(monkeypatch, caplog):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("c")))
    with caplog.at_level("WARNING"):
        assert bhashini.text_to_speech("hello", "en") is None
    assert any("bhashini TTS failed" in r.message for r in caplog.records)


def test_tts_empty_audio_returns_none(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_tts_pipeline_response())
        return _Resp(_tts_compute_response(""))

    monkeypatch.setattr(httpx, "post", _post)
    assert bhashini.text_to_speech("hello", "en") is None


# --- WAV re-encode to PCM16 (Chrome hangs decoding Bhashini's 32-bit float WAV) ---

def _build_wav(audio_format, bits_per_sample, channels, sample_rate, data: bytes) -> str:
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16, audio_format, channels, sample_rate,
        byte_rate, block_align, bits_per_sample,
        b"data", len(data),
    )
    return base64.b64encode(header + data).decode("ascii")


def _wav_format(audio_b64: str):
    raw = base64.b64decode(audio_b64)
    return struct.unpack_from("<HHIIHH", raw, 20)  # fmt, channels, rate, byte_rate, align, bits


def test_wav_pcm16_passes_through_unchanged():
    data = struct.pack("<3h", 100, -100, 32000)
    wav = _build_wav(1, 16, 1, 16000, data)
    assert bhashini._wav_to_pcm16_base64(wav) == wav


def test_wav_float32_converted_to_pcm16():
    samples = [0.0, 1.0, -1.0, 0.5]
    data = struct.pack("<4f", *samples)
    wav = _build_wav(3, 32, 1, 22050, data)
    out = bhashini._wav_to_pcm16_base64(wav)
    fmt, channels, rate, _byte_rate, _align, bits = _wav_format(out)
    assert (fmt, bits, channels, rate) == (1, 16, 1, 22050)
    pcm = struct.unpack_from("<4h", base64.b64decode(out), 44)
    assert pcm == (0, 32767, -32767, 16384)


def test_wav_8bit_pcm_converted_to_pcm16():
    wav = _build_wav(1, 8, 1, 8000, bytes([128, 255, 0]))  # silence, max, min
    out = bhashini._wav_to_pcm16_base64(wav)
    fmt, _channels, _rate, _byte_rate, _align, bits = _wav_format(out)
    assert (fmt, bits) == (1, 16)
    pcm = struct.unpack_from("<3h", base64.b64decode(out), 44)
    assert pcm == (0, 32512, -32768)


def test_wav_non_riff_passed_through():
    not_wav = base64.b64encode(b"not a wav file").decode("ascii")
    assert bhashini._wav_to_pcm16_base64(not_wav) == not_wav


def test_wav_malformed_base64_falls_back_without_raising():
    assert bhashini._wav_to_pcm16_base64("not-valid-base64!!") == "not-valid-base64!!"


def test_tts_applies_pcm16_conversion(monkeypatch):
    monkeypatch.setattr(config, "BHASHINI_USER_ID", "u")
    monkeypatch.setattr(config, "BHASHINI_ULCA_API_KEY", "k")
    float_wav = _build_wav(3, 32, 1, 22050, struct.pack("<2f", 0.0, 1.0))

    def _post(url, **kw):
        if url == bhashini.CONFIG_URL:
            return _Resp(_tts_pipeline_response())
        return _Resp(_tts_compute_response(float_wav))

    monkeypatch.setattr(httpx, "post", _post)
    out = bhashini.text_to_speech("hello", "en")
    fmt, _channels, _rate, _byte_rate, _align, bits = _wav_format(out)
    assert (fmt, bits) == (1, 16)
