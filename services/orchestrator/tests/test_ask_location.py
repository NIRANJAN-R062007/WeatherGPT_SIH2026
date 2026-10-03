"""/ask end to end with the gazetteer and GPS (location.py behind main.py).

Postgres and Redis stay unreachable here (tests/conftest.py), so every test in
this file is also a no-database, no-Redis test. Live weather is the stubbed
fetch_json, never the network: a non-demo place has no fixture, so it needs
WEATHER_MODE=auto and a stub that serves a committed payload for any point.
"""

import json

import config
import google_weather
import main
import pytest
import weather_store
from fastapi.testclient import TestClient

client = TestClient(main.app)

TRICHY = "gn:1254388"
_STEP4 = pytest.mark.xfail(strict=True, reason="step 4: GPS 'near X' label")


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)  # template path


def _payload(kind: str) -> dict:
    path = config.FIXTURES_DIR / "google_weather" / f"{kind}.chennai.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


@pytest.fixture
def live_anywhere(monkeypatch):
    """Live mode, with Google stubbed to answer any coordinates."""
    seen = []
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")

    def _serve(path, params, timeout=google_weather.TIMEOUT):
        seen.append(params)
        kind = next(k for k, ep in google_weather.ENDPOINTS.items() if ep == path)
        return _payload(kind)

    monkeypatch.setattr(google_weather, "fetch_json", _serve)
    return seen


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params}).json()


@_STEP4
def test_here_with_gps_answers_for_near_the_nearest_town(live_anywhere):
    body = _ask("will it rain here", lat=10.79, lon=78.70)
    assert "response" in body
    assert body["location"]["source"] == "gps"
    label = body["location"]["label"]
    assert "near" in label and "Tiruchirappalli" in label


def test_here_without_gps_asks_for_a_location():
    body = _ask("will it rain here")
    assert "response" not in body
    assert body["needs_location"] is True
    assert body["message"] == main._msg("need_location", "en")


def test_unknown_place_is_not_found_and_names_a_nearest_place():
    body = _ask("weather in Xyzabad")
    assert "response" not in body
    assert body["not_found"] is True
    assert body["nearest"]["label"]
    assert body["nearest"]["label"] in body["message"]


def test_a_tapped_place_id_overrides_the_text(live_anywhere):
    body = _ask("weather in Chennai", place_id=TRICHY)
    assert body["location"]["place_id"] == TRICHY
    assert "Tiruchirappalli" in body["response"]


def test_full_outage_still_answers_for_a_demo_city():
    with pytest.raises(Exception):
        weather_store._engine.begin()
    with pytest.raises(Exception):
        weather_store._redis.get("x")
    body = _ask("what's the weather in Chennai")
    assert body["response"].startswith("Chennai")
    assert body["location"]["source"] == "demo_fixture"


def test_full_outage_still_answers_for_a_gazetteer_city(live_anywhere):
    with pytest.raises(Exception):
        weather_store._engine.begin()
    body = _ask("what's the weather in Tiruchirappalli")
    assert "Tiruchirappalli" in body["response"]
    assert body["location"]["source"] == "gazetteer"
    assert body["location"]["place_id"] == TRICHY
    assert live_anywhere  # the weather call went out for Trichy's point
