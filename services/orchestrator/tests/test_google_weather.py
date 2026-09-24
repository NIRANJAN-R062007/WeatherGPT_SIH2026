"""google_weather: live fetch, TTL cache, and the fixture fallback that makes
the demo network-independent. No test here touches the real API.
"""

import json

import cities
import config
import google_weather
import httpx
import pytest
import weather_store
from config import FIXTURES_DIR

CC = "current_conditions"
FH = "forecast_hours"
FD = "forecast_days"
HH = "history_hours"


@pytest.fixture(autouse=True)
def _auto_mode(monkeypatch):
    """This module tests the live/cache/fallback machinery: auto mode, key present.
    Tests of the no-key path set GOOGLE_WEATHER_API_KEY back to None themselves.
    """
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def persist_calls(monkeypatch):
    """Record weather_store.persist() calls instead of starting its writer
    thread against a Postgres that isn't there (test_weather_store covers it)."""
    calls = []
    monkeypatch.setattr(weather_store, "persist",
                        lambda kind, city, fields: calls.append((kind, city, fields)))
    return calls


def _fixture_response(kind, city):
    path = FIXTURES_DIR / "google_weather" / f"{kind}.{city}.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


@pytest.fixture
def live_stub(monkeypatch):
    """Serve fixture bodies through the fetch_json seam, counting calls."""
    calls = {"n": 0}
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")

    _path_to_kind = {v: k for k, v in google_weather.ENDPOINTS.items()}

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        calls["n"] += 1
        kind = _path_to_kind[path]
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

    clock["t"] += google_weather.ttl_seconds(CC) + 1
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
    assert google_weather.snapshot(CC, "kolkata") is None


def test_decode_helpers():
    assert google_weather.decode_condition("SCATTERED_THUNDERSTORMS") == "scattered_thunderstorms"
    assert google_weather.decode_condition("CLOUDY") == "cloudy"
    assert google_weather.decode_condition(None) == "unknown"
    assert google_weather.decode_cardinal("SOUTH_SOUTHWEST") == "SSW"
    assert google_weather.decode_cardinal(None) == ""


def test_decode_precip_category():
    assert google_weather.decode_precip_category(None) is None
    assert google_weather.decode_precip_category(0) == "no_rain"
    assert google_weather.decode_precip_category(10) == "light"
    assert google_weather.decode_precip_category(15.6) == "moderate"
    assert google_weather.decode_precip_category(64.4) == "moderate"
    assert google_weather.decode_precip_category(64.5) == "heavy"
    assert google_weather.decode_precip_category(115.5) == "heavy"
    assert google_weather.decode_precip_category(204.4) == "very_heavy"
    assert google_weather.decode_precip_category(300) == "extremely_heavy"


def test_decode_uv_band():
    assert google_weather.decode_uv_band(None) is None
    assert google_weather.decode_uv_band(0) == "low"
    assert google_weather.decode_uv_band(2) == "low"
    assert google_weather.decode_uv_band(3) == "moderate"
    assert google_weather.decode_uv_band(6) == "high"
    assert google_weather.decode_uv_band(8) == "very_high"
    assert google_weather.decode_uv_band(11) == "extreme"
    assert google_weather.decode_uv_band(15) == "extreme"


def test_decode_condition_unknown_enum_logs(caplog):
    with caplog.at_level("INFO", logger="weathergpt.google_weather"):
        assert google_weather.decode_condition("FROG_STORM") == "frog_storm"
    assert any("unmapped" in r.message for r in caplog.records)


def test_ttl_seconds_reads_config_live(monkeypatch):
    monkeypatch.setattr(config, "TTL_CURRENT_CONDITIONS", 5)
    assert google_weather.ttl_seconds(CC) == 5


def test_params_history_hours_has_hours_param():
    params = google_weather._params("history_hours", "chennai")
    assert params["hours"] == google_weather.HISTORY_HOURS


def test_params_forecast_hours_has_hours_param():
    params = google_weather._params("forecast_hours", "chennai")
    assert params["hours"] == google_weather.FORECAST_HOURS


def test_forecast_hours_live_and_fixture(live_stub):
    snap = google_weather.snapshot(FH, "chennai")
    assert snap.is_live is True
    assert snap.payload == _fixture_response(FH, "chennai")


def test_forecast_hours_fixture_exists_for_every_demo_city():
    for city in ("chennai", "madurai", "coimbatore"):
        assert _fixture_response(FH, city)


def test_cache_stats_shape(live_stub):
    google_weather.snapshot(CC, "chennai")
    stats = google_weather.cache_stats()
    assert stats == {"entries": 1, "live": 1, "snapshot": 0}


def test_live_fetch_persists_exactly_once(live_stub, persist_calls):
    google_weather.snapshot(CC, "chennai")
    google_weather.snapshot(CC, "chennai")  # L1 hit: no fetch, no persist
    assert [(k, c) for k, c, _ in persist_calls] == [(CC, "chennai")]
    fields = persist_calls[0][2]
    assert fields["is_live"] is True
    assert fields["payload"] == _fixture_response(CC, "chennai")


def test_only_live_fetches_persist(monkeypatch, persist_calls):
    def _boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(google_weather, "fetch_json", _boom)
    assert google_weather.snapshot(CC, "chennai").is_live is False  # fixture fallback

    remote = {"payload": {}, "is_live": True, "retrieved_at": "2026-09-20T00:00:00+00:00",
              "source": "live"}
    monkeypatch.setattr(weather_store, "redis_get", lambda kind, city: remote)
    assert google_weather.snapshot(FD, "chennai").is_live is True  # L2 hit, not a fetch

    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    google_weather.snapshot(FD, "madurai")

    assert persist_calls == []


def test_live_failure_log_never_contains_the_api_key(monkeypatch, caplog):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "sekret-key-123")

    def _boom(path, params, timeout=10.0):
        raise httpx.ConnectError(f"boom https://x/y?key={params['key']}")

    monkeypatch.setattr(google_weather, "fetch_json", _boom)
    with caplog.at_level("WARNING"):
        google_weather.snapshot("current_conditions", "chennai")
    assert "sekret-key-123" not in caplog.text
    assert "REDACTED" in caplog.text
