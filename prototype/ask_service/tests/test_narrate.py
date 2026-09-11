"""narrate(): returns a sanitized sentence on success, None on anything else,
and never raises. It must not call Gemini for Tamil or when no key is set.
"""

import config
import httpx
import narrate
import pytest

FACTS = {"condition": "cloudy", "temp_c": 28, "feels_like_c": 32.5,
         "humidity_pct": 81, "source": "x", "issued": "2026-09-10T22:00Z", "is_live": False}


def _forbid_generate(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("generate() was called")
    monkeypatch.setattr(narrate, "generate", _boom)


def test_tamil_never_calls_gemini(monkeypatch):
    _forbid_generate(monkeypatch)
    assert narrate.narrate("current_weather", "Chennai", FACTS, "ta") is None


def test_no_key_never_calls_gemini(monkeypatch):
    _forbid_generate(monkeypatch)
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert narrate.narrate("current_weather", "Chennai", FACTS, "en") is None


def test_empty_facts_returns_none(monkeypatch):
    _forbid_generate(monkeypatch)
    assert narrate.narrate("current_weather", "Chennai", {}, "en") is None


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("t"), httpx.ConnectError("c")])
def test_http_error_returns_none(monkeypatch, caplog, exc):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: (_ for _ in ()).throw(exc))
    with caplog.at_level("WARNING"):
        assert narrate.narrate("current_weather", "Chennai", FACTS, "en") is None
    assert any("narration failed" in r.message for r in caplog.records)


def test_generate_empty_candidates_returns_none(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"candidates": []}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    assert narrate.generate("p", model="m", key="k") is None


def test_happy_path_sanitizes(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(narrate, "generate",
                        lambda *a, **k: "```\nChennai: cloudy, 28°C right now.\n```")
    out = narrate.narrate("current_weather", "Chennai", FACTS, "en")
    assert out == "Chennai: cloudy, 28°C right now."


def test_length_cap(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    long = "Chennai: " + "very " * 200 + "cloudy."
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: long)
    out = narrate.narrate("current_weather", "Chennai", FACTS, "en")
    assert out is not None and len(out) <= narrate.MAX_CHARS


def test_prompt_has_facts_but_not_provenance():
    prompt = narrate.build_prompt("current_weather", "Chennai", FACTS)
    assert "28" in prompt and "81" in prompt and "32.5" in prompt
    assert "2026-09-10" not in prompt
    assert '"source"' not in prompt and '"issued"' not in prompt
