"""Shared result cache for the /intelligence/* routes (plan.md §8 Phase 9, WIE-15).

Each route's answer is a pure function of one hourly-forecast snapshot and the
request's own parameters: weather_data.hourly_facts' "today"/"tomorrow" are
positions within the snapshot, so the wall clock never enters. An answer is
therefore right for exactly as long as the forecast behind it, and that is its
TTL here: the hourly-forecast TTL minus the forecast's age at the time it is
stored, so a cached answer never outlives its forecast. That holds for
/intelligence/changes too, whose baseline is fixed by the same forecast's
retrieval time.

Keys are route, city, day and the remaining parameters (activity, persona,
times). Only values the engine knows are cached: an unknown activity or a time
that isn't "HH:MM" is still answered, never stored, so a client can't fill
Redis with one key per made-up string.

Only live forecasts are cached. A fixture (WEATHER_MODE=fixtures, or a failed
live call replayed from one) is never stored, so an outage answer isn't pinned
for an hour, and offline Redis is never touched, as in weather_store.py. Redis
is best-effort: any error is a miss, and parks Redis for _REDIS_RETRY_SECONDS
(limits.py's pattern), so a dead Redis costs one connect timeout per cooldown
and never an error.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

import config
import google_weather
import redis
from fastapi.encoders import jsonable_encoder
from weather_intelligence import rules

_LOG = logging.getLogger("weathergpt.intelligence_cache")

_PREFIX = "weathergpt:intelligence"
_REDIS_RETRY_SECONDS = 30.0
_TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

_redis_retry_at = 0.0  # _monotonic() before which Redis isn't tried
_monotonic = time.monotonic  # test seam
_now = lambda: datetime.now(timezone.utc)  # noqa: E731 — test seam

# Same short timeouts as weather_store.py: a dead cache must fail fast.
_redis = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def reset() -> None:
    """Forget the Redis cooldown. Never touches Redis."""
    global _redis_retry_at
    _redis_retry_at = 0.0


def key(route: str, city: str, day: str, **params) -> str | None:
    """The cache key for one request, or None when a parameter is one the engine
    doesn't know (such a request is answered but never stored)."""
    activity = params.get("activity")
    if activity is not None and activity not in rules.ACTIVITIES:
        return None
    times = params.get("times")
    if times is not None and not all(_TIME.fullmatch(t) for t in times):
        return None
    rest = [f"{name}={','.join(value) if isinstance(value, list) else value}"
            for name, value in sorted(params.items())]
    return ":".join([_PREFIX, route, city, day, *rest])


def remaining_seconds(retrieved_at: str | None) -> int:
    """Seconds the forecast retrieved at `retrieved_at` has left of the hourly
    forecast TTL; 0 or less when it is spent or the time can't be read."""
    try:
        fetched = datetime.fromisoformat(retrieved_at)
    except (TypeError, ValueError):
        return 0
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    ttl = google_weather.ttl_seconds("forecast_hours")
    age = (_now() - fetched).total_seconds()
    return min(ttl, int(ttl - age))  # a clock-skewed future time never adds life


def _usable() -> bool:
    return config.WEATHER_MODE != "fixtures" and _monotonic() >= _redis_retry_at


def _park(exc: Exception) -> None:
    global _redis_retry_at
    _redis_retry_at = _monotonic() + _REDIS_RETRY_SECONDS
    _LOG.warning("intelligence cache: redis unavailable (%s); not cached for the "
                 "next %.0fs", exc, _REDIS_RETRY_SECONDS)


def get(cache_key: str | None) -> dict | None:
    """The stored answer for `cache_key`, or None on a miss or any error."""
    if cache_key is None or not _usable():
        return None
    try:
        blob = _redis.get(cache_key)
    except (redis.RedisError, OSError) as exc:
        _park(exc)
        return None
    if blob is None:
        return None
    try:
        return json.loads(blob)
    except ValueError:
        _LOG.warning("intelligence cache: malformed entry at %s", cache_key)
        return None


def put(cache_key: str | None, answer: dict, hourly: dict | None) -> None:
    """Store `answer`, computed from `hourly` (weather_data.hourly_facts), for
    the rest of that forecast's life. A fixture or a spent forecast is skipped."""
    if cache_key is None or not hourly or not hourly.get("is_live") or not _usable():
        return
    ttl = remaining_seconds(hourly.get("retrieved_at"))
    if ttl <= 0:
        return
    try:
        _redis.setex(cache_key, ttl, json.dumps(jsonable_encoder(answer)))
    except (redis.RedisError, OSError) as exc:
        _park(exc)
