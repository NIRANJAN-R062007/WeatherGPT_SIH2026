"""Request limits for the public /ask surface (plan.md §8 Phase 3 security pass).

/ask, /asr and /tts have no auth and every one of them can fan out to paid
Bhashini/LLM calls. Two cheap guards cover that:

- a body-size cap (413) so a multi-megabyte /asr upload never reaches Bhashini;
- a per-client sliding-window rate limit (429) on the expensive routes.

Client identity: every proxy in front of us appends the address it accepted
the connection from to X-Forwarded-For, so the Nth entry from the RIGHT is
the address the outermost proxy we trust saw, and everything left of it is
whatever the client chose to send. `client_key` takes that entry, with
N = TRUSTED_PROXY_HOPS (config.py) = the number of proxies between the
internet and this process, the gateway counting as one (services/gateway
reads the same variable with the same meaning) — never the leftmost hop,
which any client can rotate per request:

    TRUSTED_PROXY_HOPS  topology
    0                   nothing in front: socket peer, header ignored
    1 (default)         client -> gateway -> here (plain docker compose), or
                        standalone on Render (its edge appends the client)
    2                   client -> ngrok -> gateway -> here (the demo tunnel), or
                        client -> ingress-nginx -> gateway -> here (k8s/base)

A header shorter than N (a request that skipped a proxy) falls back to the
socket peer. Too small an N lumps everyone behind the innermost proxy into
one budget (safe, over-strict); too large an N keys on client-supplied data
(the bypass this replaces). "Socket peer" assumes uvicorn's own
X-Forwarded-For handling is off (`--no-proxy-headers`): by default it trusts
the header from 127.0.0.1 and rewrites `request.client` from it, so a proxy
on the same host (ngrok's agent, loadtest/run.sh's k6) would have the
gateway append a header-derived address instead of its peer. Containers
never see a 127.0.0.1 peer, so compose/k8s/Render are unaffected either way.

The window lives in Redis (config.REDIS_URL, the instance weather_store.py
already uses) so k8s replicas / Render instances share one budget instead of
each granting RATE_LIMIT_PER_MINUTE. One Lua script per request does the
check-and-record atomically. When Redis is unreachable the limiter falls back
to a per-process deque and stops trying Redis for _REDIS_RETRY_SECONDS, so a
dead Redis costs one connect timeout per cooldown — never a 5xx, never an
open door. Hits in one store are invisible to the other, so a client can get
up to twice the budget across the switch-over; fine for a best-effort guard.
"""

import logging
import secrets
import threading
import time
from collections import defaultdict, deque

import config
import redis
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_LOG = logging.getLogger("weathergpt.limits")

LIMITED_PATHS = frozenset({"/ask", "/asr", "/tts"})
_WINDOW_SECONDS = 60.0
# Long enough that a flapping Redis doesn't add a connect timeout to every
# request, short enough to pick a restarted one back up within a window.
_REDIS_RETRY_SECONDS = 30.0

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()
_monotonic = time.monotonic  # test seam — deque timestamps and the retry cooldown
_wall_clock = time.time  # test seam — Redis scores; monotonic clocks differ per pod
_redis_retry_at = 0.0  # _monotonic() before which Redis isn't tried

# Same short timeouts as weather_store.py: a dead cache must fail fast.
_redis = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)

# KEYS[1] = client, ARGV = now, window start, limit, hit id, ttl. A sorted set
# of hit timestamps: drop the ones that slid out, refuse if the rest fill the
# budget, else record this hit. Members must be unique (secrets.token_hex) or
# two pods' hits in the same instant would collapse into one.
_LUA_OVER_LIMIT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', '(' .. ARGV[2])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
  return 1
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return 0
"""


def client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = config.TRUSTED_PROXY_HOPS
    if trusted <= 0:
        return peer
    # getlist: a client can split the header over several lines; they combine
    # in order (RFC 7230 §3.2.2), so a trusted proxy's hop is still rightmost.
    forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if len(hops) < trusted:
        return peer
    return hops[-trusted]


def reset() -> None:
    """Forget this process's state (deque + Redis cooldown). Never touches Redis."""
    global _redis_retry_at
    with _lock:
        _hits.clear()
    _redis_retry_at = 0.0


def _redis_over_limit(key: str, per_minute: int) -> bool:
    now = _wall_clock()
    return bool(_redis.eval(
        _LUA_OVER_LIMIT, 1, f"weathergpt:ratelimit:{key}",
        repr(now), repr(now - _WINDOW_SECONDS), per_minute,
        secrets.token_hex(8), int(_WINDOW_SECONDS),
    ))


def _local_over_limit(key: str, per_minute: int) -> bool:
    now = _monotonic()
    with _lock:
        window = _hits[key]
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()
        if len(window) >= per_minute:
            return True
        window.append(now)
        return False


def _over_limit(key: str, per_minute: int) -> bool:
    global _redis_retry_at
    if _monotonic() >= _redis_retry_at:
        try:
            return _redis_over_limit(key, per_minute)
        except (redis.RedisError, OSError) as exc:
            _redis_retry_at = _monotonic() + _REDIS_RETRY_SECONDS
            _LOG.warning("rate limiter: redis unavailable (%s) — per-process window "
                         "for the next %.0fs", exc, _REDIS_RETRY_SECONDS)
    return _local_over_limit(key, per_minute)


class RequestLimits(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > config.MAX_BODY_BYTES:
            return JSONResponse({"detail": "request body too large"}, status_code=413)

        per_minute = config.RATE_LIMIT_PER_MINUTE
        if per_minute > 0 and request.url.path in LIMITED_PATHS:
            # Blocking Redis I/O — keep it off the event loop.
            if await run_in_threadpool(_over_limit, client_key(request), per_minute):
                return JSONResponse(
                    {"detail": "too many requests — try again in a minute"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
