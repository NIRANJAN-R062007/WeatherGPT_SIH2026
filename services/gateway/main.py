"""WeatherGPT API gateway (plan.md §4).

Everything except `/health` is reverse-proxied to the orchestrator
(`services/orchestrator/`, the former `prototype/ask_service`). The
orchestrator still owns rate limiting (`limits.py`, keyed off the first
X-Forwarded-For hop) and body-size caps, so the gateway appends the client
address to X-Forwarded-For and otherwise passes requests through untouched —
including the frontend the orchestrator serves at `/`.

Postgres/Redis are checked lazily in `/health` only; the proxy works without
them, so the demo path (`uvicorn main:app --port 8000` + ngrok) has no
database dependency.
"""

import os

import httpx
import metrics
import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

app = FastAPI(title="WeatherGPT Gateway", version="0.1.0")
app.add_middleware(metrics.HTTPMetrics, service="gateway")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001").rstrip("/")
# /tts and LLM narration can take a while; connect fast, read slow.
PROXY_TIMEOUT = httpx.Timeout(float(os.getenv("PROXY_TIMEOUT", "60")), connect=5.0)

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
    # Keep the first hop (ngrok sets it to the real client) so the
    # orchestrator's per-client rate limit keys the right address.
    if prior and client_ip:
        headers["x-forwarded-for"] = f"{prior}, {client_ip}"
    elif client_ip:
        headers["x-forwarded-for"] = client_ip
    return headers


@app.get("/health")
async def health():
    """Gateway health: Postgres+PostGIS, Redis, and the orchestrator behind us.
    Each check is independent — a dead database must not hide a live orchestrator."""
    status: dict = {"postgres": "unknown", "postgis": "unknown", "redis": "unknown",
                    "orchestrator": "unknown"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["postgres"] = "ok"
            postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            status["postgis"] = f"ok ({postgis_version})"
    except Exception as e:
        status["postgres"] = f"error: {e}"
        status["postgis"] = "error"

    try:
        redis_client.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"

    try:
        r = await _client.get("/health", timeout=5.0)
        status["orchestrator"] = (r.json() if r.status_code == 200
                                  else f"error: HTTP {r.status_code}")
    except Exception as e:
        status["orchestrator"] = f"error: {e}"

    return status


@app.get("/livez")
def livez():
    """k8s liveness probe: no I/O, just "is the process serving requests"."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics_route():
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)


# Registered before the catch-all below so /livez and /metrics are always the
# gateway's own — the orchestrator's proxy() branch never sees these paths.
@app.api_route("/{path:path}", methods=_PROXY_METHODS)
async def proxy(request: Request, path: str):
    url = f"/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    body = await request.body()
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
