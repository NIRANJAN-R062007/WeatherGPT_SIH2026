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


def test_chennai_is_orange_heavy_rainfall():
    body = client.get("/warnings", params={"city": "chennai"}).json()
    w = body["warning"]
    assert w["colour"] == "orange"
    assert w["category"] == "Heavy rainfall"
    assert w["headline"] == "Orange alert: heavy rainfall expected"


def test_madurai_is_yellow_thunderstorm():
    body = client.get("/warnings", params={"city": "madurai"}).json()
    w = body["warning"]
    assert w["colour"] == "yellow"
    assert w["category"] == "Thunderstorm with lightning"


def test_coimbatore_is_green_with_no_category():
    body = client.get("/warnings", params={"city": "coimbatore"}).json()
    w = body["warning"]
    assert w["colour"] == "green"
    assert w["category"] is None


def test_tamil_headline():
    body = client.get("/warnings", params={"city": "chennai", "lang": "ta"}).json()
    assert body["warning"]["headline"] == "ஆரஞ்சு எச்சரிக்கை: கனமழை எதிர்பார்க்கப்படுகிறது"


def test_unsupported_lang_falls_back_to_english():
    body = client.get("/warnings", params={"city": "chennai", "lang": "hi"}).json()
    assert body["warning"]["headline"] == "Orange alert: heavy rainfall expected"


def test_unknown_city_is_404():
    resp = client.get("/warnings", params={"city": "mumbai"})
    assert resp.status_code == 404


def test_alias_resolution():
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
