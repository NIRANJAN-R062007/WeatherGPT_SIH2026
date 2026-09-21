"""/health is unauthenticated, so its probe is cached for HEALTH_CACHE_SECONDS
and hits are rate limited per client — keyed like the orchestrator's limiter
(the socket peer by default; never a hop a client could forge). Counting fakes
stand in for Postgres, Redis and the orchestrator: no network, no DB. Time is
`main._monotonic`, advanced by hand."""

import asyncio
from collections import defaultdict, deque
from types import SimpleNamespace

import httpx
import main
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

client = TestClient(main.app)


class _Engine:
    """Counts connects; doubles as the connection/result for the two SELECTs."""

    def __init__(self, error: Exception | None = None):
        self.connects = 0
        self.error = error

    def connect(self):
        self.connects += 1
        if self.error:
            raise self.error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement):
        return self

    def scalar(self):
        return "3.4"


class _Redis:
    def __init__(self, error: Exception | None = None):
        self.pings = 0
        self.error = error

    def ping(self):
        self.pings += 1
        if self.error:
            raise self.error
        return True


class _Upstream:
    def __init__(self, error: Exception | None = None, delay: float = 0.0):
        self.calls = 0
        self.error = error
        self.delay = delay

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.error:
            raise self.error
        if self.delay:
            await asyncio.sleep(self.delay)
        return httpx.Response(200, json={"ok": True})


def _wire(monkeypatch, engine, redis_client, upstream):
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "redis_client", redis_client)
    monkeypatch.setattr(main, "_client", httpx.AsyncClient(
        base_url="http://orchestrator", transport=httpx.MockTransport(upstream.handler)))


@pytest.fixture
def deps(monkeypatch):
    """Healthy fakes, an empty cache/limiter, and a clock that only moves when told."""
    d = SimpleNamespace(engine=_Engine(), redis=_Redis(), upstream=_Upstream(), now=1000.0)
    _wire(monkeypatch, d.engine, d.redis, d.upstream)
    monkeypatch.setattr(main, "_health_cache", None)
    monkeypatch.setattr(main, "_health_hits", defaultdict(deque))
    monkeypatch.setattr(main, "_monotonic", lambda: d.now)
    return d


def _io(d) -> tuple[int, int, int]:
    return d.engine.connects, d.redis.pings, d.upstream.calls


def test_repeat_hits_within_the_ttl_are_served_from_cache(deps):
    first = client.get("/health")
    assert first.status_code == 200
    assert first.json() == {"postgres": "ok", "postgis": "ok (3.4)", "redis": "ok",
                            "orchestrator": {"ok": True}}
    deps.now += main.HEALTH_CACHE_SECONDS - 0.1
    assert client.get("/health").json() == first.json()
    assert _io(deps) == (1, 1, 1)

    deps.now += 0.1  # exactly at the TTL: stale
    assert client.get("/health").status_code == 200
    assert _io(deps) == (2, 2, 2)


def test_over_the_limit_is_429_with_retry_after_and_no_io(deps, monkeypatch):
    monkeypatch.setattr(main, "HEALTH_RATE_LIMIT_PER_MINUTE", 3)
    assert [client.get("/health").status_code for _ in range(4)] == [200, 200, 200, 429]
    r = client.get("/health")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "60"
    assert r.json() == {"detail": "too many requests — try again in a minute"}

    deps.now += 11  # cache is stale now, but a limited client still causes no I/O
    assert client.get("/health").status_code == 429
    assert _io(deps) == (1, 1, 1)

    deps.now += 50  # the first three hits fall out of the 60 s window
    assert client.get("/health").status_code == 200
    assert _io(deps) == (2, 2, 2)


def test_limit_of_zero_disables_the_limiter(deps, monkeypatch):
    monkeypatch.setattr(main, "HEALTH_RATE_LIMIT_PER_MINUTE", 0)
    assert all(client.get("/health").status_code == 200 for _ in range(100))
    assert _io(deps) == (1, 1, 1)  # still cached


def test_livez_and_metrics_are_neither_limited_nor_proxied(deps, monkeypatch):
    monkeypatch.setattr(main, "HEALTH_RATE_LIMIT_PER_MINUTE", 1)
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429
    for _ in range(3):
        assert client.get("/livez").json() == {"status": "ok"}
        assert client.get("/metrics").status_code == 200
    assert deps.upstream.calls == 1


def test_failures_stay_generic_and_are_cached_too(deps, monkeypatch):
    dsn = "postgresql://weathergpt:s3cret@db-internal:5432/weathergpt"
    _wire(monkeypatch, _Engine(error=RuntimeError(f"cannot connect to {dsn}")),
          _Redis(error=ConnectionError("redis-internal:6379 refused")),
          _Upstream(error=httpx.ConnectError("orchestrator-internal refused")))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"postgres": "error", "postgis": "error", "redis": "error",
                        "orchestrator": "error"}
    for leak in ("s3cret", "db-internal", "redis-internal", "orchestrator-internal",
                 "RuntimeError", "ConnectError"):
        assert leak not in r.text

    assert client.get("/health").json() == r.json()
    assert (main.engine.connects, main.redis_client.pings) == (1, 1)  # a dead DB isn't hammered


def test_concurrent_misses_probe_once(deps, monkeypatch):
    slow = _Upstream(delay=0.05)  # yields mid-probe so the second request arrives
    _wire(monkeypatch, deps.engine, deps.redis, slow)
    monkeypatch.setattr(main, "_health_lock", asyncio.Lock())  # bound to this test's loop only

    async def go():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as c:
            return await asyncio.gather(c.get("/health"), c.get("/health"))

    a, b = asyncio.run(go())
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert (deps.engine.connects, deps.redis.pings, slow.calls) == (1, 1, 1)


def _key(xff: str | None, trusted_hops: int, monkeypatch, peer: str = "10.0.0.1") -> str:
    monkeypatch.setattr(main, "_TRUSTED_XFF_HOPS", trusted_hops)
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return main._client_key(Request({"type": "http", "headers": headers, "client": (peer, 1234)}))


def test_client_key_never_trusts_a_hop_the_client_could_have_written(monkeypatch):
    two_hops = "203.0.113.9, 198.51.100.7"
    # Default (TRUSTED_PROXY_HOPS=1 -> nothing in front of the gateway): peer only.
    assert _key(two_hops, 0, monkeypatch) == "10.0.0.1"
    assert _key(None, 0, monkeypatch) == "10.0.0.1"
    # One trusted proxy in front (ngrok / the Ingress): the hop it appended, i.e. the rightmost.
    assert _key(two_hops, 1, monkeypatch) == "198.51.100.7"
    assert _key(None, 1, monkeypatch) == "10.0.0.1"
    # Two: second from the right; a header too short to have come through them -> peer.
    assert _key(two_hops, 2, monkeypatch) == "203.0.113.9"
    assert _key("203.0.113.9", 2, monkeypatch) == "10.0.0.1"
    assert _key(" 203.0.113.9 ,, 198.51.100.7 ", 2, monkeypatch) == "203.0.113.9"


def test_forged_forwarded_for_does_not_buy_a_fresh_window(deps, monkeypatch):
    monkeypatch.setattr(main, "HEALTH_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(main, "_TRUSTED_XFF_HOPS", 0)
    assert client.get("/health").status_code == 200
    for i in range(3):
        r = client.get("/health", headers={"x-forwarded-for": f"198.51.100.{i}"})
        assert r.status_code == 429
