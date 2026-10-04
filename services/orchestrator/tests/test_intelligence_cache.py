"""WIE-15: the /intelligence/* result cache (intelligence_cache.py) — keys, the
TTL that never outlives the hourly forecast, and Redis failing open."""

from datetime import datetime, timedelta, timezone

import config
import intelligence_cache
import pytest
import redis

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class FakeRedis:
    """get/setex with the TTL recorded, a call counter and an optional error."""

    def __init__(self, error: Exception | None = None):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.calls = 0
        self.error = error

    def get(self, key):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.store[key] = value
        self.ttls[key] = ttl


@pytest.fixture
def fake(monkeypatch):
    """A live-mode process with a working Redis and a fixed clock."""
    fake = FakeRedis()
    monkeypatch.setattr(intelligence_cache, "_redis", fake)
    monkeypatch.setattr(intelligence_cache, "_now", lambda: NOW)
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "TTL_FORECAST_HOURS", 3600)
    return fake


def live_hourly(age_s: float = 600) -> dict:
    return {"source": "Google Weather API", "is_live": True, "day": "today", "hours": [],
            "retrieved_at": (NOW - timedelta(seconds=age_s)).isoformat()}


KEY = "weathergpt:intelligence:best-window:chennai:today:activity=outdoor"
ANSWER = {"city": "chennai", "status": "ok", "window": {"start_local": "09:00"}}


def test_key_names_route_city_day_and_the_other_parameters():
    assert intelligence_cache.key("best-window", "chennai", "today", activity="outdoor") == KEY
    assert (intelligence_cache.key("scenario", "pune", "tomorrow", times=["09:00", "17:00"],
                                   activity="farm")
            == "weathergpt:intelligence:scenario:pune:tomorrow:activity=farm:times=09:00,17:00")
    assert (intelligence_cache.key("changes", "chennai", "today")
            == "weathergpt:intelligence:changes:chennai:today")


@pytest.mark.parametrize("params", [
    {"activity": "skydiving"},
    {"times": ["9am"]},
    {"times": ["09:00", "24:00"]},
    {"times": ["09:00\n"]},
])
def test_a_value_the_engine_does_not_know_is_never_keyed(params):
    assert intelligence_cache.key("scenario", "chennai", "today", **params) is None


def test_remaining_life_is_the_hourly_ttl_minus_the_forecasts_age(fake):
    assert intelligence_cache.remaining_seconds((NOW - timedelta(minutes=10)).isoformat()) == 3000
    assert intelligence_cache.remaining_seconds("2026-10-04T11:50:00Z") == 3000
    assert intelligence_cache.remaining_seconds("2026-10-04T11:50:00") == 3000  # naive = UTC
    assert intelligence_cache.remaining_seconds("2026-10-04T10:00:00Z") <= 0
    # A clock-skewed future retrieval time never stretches the TTL.
    assert intelligence_cache.remaining_seconds("2026-10-04T12:30:00Z") == 3600
    assert intelligence_cache.remaining_seconds("not a time") == 0
    assert intelligence_cache.remaining_seconds(None) == 0


def test_an_answer_is_kept_for_the_rest_of_its_forecasts_life(fake):
    intelligence_cache.put(KEY, ANSWER, live_hourly(age_s=600))
    assert fake.ttls[KEY] == 3000
    assert intelligence_cache.get(KEY) == ANSWER


def test_the_stored_answer_is_what_the_client_would_see(fake):
    intelligence_cache.put(KEY, {"at": NOW, "n": 1.5}, live_hourly())
    assert intelligence_cache.get(KEY) == {"at": NOW.isoformat(), "n": 1.5}


@pytest.mark.parametrize("hourly", [
    {**live_hourly(), "is_live": False},  # a fixture, e.g. a failed live call replayed
    live_hourly(age_s=3600),  # the forecast is already spent
    {**live_hourly(), "retrieved_at": None},
    None,  # no forecast at all: "unavailable" is never pinned
])
def test_only_a_live_forecast_with_life_left_is_stored(fake, hourly):
    intelligence_cache.put(KEY, ANSWER, hourly)
    assert fake.store == {}


def test_an_unkeyed_request_is_never_stored(fake):
    intelligence_cache.put(None, ANSWER, live_hourly())
    assert intelligence_cache.get(None) is None
    assert fake.calls == 0


def test_fixtures_mode_never_touches_redis(fake, monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    intelligence_cache.put(KEY, ANSWER, live_hourly())
    assert intelligence_cache.get(KEY) is None
    assert fake.calls == 0


def test_a_malformed_entry_is_a_miss(fake):
    fake.store[KEY] = "{not json"
    assert intelligence_cache.get(KEY) is None


@pytest.mark.parametrize("error", [redis.ConnectionError("refused"), TimeoutError("timed out")])
def test_a_dead_redis_is_a_miss_and_is_parked(fake, monkeypatch, caplog, error):
    fake.error = error
    clock = [100.0]
    monkeypatch.setattr(intelligence_cache, "_monotonic", lambda: clock[0])
    assert intelligence_cache.get(KEY) is None
    intelligence_cache.put(KEY, ANSWER, live_hourly())  # parked: not even tried
    assert intelligence_cache.get(KEY) is None
    assert fake.calls == 1
    assert "redis unavailable" in caplog.text
    clock[0] += intelligence_cache._REDIS_RETRY_SECONDS
    fake.error = None
    intelligence_cache.put(KEY, ANSWER, live_hourly())  # tried again after the cooldown
    assert intelligence_cache.get(KEY) == ANSWER

