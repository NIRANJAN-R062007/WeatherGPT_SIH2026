"""Gateway body cap (MAX_BODY_BYTES): an oversize upload gets the orchestrator's
413 before the gateway buffers it or calls upstream — whether Content-Length
says so up front, the body arrives chunked with no length at all, or the
declared length lies. Under-cap bodies still reach the orchestrator byte-exact.

The orchestrator is a MockTransport that echoes the body (no network). The
streaming cases drive the app through httpx's ASGITransport, which hands each
generator chunk to the app as its own ASGI message and only pulls a chunk when
the app asks for it — so `pulled` is exactly what the gateway read.
"""

import asyncio

import httpx
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)
CAP = 16


class _Upstream:
    def __init__(self):
        self.last: httpx.Request | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last = request
        return httpx.Response(200, content=request.content)


@pytest.fixture
def upstream(monkeypatch):
    up = _Upstream()
    monkeypatch.setattr(main, "_client", httpx.AsyncClient(
        base_url="http://orchestrator", transport=httpx.MockTransport(up.handler)))
    monkeypatch.setattr(main, "MAX_BODY_BYTES", CAP)
    return up


def _stream_post(chunks: list[bytes], headers: dict | None = None):
    """POST `chunks` one ASGI message at a time; returns (response, chunk sizes the app read)."""
    pulled: list[int] = []

    async def body():
        for chunk in chunks:
            pulled.append(len(chunk))
            yield chunk

    async def go():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as c:
            return await c.post("/asr", content=body(), headers=headers or {})

    return asyncio.run(go()), pulled


def test_oversize_content_length_is_413_before_the_body_is_read(upstream):
    r, pulled = _stream_post([b"x" * 10] * 3, headers={"content-length": str(CAP + 1)})
    assert r.status_code == 413
    assert r.json() == {"detail": "request body too large"}
    assert pulled == []  # refused on the header alone
    assert upstream.last is None


def test_one_byte_over_the_cap_is_413_and_never_forwarded(upstream):
    r = client.post("/asr", content=b"x" * (CAP + 1))
    assert r.status_code == 413
    assert r.json() == {"detail": "request body too large"}
    assert upstream.last is None


@pytest.mark.parametrize("headers", [
    {},                        # chunked: httpx sends Transfer-Encoding, no Content-Length
    {"content-length": "4"},   # declared small, actually large
], ids=["no-content-length", "lying-content-length"])
def test_streamed_body_is_413_the_moment_it_crosses_the_cap(upstream, headers):
    r, pulled = _stream_post([b"x" * 10] * 5, headers=headers)
    assert r.status_code == 413
    assert r.json() == {"detail": "request body too large"}
    assert pulled == [10, 10]  # 10 fits, 20 doesn't; the other three are never read
    assert upstream.last is None


def test_body_at_the_cap_is_forwarded_byte_exact(upstream):
    payload = bytes(range(CAP))
    r = client.post("/asr", content=payload)
    assert r.status_code == 200
    assert upstream.last.content == payload
    assert r.content == payload


def test_chunked_body_under_the_cap_is_reassembled_and_forwarded(upstream):
    r, pulled = _stream_post([b"abc", b"", b"defgh"])
    assert r.status_code == 200
    assert pulled == [3, 0, 5]
    assert upstream.last.content == b"abcdefgh"
    assert r.content == b"abcdefgh"
