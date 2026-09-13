"""Config must never break the demo path: it imports with an empty environment,
and /ask keeps working whether or not any key is set.
"""

import importlib

import config
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_config_imports_without_environment(monkeypatch):
    for var in ("GOOGLE_WEATHER_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "ALLOWED_ORIGINS"):
        monkeypatch.delenv(var, raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.GEMINI_MODEL == "gemini-flash-latest"
    assert reloaded.ALLOWED_ORIGINS == ["*"]
    importlib.reload(config)  # restore real env for other tests


def test_require_raises_configerror_on_missing():
    with pytest.raises(config.ConfigError):
        config.require("SOME_KEY", None)
    assert config.require("SOME_KEY", "value") == "value"


def test_redact_never_leaks():
    assert config.redact("AIzaSyDVeryLongSecretKey1234") == "AIza…1234"
    assert config.redact(None) == "<unset>"
    assert config.redact("short") == "…"


def test_ask_still_returns_200_regardless_of_keys():
    r = client.get("/ask", params={"text": "what's the weather in Chennai", "lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounding"]["ok"] is True
    assert body["provenance"]["is_live"] is False


def test_offline_mode_forces_fixtures(monkeypatch):
    monkeypatch.setenv("OFFLINE_MODE", "1")
    monkeypatch.setenv("WEATHER_MODE", "auto")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.OFFLINE_MODE is True
        assert reloaded.WEATHER_MODE == "fixtures"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_offline_defaults(monkeypatch):
    # conftest's autouse _llm_defaults fixture forces OLLAMA_MODEL to None for
    # every other test; check its real default via a clean reload instead.
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.OFFLINE_MODE is False
    assert reloaded.OLLAMA_BASE == "http://localhost:11434"
    assert reloaded.OLLAMA_MODEL == "llama3.2:3b"
    assert reloaded.OLLAMA_TIMEOUT == 30.0
    importlib.reload(config)
