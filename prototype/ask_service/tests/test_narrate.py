"""narrate(): returns a sanitized sentence on success, None on anything else,
and never raises. It must not call Gemini for Tamil or when no key is set.
"""

import config
import httpx
import narrate
import nlu
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


def test_generate_sets_gemini_json_schema(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def _post(url, *, headers, json, timeout):
        captured.update(json)
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    schema = {"type": "OBJECT", "properties": {}}
    narrate.generate("p", model="m", key="k", response_schema=schema)
    assert captured["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["generationConfig"]["responseSchema"] == schema


def test_generate_without_schema_has_no_json_mime(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "x"}]}}]}

    def _post(url, *, headers, json, timeout):
        captured.update(json)
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    narrate.generate("p", model="m", key="k")
    assert "responseMimeType" not in captured["generationConfig"]


def test_generate_groq_sets_json_object_mode(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def _post(url, *, headers, json, timeout):
        captured.update(json)
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    narrate.generate_groq("p", model="m", key="k", response_schema={"type": "object"})
    assert captured["response_format"] == {"type": "json_object"}


def test_feedback_appended_to_prompt():
    prompt = narrate.build_prompt("current_weather", "Chennai", FACTS,
                                  feedback="99°C, 4 inches")
    assert "99°C, 4 inches" in prompt
    assert "Rewrite using only the facts' numbers" in prompt


def test_prompt_hides_counts_and_since():
    facts = {**FACTS, "since": "2026-09-11T00:00:00+05:30",
             "days_requested": 5, "days_counted": 2, "hours_counted": 8}
    prompt = narrate.build_prompt("rainfall_so_far_today", "Chennai", facts)
    assert '"since"' not in prompt
    assert '"days_requested"' not in prompt
    assert '"days_counted"' not in prompt
    assert '"hours_counted"' not in prompt
    assert "N=8" in prompt  # count still reaches the model via the intent hint


def test_word_cap_grows_with_multi_day_facts():
    facts = {"days": [{"label": "today"}, {"label": "tomorrow"}, {"label": "day2"}]}
    prompt = narrate.build_prompt("forecast", "Chennai", facts)
    assert f"max {25 + 15 * 2} words" in prompt


# --- Ollama provider ---------------------------------------------------------

def test_generate_ollama_request_body(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"response": "hi", "done_reason": "stop"}

    def _post(url, *, json, timeout):
        captured["url"] = url
        captured.update(json)
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    out = narrate.generate_ollama("p", model="llama3.2:3b", base="http://x:11434",
                                  response_schema={"type": "OBJECT"})
    assert out == "hi"
    assert captured["url"] == "http://x:11434/api/generate"
    assert captured["stream"] is False
    assert captured["format"] == {"type": "OBJECT"}
    assert captured["keep_alive"] == "30m"
    assert captured["options"]["num_predict"] == 200


def test_generate_ollama_length_finish_returns_none(monkeypatch):
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"response": "cut off", "done_reason": "length"}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    assert narrate.generate_ollama("p", model="m", base="http://x:11434") is None


def test_chain_order_gemini_groq_ollama(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "g")
    monkeypatch.setattr(config, "GROQ_API_KEY", "q")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    calls = []

    def _gemini_boom(*a, **k):
        calls.append("gemini")
        raise httpx.ConnectError("down")

    def _groq_boom(*a, **k):
        calls.append("groq")
        raise httpx.ConnectError("down")

    def _ollama_ok(*a, **k):
        calls.append("ollama")
        return "Chennai: cloudy."

    monkeypatch.setattr(narrate, "generate", _gemini_boom)
    monkeypatch.setattr(narrate, "generate_groq", _groq_boom)
    monkeypatch.setattr(narrate, "generate_ollama", _ollama_ok)
    text, name = narrate.run_chain("prompt")
    assert calls == ["gemini", "groq", "ollama"]
    assert text == "Chennai: cloudy." and name == "ollama"
    assert narrate.last_provider == "ollama"


def test_offline_mode_skips_cloud_providers(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "g")
    monkeypatch.setattr(config, "GROQ_API_KEY", "q")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _boom(*a, **k):
        raise AssertionError("cloud provider was called in OFFLINE_MODE")

    monkeypatch.setattr(narrate, "generate", _boom)
    monkeypatch.setattr(narrate, "generate_groq", _boom)
    names = [name for name, _ in narrate.providers()]
    assert names == ["ollama"]


def test_is_configured_with_only_ollama(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    assert narrate.is_configured() is True


def test_ollama_status_unreachable_never_raises(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(
        httpx.ConnectError("down")))
    status = narrate.ollama_status()
    assert status["reachable"] is False
    assert status["model_present"] is None


def test_ollama_status_no_model_configured(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", None)
    status = narrate.ollama_status()
    assert status["reachable"] is None and status["model_present"] is None


# --- gemini_schema() ----------------------------------------------------------

_EXPECTED_NLU_GEMINI_SCHEMA = {
    "type": "OBJECT",
    "propertyOrdering": ["intent", "city", "time_window", "days", "parameter",
                         "language", "confidence"],
    "required": ["intent", "city", "time_window", "days", "parameter", "language", "confidence"],
    "properties": {
        "intent": {"type": "STRING", "enum": list(nlu.INTENTS)},
        "city": {"type": "STRING", "nullable": True},
        "time_window": {"type": "STRING", "enum": list(nlu.TIME_WINDOWS)},
        "days": {"type": "INTEGER", "nullable": True},
        "parameter": {"type": "STRING", "enum": list(nlu.PARAMETERS)},
        "language": {"type": "STRING", "enum": [*nlu.LANGUAGES, "other"]},
        "confidence": {"type": "NUMBER"},
    },
}


def test_gemini_schema_matches_expected_nlu_schema():
    assert narrate.gemini_schema(nlu._NLU_SCHEMA) == _EXPECTED_NLU_GEMINI_SCHEMA


def test_gemini_schema_nested_items():
    schema = {
        "type": "object",
        "properties": {
            "days": {"type": "array", "items": {
                "type": "object",
                "properties": {"label": {"type": ["string", "null"]}},
            }},
        },
    }
    out = narrate.gemini_schema(schema)
    assert out["properties"]["days"]["type"] == "ARRAY"
    assert out["properties"]["days"]["items"]["type"] == "OBJECT"
    assert out["properties"]["days"]["items"]["properties"]["label"] == \
        {"type": "STRING", "nullable": True}
