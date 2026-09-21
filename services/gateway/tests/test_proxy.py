"""Gateway reverse proxy: everything but /health reaches the orchestrator with
the client address appended to X-Forwarded-For; upstream failures are a 502,
not a stack trace. The orchestrator is a MockTransport — no network, no DB."""

import json

import httpx
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


class _Upstream:
    """Records the last request the gateway forwarded and plays a canned reply."""

    def __init__(self):
        self.last: httpx.Request | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last = request
        path = request.url.path
        if path == "/":
            return httpx.Response(307, headers={"location": "/WeatherGPT.dc.html"})
        if path == "/health":
            return httpx.Response(200, json={"ok": True})
        if path == "/boom":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"path": path, "query": request.url.query.decode(),
                                         "body": request.content.decode()},
                              headers={"x-upstream": "1", "content-encoding": "identity"})


@pytest.fixture
def upstream(monkeypatch):
    up = _Upstream()
    monkeypatch.setattr(main, "_client", httpx.AsyncClient(
        base_url="http://orchestrator", transport=httpx.MockTransport(up.handler)))
    return up


def test_get_is_forwarded_with_query_and_client_ip(upstream):
    r = client.get("/ask?text=weather%20in%20Chennai&lang=ta")
    assert r.status_code == 200
    assert r.json()["path"] == "/ask"
    assert r.json()["query"] == "text=weather%20in%20Chennai&lang=ta"
    assert upstream.last.headers["x-forwarded-for"] == "testclient"
    assert r.headers["x-upstream"] == "1"
    assert "content-encoding" not in r.headers  # httpx already decoded the body


def test_existing_forwarded_for_gets_the_peer_appended_as_last_hop(upstream):
    client.get("/facts?city=chennai", headers={"x-forwarded-for": "203.0.113.9"})
    assert upstream.last.headers["x-forwarded-for"] == "203.0.113.9, testclient"


def test_post_body_and_bearer_token_pass_through(upstream):
    r = client.post("/tts", json={"text": "hi", "lang": "en"},
                    headers={"authorization": "Bearer abc"})
    assert r.status_code == 200
    assert json.loads(r.json()["body"]) == {"text": "hi", "lang": "en"}
    assert upstream.last.headers["authorization"] == "Bearer abc"
    assert upstream.last.method == "POST"
    assert "host" not in {k.lower() for k in upstream.last.headers} or \
        upstream.last.headers["host"] == "orchestrator"


def test_root_redirect_passes_through_unfollowed(upstream):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/WeatherGPT.dc.html"


def test_unreachable_orchestrator_is_a_502(upstream):
    r = client.get("/boom")
    assert r.status_code == 502
    assert r.json()["error"] == "orchestrator unreachable"


def test_health_is_the_gateways_own_and_reports_orchestrator(upstream, monkeypatch):
    class _DeadEngine:
        def connect(self):
            raise RuntimeError("no db")

    class _DeadRedis:
        def ping(self):
            raise RuntimeError("no redis")

    monkeypatch.setattr(main, "engine", _DeadEngine())
    monkeypatch.setattr(main, "redis_client", _DeadRedis())
    monkeypatch.setattr(main, "_health_cache", None)  # force a real probe
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["orchestrator"] == {"ok": True}
    assert body["postgres"].startswith("error") and body["redis"].startswith("error")
    assert upstream.last.url.path == "/health"
