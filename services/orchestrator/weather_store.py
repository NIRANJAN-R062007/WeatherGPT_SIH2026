"""Shared Redis cache + Postgres persistence for Google Weather snapshots
(plan.md §8 Phase 1: "Store into Postgres/Redis with TTLs", and the
"Schema/infra support for the data layer" line under it).

Layered on top of google_weather.py's in-memory `_CACHE`, not instead of it:
- In-memory dict stays the L1 cache (fastest, zero network, what the demo
  falls back to if Redis is unreachable).
- Redis is the L2 cache: shared across processes/replicas/restarts, keyed
  with the same per-kind TTL via SETEX so expiry needs no extra bookkeeping.
- Postgres is durable history: every *live* snapshot is appended to
  `weather_facts` (see sql/002_weather_facts.sql) for audit/replay. Reads
  never go through Postgres, and neither do writes on the request path:
  persist() only queues the row and a single daemon thread does the INSERT.
  (Audit item 1.5: the synchronous write used to cost a 2 s connect timeout
  per live fetch whenever Postgres wasn't provisioned — the whole of plan.md
  §1's p95 < 2 s budget.)

Schema lives in sql/*.sql and nowhere else. `_apply_migrations()` executes
those files in filename order, each in its own transaction, recording what
applied in a `schema_migrations` ledger. This replaced a hand-synced copy of
the CREATE TABLE that used to sit inline here: two definitions of one table,
either free to drift. Per-file transactions matter because 001 (CREATE
EXTENSION postgis) is the one statement a managed Postgres role may lack
rights for — when it fails we lose PostGIS and the cities geography column,
logged, while weather_facts (002) still applies.

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
from pathlib import Path

import cities
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
_MIGRATIONS_DIR = Path(__file__).parent / "sql"

# Retention sweep cadence. Runs on the writer thread after a write, never on
# the request path — see _maybe_prune().
_PRUNE_INTERVAL_SECONDS = 3600
_last_prune = 0.0

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


def migration_files() -> list[Path]:
    """Our migrations, in apply order: sql/NNN_*.sql, sorted by that prefix.

    Deliberately NOT every *.sql in the directory. sql/supabase_schema.sql
    also lives there and is a Supabase-dashboard script — it references
    auth.users and Supabase's RLS helpers, so running it against the
    orchestrator's own Postgres fails, and failing forever would keep
    _SCHEMA_READY False and re-run the whole set on every write. The numeric
    prefix is what marks a file as ours to execute.
    """
    return sorted(p for p in _MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def _ensure_schema() -> None:
    """Bring the database up to sql/*.sql. Idempotent; safe to call often.

    Kept under the name _write() already calls, so a failure here still trips
    the writer's cooldown and still leaves _SCHEMA_READY False for the retry.

    Every file is written with IF NOT EXISTS, so the ledger is an optimisation
    and an ops breadcrumb ("which of these has this database actually seen"),
    not the thing that makes re-running safe.
    """
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with _engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        applied = {row[0] for row in conn.exec_driver_sql(
            "SELECT filename FROM schema_migrations")}

    failed = False
    for path in migration_files():
        if path.name in applied:
            continue
        try:
            # Own transaction per file: one file failing (001's CREATE
            # EXTENSION, on a role without the rights) must not roll back the
            # files that did apply, and must not stop later ones being tried.
            with _engine.begin() as conn:
                conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                conn.exec_driver_sql(
                    "INSERT INTO schema_migrations (filename) VALUES (%s) "
                    "ON CONFLICT DO NOTHING", (path.name,))
            _LOG.info("applied migration %s", path.name)
        except Exception:
            # Left out of the ledger, so the next attempt retries it — the
            # failure is usually environmental (missing extension rights,
            # PostGIS absent) and gets fixed outside this process.
            failed = True
            _LOG.exception("migration %s failed; continuing", path.name)

    # Only latch when everything applied. A partial schema is worth retrying
    # on the next write rather than pinning for the life of the process.
    _SCHEMA_READY = not failed


def sync_cities() -> int:
    """Upsert data/cities.json into the `cities` table. Returns rows written.

    data/cities.json stays the source of truth (cities.py loads it at import
    and the request path answers from that); this is the queryable mirror the
    Phase 4 geofence needs. Idempotent, so it is fine to run on every boot or
    from `python migrate.py --sync-cities`.
    """
    _ensure_schema()
    rows = 0
    with _engine.begin() as conn:
        for city in cities.CITIES.values():
            conn.execute(
                text("""
                    INSERT INTO cities
                        (key, lat, lon, names, region, timezone, aliases, synced_at)
                    VALUES
                        (:key, :lat, :lon, :names, :region, :timezone, :aliases, now())
                    ON CONFLICT (key) DO UPDATE SET
                        lat = EXCLUDED.lat,
                        lon = EXCLUDED.lon,
                        names = EXCLUDED.names,
                        region = EXCLUDED.region,
                        timezone = EXCLUDED.timezone,
                        aliases = EXCLUDED.aliases,
                        synced_at = now()
                """),
                {
                    "key": city.key,
                    "lat": city.lat,
                    "lon": city.lon,
                    "names": json.dumps(city.names, ensure_ascii=False),
                    "region": json.dumps(city.region, ensure_ascii=False),
                    "timezone": city.timezone,
                    "aliases": list(city.aliases),
                },
            )
            rows += 1
    return rows


def prune() -> int:
    """Delete weather_facts rows past the retention window. Returns row count.

    0 (or a non-positive WEATHER_FACTS_RETENTION_DAYS) means keep everything.
    """
    days = config.WEATHER_FACTS_RETENTION_DAYS
    if days <= 0:
        return 0
    _ensure_schema()
    with _engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM weather_facts "
                 "WHERE created_at < now() - make_interval(days => :days)"),
            {"days": days},
        )
    return result.rowcount or 0


def _maybe_prune() -> None:
    """Run the retention sweep at most once an hour, on the writer thread.

    Deliberately after _write() and inside _process()'s except, so a sweep
    that fails is logged like any other worker error and never costs a row.
    """
    global _last_prune
    now = _monotonic()
    if now < _cooldown_until:
        return  # Postgres is parked; don't spend the connect timeout on a sweep
    if _last_prune and now - _last_prune < _PRUNE_INTERVAL_SECONDS:
        return
    _last_prune = now
    deleted = prune()
    if deleted:
        _LOG.info("pruned %d weather_facts rows past retention", deleted)


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
        _maybe_prune()
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
