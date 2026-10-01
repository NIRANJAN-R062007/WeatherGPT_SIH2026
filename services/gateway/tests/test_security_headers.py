"""SEC-N13 on the gateway: its own responses get the API headers, proxied ones
keep the orchestrator's, /livez is platform-only and the docs are off.
"""

import httpx
import main
import pytest
import security_headers
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture
def upstream(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/page":
            return httpx.Response(200, html="<p>hi</p>", headers={
                "Content-Security-Policy": "from-orchestrator"})
        return httpx.Response(200, json={"path": request.url.path})
    monkeypatch.setattr(main, "_client", httpx.AsyncClient(
        base_url="http://orchestrator", transport=httpx.MockTransport(handler)))


def test_own_responses_carry_the_api_headers():
    h = client.get("/livez").headers
    assert h["content-security-policy"] == security_headers.API_CSP
    assert h["x-content-type-options"] == "nosniff"
    assert h["strict-transport-security"].startswith("max-age=")
    assert h["referrer-policy"]


def test_proxied_responses_keep_the_orchestrators_csp(upstream):
    r = client.get("/page")
    assert r.headers["content-security-policy"] == "from-orchestrator"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_livez_through_the_ingress_is_a_404():
    assert client.get("/livez", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 404


@pytest.mark.skipif(security_headers.DOCS_ENABLED, reason="API_DOCS_ENABLED is on in this env")
def test_gateway_docs_are_off(upstream):
    # No gateway docs route: the catch-all forwards the path, and the
    # orchestrator (docs off too) answers it — the gateway never serves them.
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).json() == {"path": path}
