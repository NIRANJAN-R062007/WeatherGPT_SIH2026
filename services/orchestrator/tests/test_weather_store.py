"""weather_store: Redis L2 cache + Postgres persistence for weather snapshots
(plan.md §8 Phase 1). CI has no live Redis/Postgres, so every test here
exercises the "unreachable backend" path — the one that matters for the
demo, since a dead cache/DB must never break /ask (see the module docstring).

Postgres tests fake `_engine` and run the persist queue on the test's own
thread via `_drain()`; only the thread tests start a real writer, bound to
that test's private queue.
"""

import os
import queue
import threading

import pytest
import redis
import weather_store

_ENSURE_WORKER = weather_store._ensure_worker  # the real one; stubbed out below

FIELDS = {"payload": {"temp": 30}, "is_live": True,
          "retrieved_at": "2026-09-20T00:00:00+00:00", "source": "live"}


class _FakeEngine:
    """Stands in for weather_store._engine: counts begin() calls, records
    INSERT params, and refuses connections while `down` is set."""

    def __init__(self, down=False):
        self.down = down
        self.begins = 0
        self.ddl = 0
        self.rows = []

    def begin(self):
        self.begins += 1
        if self.down:
            raise RuntimeError("connection refused")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        if params is None:
            self.ddl += 1
        else:
            self.rows.append(params)


@pytest.fixture(autouse=True)
def _isolated_writer(monkeypatch):
    """Fresh queue + cooldown per test and no writer thread, so tests drain
    synchronously. Thread tests put the real _ensure_worker back themselves."""
    monkeypatch.setattr(weather_store, "_queue", queue.Queue(maxsize=weather_store._QUEUE_MAX))
    monkeypatch.setattr(weather_store, "_ensure_worker", lambda: None)
    monkeypatch.setattr(weather_store, "_worker", None)
    monkeypatch.setattr(weather_store, "_worker_pid", None)
    monkeypatch.setattr(weather_store, "_cooldown_until", 0.0)
    monkeypatch.setattr(weather_store, "_SCHEMA_READY", False)


@pytest.fixture
def clock(monkeypatch):
    state = {"t": 1000.0}
    monkeypatch.setattr(weather_store, "_monotonic", lambda: state["t"])
    return state


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

    weather_store.redis_set("current_conditions", "chennai", FIELDS, 900)
    assert weather_store.redis_get("current_conditions", "chennai") == FIELDS


def test_redis_set_swallows_connection_error(monkeypatch):
    def _boom(*a, **k):
        raise redis.ConnectionError("refused")

    monkeypatch.setattr(weather_store._redis, "setex", _boom)
    weather_store.redis_set("current_conditions", "chennai", {"payload": {}}, 900)


def test_persist_swallows_any_failure(monkeypatch):
    def _boom():
        raise RuntimeError("no such host")

    monkeypatch.setattr(weather_store, "_ensure_schema", _boom)
    weather_store.persist("current_conditions", "chennai", FIELDS)
    weather_store._drain()


def test_persist_bootstraps_schema_once_and_inserts_each_row(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)

    weather_store.persist("current_conditions", "chennai", FIELDS)
    weather_store.persist("forecast_days", "madurai", FIELDS)
    weather_store._drain()

    assert engine.ddl == 2 and weather_store._SCHEMA_READY  # CREATE TABLE + INDEX, once
    assert [(r["kind"], r["city"]) for r in engine.rows] == [
        ("current_conditions", "chennai"), ("forecast_days", "madurai"),
    ]
    assert engine.rows[0]["payload"] == '{"temp": 30}'
    assert engine.rows[0]["is_live"] is True
    assert engine.rows[0]["retrieved_at"] == FIELDS["retrieved_at"]


def test_failed_write_trips_cooldown_with_one_warning(monkeypatch, clock, caplog):
    engine = _FakeEngine(down=True)
    monkeypatch.setattr(weather_store, "_engine", engine)

    with caplog.at_level("WARNING", logger="weathergpt.weather_store"):
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store._drain()
        for _ in range(3):
            weather_store.persist("current_conditions", "chennai", FIELDS)
        clock["t"] += weather_store._COOLDOWN_SECONDS - 1
        weather_store._drain()

    assert engine.begins == 1  # the three rows inside the window never touched the engine
    assert weather_store._SCHEMA_READY is False
    warnings = [r for r in caplog.records if "skipping weather_facts" in r.message]
    assert len(warnings) == 1 and warnings[0].levelname == "WARNING"
    assert warnings[0].exc_info is None  # a one-liner, not a stack trace


def test_cooldown_expiry_retries_schema_and_insert(monkeypatch, clock):
    engine = _FakeEngine(down=True)
    monkeypatch.setattr(weather_store, "_engine", engine)
    weather_store.persist("current_conditions", "chennai", FIELDS)
    weather_store._drain()
    assert engine.begins == 1 and engine.rows == []

    clock["t"] += weather_store._COOLDOWN_SECONDS + 1
    engine.down = False
    weather_store.persist("current_conditions", "chennai", FIELDS)
    weather_store._drain()

    assert engine.ddl == 2 and weather_store._SCHEMA_READY  # DDL reran after the failed attempt
    assert len(engine.rows) == 1


def test_failure_after_expiry_opens_a_new_window(monkeypatch, clock, caplog):
    engine = _FakeEngine(down=True)
    monkeypatch.setattr(weather_store, "_engine", engine)

    with caplog.at_level("WARNING", logger="weathergpt.weather_store"):
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store._drain()
        clock["t"] += weather_store._COOLDOWN_SECONDS + 1
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store._drain()

    assert engine.begins == 2
    assert sum("skipping weather_facts" in r.message for r in caplog.records) == 2


def test_full_queue_drops_newest_without_raising(caplog, monkeypatch):
    monkeypatch.setattr(weather_store, "_queue", queue.Queue(maxsize=1))

    with caplog.at_level("WARNING", logger="weathergpt.weather_store"):
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store.persist("forecast_days", "chennai", FIELDS)

    assert weather_store._queue.qsize() == 1
    assert weather_store._queue.get_nowait()[0] == "current_conditions"
    assert any("queue full" in r.message and "forecast_days" in r.message
               for r in caplog.records)


def test_malformed_item_is_a_worker_error_not_a_cooldown(monkeypatch, caplog):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)

    with caplog.at_level("ERROR", logger="weathergpt.weather_store"):
        weather_store.persist("current_conditions", "chennai", {"payload": {}})
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store._drain()

    assert any("unexpected error" in r.message for r in caplog.records)
    assert weather_store._cooldown_until == 0.0
    assert len(engine.rows) == 1  # the good row behind it still went in


def test_persist_returns_while_writer_is_blocked(monkeypatch):
    monkeypatch.setattr(weather_store, "_ensure_worker", _ENSURE_WORKER)
    entered, release = threading.Event(), threading.Event()
    done = queue.Queue()

    def _slow_write(kind, city, fields):
        entered.set()
        release.wait(5)
        done.put(kind)

    monkeypatch.setattr(weather_store, "_write", _slow_write)
    weather_store.persist("current_conditions", "chennai", FIELDS)
    worker = weather_store._worker
    assert worker.is_alive() and worker.daemon
    assert entered.wait(5)
    assert done.empty()  # persist() is back while the write is still in flight
    weather_store.persist("forecast_days", "chennai", FIELDS)  # queues behind it, no wait
    assert weather_store._worker is worker  # started once, then reused

    release.set()
    assert [done.get(timeout=5), done.get(timeout=5)] == ["current_conditions", "forecast_days"]


def test_worker_thread_survives_unexpected_exception(monkeypatch, caplog):
    monkeypatch.setattr(weather_store, "_ensure_worker", _ENSURE_WORKER)
    done = threading.Event()
    seen = []

    def _write(kind, city, fields):
        seen.append(kind)
        if kind == "current_conditions":
            raise ValueError("bug")
        done.set()

    monkeypatch.setattr(weather_store, "_write", _write)
    with caplog.at_level("ERROR", logger="weathergpt.weather_store"):
        weather_store.persist("current_conditions", "chennai", FIELDS)
        weather_store.persist("forecast_days", "chennai", FIELDS)
        assert done.wait(5)

    assert seen == ["current_conditions", "forecast_days"]
    assert weather_store._worker.is_alive()
    assert any("unexpected error" in r.message for r in caplog.records)


def test_worker_restarts_with_a_fresh_queue_after_fork(monkeypatch):
    monkeypatch.setattr(weather_store, "_ensure_worker", _ENSURE_WORKER)
    written = queue.Queue()
    monkeypatch.setattr(weather_store, "_write", lambda kind, city, fields: written.put(kind))

    weather_store.persist("current_conditions", "chennai", FIELDS)
    assert written.get(timeout=5) == "current_conditions"
    parent_worker, parent_queue = weather_store._worker, weather_store._queue

    real_pid = os.getpid()
    monkeypatch.setattr(os, "getpid", lambda: real_pid + 1)  # what a forked child sees
    weather_store.persist("forecast_days", "chennai", FIELDS)
    assert written.get(timeout=5) == "forecast_days"

    assert weather_store._worker is not parent_worker
    assert weather_store._queue is not parent_queue


def test_redis_key_is_namespaced_by_kind_and_city():
    assert weather_store._redis_key("current_conditions", "chennai") == (
        "weathergpt:weather:current_conditions:chennai"
    )
