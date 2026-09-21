"""Shared Redis cache + Postgres persistence for Google Weather snapshots
(plan.md §8 Phase 1: "Store into Postgres/Redis with TTLs").

Layered on top of google_weather.py's in-memory `_CACHE`, not instead of it:
- In-memory dict stays the L1 cache (fastest, zero network, what the demo
  falls back to if Redis is unreachable).
- Redis is the L2 cache: shared across processes/replicas/restarts, keyed
  with the same per-kind TTL via SETEX so expiry needs no extra bookkeeping.
- Postgres is durable history: every *live* snapshot is appended to
  `weather_facts` (see sql/weather_facts.sql) for audit/replay. Reads never
  go through Postgres, and neither do writes on the request path: persist()
  only queues the row and a single daemon thread does the INSERT. (Audit
  item 1.5: the synchronous write used to cost a 2 s connect timeout per
  live fetch whenever Postgres wasn't provisioned — the whole of plan.md
  §1's p95 < 2 s budget.)

Both are best-effort and silently degrade to a no-op on any error (dead
connection, unreachable host, missing table) — a broken cache/DB must never
break `/ask`, same rule gateway/main.py's `/health` and history.py already
follow. A failed Postgres write also puts the writer on a cooldown
(`_COOLDOWN_SECONDS`): one warning, rows queued inside the window are
dropped without further noise, and the next row after it retries. Neither
backend is touched at all in WEATHER_MODE=fixtures (offline demo).

Redis/Postgres are now provisioned for real, not just in docker-compose's
dev containers: `render.yaml` (weathergpt-redis, weathergpt-postgres) for the
live Render deploy, `k8s/base/redis.yaml` + `k8s/base/postgres.yaml` for the
k8s target. The best-effort fallback above stays regardless — it's what lets
this run in any environment that hasn't (yet) provisioned either, e.g. a
bare `uvicorn main:app` with no .env DB config at all.
"""

import json
import logging
import os
import queue
import threading
import time

import config
import redis
from sqlalchemy import create_engine, text

_LOG = logging.getLogger("weathergpt.weather_store")

# Short timeouts: a dead/unreachable Redis must fail fast because a cache
# miss reads it on the request path. Postgres is only ever touched by the
# persist worker thread, so its timeout bounds how long one attempt ties
# that thread up, not how long /ask waits.
_engine = create_engine(config.DATABASE_URL, pool_pre_ping=True,
                         connect_args={"connect_timeout": 2})
_redis = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)

_SCHEMA_READY = False

# The L1 cache means a live fetch — hence a persist() — happens at most once
# per (kind, city) per TTL: 4 kinds x 3 demo cities at >= 15 min. So 64 is
# over an hour of backlog, and reaching it means the worker is hung on
# Postgres, not busy; newer rows are then dropped, never the caller blocked.
_QUEUE_MAX = 64
# One failed write parks Postgres for this long: an unprovisioned DB costs
# one warning a minute instead of a 2 s connect timeout per row, and a
# container that comes back is noticed within a minute.
_COOLDOWN_SECONDS = 60.0

_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
_worker: threading.Thread | None = None
_worker_pid: int | None = None
_worker_lock = threading.Lock()
_cooldown_until = 0.0
_monotonic = time.monotonic  # test seam


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_facts (
                id BIGSERIAL PRIMARY KEY,
                kind TEXT NOT NULL,
                city TEXT NOT NULL,
                payload JSONB NOT NULL,
                is_live BOOLEAN NOT NULL,
                source TEXT NOT NULL,
                retrieved_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS weather_facts_kind_city_idx "
            "ON weather_facts (kind, city, created_at DESC)"
        ))
    _SCHEMA_READY = True


def _redis_key(kind: str, city: str) -> str:
    return f"weathergpt:weather:{kind}:{city}"


def redis_get(kind: str, city: str):
    """Return a decoded snapshot dict from Redis, or None on miss/any error."""
    try:
        blob = _redis.get(_redis_key(kind, city))
    except redis.RedisError as exc:
        _LOG.warning("redis get failed for %s/%s: %s", kind, city, exc)
        return None
    if blob is None:
        return None
    try:
        return json.loads(blob)
    except ValueError:
        _LOG.warning("redis get returned malformed json for %s/%s", kind, city)
        return None


def redis_set(kind: str, city: str, fields: dict, ttl_seconds: int) -> None:
    try:
        _redis.setex(_redis_key(kind, city), ttl_seconds, json.dumps(fields))
    except redis.RedisError as exc:
        _LOG.warning("redis set failed for %s/%s: %s", kind, city, exc)


def persist(kind: str, city: str, fields: dict) -> None:
    """Queue one live snapshot for the weather_facts writer thread.

    Returns at once and never raises: a full queue drops this row, and a
    dead Postgres is the worker's problem (see _write).
    """
    try:
        _ensure_worker()
        _queue.put_nowait((kind, city, fields))
    except queue.Full:
        _LOG.warning("weather_facts queue full (%d); dropping %s/%s", _QUEUE_MAX, kind, city)
    except Exception:
        _LOG.exception("weather_facts worker failed to start; dropping %s/%s", kind, city)


def _ensure_worker() -> None:
    """Start the writer thread on first use, never at import — tests, CI and
    py_compile import this module and must not get a thread dialling
    Postgres. uvicorn spawns (not forks) its reload/worker subprocesses, so
    each imports afresh; the pid check is for a fork-based supervisor
    (gunicorn --preload), where the parent's thread doesn't survive and its
    queue's lock state is whatever it was mid-fork.
    """
    global _queue, _worker, _worker_pid
    with _worker_lock:
        pid = os.getpid()
        if _worker is not None and _worker_pid == pid and _worker.is_alive():
            return
        if _worker_pid is not None and _worker_pid != pid:
            _queue = queue.Queue(maxsize=_QUEUE_MAX)
        _worker_pid = pid
        _worker = threading.Thread(target=_worker_loop, args=(_queue,),
                                   name="weather-store-persist", daemon=True)
        _worker.start()


def _worker_loop(q: queue.Queue) -> None:
    while True:
        _process(q.get())


def _drain() -> None:
    """Handle everything queued so far on the calling thread. Test seam, so
    tests need neither the worker thread nor Postgres."""
    while True:
        try:
            item = _queue.get_nowait()
        except queue.Empty:
            return
        _process(item)


def _process(item: tuple) -> None:
    kind, city, fields = item
    try:
        _write(kind, city, fields)
    except Exception:
        _LOG.exception("weather_facts worker: unexpected error for %s/%s", kind, city)


def _write(kind: str, city: str, fields: dict) -> None:
    """The actual INSERT. Any Postgres failure — schema bootstrap included —
    starts the cooldown; _SCHEMA_READY stays False so the DDL reruns on the
    retry. The row is built outside the try so a malformed item is a worker
    bug (logged by _process), not a reason to park Postgres.
    """
    global _cooldown_until
    if _monotonic() < _cooldown_until:
        return
    row = {
        "kind": kind,
        "city": city,
        "payload": json.dumps(fields["payload"]),
        "is_live": fields["is_live"],
        "source": fields["source"],
        "retrieved_at": fields["retrieved_at"],
    }
    try:
        _ensure_schema()
        with _engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO weather_facts
                        (kind, city, payload, is_live, source, retrieved_at)
                    VALUES
                        (:kind, :city, :payload, :is_live, :source, :retrieved_at)
                """),
                row,
            )
    except Exception as exc:
        _cooldown_until = _monotonic() + _COOLDOWN_SECONDS
        # psycopg2/SQLAlchemy error text spans several lines; keep the once-a-
        # minute warning to one.
        _LOG.warning("postgres persist failed for %s/%s (%s); skipping weather_facts "
                     "writes for %.0f s", kind, city, " ".join(str(exc).split()),
                     _COOLDOWN_SECONDS)
