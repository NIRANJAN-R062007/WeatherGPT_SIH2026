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
                    if abs(params["location.latitude"] - cities.CITIES[c].lat) < 0.05)
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
    assert google_weather.snapshot(CC, "patna") is None


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
    # 48, not the 24 GET /forecast/hourly serves: 24 hours fetched at 10:00 end at 09:00
    # tomorrow, which would make "tomorrow" a part-day.
    params = google_weather._params("forecast_hours", "chennai")
    assert params["hours"] == google_weather.FORECAST_HOURS_FETCHED == 48
    assert google_weather.FORECAST_HOURS == 24


# --- the hourly lookup's pages: 48 hours take two calls ------------------------------


def _page(first_hour, n=24, token=""):
    """A forecast/hours:lookup reply of `n` hours starting `first_hour` hours after the
    fixture's first hour (so pages do not repeat each other), with `token` as its next page."""
    from datetime import datetime, timedelta

    hours = json.loads(json.dumps(_fixture_response(FH, "chennai")["forecastHours"]))[:n]
    for h in hours:
        start = datetime.fromisoformat(h["interval"]["startTime"].replace("Z", "+00:00"))
        start += timedelta(hours=first_hour)
        end = start + timedelta(hours=1)
        h["interval"] = {"startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ")}
    return {"forecastHours": hours, "timeZone": {"id": "Asia/Calcutta"}, "nextPageToken": token}


@pytest.fixture
def paged(monkeypatch):
    """fetch_json serving a two-page hourly series; every request is recorded."""
    sent = []
    pages = {None: _page(0, token="page-2"), "page-2": _page(24, token="")}

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        sent.append((path, dict(params)))
        return pages[params.get("pageToken")]

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    return sent


def test_forecast_hours_follows_the_next_page_token_to_48_hours(paged):
    snap = google_weather.snapshot(FH, "chennai")
    assert snap.is_live is True
    starts = [h["interval"]["startTime"] for h in snap.payload["forecastHours"]]
    assert len(starts) == 48 and starts == sorted(starts) and len(set(starts)) == 48
    assert "nextPageToken" not in snap.payload  # it was the first page's, not the series'
    assert snap.payload["timeZone"] == {"id": "Asia/Calcutta"}
    (_, first), (_, second) = paged
    assert first["hours"] == 48 and "pageToken" not in first
    assert second == {**first, "pageToken": "page-2"}  # the same query, one more key


def test_the_snapshot_script_captures_48_hours_for_the_next_refresh(monkeypatch, tmp_path):
    import snapshot_google_weather as script

    pages = {None: _page(0, token="page-2"), "page-2": _page(24, token="")}
    sent = []

    def _fetch(endpoint, lat, lon, **params):
        sent.append(params)
        return 200, pages[params.get("pageToken")]

    monkeypatch.setattr(script, "fetch", _fetch)
    monkeypatch.setattr(script, "OUT_DIR", tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)  # the script prints paths relative to it
    cities_ = script._load_cities()
    rows = script.snapshot("chennai", cities_, days=5, units="METRIC", force=True,
                           dry_run=False, kind=FH)
    assert [r[2] for r in rows] == [200]
    saved = json.loads((tmp_path / "forecast_hours.chennai.json").read_text(encoding="utf-8"))
    assert len(saved["response"]["forecastHours"]) == 48
    assert "nextPageToken" not in saved["response"]
    assert saved["_meta"]["request"]["hours"] == 48
    assert [p.get("pageToken") for p in sent] == [None, "page-2"]


def test_a_48_hour_live_series_gives_tomorrow_as_a_whole_day(paged):
    import weather_data

    tomorrow = weather_data.hourly_facts("chennai", "tomorrow")
    assert tomorrow["is_live"] is True
    times = [h["local_time"] for h in tomorrow["hours"]]
    assert times == [f"{h:02d}:00" for h in range(24)]


def test_a_reply_with_no_next_page_token_is_one_call(monkeypatch):
    calls = []

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        calls.append(params)
        return _fixture_response(FH, "chennai")  # nextPageToken is ""

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    snap = google_weather.snapshot(FH, "chennai")
    assert len(calls) == 1 and snap.payload == _fixture_response(FH, "chennai")


def test_a_failed_later_page_keeps_the_hours_already_fetched(monkeypatch, caplog):
    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        if params.get("pageToken"):
            raise httpx.ConnectError(f"down https://x/y?key={params['key']}")
        return _page(0, token="page-2")

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    with caplog.at_level("WARNING"):
        snap = google_weather.snapshot(FH, "chennai")
    assert snap.is_live is True  # not the stale fixture
    assert len(snap.payload["forecastHours"]) == 24
    assert "test-key" not in caplog.text
    import weather_data

    assert weather_data.hourly_facts("chennai", "today") is not None
    assert weather_data.hourly_facts("chennai", "tomorrow") is None  # the short series says so


def test_paging_stops_once_48_hours_are_in_hand(monkeypatch):
    calls = []

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        calls.append(params)
        return _page(24 * (len(calls) - 1), token="more")  # a token on every page

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    snap = google_weather.snapshot(FH, "chennai")
    assert len(snap.payload["forecastHours"]) == 48 and len(calls) == 2


def test_a_reply_that_never_stops_paging_is_cut_off(monkeypatch):
    calls = []

    def _fetch(path, params, timeout=google_weather.TIMEOUT):
        calls.append(params)
        return _page(len(calls) - 1, n=1, token="more")  # one hour a page, forever

    monkeypatch.setattr(google_weather, "fetch_json", _fetch)
    snap = google_weather.snapshot(FH, "chennai")
    assert len(calls) == google_weather.MAX_HOUR_PAGES
    assert len(snap.payload["forecastHours"]) == google_weather.MAX_HOUR_PAGES


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
    chennai = cities.CITIES["chennai"]  # keyed by its 0.05° cell, never a city name
    assert [(k, c) for k, c, _ in persist_calls] == \
        [(CC, google_weather.grid_key(chennai.lat, chennai.lon))]
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
    # The process-wide scrub (log_redaction, SEC-N8) shrinks the URL to its
    # host before this module's own _redacted() marker would show; the latter
    # stays as a second layer and is checked directly.
    assert "https://x" in caplog.text
    assert "REDACTED" in google_weather._redacted(httpx.ConnectError("https://x/y?key=sekret-key-123"))
