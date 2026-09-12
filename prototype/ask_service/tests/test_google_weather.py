"""google_weather: live fetch, TTL cache, and the fixture fallback that makes
the demo network-independent. No test here touches the real API.
"""

import json

import cities
import config
import google_weather
import httpx
import pytest
from config import FIXTURES_DIR

CC = "current_conditions"
FD = "forecast_days"


@pytest.fixture(autouse=True)
def _auto_mode(monkeypatch):
    """This module tests the live/cache/fallback machinery: auto mode, key present.
    Tests of the no-key path set GOOGLE_WEATHER_API_KEY back to None themselves.
    """
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")


def _fixture_response(kind, city):
    path = FIXTURES_DIR / "google_weather" / f"{kind}.{city}.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


@pytest.fixture
def live_stub(monkeypatch):
    """Serve fixture bodies through the fetch_json seam, counting calls."""
    calls = {"n": 0}
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        calls["n"] += 1
        kind = CC if "currentConditions" in path else FD
        city = next(c for c in ("chennai", "madurai", "coimbatore")
                    if abs(params["location.latitude"] - cities.CITIES[c].lat) < 1e-6)
        return _fixture_response(kind, city)

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    return calls


def test_live_path_marks_is_live(live_stub):
    snap = google_weather.snapshot(CC, "chennai")
    assert snap.is_live is True
    assert "live" in snap.source
    assert snap.payload == _fixture_response(CC, "chennai")
    assert live_stub["n"] == 1


def test_fixture_fallback_on_network_error(monkeypatch, caplog):
    def _boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(google_weather, "fetch_json", _boom)
    with caplog.at_level("WARNING"):
        snap = google_weather.snapshot(CC, "madurai")
    assert snap.is_live is False
    assert "snapshot" in snap.source
    assert snap.payload == _fixture_response(CC, "madurai")
    assert any("replaying fixture" in r.message for r in caplog.records)


def test_no_key_falls_back_to_fixture(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", None)
    snap = google_weather.snapshot(FD, "chennai")
    assert snap is not None and snap.is_live is False


def test_ttl_cache_reuses_within_window(live_stub, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(google_weather, "_monotonic", lambda: clock["t"])

    google_weather.snapshot(CC, "chennai")
    google_weather.snapshot(CC, "chennai")
    assert live_stub["n"] == 1  # second call served from cache

    clock["t"] += google_weather.TTL_SECONDS[CC] + 1
    google_weather.snapshot(CC, "chennai")
    assert live_stub["n"] == 2  # expired -> refetched

    clock["t"] += 1000  # forecast TTL is 6 h, still fresh conceptually
    google_weather.snapshot(FD, "chennai")
    google_weather.snapshot(FD, "chennai")
    assert live_stub["n"] == 3  # one forecast fetch, then cached


def test_fixture_fallback_is_not_cached(monkeypatch):
    state = {"fail": True}

    def _maybe(path, params, timeout=google_weather.TIMEOUT):
        if state["fail"]:
            raise httpx.ConnectError("down")
        return _fixture_response(CC, "chennai")

    monkeypatch.setattr(google_weather, "fetch_json", _maybe)
    assert google_weather.snapshot(CC, "chennai").is_live is False
    state["fail"] = False
    assert google_weather.snapshot(CC, "chennai").is_live is True


def test_fixtures_mode_never_calls_fetch(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")

    def _forbidden(*a, **k):
        raise AssertionError("fetch_json called in WEATHER_MODE=fixtures")

    monkeypatch.setattr(google_weather, "fetch_json", _forbidden)
    snap = google_weather.snapshot(CC, "coimbatore")
    assert snap.is_live is False


def test_live_mode_reraises(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "live")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")
    def _boom(*a, **k):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(google_weather, "fetch_json", _boom)
    with pytest.raises(httpx.HTTPError):
        google_weather.snapshot(CC, "chennai")


def test_unknown_kind_or_city_returns_none():
    assert google_weather.snapshot("hourly", "chennai") is None
    assert google_weather.snapshot(CC, "mumbai") is None


def test_decode_helpers():
    assert google_weather.decode_condition("SCATTERED_THUNDERSTORMS") == "scattered_thunderstorms"
    assert google_weather.decode_condition("CLOUDY") == "cloudy"
    assert google_weather.decode_condition(None) == "unknown"
    assert google_weather.decode_cardinal("SOUTH_SOUTHWEST") == "SSW"
    assert google_weather.decode_cardinal(None) == ""


def test_decode_condition_unknown_enum_logs(caplog):
    with caplog.at_level("INFO", logger="weathergpt.google_weather"):
        assert google_weather.decode_condition("FROG_STORM") == "frog_storm"
    assert any("unmapped" in r.message for r in caplog.records)


def test_params_history_hours_has_hours_param():
    params = google_weather._params("history_hours", "chennai")
    assert params["hours"] == google_weather.HISTORY_HOURS


def test_cache_stats_shape(live_stub):
    google_weather.snapshot(CC, "chennai")
    stats = google_weather.cache_stats()
    assert stats == {"entries": 1, "live": 1, "snapshot": 0}
