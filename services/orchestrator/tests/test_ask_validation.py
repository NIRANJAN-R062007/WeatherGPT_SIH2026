"""/ask's optional lat, lon and place_id: garbage is a 422; a real point
outside India is answered "India only" and never fetched; a name with
several close homonyms is answered with the candidates to tap.
"""

import config
import google_weather
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)
_STEP3 = pytest.mark.xfail(strict=True, reason="step 3: /ask lat/lon/place_id")


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)


def _get(**params):
    return client.get("/ask", params={"text": "will it rain here", **params})


@_STEP3
@pytest.mark.parametrize("params", [
    {"lat": "abc", "lon": "78.7"},
    {"lat": "nan", "lon": "78.7"},
    {"lat": "10.8", "lon": "inf"},
    {"lat": "91", "lon": "78.7"},
    {"lat": "10.8", "lon": "-181"},
    {"lat": "10.8"},                       # half a point
    {"lon": "78.7"},
    {"place_id": "../../etc/passwd"},
    {"place_id": "gn:abc"},
    {"place_id": "gn:" + "1" * 30},
])
def test_garbage_location_params_are_a_422(params):
    assert _get(**params).status_code == 422


@_STEP3
def test_a_point_outside_india_is_india_only_and_never_fetched(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(google_weather, "fetch_json",
                        lambda *a, **k: pytest.fail("weather fetched outside India"))
    resp = _get(lat=51.5074, lon=-0.1278)
    assert resp.status_code == 200
    body = resp.json()
    assert body["outside_india"] is True and "response" not in body
    assert body["message"] == main._msg("india_only", "en")


@_STEP3
@pytest.mark.parametrize("lang", ["ta", "hi", "te", "mr"])
def test_location_replies_are_in_the_users_language(lang):
    body = client.get("/ask", params={"text": "will it rain here", "lang": lang}).json()
    assert body["message"] == main._msg("need_location", lang)


@_STEP3
def test_close_homonyms_come_back_as_candidates_to_tap():
    body = client.get("/ask", params={"text": "weather in Puttur"}).json()
    assert "response" not in body
    assert body["message"] == main._msg("which_place", "en")
    assert len(body["ambiguous"]) >= 2
    for cand in body["ambiguous"]:
        assert cand["place_id"].startswith("gn:") and cand["state"]


@_STEP3
def test_resolved_location_is_reported_rounded():
    body = client.get("/ask", params={"text": "what's the weather in Chennai"}).json()
    loc = body["location"]
    assert loc["source"] == "demo_fixture" and loc["label"] == "Chennai"
    assert loc["lat"] == round(loc["lat"], 2) and loc["lon"] == round(loc["lon"], 2)
    assert body["city"] == "chennai"


@_STEP3
def test_a_named_place_beats_the_gps_fix(monkeypatch):
    body = client.get("/ask", params={"text": "what's the weather in Chennai",
                                      "lat": 51.5, "lon": -0.12}).json()
    assert body["location"]["source"] == "demo_fixture" and "response" in body
