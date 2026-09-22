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
from pathlib import Path

import cities
import pytest
import redis
import weather_store

_ENSURE_WORKER = weather_store._ensure_worker  # the real one; stubbed out below

FIELDS = {"payload": {"temp": 30}, "is_live": True,
          "retrieved_at": "2026-09-20T00:00:00+00:00", "source": "live"}


class _Result:
    """Enough of a SQLAlchemy result for the migration ledger SELECT (iterated
    for applied filenames) and prune()'s DELETE (asked for rowcount)."""

    def __init__(self, rows=(), rowcount=0):
        self._rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)


class _FakeEngine:
    """Stands in for weather_store._engine: counts begin() calls, records
    INSERT params, and refuses connections while `down` is set."""

    def __init__(self, down=False, fail_on=None):
        self.down = down
        # Substring of a migration file's SQL that should fail when applied —
        # used to reproduce a role without CREATE EXTENSION rights.
        self.fail_on = fail_on
        self.begins = 0
        self.ddl = 0
        self.rows = []
        self.deletes = []
        self.statements = []

    def begin(self):
        self.begins += 1
        if self.down:
            raise RuntimeError("connection refused")
        return self

    def connect(self):
        return self.begin()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        if params is None:
            self.ddl += 1
        elif "DELETE" in str(stmt).upper():
            # prune()'s retention sweep — kept out of `rows` so it can't be
            # mistaken for a written snapshot.
            self.deletes.append(params)
        else:
            self.rows.append(params)
        return _Result(rowcount=len(self.deletes))

    def exec_driver_sql(self, sql, params=None):
        """The migration runner's channel. `ddl` counts applied migration
        *files* only — the schema_migrations ledger's own create/select/insert
        is bookkeeping, not schema — so the existing assertions below still
        read as "the schema was applied once"."""
        self.statements.append(sql)
        if "schema_migrations" in sql:
            return _Result()  # ledger: nothing applied yet, so every file runs
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("permission denied to create extension")
        self.ddl += 1
        return _Result()


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

    # One apply per migration file, once — sql/NNN_*.sql, not a copy in the module.
    assert engine.ddl == len(weather_store.migration_files())
    assert weather_store._SCHEMA_READY
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

    # DDL reran after the failed attempt
    assert engine.ddl == len(weather_store.migration_files())
    assert weather_store._SCHEMA_READY
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


# --------------------------------------------------------------------------
# Schema: sql/NNN_*.sql is the only definition (plan.md §8 Phase 1,
# "Schema/infra support for the data layer")
# --------------------------------------------------------------------------

def test_migration_files_are_ordered_and_numbered():
    names = [p.name for p in weather_store.migration_files()]
    assert names == sorted(names)
    assert names[0].startswith("001_")
    assert all(n[:3].isdigit() for n in names), names


def test_supabase_schema_is_not_treated_as_a_migration():
    """sql/supabase_schema.sql shares the directory but is a Supabase-dashboard
    script (auth.users, RLS helpers) — running it against our own Postgres
    fails, and failing forever would keep _SCHEMA_READY False and re-run the
    whole set on every write."""
    assert (weather_store._MIGRATIONS_DIR / "supabase_schema.sql").exists()
    assert "supabase_schema.sql" not in [p.name for p in weather_store.migration_files()]


def test_no_schema_ddl_lives_outside_the_sql_files():
    """weather_store.py used to carry its own copy of the CREATE TABLE.

    Two definitions of one table drift silently, which is what this task set
    out to remove — so the module must not grow one back.
    """
    source = Path(weather_store.__file__).read_text(encoding="utf-8")
    code = source.split('"""', 2)[2]  # skip the module docstring
    assert "CREATE TABLE IF NOT EXISTS weather_facts" not in code
    assert "CREATE TABLE IF NOT EXISTS cities" not in code


def test_weather_facts_columns_match_the_insert():
    """Guard the one join between sql/002 and _write()'s INSERT."""
    ddl = (weather_store._MIGRATIONS_DIR / "002_weather_facts.sql").read_text(encoding="utf-8")
    for column in ("kind", "city", "payload", "is_live", "source", "retrieved_at"):
        assert f"{column} " in ddl or f"    {column}" in ddl, column


def test_each_migration_gets_its_own_transaction(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)

    weather_store._ensure_schema()

    assert weather_store._SCHEMA_READY
    # One for the ledger, then one per migration file.
    assert engine.begins == 1 + len(weather_store.migration_files())
    assert any("CREATE TABLE IF NOT EXISTS weather_facts" in s for s in engine.statements)


def test_failing_extension_does_not_stop_later_migrations(monkeypatch):
    """001 (CREATE EXTENSION postgis) is the statement a managed role may lack
    rights for — verified live against such a role. weather_facts must still
    be created when it fails."""
    engine = _FakeEngine(fail_on="CREATE EXTENSION")
    monkeypatch.setattr(weather_store, "_engine", engine)

    weather_store._ensure_schema()

    assert any("CREATE TABLE IF NOT EXISTS weather_facts" in s
               for s in engine.statements), "gave up after the failed file"
    assert not weather_store._SCHEMA_READY, "a partial schema must be retried, not latched"


def test_prune_is_a_no_op_when_retention_is_disabled(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(weather_store.config, "WEATHER_FACTS_RETENTION_DAYS", 0)

    assert weather_store.prune() == 0
    assert engine.begins == 0, "touched the database with retention off"


def test_retention_sweep_runs_at_most_once_an_hour(monkeypatch, clock):
    calls = []
    monkeypatch.setattr(weather_store, "prune", lambda: calls.append(1) or 0)
    monkeypatch.setattr(weather_store, "_last_prune", 0.0)

    weather_store._maybe_prune()
    weather_store._maybe_prune()
    assert len(calls) == 1

    clock["t"] += weather_store._PRUNE_INTERVAL_SECONDS + 1
    weather_store._maybe_prune()
    assert len(calls) == 2


def test_retention_sweep_respects_the_postgres_cooldown(monkeypatch, clock):
    """A parked Postgres must not pay a connect timeout for a sweep either."""
    calls = []
    monkeypatch.setattr(weather_store, "prune", lambda: calls.append(1) or 0)
    monkeypatch.setattr(weather_store, "_last_prune", 0.0)
    monkeypatch.setattr(weather_store, "_cooldown_until", clock["t"] + 30)

    weather_store._maybe_prune()
    assert calls == []


def test_a_failed_sweep_does_not_cost_the_row(monkeypatch):
    """_maybe_prune runs inside _process's try, so a broken sweep is a logged
    worker error, not a lost write."""
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(weather_store, "_last_prune", 0.0)

    def _boom():
        raise RuntimeError("delete failed")

    monkeypatch.setattr(weather_store, "prune", _boom)
    weather_store.persist("current_conditions", "chennai", FIELDS)
    weather_store._drain()

    assert len(engine.rows) == 1, "the row was written before the sweep ran"


def test_sync_cities_writes_every_city_in_the_registry(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)

    assert weather_store.sync_cities() == len(cities.CITIES)
    assert {row["key"] for row in engine.rows} == set(cities.CITIES)
    # lat/lon feed the generated geography column the Phase 4 geofence queries.
    assert all(isinstance(row["lat"], float) and isinstance(row["lon"], float)
               for row in engine.rows)
