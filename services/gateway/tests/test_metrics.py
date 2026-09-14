"""Gateway Prometheus metrics: /livez and /metrics are the gateway's own (not
proxied), a proxied request is counted under the route the catch-all matches,
and an unreachable orchestrator bumps gateway_upstream_errors_total.

Own MockTransport fixture (not imported from test_proxy.py — see that file
for the original pattern this mirrors).
"""

import httpx
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


class _Upstream:
    def __init__(self):
        self.last: httpx.Request | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last = request
        if request.url.path == "/boom":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"path": request.url.path})


@pytest.fixture
def upstream(monkeypatch):
    up = _Upstream()
    monkeypatch.setattr(main, "_client", httpx.AsyncClient(
        base_url="http://orchestrator", transport=httpx.MockTransport(up.handler)))
    return up


def test_livez_is_the_gateways_own(upstream):
    r = client.get("/livez")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert upstream.last is None  # never proxied


def test_metrics_is_the_gateways_own(upstream):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert upstream.last is None  # never proxied


def test_proxied_ask_is_counted_under_the_catchall_route(upstream):
    r = client.get("/ask?text=weather%20in%20Chennai&lang=en")
    assert r.status_code == 200
    assert upstream.last.url.path == "/ask"  # actually reached the orchestrator

    body = client.get("/metrics").text
    # FastAPI's catch-all matches everything as one route template — asserting
    # on what's actually observed rather than assuming "/ask" survives as a label.
    assert 'route="/{path:path}"' in body
    assert 'http_requests_total{' in body


def test_unreachable_orchestrator_bumps_upstream_errors_total(upstream):
    r = client.get("/boom")
    assert r.status_code == 502

    body = client.get("/metrics").text
    assert "gateway_upstream_errors_total" in body
    for line in body.splitlines():
        if line.startswith("gateway_upstream_errors_total ") or \
                line.startswith("gateway_upstream_errors_total{"):
            assert not line.endswith(" 0.0")
