"""ivr_simulate.py: the local simulated-call path through the IVR routes
(plan.md Phase 7 B3). Bhashini is mocked; the recording download goes
through the simulator's real 127.0.0.1 server via urllib, since conftest's
kill switch blocks httpx's transport."""

import base64
import json
import struct
import urllib.request

import bhashini
import config
import httpx
import ivr
import ivr_simulate
import pytest
from fastapi.testclient import TestClient


def _wav(pcm: bytes, rate: int, channels: int = 1) -> bytes:
    return ivr_simulate._pcm16_wav(pcm, rate, channels)


class _Resp:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def fake_call(monkeypatch):
    ivr._answer_cache.clear()
    monkeypatch.setattr(ivr, "_menu_cache", None)
    monkeypatch.setattr(config, "IVR_WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(
        httpx, "get", lambda url, **k: _Resp(urllib.request.urlopen(url).read()),
    )
    seen = {"asr": []}

    def _stt(audio_b64, lang, sampling_rate=16000):
        seen["asr"].append((base64.b64decode(audio_b64), lang, sampling_rate))
        return "will it rain in chennai"

    monkeypatch.setattr(bhashini, "speech_to_text", _stt)
    monkeypatch.setattr(
        bhashini, "text_to_speech",
        lambda text, lang: base64.b64encode(_wav(b"\x01\x00" * 4, 8000)).decode(),
    )

    def _ask(text, lang, city, token):
        seen["ask"] = (text, lang)
        return {"response": "Light rain expected in Chennai."}

    client = TestClient(ivr_simulate.build_app(_ask, lambda key, lang: f"[{key}:{lang}]"))
    return client, seen


def test_simulated_call_round_trips_through_routes(fake_call, tmp_path):
    client, seen = fake_call
    question = _wav(b"\x10\x00" * 1600, 16000)
    manifest = ivr_simulate.simulate_call(client, question, "ta", tmp_path, key="s3cr3t")

    assert manifest["ok"] is True
    assert manifest["simulated"] is True
    assert manifest["call_sid"].startswith("SIM-")
    assert manifest["digits"] == "3"
    assert [s["status"] for s in manifest["steps"]] == [200, 200, 200]
    assert manifest["transcript"] == "will it rain in chennai"
    assert manifest["answer_text"] == "Light rain expected in Chennai."
    assert seen["ask"] == ("will it rain in chennai", "ta")
    # ASR got the 8kHz telephony version, told the truth about its rate
    asr_audio, asr_lang, asr_rate = seen["asr"][0]
    assert (asr_lang, asr_rate) == ("ta", 8000)
    assert ivr_simulate._parse_pcm16(asr_audio)[1] == 8000


def test_every_output_is_marked_simulated(fake_call, tmp_path):
    client, _ = fake_call
    manifest = ivr_simulate.simulate_call(
        client, _wav(b"\x00\x00" * 800, 8000), "en", tmp_path, key="s3cr3t",
    )
    call_dir = tmp_path / manifest["call_sid"]
    files = sorted(p.name for p in call_dir.iterdir())
    assert files == [
        "SIMULATED_answer.wav", "SIMULATED_call.json",
        "SIMULATED_menu.wav", "SIMULATED_question.wav",
    ]
    for name in files:
        body = (call_dir / name).read_bytes()
        assert ivr_simulate.SIM_LABEL.encode() in body
    assert json.loads((call_dir / "SIMULATED_call.json").read_text())["simulated"] is True


def test_wrong_key_is_rejected_by_the_real_routes(fake_call, tmp_path):
    client, _ = fake_call
    manifest = ivr_simulate.simulate_call(
        client, _wav(b"\x00\x00" * 800, 8000), "en", tmp_path, key="wrong",
    )
    assert manifest["ok"] is False
    assert [s["status"] for s in manifest["steps"]] == [403, 403, 403]


def test_build_app_does_not_leave_ivr_enabled(monkeypatch):
    monkeypatch.setattr(config, "IVR_ENABLED", False)
    app = ivr_simulate.build_app(lambda **k: {}, lambda k, lang: "")
    assert config.IVR_ENABLED is False
    assert "/ivr/recording" in {r.path for r in app.routes}


def test_to_telephony_wav_downmixes_and_resamples():
    # stereo 16kHz, L=100 R=300 -> mono 200 at 8kHz, half the frames
    pcm = struct.pack("<hh", 100, 300) * 1600
    out = ivr_simulate.to_telephony_wav(_wav(pcm, 16000, channels=2))
    channels, rate, mono = ivr_simulate._parse_pcm16(out)
    assert (channels, rate) == (1, 8000)
    samples = struct.unpack(f"<{len(mono) // 2}h", mono)
    assert len(samples) == 800
    assert set(samples) == {200}


def test_to_telephony_wav_rejects_non_pcm16():
    fmt = struct.pack("<HHIIHH", 3, 1, 8000, 32000, 4, 32)  # float32
    wav = (struct.pack("<4sI4s", b"RIFF", 36 + 4, b"WAVE")
           + struct.pack("<4sI", b"fmt ", 16) + fmt + struct.pack("<4sI", b"data", 4) + b"\0" * 4)
    with pytest.raises(ValueError):
        ivr_simulate.to_telephony_wav(wav)


def test_tag_simulated_keeps_wav_parseable():
    wav = _wav(b"\x01\x02\x03\x04", 8000)
    tagged = ivr_simulate.tag_simulated(wav)
    assert struct.unpack("<I", tagged[4:8])[0] == len(tagged) - 8
    assert ivr._wav_data_chunk(tagged) == ivr._wav_data_chunk(wav)
    assert ivr_simulate.tag_simulated(b"ID3 mp3") == b"ID3 mp3"
