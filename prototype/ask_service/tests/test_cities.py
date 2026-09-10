"""City registry loads and resolves, the stub + i18n stay in parity with it,
and every demo city grounds across both intents and both languages.
"""

import re

import cities
import i18n
import pytest
import weather_data
from config import REPO_ROOT
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

EXPECTED_KEYS = {"chennai", "madurai", "coimbatore"}
DC_HTML = REPO_ROOT / "prototype" / "frontend" / "WeatherGPT.dc.html"


def test_registry_loads():
    assert set(cities.CITY_KEYS) == EXPECTED_KEYS
    for c in cities.CITIES.values():
        assert 6 <= c.lat <= 38 and 68 <= c.lon <= 98  # India bbox
        assert c.names["en"] and c.names["ta"]


@pytest.mark.parametrize(("text", "expected"), [
    ("Chennai", "chennai"),
    (" chennai ", "chennai"),
    ("MADURAI", "madurai"),
    ("kovai", "coimbatore"),
    ("சென்னை", "chennai"),
    ("what's the weather in Coimbatore", "coimbatore"),
    ("Mumbai", None),
    ("", None),
    (None, None),
])
def test_resolve(text, expected):
    assert cities.resolve(text) == expected


def test_stub_and_i18n_cover_every_registry_city():
    for key in cities.CITY_KEYS:
        data = weather_data.get_weather(key)
        assert data is not None, f"no stub weather for {key}"
        cond = data["condition"]
        assert cond in i18n.CONDITION_EN, f"{cond} missing from CONDITION_EN"
        assert cond in i18n.CONDITION_TA, f"{cond} missing from CONDITION_TA"


@pytest.mark.parametrize("key", sorted(EXPECTED_KEYS))
@pytest.mark.parametrize("lang", ["en", "ta"])
@pytest.mark.parametrize("template", [
    "what's the weather in {c}",
    "will it rain in {c} tomorrow",
])
def test_every_city_intent_language_grounds(key, lang, template):
    name = cities.CITIES[key].names["en"]
    r = client.get("/ask", params={"text": template.format(c=name), "lang": lang})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == key
    assert body["grounding"]["ok"] is True
    assert body["grounding"]["matched"] == body["grounding"]["total"] >= 1


def test_no_city_query_returns_message_not_500():
    r = client.get("/ask", params={"text": "will it rain tomorrow"})
    assert r.status_code == 200
    body = r.json()
    assert "message" in body and "response" not in body


def test_no_city_query_uses_explicit_city_param():
    r = client.get("/ask", params={"text": "will it rain tomorrow", "city": "madurai"})
    assert r.status_code == 200
    assert r.json()["city"] == "madurai"


def test_cities_endpoint():
    body = client.get("/cities").json()
    assert {c["key"] for c in body["cities"]} == EXPECTED_KEYS
    for c in body["cities"]:
        assert "lat" in c and "lon" in c


def test_health_endpoint():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body["cities"]) == EXPECTED_KEYS


def test_frontend_latlon_matches_registry():
    if not DC_HTML.exists():
        pytest.skip("frontend export not present")
    text = DC_HTML.read_text(encoding="utf-8")
    found = {}
    pattern = r'name:\s*\{en:\s*"([^"]+)".*?lat:\s*([\d.]+),\s*lon:\s*([\d.]+)'
    for m in re.finditer(pattern, text):
        found[m.group(1).lower()] = (round(float(m.group(2)), 4), round(float(m.group(3)), 4))
    if not found:
        pytest.skip("could not parse CITIES lat/lon from the export")
    for key, c in cities.CITIES.items():
        if key in found:
            assert found[key] == (round(c.lat, 4), round(c.lon, 4)), f"{key} lat/lon drift"
