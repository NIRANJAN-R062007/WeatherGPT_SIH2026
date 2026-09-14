"""Prometheus metrics for the orchestrator (plan.md §14 observability track).

`HTTPMetrics` is a pure-ASGI middleware (not `BaseHTTPMiddleware` — that would
buffer the response body just to time a request) that wraps every HTTP call,
records its duration and status, and labels it with the *matched route
template* rather than the raw path so an attacker probing random URLs can't
explode label cardinality. `observe_ask` records the /ask-specific counters
(answer provider/narration mix, template-fallback reasons). `render()` backs
`GET /metrics` on both services.

Registered with `app.add_middleware(metrics.HTTPMetrics, service=...)` AFTER
`limits.RequestLimits` in main.py, so it ends up outermost and also counts
413s/429s that never reach the route handlers.
"""

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled",
    ["service", "method", "route", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

ASK_TOTAL = Counter(
    "weathergpt_ask_total",
    "Total /ask answers, by how they were produced",
    ["intent", "lang", "provider", "narration"],
)

ASK_FALLBACK_TOTAL = Counter(
    "weathergpt_ask_fallback_total",
    "Total /ask answers that fell back to the template narrator",
    ["reason"],
)


class HTTPMetrics:
    """ASGI middleware: times every HTTP request/response cycle and records
    `http_requests_total` / `http_request_duration_seconds`.

    The route label is read from `scope["route"]` *after* `self.app` runs —
    Starlette's router sets it while dispatching, so it isn't there yet on
    entry. Anything that never matches a route (typos, scanners) is labelled
    "unmatched" instead of leaking the raw path into a metric label.
    """

    def __init__(self, app, service: str):
        self.app = app
        self.service = service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            raise
        finally:
            route = scope.get("route")
            route_path = route.path if route is not None else "unmatched"
            duration = time.perf_counter() - start
            HTTP_REQUESTS_TOTAL.labels(
                service=self.service, method=method, route=route_path,
                status=str(status_code),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                service=self.service, method=method, route=route_path,
            ).observe(duration)


def observe_ask(intent: str, lang: str, provider: str, narration: str,
                fallback_used: bool, no_llm: bool) -> None:
    """Record one /ask answer. `narration` is "llm", "llm+bhashini" or
    "template" (main.py's own labelling). A template answer always means a
    fallback happened; `no_llm` (narrate() never produced usable text, e.g.
    no provider configured) vs. the guardrail rejecting an LLM answer picks
    the reason label.
    """
    ASK_TOTAL.labels(intent=intent, lang=lang, provider=provider, narration=narration).inc()
    if narration == "template":
        reason = "no_llm" if no_llm else "guardrail"
        ASK_FALLBACK_TOTAL.labels(reason=reason).inc()


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
