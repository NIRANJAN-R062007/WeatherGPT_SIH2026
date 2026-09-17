"""IMD warning colour-code fixtures and the GET /warnings endpoint
(plan.md §14 Task D). All fully offline against tracked fixture files.
"""

import json
from datetime import datetime

import config
import imd_warnings as warnings_module
import main
import pytest
from config import FIXTURES_DIR
from fastapi.testclient import TestClient

client = TestClient(main.app)

WARN_DIR = FIXTURES_DIR / "imd_warnings"
CITIES = ["chennai", "madurai", "coimbatore"]
COLOURS = {"green", "yellow", "orange", "red"}


@pytest.fixture(autouse=True)
def _clear_warnings_cache():
    warnings_module.cache_clear()
    yield
    warnings_module.cache_clear()


@pytest.fixture
def _warnings_enabled(monkeypatch):
    """WARNINGS_ENABLED defaults off (config.py) since the fixture is fake
    data, not a live feed — tests exercising the fixture content opt in
    explicitly rather than relying on a default that no longer holds."""
    monkeypatch.setattr(config, "WARNINGS_ENABLED", True)


@pytest.mark.parametrize("city", CITIES)
def test_fixture_is_well_formed(city):
    path = WARN_DIR / f"warnings.{city}.json"
    assert path.exists(), f"missing fixture: {path}"
    env = json.loads(path.read_text(encoding="utf-8"))
    meta = env["_meta"]
    assert meta["city"] == city
    assert meta["issued_by"]
    datetime.fromisoformat(meta["retrieved_at"])

    response = env["response"]
    assert response["colour"] in COLOURS
    datetime.fromisoformat(response["valid_from"])
    datetime.fromisoformat(response["valid_to"])
    assert response["advice"]
    assert "en" in response["labels"] and response["labels"]["en"]["headline"]


@pytest.mark.parametrize("city", CITIES)
def test_fixture_has_all_five_languages(city):
    # plan.md §14: hi/te/mr were missing from labels and silently fell back
    # to English — make sure a future edit can't drop one by accident.
    path = WARN_DIR / f"warnings.{city}.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    labels = env["response"]["labels"]
    for lang in ("en", "ta", "hi", "te", "mr"):
        assert lang in labels, f"{city} fixture missing '{lang}' label"
        assert labels[lang]["headline"], f"{city} fixture has an empty '{lang}' headline"


def test_warnings_disabled_by_default():
    # config.WARNINGS_ENABLED defaults off — the fixture is fake data, not a
    # live feed, so /warnings shouldn't serve it as if it were real.
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["warning"] is None


def test_chennai_is_orange_heavy_rainfall(_warnings_enabled):
    body = client.get("/warnings", params={"city": "chennai"}).json()
    w = body["warning"]
    assert w["colour"] == "orange"
    assert w["category"] == "Heavy rainfall"
    assert w["headline"] == "Orange alert: heavy rainfall expected"


def test_madurai_is_yellow_thunderstorm(_warnings_enabled):
    body = client.get("/warnings", params={"city": "madurai"}).json()
    w = body["warning"]
    assert w["colour"] == "yellow"
    assert w["category"] == "Thunderstorm with lightning"


def test_coimbatore_is_green_with_no_category(_warnings_enabled):
    body = client.get("/warnings", params={"city": "coimbatore"}).json()
    w = body["warning"]
    assert w["colour"] == "green"
    assert w["category"] is None


def test_tamil_headline(_warnings_enabled):
    body = client.get("/warnings", params={"city": "chennai", "lang": "ta"}).json()
    assert body["warning"]["headline"] == "ஆரஞ்சு எச்சரிக்கை: கனமழை எதிர்பார்க்கப்படுகிறது"


@pytest.mark.parametrize(
    "lang,expected",
    [
        ("hi", "नारंगी अलर्ट: भारी बारिश की आशंका"),
        ("te", "నారింజ హెచ్చరిక: భారీ వర్షం ఆశించబడుతోంది"),
        ("mr", "नारिंगी इशारा: मुसळधार पावसाची शक्यता"),
    ],
)
def test_chennai_headline_all_languages(_warnings_enabled, lang, expected):
    # plan.md §14: hi/te/mr headlines were missing from the fixtures and
    # silently fell back to English (imd_warnings.public()'s
    # `labels.get(lang) or labels["en"]`) — now all 5 languages have real text.
    body = client.get("/warnings", params={"city": "chennai", "lang": lang}).json()
    assert body["warning"]["headline"] == expected


def test_unsupported_lang_falls_back_to_english(_warnings_enabled):
    # All 5 SUPPORTED_LANGUAGES now have real headlines in the fixtures, so
    # the /warnings route's own _require_lang(lang) rejects anything else
    # with a 422 before imd_warnings.public() is even reached — the
    # labels.get(lang) or labels["en"] fallback in public() is no longer
    # reachable through the route. Exercise it directly against the module
    # instead, with a language the fixture genuinely doesn't carry.
    warning = warnings_module.public("chennai", "fr")
    assert warning["headline"] == "Orange alert: heavy rainfall expected"


def test_route_rejects_unsupported_lang(_warnings_enabled):
    resp = client.get("/warnings", params={"city": "chennai", "lang": "fr"})
    assert resp.status_code == 422


def test_unknown_city_is_404():
    resp = client.get("/warnings", params={"city": "mumbai"})
    assert resp.status_code == 404


def test_alias_resolution(_warnings_enabled):
    # "kovai" is a Tamil-side alias for coimbatore in data/cities.json
    body = client.get("/warnings", params={"city": "kovai"}).json()
    assert body["city"] == "coimbatore"
    assert body["warning"]["colour"] == "green"


def test_load_returns_none_for_missing_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path)
    monkeypatch.setattr(warnings_module, "_WARNINGS_DIR", tmp_path / "imd_warnings")
    warnings_module.cache_clear()
    assert warnings_module.load("chennai") is None


def test_load_returns_none_for_malformed_fixture(tmp_path, monkeypatch):
    d = tmp_path / "imd_warnings"
    d.mkdir()
    (d / "warnings.chennai.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(warnings_module, "_WARNINGS_DIR", d)
    warnings_module.cache_clear()
    assert warnings_module.load("chennai") is None
