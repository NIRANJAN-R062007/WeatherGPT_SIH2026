"""Shared Redis cache + Postgres persistence for Google Weather snapshots
(plan.md §8 Phase 1: "Store into Postgres/Redis with TTLs").

Layered on top of google_weather.py's in-memory `_CACHE`, not instead of it:
- In-memory dict stays the L1 cache (fastest, zero network, what the demo
  falls back to if Redis is unreachable).
- Redis is the L2 cache: shared across processes/replicas/restarts, keyed
  with the same per-kind TTL via SETEX so expiry needs no extra bookkeeping.
- Postgres is durable history: every *live* snapshot is appended to
  `weather_facts` (see sql/weather_facts.sql) for audit/replay. Reads never
  go through Postgres — it is write-only from the request path.

Both are best-effort and silently degrade to a no-op on any error (dead
connection, unreachable host, missing table) — a broken cache/DB must never
break `/ask`, same rule gateway/main.py's `/health` and history.py already
follow. Neither is touched at all in WEATHER_MODE=fixtures (offline demo).

Redis/Postgres are now provisioned for real, not just in docker-compose's
dev containers: `render.yaml` (weathergpt-redis, weathergpt-postgres) for the
live Render deploy, `k8s/base/redis.yaml` + `k8s/base/postgres.yaml` for the
k8s target. The best-effort fallback above stays regardless — it's what lets
this run in any environment that hasn't (yet) provisioned either, e.g. a
bare `uvicorn main:app` with no .env DB config at all.
"""

import json
import logging

import config
import redis
from sqlalchemy import create_engine, text

_LOG = logging.getLogger("weathergpt.weather_store")

# Short timeouts: a dead/unreachable cache must fail fast, not stall the
# request that's trying to answer a weather question.
_engine = create_engine(config.DATABASE_URL, pool_pre_ping=True,
                         connect_args={"connect_timeout": 2})
_redis = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)

_SCHEMA_READY = False


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
    """Append one live snapshot to weather_facts. Never raises."""
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
                {
                    "kind": kind,
                    "city": city,
                    "payload": json.dumps(fields["payload"]),
                    "is_live": fields["is_live"],
                    "source": fields["source"],
                    "retrieved_at": fields["retrieved_at"],
                },
            )
    except Exception:
        _LOG.exception("postgres persist failed for %s/%s", kind, city)
