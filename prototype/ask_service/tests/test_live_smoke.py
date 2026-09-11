"""Deliberate live calls — one per external API. Skipped in CI (no keys).

Run: pytest prototype/ask_service/tests -m live -v
"""

import config
import google_weather
import guardrail
import narrate
import pytest
import weather_data

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _auto_mode(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    google_weather.cache_clear()


@pytest.mark.skipif(not config.GOOGLE_WEATHER_API_KEY, reason="no GOOGLE_WEATHER_API_KEY")
def test_live_google_weather_current_conditions_chennai():
    snap = google_weather._live("current_conditions", "chennai")
    assert snap.is_live is True
    temp = snap.payload["temperature"]["degrees"]
    assert 0 <= temp <= 60
    facts = weather_data.get_weather("chennai", "current_weather", "today")
    assert facts["is_live"] is True
    from i18n import render
    assert guardrail.check(render("current_weather", "Chennai", facts, "en"), facts).ok


@pytest.mark.skipif(not config.GEMINI_API_KEY, reason="no GEMINI_API_KEY")
def test_live_gemini_narrates_grounded_english():
    facts = {"condition": "cloudy", "temp_c": 28, "feels_like_c": 32.5,
             "humidity_pct": 81, "source": "x", "issued": "2026-01-01T00:00Z", "is_live": False}
    text = narrate.narrate("current_weather", "Chennai", facts, "en")
    if text is None:
        pytest.skip("Gemini unavailable (rate limit / transient)")
    assert text.startswith("Chennai:")
    report = guardrail.check(text, facts)
    assert report.ok and report.total > 0
