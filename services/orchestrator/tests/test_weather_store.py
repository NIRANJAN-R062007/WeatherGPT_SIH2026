"""weather_store: Redis L2 cache + Postgres persistence for weather snapshots
(plan.md §8 Phase 1). CI has no live Redis/Postgres, so every test here
exercises the "unreachable backend" path — the one that matters for the
demo, since a dead cache/DB must never break /ask (see the module docstring).
"""

import redis
import weather_store


def test_redis_get_returns_none_on_connection_error(monkeypatch):
    def _boom(*a, **k):
        raise redis.ConnectionError("refused")

    monkeypatch.setattr(weather_store._redis, "get", _boom)
    assert weather_store.redis_get("current_conditions", "chennai") is None


def test_redis_get_returns_none_on_miss(monkeypatch):
    monkeypatch.setattr(weather_store._redis, "get", lambda key: None)
    assert weather_store.redis_get("current_conditions", "chennai") is None


def test_redis_get_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(weather_store._redis, "get", lambda key: b"not json")
    assert weather_store.redis_get("current_conditions", "chennai") is None


def test_redis_get_roundtrips_through_setex(monkeypatch):
    store = {}

    def _setex(key, ttl, value):
        store[key] = value

    def _get(key):
        return store.get(key)

    monkeypatch.setattr(weather_store._redis, "setex", _setex)
    monkeypatch.setattr(weather_store._redis, "get", _get)

    fields = {"payload": {"temp": 30}, "is_live": True,
              "retrieved_at": "2026-09-20T00:00:00+00:00", "source": "live"}
    weather_store.redis_set("current_conditions", "chennai", fields, 900)
    assert weather_store.redis_get("current_conditions", "chennai") == fields


def test_redis_set_swallows_connection_error(monkeypatch):
    def _boom(*a, **k):
        raise redis.ConnectionError("refused")

    monkeypatch.setattr(weather_store._redis, "setex", _boom)
    weather_store.redis_set("current_conditions", "chennai", {"payload": {}}, 900)


def test_persist_swallows_any_failure(monkeypatch):
    def _boom():
        raise RuntimeError("no such host")

    monkeypatch.setattr(weather_store, "_ensure_schema", _boom)
    fields = {"payload": {"temp": 30}, "is_live": True,
              "retrieved_at": "2026-09-20T00:00:00+00:00", "source": "live"}
    weather_store.persist("current_conditions", "chennai", fields)


def test_redis_key_is_namespaced_by_kind_and_city():
    assert weather_store._redis_key("current_conditions", "chennai") == (
        "weathergpt:weather:current_conditions:chennai"
    )
