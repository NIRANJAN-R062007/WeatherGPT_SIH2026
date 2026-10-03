"""Snapping and privacy for location-based weather (plan.md design decision,
step 5): weather is fetched and cached for the 0.05° grid cell, never the raw
fix, and a raw GPS fix reaches no log, metric, cache key, weather_facts row or
history record — at most 2 decimals (~1 km) anywhere.
"""

import json
import logging
import re

import cities
import config
import google_weather
import history
import location
import main
import metrics
import pytest
import weather_store
from fastapi.testclient import TestClient

client = TestClient(main.app)
_STEP5 = pytest.mark.xfail(strict=True, reason="step 5: grid snapping + privacy")

RAW_LAT, RAW_LON = 10.790537, 78.704681
# Anything finer than 2 decimals of the raw fix: 10.790537 -> "10.79" is
# allowed, "10.790", "10.7905", "790537" are not.
_LEAK = re.compile(r"10\.79\d|78\.70[1-9]|78\.704|790537|704681")


def _payload(kind):
    path = config.FIXTURES_DIR / "google_weather" / f"{kind}.chennai.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    fetched = []

    def _serve(path, params, timeout=google_weather.TIMEOUT):
        fetched.append(dict(params))
        kind = next(k for k, ep in google_weather.ENDPOINTS.items() if ep == path)
        return _payload(kind)

    monkeypatch.setattr(google_weather, "fetch_json", _serve)
    return fetched


@_STEP5
@pytest.mark.parametrize("raw,snapped", [
    (10.790537, 10.80), (78.704681, 78.70), (13.0827, 13.10), (80.2707, 80.25),
    (8.4249, 8.40), (-0.024, 0.0), (77.5946, 77.60),
])
def test_snap_is_a_two_decimal_point_on_the_005_grid(raw, snapped):
    out = google_weather.snap(raw)
    assert out == snapped
    assert str(out) != "-0.0"


@_STEP5
def test_grid_key_is_the_snapped_cell():
    assert google_weather.grid_key(RAW_LAT, RAW_LON) == "@10.80,78.70"
    c = cities.CITIES["chennai"]
    assert google_weather.grid_key(c.lat, c.lon) == "@13.10,80.25"


@_STEP5
def test_weather_is_fetched_for_the_snapped_point(live):
    client.get("/ask", params={"text": "will it rain here", "lat": RAW_LAT, "lon": RAW_LON})
    assert live
    for params in live:
        assert (params["location.latitude"], params["location.longitude"]) == (10.80, 78.70)


@_STEP5
def test_a_demo_city_is_fetched_for_its_cell_too(live):
    client.get("/ask", params={"text": "what's the weather in Chennai"})
    assert {(p["location.latitude"], p["location.longitude"]) for p in live} == {(13.10, 80.25)}


@_STEP5
def test_nearby_users_share_one_cache_entry(live):
    for lat, lon in ((10.790537, 78.704681), (10.81, 78.69), (10.79, 78.72)):
        client.get("/ask", params={"text": "what's the weather here", "lat": lat, "lon": lon})
    assert len(live) == 1  # one current-conditions fetch for the whole cell


@_STEP5
def test_redis_and_weather_facts_are_keyed_by_cell(live, monkeypatch):
    keys = []
    monkeypatch.setattr(weather_store, "redis_set",
                        lambda kind, city, fields, ttl: keys.append(("redis", kind, city)))
    monkeypatch.setattr(weather_store, "persist",
                        lambda kind, city, fields: keys.append(("pg", kind, city)))
    client.get("/ask", params={"text": "what's the weather in Chennai"})
    client.get("/ask", params={"text": "what's the weather here", "lat": RAW_LAT,
                               "lon": RAW_LON})
    cells = {city for _, _, city in keys}
    assert cells == {"@13.10,80.25", "@10.80,78.70"}  # never "chennai"


class _LeakyEngine:
    """Fails the way SQLAlchemy does: the bound parameters in the error text."""

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        raise RuntimeError(f"(psycopg2.OperationalError) boom [parameters: {params}]")


@_STEP5
def test_a_raw_gps_fix_reaches_no_log_metric_cache_or_history(live, monkeypatch, caplog):
    sinks = []
    monkeypatch.setattr(weather_store, "redis_set",
                        lambda *a, **k: sinks.append(("redis_set", a, k)))
    monkeypatch.setattr(weather_store, "persist",
                        lambda *a, **k: sinks.append(("persist", a, k)))
    monkeypatch.setattr(history, "record", lambda *a, **k: sinks.append(("history", a, k)))
    real_observe = metrics.observe_ask
    monkeypatch.setattr(metrics, "observe_ask",
                        lambda **k: (sinks.append(("metrics", (), k)), real_observe(**k)))
    monkeypatch.setattr(weather_store, "_engine", _LeakyEngine())
    monkeypatch.setattr(location, "_pg_down_until", 0.0)
    caplog.set_level(logging.DEBUG)

    resp = client.get("/ask", params={"text": "will it rain here", "lat": RAW_LAT,
                                      "lon": RAW_LON},
                      headers={"Authorization": "Bearer test-token"})
    body = resp.json()
    assert "response" in body and body["location"]["source"] == "gps"

    assert any(name == "history" for name, _, _ in sinks)
    assert any(name == "persist" for name, _, _ in sinks)
    for name, args, kwargs in sinks:
        assert not _LEAK.search(repr((args, kwargs))), name
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "postgres unavailable" in logged  # the leaky error path really ran
    assert not _LEAK.search(logged)
    assert not _LEAK.search(json.dumps(body, ensure_ascii=False))
    assert not _LEAK.search(repr(google_weather._CACHE.keys()))
