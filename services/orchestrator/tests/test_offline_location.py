"""Offline (OFFLINE_MODE=1 or WEATHER_MODE=fixtures; step 7): only the demo
cities have saved data. A GPS fix is answered for the nearest demo city, and
the answer says so; a named non-demo place is told that only the demo cities
are available offline — never answered for some other city silently.
"""

import inspect

import cities
import config
import i18n
import location
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)
_STEP7 = pytest.mark.xfail(strict=True, reason="step 7: offline snap to demo city")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params}).json()


@_STEP7
@pytest.mark.parametrize("lat,lon,demo", [(10.79, 78.70, "madurai"), (11.10, 77.00, "coimbatore"),
                                          (28.40, 77.30, "delhi")])
def test_gps_offline_answers_for_the_nearest_demo_city_and_says_so(lat, lon, demo):
    body = _ask("what's the weather here", lat=lat, lon=lon)
    name = cities.display_name(demo, "en")
    assert body["response"].startswith(f"{name}:")
    assert i18n.location_message("offline_nearest_demo", "en", city=name) in body["response"]
    assert body["offline"] is True
    assert body["city"] == demo and body["location"]["source"] == "demo_fixture"
    assert body["provenance"]["place"]["label"] == name


@_STEP7
def test_offline_mode_flag_behaves_the_same(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    body = _ask("will it rain here", lat=9.95, lon=78.15)
    assert body["city"] == "madurai" and body["offline"] is True


@_STEP7
@pytest.mark.parametrize("params", [{"text": "what's the weather in Tiruchirappalli"},
                                    {"text": "weather", "place_id": "gn:1254388"}])
def test_a_named_non_demo_place_offline_is_told_demo_cities_only(params):
    body = client.get("/ask", params=params).json()
    assert "response" not in body
    assert body["offline"] is True
    assert body["message"] == main._msg("offline_demo_only", "en",
                                        place="Tiruchirappalli, Tamil Nadu",
                                        cities=main._city_list("en"))


def test_a_demo_city_offline_is_answered_normally():
    body = _ask("what's the weather in Chennai")
    assert body["response"].startswith("Chennai:") and "offline" not in body


@_STEP7
def test_the_nearest_demo_city_helper():
    assert location.nearest_demo_city(10.79, 78.70).key == "madurai"
    assert location.nearest_demo_city(19.2, 72.9).key == "mumbai"


@_STEP7
@pytest.mark.parametrize("key", ["offline_nearest_demo", "offline_demo_only"])
@pytest.mark.parametrize("lang", i18n.SUPPORTED_LANGUAGES)
def test_offline_messages_exist_in_every_language(key, lang):
    text = i18n.location_message(key, lang, city="Madurai", place="Trichy",
                                 cities="Chennai, Madurai")
    assert text and "{" not in text


@_STEP7
def test_offline_messages_carry_the_native_qa_marker():
    source = inspect.getsource(i18n).splitlines()
    for key in ("offline_nearest_demo", "offline_demo_only"):
        for lang in ("ta", "hi", "te", "mr"):
            first = i18n.LOCATION_MESSAGES[key][lang][:12]
            lines = [ln for ln in source if first in ln]
            assert lines and all("TODO: native_qa" in ln for ln in lines), (key, lang)
