"""WIE-9: forecast_snapshots (the in-process ring + the Postgres hand-off)
and weather_store's snapshot read/write/prune."""

import queue
from datetime import datetime, timezone

import forecast_snapshots
import pytest
import weather_store
from test_weather_store import _FakeEngine  # shared test double


@pytest.fixture(autouse=True)
def _isolated_writer(monkeypatch):
    """Fresh queue + cooldown per test and no writer thread: tests drain the
    persist queue synchronously (the same isolation test_weather_store uses)."""
    monkeypatch.setattr(weather_store, "_queue", queue.Queue(maxsize=weather_store._QUEUE_MAX))
    monkeypatch.setattr(weather_store, "_ensure_worker", lambda: None)
    monkeypatch.setattr(weather_store, "_worker", None)
    monkeypatch.setattr(weather_store, "_worker_pid", None)
    monkeypatch.setattr(weather_store, "_cooldown_until", 0.0)
    monkeypatch.setattr(weather_store, "_SCHEMA_READY", False)

PAYLOAD = {"forecastHours": [
    {"interval": {"startTime": "2026-10-04T08:00:00Z"},
     "temperature": {"degrees": 27.5}, "precipitation": {"probability": {"percent": 30}},
     "wind": {"speed": {"value": 11.0}}, "weatherCondition": {"type": "CLOUDY"}, "uvIndex": 6},
    {"interval": {"startTime": "2026-10-04T09:00:00Z"},
     "temperature": {"degrees": 28.0}, "precipitation": {"probability": {"percent": 40}},
     "wind": {"speed": {"value": 12.0}}},
    {"interval": {}},  # no start time: skipped
]}


def test_rows_from_payload_flattens_the_columns_of_the_table():
    rows = forecast_snapshots.rows_from_payload(PAYLOAD)
    assert [r["forecast_time"] for r in rows] == [
        "2026-10-04T08:00:00+00:00", "2026-10-04T09:00:00+00:00"]
    assert rows[0] == {
        "forecast_time": "2026-10-04T08:00:00+00:00", "temp_c": 27.5,
        "rain_probability_pct": 30, "wind_kmh": 11.0, "condition": "CLOUDY", "uv_index": 6}
    assert rows[1]["uv_index"] is None and rows[1]["condition"] is None


def test_previous_is_the_newest_retrieval_strictly_before_the_given_one(monkeypatch):
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: None)
    for when in ("2026-10-04T05:00:00Z", "2026-10-04T06:00:00Z", "2026-10-04T07:00:00Z"):
        forecast_snapshots.record("pt:13.10,80.25", 13.1, 80.25, PAYLOAD, when)
    got = forecast_snapshots.previous("pt:13.10,80.25", "2026-10-04T07:00:00Z")
    assert got["retrieved_at"] == "2026-10-04T06:00:00+00:00"
    assert set(got["hours"]) == {"2026-10-04T08:00:00+00:00", "2026-10-04T09:00:00+00:00"}


def test_previous_is_none_when_nothing_is_earlier_and_the_database_has_nothing(monkeypatch):
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: None)
    monkeypatch.setattr(weather_store, "read_snapshot_before", lambda cell, before: None)
    forecast_snapshots.record("pt:13.10,80.25", 13.1, 80.25, PAYLOAD, "2026-10-04T06:00:00Z")
    assert forecast_snapshots.previous("pt:13.10,80.25", "2026-10-04T06:00:00Z") is None
    assert forecast_snapshots.previous("pt:9.90,78.10", "2026-10-04T09:00:00Z") is None


def test_previous_falls_back_to_the_database(monkeypatch):
    stored = {"retrieved_at": "2026-10-04T01:00:00+00:00", "hours": {}}
    monkeypatch.setattr(weather_store, "read_snapshot_before", lambda cell, before: stored)
    assert forecast_snapshots.previous("pt:13.10,80.25", "2026-10-04T06:00:00Z") is stored


def test_the_same_retrieval_is_not_recorded_twice(monkeypatch):
    queued = []
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: queued.append(a))
    for _ in range(2):
        forecast_snapshots.record("pt:13.10,80.25", 13.1, 80.25, PAYLOAD, "2026-10-04T06:00:00Z")
    assert len(queued) == 1


def test_the_ring_keeps_only_the_newest_snapshots(monkeypatch):
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: None)
    monkeypatch.setattr(weather_store, "read_snapshot_before", lambda cell, before: None)
    for h in range(forecast_snapshots._MEMORY_PER_CELL + 3):
        forecast_snapshots.record(
            "pt:13.10,80.25", 13.1, 80.25, PAYLOAD, f"2026-10-04T{h:02d}:00:00Z")
    assert forecast_snapshots.previous("pt:13.10,80.25", "2026-10-04T02:30:00Z") is None


def test_record_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("queue exploded")

    monkeypatch.setattr(weather_store, "persist", boom)
    forecast_snapshots.record("pt:13.10,80.25", 13.1, 80.25, PAYLOAD, "2026-10-04T06:00:00Z")


def test_record_ignores_a_payload_with_no_hours(monkeypatch):
    queued = []
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: queued.append(a))
    forecast_snapshots.record("pt:13.10,80.25", 13.1, 80.25, {}, "2026-10-04T06:00:00Z")
    assert queued == []


# --- weather_store: the worker's INSERT, the read, the sweep -----------------


def test_write_snapshot_inserts_one_row_per_hour(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    fields = {"latitude": 13.1, "longitude": 80.25, "retrieved_at": "2026-10-04T06:00:00+00:00",
              "rows": forecast_snapshots.rows_from_payload(PAYLOAD)}
    weather_store.persist(forecast_snapshots.KIND, "pt:13.10,80.25", fields)
    weather_store._drain()
    assert len(engine.rows) == 1 and isinstance(engine.rows[0], list)
    written = engine.rows[0]
    assert [r["city"] for r in written] == ["pt:13.10,80.25"] * 2
    assert written[0]["latitude"] == 13.1 and written[0]["temp_c"] == 27.5


def test_a_failed_snapshot_write_parks_postgres(monkeypatch):
    monkeypatch.setattr(weather_store, "_engine", _FakeEngine(down=True))
    monkeypatch.setattr(weather_store, "_cooldown_until", 0.0)
    fields = {"latitude": 1, "longitude": 2, "retrieved_at": "x", "rows": []}
    weather_store.persist(forecast_snapshots.KIND, "pt:1.00,2.00", fields)
    weather_store._drain()
    assert weather_store._cooldown_until > 0


def test_read_snapshot_before_is_none_in_fixtures_mode_and_touches_nothing(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(weather_store.config, "WEATHER_MODE", "fixtures")
    assert weather_store.read_snapshot_before("pt:13.10,80.25", "2026-10-04T06:00:00+00:00") is None
    assert engine.begins == 0


def test_read_snapshot_before_is_none_and_parks_when_postgres_is_down(monkeypatch):
    monkeypatch.setattr(weather_store, "_engine", _FakeEngine(down=True))
    monkeypatch.setattr(weather_store.config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(weather_store, "_cooldown_until", 0.0)
    assert weather_store.read_snapshot_before("c", "2026-10-04T06:00:00+00:00") is None
    assert weather_store._cooldown_until > 0
    # Parked: the next read returns at once without another connection attempt.
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    assert weather_store.read_snapshot_before("c", "2026-10-04T06:00:00+00:00") is None
    assert engine.begins == 0


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


def test_read_snapshot_before_returns_the_newest_earlier_retrieval(monkeypatch):
    when = datetime(2026, 10, 4, 6, 0, tzinfo=timezone.utc)
    hour = datetime(2026, 10, 4, 14, 0, tzinfo=timezone.utc)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, stmt, params=None):
            if "max(retrieved_at)" in str(stmt):
                return type("R", (), {"scalar": lambda self: when})()
            return _Rows([{"forecast_time": hour, "temp_c": 29.0, "rain_probability_pct": 30,
                           "wind_kmh": 9.0, "condition": None, "uv_index": None}])

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(weather_store, "_engine", _Engine())
    monkeypatch.setattr(weather_store, "_SCHEMA_READY", True)
    monkeypatch.setattr(weather_store.config, "WEATHER_MODE", "auto")
    got = weather_store.read_snapshot_before("c", "2026-10-04T07:00:00+00:00")
    assert got["retrieved_at"] == "2026-10-04T06:00:00+00:00"
    assert got["hours"]["2026-10-04T14:00:00+00:00"]["rain_probability_pct"] == 30


def test_the_retention_sweep_covers_forecast_snapshots(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(weather_store, "_engine", engine)
    monkeypatch.setattr(weather_store.config, "WEATHER_FACTS_RETENTION_DAYS", 30)
    weather_store.prune()
    assert len(engine.deletes) == 2
