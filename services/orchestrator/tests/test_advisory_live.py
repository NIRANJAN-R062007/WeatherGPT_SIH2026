"""Live checks of the Strands advisory agent (plan.md TFA-19). Skipped in CI.

Run: pytest services/orchestrator/tests/test_advisory_live.py -m live -v

Each test leaves exactly one provider key in place, posts a real travel question
to /advisory/travel and checks the answer came from that provider's agent, not
the template. A free-tier 429 skips rather than fails: it says nothing about
whether the provider works through Strands.
"""

import config
import google_weather
import main
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.live

client = TestClient(main.app)
QUESTION = "can I travel from Chennai to Madurai by road tomorrow"


@pytest.fixture(autouse=True)
def _live_weather(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", True)
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    google_weather.cache_clear()


def _travel() -> dict:
    r = client.post("/advisory/travel", json={"text": QUESTION, "lang": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok", body
    reason = (body.get("fallback_reason") or "").lower()
    if body["path"] == "template" and ("429" in reason or "throttl" in reason
                                       or "rate" in reason or "exhausted" in reason):
        pytest.skip(f"provider rate-limited: {body['fallback_reason']}")
    return body


@pytest.mark.skipif(not config.GROQ_API_KEY, reason="no GROQ_API_KEY")
def test_groq_alone_answers_through_strands(monkeypatch):
    """TFA-19: Groq through Strands' OpenAI-compatible client (base_url = GROQ_BASE)."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    body = _travel()
    assert body["path"] == "agent:groq", body["fallback_reason"]
    assert body["fallback_reason"] is None
    assert body["answer"]["verdict"] in ("go", "caution", "avoid", "not_available")


@pytest.mark.skipif(not config.GEMINI_API_KEY, reason="no GEMINI_API_KEY")
def test_gemini_alone_answers_through_strands(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    body = _travel()
    assert body["path"] == "agent:gemini", body["fallback_reason"]
    assert body["answer"]["verdict"] in ("go", "caution", "avoid", "not_available")
