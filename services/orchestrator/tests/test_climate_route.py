"""GET /climate: serves climate.public() — the dated fixture snapshot when
offline, "unavailable" (never zero rain or "no trend") when ERA5 can't be read,
and a 404 for a city that isn't a demo city. No test touches the real service."""

import climate
import config
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _fresh_cache():
    climate.cache_clear()
    yield
    climate.cache_clear()


def test_climate_serves_the_fixture_snapshot_with_the_source_metadata(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    body = client.get("/climate", params={"city": "chennai"}).json()
    assert body["status"] == "ok"
    assert body["is_live"] is False
    assert body["city"] == "chennai"
    assert body["label"] == "Open-Meteo / ERA5 reanalysis, not IMD station data"
    assert body["credit"]["url"] == "https://open-meteo.com/"
    assert "computed by WeatherGPT" in body["changes_note"]
    assert body["licence_url"].startswith("https://open-meteo.com/")
    year = body["trends"]["year"]["temp_mean_c"]
    assert year["status"] == "ok" and year["n"] >= body["min_trend_years"]
    assert any(row["rain_mm"] is not None for row in body["annual"])


def test_climate_accepts_any_name_the_registry_knows(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    assert client.get("/climate", params={"city": "Mumbai"}).json()["city"] == "mumbai"


def test_climate_unknown_city_is_404_and_missing_city_is_422(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    assert client.get("/climate", params={"city": "patna"}).status_code == 404
    assert client.get("/climate", params={"city": "../../etc/passwd"}).status_code == 404
    assert client.get("/climate").status_code == 422


def test_climate_a_city_with_no_snapshot_offline_is_unavailable_not_zero(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    body = client.get("/climate", params={"city": "madurai"}).json()
    assert body["status"] == "unavailable"
    for field in ("monthly", "seasonal", "annual", "trends"):
        assert body[field] is None
    assert body["label"] and body["credit"]


def test_climate_never_calls_the_network_in_fixtures_mode(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    calls = []
    monkeypatch.setattr(climate, "_get_json", lambda *a, **k: calls.append(a))
    client.get("/climate", params={"city": "delhi"})
    assert calls == []
