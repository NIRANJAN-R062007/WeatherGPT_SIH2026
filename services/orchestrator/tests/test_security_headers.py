"""SEC-N13 (plan.md §8 Phase 8; findings F8, F12): security headers on every
response, API docs off by default, /metrics behind METRICS_TOKEN, and /livez
answering direct (platform) requests only.
"""

from pathlib import Path

import config
import main
import pytest
import security_headers
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
client = TestClient(main.app)


def test_gateway_copy_is_identical():
    ours = (REPO / "services/orchestrator/security_headers.py").read_text()
    assert (REPO / "services/gateway/security_headers.py").read_text() == ours


def test_json_responses_carry_the_api_headers():
    h = client.get("/cities").headers
    assert h["content-security-policy"] == security_headers.API_CSP
    assert h["strict-transport-security"].startswith("max-age=31536000")
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"


def test_rejections_carry_the_headers_too():
    # 404s from the router and CORS preflight rejections pass through the
    # same outermost middleware.
    h = client.get("/no-such-route").headers
    assert h["x-content-type-options"] == "nosniff"
    pre = client.options("/cities", headers={
        "Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"})
    assert pre.headers["content-security-policy"] == security_headers.API_CSP


def test_html_gets_the_page_csp_and_upstream_values_are_kept():
    app = FastAPI()
    app.get("/page")(lambda: HTMLResponse("<p>hi</p>"))
    app.get("/own")(lambda: HTMLResponse("<p>hi</p>", headers={
        "Content-Security-Policy": "default-src 'none'"}))
    app.add_middleware(security_headers.SecurityHeaders)
    c = TestClient(app)
    assert c.get("/page").headers["content-security-policy"] == security_headers.PAGE_CSP
    # setdefault, not overwrite — what lets the gateway pass the orchestrator's through.
    assert c.get("/own").headers["content-security-policy"] == "default-src 'none'"


def test_page_csp_matches_amplify():
    # Text match, not a YAML parse: PyYAML isn't an orchestrator dependency.
    custom = (REPO / "customHttp.yml").read_text()
    assert f"value: \"{security_headers.PAGE_CSP}\"" in custom
    for name in ("Strict-Transport-Security", "X-Content-Type-Options", "Referrer-Policy"):
        assert f"key: {name}" in custom


@pytest.mark.skipif(security_headers.DOCS_ENABLED, reason="API_DOCS_ENABLED is on in this env")
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_are_off_by_default(path):
    assert client.get(path).status_code == 404


def test_docs_kwargs(monkeypatch):
    monkeypatch.setattr(security_headers, "DOCS_ENABLED", False)
    assert security_headers.docs_kwargs() == {
        "docs_url": None, "redoc_url": None, "openapi_url": None}
    monkeypatch.setattr(security_headers, "DOCS_ENABLED", True)
    assert security_headers.docs_kwargs() == {}


def test_livez_is_platform_only():
    assert client.get("/livez").status_code == 200
    proxied = client.get("/livez", headers={"X-Forwarded-For": "203.0.113.7"})
    assert proxied.status_code == 404


def test_metrics_is_disabled_without_a_token(monkeypatch):
    monkeypatch.setattr(config, "METRICS_TOKEN", "")
    assert client.get("/metrics").status_code == 404


def test_metrics_requires_the_bearer_token(monkeypatch):
    monkeypatch.setattr(config, "METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200 and "http_requests_total" in ok.text
