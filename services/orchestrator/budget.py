"""Daily ceiling on paid outbound API calls — a circuit breaker against a
runaway bill (plan.md §8 Phase 8, SEC-N15).

Every call to a paid provider goes through `charge(provider)` first, at the
one place each provider is called: google_weather.fetch_json, narrate.generate
(Gemini), narrate.generate_groq (Groq) and bhashini's translate /
speech_to_text / text_to_speech. Each provider has its own ceiling per UTC day
(DAILY_CAP_* in config.py; 0 = no ceiling), so an LLM flood can't also starve
weather data. The count is global — all users, all replicas — not per user;
per-user quotas are deferred until there are many signed-in users.

Over the ceiling, `charge` raises BudgetExceeded, an httpx.HTTPError: every
caller already catches that and falls back the way it does for a provider
outage — fixture weather, the next LLM provider then the i18n template, no
translation or voice. The breaker therefore needs no caller changes and can
never turn into a 5xx.

The counter lives in Redis (INCR on a per-provider, per-day key that expires
after two days) so replicas share one budget. When Redis is unreachable it
falls back to a per-process count and stops trying Redis for
_REDIS_RETRY_SECONDS, like limits.py: with N replicas that allows up to N
times the ceiling while Redis is down — still a ceiling, never an open door.
"""

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import config
import httpx
import redis
from prometheus_client import Counter

_LOG = logging.getLogger("weathergpt.budget")

PROVIDERS = ("google_weather", "gemini", "groq", "bhashini")
_REDIS_RETRY_SECONDS = 30.0
_KEY_TTL_SECONDS = 2 * 24 * 3600

BUDGET_REFUSED_TOTAL = Counter(
    "weathergpt_budget_refused_total",
    "Paid API calls refused because the provider's daily ceiling was reached",
    ["provider"],
)


class BudgetExceeded(httpx.HTTPError):
    """A provider's daily ceiling is spent; callers treat it as an outage."""


_local: dict[str, int] = defaultdict(int)
_lock = threading.Lock()
_warned: set[str] = set()  # "provider:day" already logged, so a flood logs once
_redis_retry_at = 0.0
_monotonic = time.monotonic  # test seam
_today = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: E731 — test seam

_redis = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def ceiling(provider: str) -> int:
    return config.DAILY_CAPS.get(provider, 0)


def reset() -> None:
    """Forget this process's state (counts, warnings, Redis cooldown)."""
    global _redis_retry_at
    with _lock:
        _local.clear()
        _warned.clear()
    _redis_retry_at = 0.0


def _count(provider: str, day: str) -> int:
    """Record one call and return today's total so far, including it."""
    global _redis_retry_at
    key = f"weathergpt:budget:{provider}:{day}"
    if _monotonic() >= _redis_retry_at:
        try:
            pipe = _redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, _KEY_TTL_SECONDS)
            return int(pipe.execute()[0])
        except (redis.RedisError, OSError) as exc:
            _redis_retry_at = _monotonic() + _REDIS_RETRY_SECONDS
            _LOG.warning("budget: redis unavailable (%s) — per-process count for the "
                         "next %.0fs", exc, _REDIS_RETRY_SECONDS)
    with _lock:
        _local[key] += 1
        return _local[key]


def charge(provider: str) -> None:
    """Count one call to `provider`; raise BudgetExceeded once today's ceiling
    is spent. A refused call still counts, so the day's total shows the demand."""
    limit = ceiling(provider)
    if limit <= 0:
        return
    day = _today()
    if _count(provider, day) <= limit:
        return
    BUDGET_REFUSED_TOTAL.labels(provider=provider).inc()
    flag = f"{provider}:{day}"
    if flag not in _warned:
        _warned.add(flag)
        _LOG.warning("budget: %s reached its daily ceiling of %d calls (UTC %s); "
                     "falling back until the day rolls over", provider, limit, day)
    raise BudgetExceeded(f"{provider} daily ceiling of {limit} calls reached")
