"""IMD warning colour-code fixtures and the GET /warnings endpoint
(plan.md §14 Task D). All fully offline against tracked fixture files.

`status` is the point of most of these: "unavailable" (feed off — the
default — or no usable fixture) must be distinguishable from "clear"
(checked, green) so no UI can draw a null as an all-clear (plan.md §2
principle 3), while `warning`'s null-vs-object contract stays exactly what
prototype/frontend's loadHero() already consumes.
"""

import json
from datetime import datetime

import config
import glossary
import imd_warnings as warnings_module
import main
import pytest
from config import FIXTURES_DIR
from fastapi.testclient import TestClient

client = TestClient(main.app)

WARN_DIR = FIXTURES_DIR / "imd_warnings"
CITIES = ["chennai", "madurai", "coimbatore"]
COLOURS = {"green", "yellow", "orange", "red"}
LANGS = ["en", "ta", "hi", "te", "mr"]


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


@pytest.fixture
def _fixture_dir(tmp_path, monkeypatch):
    """Point the loader at an empty fixture directory the test can populate."""
    d = tmp_path / "imd_warnings"
    d.mkdir()
    monkeypatch.setattr(warnings_module, "_WARNINGS_DIR", d)
    warnings_module.cache_clear()
    return d


def _write_fixture(d, city, **response_overrides):
    env = json.loads((WARN_DIR / f"warnings.{city}.json").read_text(encoding="utf-8"))
    env["response"].update(response_overrides)
    (d / f"warnings.{city}.json").write_text(json.dumps(env), encoding="utf-8")


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
    for lang in LANGS:
        assert lang in labels, f"{city} fixture missing '{lang}' label"
        assert labels[lang]["headline"], f"{city} fixture has an empty '{lang}' headline"


@pytest.mark.parametrize("city", CITIES)
def test_fixture_category_has_a_glossary_entry(city):
    # The category label next to the headline comes from the glossary, keyed
    # by the fixture's category text — a fixture that invents a category the
    # glossary lacks would silently render the raw feed text in every language.
    env = json.loads((WARN_DIR / f"warnings.{city}.json").read_text(encoding="utf-8"))
    category = env["response"]["category"]
    assert glossary.category_label(category, "ta") != category


# --- status: unavailable ----------------------------------------------------


def test_warnings_disabled_by_default():
    # config.WARNINGS_ENABLED defaults off — the fixture is fake data, not a
    # live feed, so /warnings must say "no verdict", not "all clear".
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["status"] == warnings_module.STATUS_UNAVAILABLE == "unavailable"
    assert body["warning"] is None
    assert body["city"] == "chennai" and body["city_name"] == "Chennai"


def test_disabled_does_not_read_the_fixture(monkeypatch):
    # Off means off: not even a green fixture should be consulted.
    monkeypatch.setattr(config, "WARNINGS_ENABLED", False)
    monkeypatch.setattr(warnings_module, "load", lambda key: pytest.fail("fixture read"))
    assert warnings_module.public("coimbatore", "en")["status"] == "unavailable"


def test_status_unavailable_when_fixture_missing(_warnings_enabled, _fixture_dir):
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable"
    assert body["warning"] is None


def test_status_unavailable_when_fixture_malformed(_warnings_enabled, _fixture_dir):
    (_fixture_dir / "warnings.chennai.json").write_text("{not valid json", encoding="utf-8")
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable"
    assert body["warning"] is None


def test_status_unavailable_when_colour_unknown(_warnings_enabled, _fixture_dir):
    # public() looks the colour word up in the glossary, so a colour outside
    # IMD's four-level scale is a malformed fixture, not a 500.
    _write_fixture(_fixture_dir, "chennai", colour="purple")
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable"
    assert body["warning"] is None


def test_unavailable_still_carries_the_legend():
    # The colour-code legend is static glossary text, not a feed verdict —
    # a page can explain the colours even when it has no warning to show.
    body = client.get("/warnings", params={"city": "chennai", "lang": "ta"}).json()
    assert body["status"] == "unavailable"
    assert [row["colour"] for row in body["legend"]] == ["green", "yellow", "orange", "red"]
    assert body["legend"][0]["label"] == "பச்சை"


# --- status: active / clear -------------------------------------------------


def test_chennai_is_orange_heavy_rainfall(_warnings_enabled):
    body = client.get("/warnings", params={"city": "chennai"}).json()
    assert body["status"] == warnings_module.STATUS_ACTIVE == "active"
    w = body["warning"]
    assert w["colour"] == "orange"
    assert w["colour_label"] == "Orange"
    assert w["category"] == "Heavy rainfall"
    assert w["category_label"] == "Heavy rainfall"
    assert w["headline"] == "Orange alert: heavy rainfall expected"
    assert w["issued_by"] == "IMD (fixture)" and w["source"] == "fixture"


def test_madurai_is_yellow_thunderstorm(_warnings_enabled):
    body = client.get("/warnings", params={"city": "madurai"}).json()
    assert body["status"] == "active"
    w = body["warning"]
    assert w["colour"] == "yellow"
    assert w["category"] == "Thunderstorm with lightning"


def test_coimbatore_is_green_and_clear(_warnings_enabled):
    # Green is a verdict ("checked, nothing in force"), so the object is still
    # returned — it carries the feed's own headline, validity and issuer.
    body = client.get("/warnings", params={"city": "coimbatore"}).json()
    assert body["status"] == warnings_module.STATUS_CLEAR == "clear"
    w = body["warning"]
    assert w["colour"] == "green"
    assert w["category"] is None
    assert w["category_label"] == "No warning in force"
    assert w["headline"] == "No warning in force"
    assert w["valid_from"] and w["valid_to"] and w["issued_by"]


def test_public_shape_is_status_warning_legend(_warnings_enabled):
    # The shape /ask's warning intent will code against.
    result = warnings_module.public("chennai", "en")
    assert set(result) == {"status", "warning", "legend"}
    assert result["status"] in (
        warnings_module.STATUS_UNAVAILABLE, warnings_module.STATUS_CLEAR,
        warnings_module.STATUS_ACTIVE,
    )
    assert (result["warning"] is None) == (result["status"] == "unavailable")
    assert result["legend"] == glossary.legend("en")


# --- glossary-sourced labels (plan.md §3.1: one decoder, five outputs) -----


@pytest.mark.parametrize("lang", LANGS)
def test_labels_come_from_the_glossary(_warnings_enabled, lang):
    body = client.get("/warnings", params={"city": "chennai", "lang": lang}).json()
    w = body["warning"]
    assert w["colour_label"] == glossary.text("colour_word_orange", lang)
    assert w["category_label"] == glossary.text("category_heavy_rainfall", lang)
    assert body["legend"] == glossary.legend(lang)


def test_unknown_category_label_is_the_feed_text(_warnings_enabled, _fixture_dir):
    # plan.md §2 principle 4: the feed's own category text, never a guess.
    _write_fixture(_fixture_dir, "chennai", category="Dense fog")
    w = client.get("/warnings", params={"city": "chennai", "lang": "hi"}).json()["warning"]
    assert w["category"] == "Dense fog"
    assert w["category_label"] == "Dense fog"


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
    warning = warnings_module.public("chennai", "fr")["warning"]
    assert warning["headline"] == "Orange alert: heavy rainfall expected"
    assert warning["colour_label"] == "Orange"


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


def test_load_returns_none_for_malformed_fixture(_fixture_dir):
    (_fixture_dir / "warnings.chennai.json").write_text("{not valid json", encoding="utf-8")
    assert warnings_module.load("chennai") is None
