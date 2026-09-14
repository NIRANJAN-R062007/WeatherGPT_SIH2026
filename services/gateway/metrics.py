"""Prometheus metrics for the gateway (plan.md §14 observability track).

Deliberately a standalone copy of `services/orchestrator/metrics.py`'s
`HTTPMetrics` rather than a shared import: the gateway's Docker build context
is `services/gateway/` alone (see its Dockerfile), so it can't reach into
`services/orchestrator/`. Keep the two in sync by hand if the contract
changes — see the observability task write-up for the shared label/metric
names both services must emit identically.

`gateway_upstream_errors_total` is gateway-only: it counts proxy requests
that never got a response from the orchestrator at all (httpx.HTTPError in
main.py's `proxy()`), as opposed to the orchestrator answering with an error
status, which is just a normal `http_requests_total{status=...}`.
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

GATEWAY_UPSTREAM_ERRORS_TOTAL = Counter(
    "gateway_upstream_errors_total",
    "Total proxied requests that never reached/received a response from the orchestrator",
)


class HTTPMetrics:
    """ASGI middleware: times every HTTP request/response cycle and records
    `http_requests_total` / `http_request_duration_seconds`. See the
    orchestrator's `metrics.py` for the full rationale — identical behaviour
    here, just duplicated because the two services build from separate
    Docker contexts.
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


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
