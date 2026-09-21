"""WeatherGPT API gateway (plan.md §4).

Everything except `/health`, `/livez` and `/metrics` is reverse-proxied to
the orchestrator (`services/orchestrator/`, the former `prototype/ask_service`).
The orchestrator still owns per-route rate limiting (`limits.py`, keyed off
the TRUSTED_PROXY_HOPS-th X-Forwarded-For hop from the right — by default the
hop this gateway appends), so the gateway appends the client address to
X-Forwarded-For and otherwise passes requests through untouched — including
the frontend the orchestrator serves at `/`. The body-size cap is enforced
here too (MAX_BODY_BYTES, the orchestrator's knob and default), so an
oversize upload is refused before the gateway buffers it, not after.

Postgres/Redis are checked lazily in `/health` only; the proxy works without
them, so the demo path (`uvicorn main:app --port 8000` + ngrok) has no
database dependency. `/health` is unauthenticated, so its result is cached
for HEALTH_CACHE_SECONDS and rate limited per client
(HEALTH_RATE_LIMIT_PER_MINUTE, 0 disables) — see `health()`.

TRUSTED_PROXY_HOPS (default 1) has one meaning for both services: the number
of proxies between the internet and the orchestrator, this gateway included.
The gateway is always the last of them, so for its own limiter it trusts one
fewer hop of the header *it* receives — with the default that is the socket
peer alone, and a forged header cannot pick a key. Behind something that
records the real client in X-Forwarded-For (ngrok, the k8s nginx Ingress)
set 2, and both services key on that address.
"""

import asyncio
import logging
import os
import time
from collections import defaultdict, deque

import httpx
import metrics
import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

_LOG = logging.getLogger("weathergpt.gateway")

app = FastAPI(title="WeatherGPT Gateway", version="0.1.0")
app.add_middleware(metrics.HTTPMetrics, service="gateway")

# `or default`, not getenv's second argument: a k8s Secret with an empty value
# still *sets* the variable, and create_engine("") raises at import.
DATABASE_URL = (os.getenv("DATABASE_URL")
                or "postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt")
REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
ORCHESTRATOR_URL = (os.getenv("ORCHESTRATOR_URL") or "http://localhost:8001").rstrip("/")
# /tts and LLM narration can take a while; connect fast, read slow.
PROXY_TIMEOUT = httpx.Timeout(float(os.getenv("PROXY_TIMEOUT") or "60"), connect=5.0)
MAX_BODY_BYTES = int(float(os.getenv("MAX_BODY_BYTES") or 2 * 1024 * 1024))
HEALTH_RATE_LIMIT_PER_MINUTE = int(float(os.getenv("HEALTH_RATE_LIMIT_PER_MINUTE") or 60))
HEALTH_CACHE_SECONDS = 10.0
# See the module docstring; 0 must be checked explicitly below, since hops[-0]
# would be the leftmost, attacker-controlled hop.
_TRUSTED_XFF_HOPS = max(int(float(os.getenv("TRUSTED_PROXY_HOPS") or 1)) - 1, 0)

engine = create_engine(DATABASE_URL)
redis_client = redis.Redis.from_url(REDIS_URL)

# RFC 7230 §6.1 hop-by-hop headers plus the ones httpx/uvicorn recompute.
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
    "host", "content-length", "content-encoding",
})
_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]

_client = httpx.AsyncClient(base_url=ORCHESTRATOR_URL, timeout=PROXY_TIMEOUT)


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    client_ip = request.client.host if request.client else None
    prior = request.headers.get("x-forwarded-for")
    # Prior hops stay verbatim and the socket peer goes last: the orchestrator's
    # per-client rate limit counts trusted hops from the right, and this append
    # is the one it always trusts.
    if prior and client_ip:
        headers["x-forwarded-for"] = f"{prior}, {client_ip}"
    elif client_ip:
        headers["x-forwarded-for"] = client_ip
    return headers


def _client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if _TRUSTED_XFF_HOPS == 0 or len(hops) < _TRUSTED_XFF_HOPS:
        return peer
    return hops[-_TRUSTED_XFF_HOPS]


_health_cache: tuple[dict, float] | None = None  # (payload, expires at _monotonic())
_health_lock = asyncio.Lock()
_health_hits: dict[str, deque] = defaultdict(deque)
_monotonic = time.monotonic  # test seam


def _health_over_limit(key: str) -> bool:
    # Only called on the event loop, so no lock around the window.
    now = _monotonic()
    window = _health_hits[key]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= HEALTH_RATE_LIMIT_PER_MINUTE:
        return True
    window.append(now)
    return False


def _health_stale() -> bool:
    return _health_cache is None or _monotonic() >= _health_cache[1]


async def _probe() -> dict:
    """Postgres+PostGIS, Redis, and the orchestrator behind us. Each check is
    independent — a dead database must not hide a live orchestrator. /health is
    unauthenticated and internet-facing, so results stay generic ("ok"/"error")
    — full exception details (which can include internal hostnames/DSNs) go to
    the server log only, not the caller."""
    status: dict = {"postgres": "unknown", "postgis": "unknown", "redis": "unknown",
                    "orchestrator": "unknown"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["postgres"] = "ok"
            postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            status["postgis"] = f"ok ({postgis_version})"
    except Exception:
        _LOG.exception("health check: postgres/postgis failed")
        status["postgres"] = "error"
        status["postgis"] = "error"

    try:
        redis_client.ping()
        status["redis"] = "ok"
    except Exception:
        _LOG.exception("health check: redis failed")
        status["redis"] = "error"

    try:
        r = await _client.get("/health", timeout=5.0)
        status["orchestrator"] = r.json() if r.status_code == 200 else "error"
    except Exception:
        _LOG.exception("health check: orchestrator unreachable")
        status["orchestrator"] = "error"

    return status


@app.get("/health")
async def health(request: Request):
    """`_probe()`'s result, cached for HEALTH_CACHE_SECONDS and rate limited per
    client, so an unauthenticated caller can't turn every hit into a Postgres
    connect + Redis ping + upstream call. The limiter is process-local like the
    orchestrator's, on purpose: the cache already bounds the expensive I/O, so
    this is defence in depth, and with two gateway replicas in k8s the effective
    per-client limit is simply 2x — a shared store isn't worth it for a cached
    endpoint. Neither a 429 nor a cache hit does any I/O."""
    global _health_cache
    if HEALTH_RATE_LIMIT_PER_MINUTE > 0 and _health_over_limit(_client_key(request)):
        return JSONResponse({"detail": "too many requests — try again in a minute"},
                            status_code=429, headers={"Retry-After": "60"})
    if _health_stale():
        async with _health_lock:
            if _health_stale():  # a concurrent miss may have refilled it meanwhile
                _health_cache = (await _probe(), _monotonic() + HEALTH_CACHE_SECONDS)
    return _health_cache[0]


@app.get("/livez")
def livez():
    """k8s liveness probe: no I/O, just "is the process serving requests"."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics_route():
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)


async def _read_body(request: Request) -> bytes | None:
    """The request body, or None once it exceeds MAX_BODY_BYTES. Content-Length
    is only a hint — a chunked upload has none — so the stream is counted as it
    arrives and abandoned the moment the cap is crossed; the gateway never
    buffers more than the cap plus one chunk."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return None
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


# Registered before the catch-all below so /livez and /metrics are always the
# gateway's own — the orchestrator's proxy() branch never sees these paths.
@app.api_route("/{path:path}", methods=_PROXY_METHODS)
async def proxy(request: Request, path: str):
    url = f"/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    body = await _read_body(request)
    if body is None:
        return JSONResponse({"detail": "request body too large"}, status_code=413)
    try:
        upstream = await _client.request(request.method, url, content=body,
                                         headers=_forward_headers(request))
    except httpx.HTTPError as e:
        metrics.GATEWAY_UPSTREAM_ERRORS_TOTAL.inc()
        return JSONResponse({"error": "orchestrator unreachable",
                             "detail": e.__class__.__name__}, status_code=502)
    # Redirects (the orchestrator's `/` -> /WeatherGPT.dc.html) pass through
    # untouched so the browser follows them via the gateway.
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}
    return Response(content=upstream.content, status_code=upstream.status_code,
                    headers=headers)
