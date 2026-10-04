"""Public-surface guards: body cap, per-client rate limit, input validation."""

import asyncio
import json
import logging
import secrets

import config
import httpx
import limits
import main
import pytest
import redis
from fastapi.testclient import TestClient
from starlette.requests import Request

client = TestClient(main.app)


class FakeRedis:
    """Just enough of redis-py for limits._redis_over_limit: the Lua script's
    sliding-window semantics evaluated in Python, plus per-key TTLs and a call
    counter (the cooldown tests need to know when Redis was tried).
    test_lua_window_against_a_real_redis runs the actual script."""

    def __init__(self, error: Exception | None = None):
        self.zsets: dict[str, list[tuple[float, str]]] = {}
        self.ttls: dict[str, int] = {}
        self.calls = 0
        self.error = error

    def eval(self, script, numkeys, key, now, cutoff, limit, member, ttl):
        self.calls += 1
        if self.error is not None:
            raise self.error
        hits = [h for h in self.zsets.get(key, []) if h[0] >= float(cutoff)]
        if len(hits) >= int(limit):
            self.zsets[key] = hits
            return 1
        hits.append((float(now), member))
        self.zsets[key] = hits
        self.ttls[key] = int(ttl)
        return 0


@pytest.fixture(autouse=True)
def _template_only(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Shared-store path by default (the production path), one proxy in front.
    A fresh fake per test is what keeps these independent: limits.reset()
    (conftest) clears per-process state only, never the store."""
    fake = FakeRedis()
    monkeypatch.setattr(limits, "_redis", fake)
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 1)
    return fake


def _request(xff: str | list[str] | None, peer: str = "10.0.0.5") -> Request:
    lines = [xff] if isinstance(xff, str) else (xff or [])
    headers = [(b"x-forwarded-for", line.encode()) for line in lines]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


Q = {"text": "weather in Chennai"}


def test_oversized_body_is_rejected_before_the_route(monkeypatch):
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 1000)
    resp = client.post("/asr", json={"audio": "A" * 5000, "lang": "en"})
    assert resp.status_code == 413


def _stream_post(path: str, chunks: list[bytes], headers: dict | None = None):
    """POST `chunks` one ASGI message at a time, so the body has no Content-Length unless
    `headers` gives one. Returns (response, sizes of the chunks the server pulled): httpx's
    ASGITransport only reads the next chunk when the app asks for it."""
    pulled: list[int] = []

    async def body():
        for chunk in chunks:
            pulled.append(len(chunk))
            yield chunk

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                                     base_url="http://orchestrator") as c:
            return await c.post(path, content=body(), headers={
                "content-type": "application/json", **(headers or {})})

    return asyncio.run(go()), pulled


def test_a_chunked_body_over_the_cap_is_413_too(monkeypatch):
    """No Content-Length (Transfer-Encoding: chunked) used to skip the cap entirely."""
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 1000)
    payload = b"x" * 6000
    assert client.post("/tts", content=payload).status_code == 413
    resp = client.post("/tts", content=(payload[i:i + 1500] for i in range(0, 6000, 1500)))
    assert resp.status_code == 413
    assert resp.json() == {"detail": "request body too large"}
    assert resp.headers["x-content-type-options"] == "nosniff"  # the outer layers still apply


@pytest.mark.parametrize("headers", [
    {},                        # chunked: no Content-Length at all
    {"content-length": "4"},   # declared small, actually large
], ids=["no-content-length", "lying-content-length"])
def test_a_streamed_body_is_cut_off_the_moment_it_crosses_the_cap(monkeypatch, headers):
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 1000)
    resp, pulled = _stream_post("/tts", [b"x" * 400] * 5, headers)
    assert resp.status_code == 413
    assert pulled == [400, 400, 400]  # 800 fits, 1200 doesn't; the other two are never read


def test_a_chunked_body_under_the_cap_reaches_the_route_whole(monkeypatch):
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 1000)
    seen = []
    monkeypatch.setattr(main.bhashini, "text_to_speech", lambda text, lang: seen.append(text))
    raw = json.dumps({"text": "namaste chennai", "lang": "en"}).encode()
    resp, pulled = _stream_post("/tts", [raw[:7], b"", raw[7:20], raw[20:]])
    assert resp.status_code == 200 and resp.json() == {"audio": None}
    assert seen == ["namaste chennai"]
    assert pulled == [7, 0, 13, len(raw) - 20]


def test_a_body_exactly_at_the_cap_is_not_refused(monkeypatch):
    raw = json.dumps({"text": "hi", "lang": "en"}).encode()
    monkeypatch.setattr(config, "MAX_BODY_BYTES", len(raw))
    resp, _ = _stream_post("/tts", [raw[:5], raw[5:]])
    assert resp.status_code == 200
    monkeypatch.setattr(config, "MAX_BODY_BYTES", len(raw) - 1)
    resp, _ = _stream_post("/tts", [raw[:5], raw[5:]])
    assert resp.status_code == 413


def test_asr_audio_field_has_a_length_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 10 * 1024 * 1024)  # get past the body cap
    resp = client.post("/asr", json={"audio": "A" * (main.MAX_AUDIO_B64_CHARS + 1), "lang": "en"})
    assert resp.status_code == 422


def test_tts_text_field_has_a_length_cap():
    resp = client.post("/tts", json={"text": "x" * (main.MAX_TTS_CHARS + 1), "lang": "en"})
    assert resp.status_code == 422


@pytest.mark.parametrize("path,body", [("/asr", {"audio": "AAAA"}), ("/tts", {"text": "hi"})])
def test_voice_routes_reject_unknown_lang(path, body):
    resp = client.post(path, json={**body, "lang": "../../x"})
    assert resp.status_code == 422


def test_facts_rejects_unknown_intent_or_day():
    bad_intent = client.get("/facts", params={"city": "chennai", "intent": "__import__"})
    assert bad_intent.status_code == 422
    assert client.get("/facts", params={"city": "chennai", "day": "99"}).status_code == 422
    assert client.get("/facts", params={"city": "chennai", "lang": "zz"}).status_code == 422
    assert client.get("/facts", params={"city": "chennai"}).status_code == 200


def test_ask_unknown_lang_falls_back_to_english():
    body = client.get("/ask", params={"text": "weather in Chennai", "lang": "zz"}).json()
    assert body["response"].startswith("Chennai")


# --- client identity: which X-Forwarded-For hop is the key -------------------


@pytest.mark.parametrize("trusted,xff,expected", [
    (1, "203.0.113.9", "203.0.113.9"),  # the one proxy in front appended the client
    (1, "1.2.3.4, 203.0.113.9", "203.0.113.9"),  # leftmost hop is client-supplied
    (1, " 1.2.3.4,5.6.7.8 , 203.0.113.9 ,", "203.0.113.9"),  # whitespace, empty entries
    (2, "1.2.3.4, 203.0.113.9, 127.0.0.1", "203.0.113.9"),  # ngrok/ingress -> gateway -> here
    (2, "203.0.113.9", "10.0.0.5"),  # shorter than N: socket peer
    (1, None, "10.0.0.5"),  # no header: socket peer
    (0, "203.0.113.9", "10.0.0.5"),  # nothing in front: header ignored
])
def test_client_key_counts_trusted_hops_from_the_right(monkeypatch, trusted, xff, expected):
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", trusted)
    assert limits.client_key(_request(xff)) == expected


def test_client_key_joins_header_lines_in_order():
    # Two X-Forwarded-For lines combine in order, so a proxy's hop on its own
    # line is still the rightmost.
    assert limits.client_key(_request(["1.2.3.4", "203.0.113.9"])) == "203.0.113.9"


def test_spoofed_leftmost_hop_shares_the_real_clients_window(monkeypatch):
    # The gateway appended 203.0.113.9; what the client typed in front of it
    # must not buy a second window.
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    statuses = [
        client.get("/ask", params=Q,
                   headers={"x-forwarded-for": f"{fake}, 203.0.113.9"}).status_code
        for fake in ("1.2.3.4", "5.6.7.8", "9.9.9.9")
    ]
    assert statuses == [200, 200, 429]


def test_rotating_leftmost_hop_still_gets_429_on_request_31(monkeypatch):
    # The bypass this fix closes: a fresh X-Forwarded-For per request.
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 30)
    statuses = [
        client.get("/ask", params=Q,
                   headers={"x-forwarded-for": f"198.51.100.{i}, 203.0.113.9"}).status_code
        for i in range(31)
    ]
    assert statuses == [200] * 30 + [429]


def test_zero_trusted_hops_ignores_forwarded_for(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 0)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    statuses = [
        client.get("/ask", params=Q, headers={"x-forwarded-for": f"198.51.100.{i}"}).status_code
        for i in range(3)
    ]
    assert statuses == [200, 200, 429]


def test_forwarded_for_shorter_than_trusted_hops_keys_on_the_socket_peer(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 2)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    one_hop = {"x-forwarded-for": "203.0.113.9"}
    another_hop = {"x-forwarded-for": "203.0.113.10"}
    assert client.get("/ask", params=Q, headers=one_hop).status_code == 200
    assert client.get("/ask", params=Q, headers=another_hop).status_code == 429
    assert client.get("/ask", params=Q).status_code == 429  # same peer, no header


# --- the window itself: Redis, fallback, sliding ------------------------------


def test_rate_limit_applies_per_client_on_expensive_routes(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 3)
    statuses = [client.get("/ask", params=Q).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    assert client.get("/health").status_code == 200  # not a limited path
    # A different address, as appended by the trusted proxy, has its own window.
    other = client.get("/ask", params=Q, headers={"x-forwarded-for": "203.0.113.9"})
    assert other.status_code == 200


def test_redis_window_is_shared_across_workers(monkeypatch, fake_redis):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 3)
    assert [client.get("/ask", params=Q).status_code for _ in range(3)] == [200, 200, 200]
    assert fake_redis.ttls == {"weathergpt:ratelimit:testclient": 60}
    hits = fake_redis.zsets["weathergpt:ratelimit:testclient"]
    assert len({member for _, member in hits}) == 3  # distinct members, not one collapsed hit
    limits.reset()  # a second worker: empty deque, no cooldown, same Redis
    assert client.get("/ask", params=Q).status_code == 429
    assert not limits._hits  # the per-process window was never involved


@pytest.mark.parametrize("error", [redis.ConnectionError("refused"), TimeoutError("timed out")])
def test_redis_failure_falls_back_to_the_local_window(monkeypatch, caplog, error):
    dead = FakeRedis(error=error)
    monkeypatch.setattr(limits, "_redis", dead)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    now = [1000.0]
    monkeypatch.setattr(limits, "_monotonic", lambda: now[0])
    with caplog.at_level(logging.WARNING, logger="weathergpt.limits"):
        assert [client.get("/ask", params=Q).status_code for _ in range(3)] == [200, 200, 429]
        assert dead.calls == 1  # cooldown: the next two requests didn't retry Redis
        warnings = [r for r in caplog.records if r.name == "weathergpt.limits"]
        assert len(warnings) == 1  # one line per outage, not per request
    now[0] += limits._REDIS_RETRY_SECONDS
    client.get("/ask", params=Q)
    assert dead.calls == 2  # retried once the cooldown expired


@pytest.mark.parametrize("store", ["redis", "deque"])
def test_rate_limit_window_slides(monkeypatch, store):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    now = [1000.0]
    if store == "redis":
        monkeypatch.setattr(limits, "_wall_clock", lambda: now[0])
    else:
        monkeypatch.setattr(limits, "_redis_retry_at", float("inf"))  # never tried
        monkeypatch.setattr(limits, "_monotonic", lambda: now[0])
    assert client.get("/ask", params=Q).status_code == 200
    assert client.get("/ask", params=Q).status_code == 429
    now[0] += 61
    assert client.get("/ask", params=Q).status_code == 200


@pytest.mark.live
def test_lua_window_against_a_real_redis(monkeypatch):
    """FakeRedis re-implements the Lua script; this runs the real one. Needs a
    Redis at config.REDIS_URL (`docker compose up redis`) and `-m live`."""
    real = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    try:
        real.ping()
    except (redis.RedisError, OSError):
        pytest.skip(f"no Redis at {config.REDIS_URL}")
    monkeypatch.setattr(limits, "_redis", real)
    now = [1000.0]
    monkeypatch.setattr(limits, "_wall_clock", lambda: now[0])
    key = f"live-{secrets.token_hex(4)}"
    try:
        assert [limits._redis_over_limit(key, 2) for _ in range(3)] == [False, False, True]
        assert 0 < real.ttl(f"weathergpt:ratelimit:{key}") <= 60
        now[0] += 61
        assert limits._redis_over_limit(key, 2) is False  # the old hits slid out
    finally:
        real.delete(f"weathergpt:ratelimit:{key}")


def test_delete_history_requires_a_session():
    assert client.delete("/history").status_code == 401


def test_history_without_supabase_config_is_503_not_500(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    resp = client.get("/history", headers={"Authorization": "Bearer abc"})
    assert resp.status_code == 503


def test_me_without_supabase_config_is_503_not_500(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "SUPABASE_URL", None)
    resp = client.get("/me", headers={"Authorization": "Bearer abc"})
    assert resp.status_code == 503


# --- /alerts, /metar/decode and the /ivr/recording global cap ------------------


def _xff(i: int) -> dict:
    return {"x-forwarded-for": f"198.51.100.{i}"}


def test_alerts_writes_are_stricter_and_cover_delete(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 30)
    monkeypatch.setattr(config, "ALERTS_WRITE_RATE_LIMIT_PER_MINUTE", 2)
    body = {"target": "x", "city": "chennai"}
    assert client.post("/alerts/subscribe", json=body).status_code != 429
    assert client.delete("/alerts/subscribe/abc").status_code != 429  # parameterised path
    assert client.post("/alerts/subscribe", json=body).status_code == 429
    assert client.delete("/alerts/subscribe/other").status_code == 429
    assert client.post("/alerts/subscribe/", json=body).status_code == 429  # trailing slash
    # another client has its own budget; /ask is a separate bucket
    assert client.post("/alerts/subscribe", json=body, headers=_xff(7)).status_code != 429
    assert client.get("/ask", params=Q).status_code == 200


def test_alerts_write_limit_never_exceeds_the_master_limit(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(config, "ALERTS_WRITE_RATE_LIMIT_PER_MINUTE", 5)
    assert client.delete("/alerts/subscribe/a").status_code != 429
    assert client.delete("/alerts/subscribe/a").status_code == 429


@pytest.mark.parametrize("path,params", [
    ("/alerts/subscriptions", {"target": "x"}),
    ("/metar/decode", {"raw": "VOMM 010000Z 27005KT 9999 FEW020 28/24 Q1009"}),
])
def test_read_style_routes_are_limited_in_their_own_bucket(monkeypatch, path, params):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    # the handlers may 5xx here (no DB in tests); only the 429 matters
    tolerant = TestClient(main.app, raise_server_exceptions=False)
    statuses = [tolerant.get(path, params=params).status_code for _ in range(3)]
    assert 429 not in statuses[:2]
    assert statuses[2] == 429
    assert client.get("/ask", params=Q).status_code == 200  # /ask budget untouched


# WIE-15: every /intelligence/* route, one per-client bucket of its own.
INTELLIGENCE_ROUTES = [
    ("GET", "/intelligence/best-window", {"params": {"city": "chennai", "day": "today"}}),
    ("POST", "/intelligence/scenario", {"json": {"city": "chennai", "times": ["09:00"]}}),
    ("POST", "/intelligence/advisory", {"json": {"city": "chennai", "day": "today"}}),
    ("GET", "/intelligence/changes", {"params": {"city": "chennai", "day": "today"}}),
]


@pytest.mark.parametrize("method,path,kwargs", INTELLIGENCE_ROUTES)
def test_intelligence_routes_return_429_with_retry_after(monkeypatch, method, path, kwargs):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    statuses = [client.request(method, path, **kwargs) for _ in range(3)]
    assert [r.status_code for r in statuses[:2]] == [200, 200]
    assert statuses[2].status_code == 429
    assert statuses[2].headers["retry-after"] == "60"


def test_intelligence_bucket_is_shared_by_its_routes_but_not_with_ask(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    for method, path, kwargs in INTELLIGENCE_ROUTES[:2]:
        assert client.request(method, path, **kwargs).status_code == 200
    method, path, kwargs = INTELLIGENCE_ROUTES[3]
    assert client.request(method, path, **kwargs).status_code == 429  # same bucket, full
    assert client.get("/ask", params=Q).status_code == 200  # /ask budget untouched
    assert client.get("/cities").status_code == 200  # nor the browse bucket
    assert client.request(method, path, headers=_xff(9), **kwargs).status_code == 200


def test_intelligence_limit_follows_the_master_switch():
    # RATE_LIMIT_PER_MINUTE is 0 (conftest): every per-client rule is off.
    method, path, kwargs = INTELLIGENCE_ROUTES[0]
    assert all(client.request(method, path, **kwargs).status_code == 200 for _ in range(40))


def test_new_paths_unlimited_when_master_switch_is_off():
    for _ in range(40):
        assert client.get("/metar/decode", params={"raw": "x"}).status_code != 429
        assert client.delete("/alerts/subscribe/a").status_code != 429


def test_ivr_recording_hits_a_global_cap_regardless_of_client(monkeypatch):
    monkeypatch.setattr(config, "IVR_GLOBAL_RATE_PER_MIN", 3)
    # RATE_LIMIT_PER_MINUTE is 0 (conftest): the IVR cap is independent of it.
    statuses = [client.post("/ivr/recording", headers=_xff(i)).status_code for i in range(4)]
    assert 429 not in statuses[:3]
    assert statuses[3] == 429


def test_ivr_global_cap_zero_disables_it(monkeypatch):
    monkeypatch.setattr(config, "IVR_GLOBAL_RATE_PER_MIN", 0)
    assert all(client.post("/ivr/recording").status_code != 429 for _ in range(10))


# SEC-N6 (plan.md §8 Phase 8, finding F7): every remaining public route is limited.
# The IVR routes aren't mounted here (IVR_ENABLED off), but the limiter runs
# before routing, so the 429 is the same either way.
BROWSE_ROUTES = [
    ("GET", "/me"), ("GET", "/history"), ("DELETE", "/history"),
    ("GET", "/facts"), ("GET", "/warnings"), ("GET", "/cities"), ("GET", "/glossary"),
    ("GET", "/forecast/daily"), ("GET", "/forecast/hourly"), ("GET", "/hotlines"),
]


@pytest.mark.parametrize("method,path", BROWSE_ROUTES)
def test_browse_routes_return_429_with_retry_after(monkeypatch, method, path):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 30)
    monkeypatch.setattr(config, "BROWSE_RATE_LIMIT_PER_MINUTE", 2)
    tolerant = TestClient(main.app, raise_server_exceptions=False)
    statuses = [tolerant.request(method, path).status_code for _ in range(3)]
    assert 429 not in statuses[:2]
    assert statuses[2] == 429
    assert tolerant.request(method, path).headers["retry-after"] == "60"


def test_browse_bucket_is_shared_by_its_routes_but_not_with_ask(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 30)
    monkeypatch.setattr(config, "BROWSE_RATE_LIMIT_PER_MINUTE", 2)
    assert client.get("/cities").status_code == 200
    assert client.get("/glossary").status_code != 429
    assert client.get("/facts").status_code == 429  # same bucket, now full
    assert client.get("/ask", params=Q).status_code == 200  # /ask budget untouched
    assert client.get("/cities", headers=_xff(9)).status_code == 200  # per client


def test_browse_limit_follows_the_master_switch(monkeypatch):
    monkeypatch.setattr(config, "BROWSE_RATE_LIMIT_PER_MINUTE", 1)
    # RATE_LIMIT_PER_MINUTE is 0 (conftest): every per-client rule is off.
    assert all(client.get("/cities").status_code == 200 for _ in range(5))


@pytest.mark.parametrize("path", ["/ivr/menu.wav", "/ivr/answer/CA123.wav"])
def test_ivr_audio_hits_a_global_cap_with_retry_after(monkeypatch, path):
    monkeypatch.setattr(config, "IVR_AUDIO_RATE_PER_MIN", 2)
    statuses = [client.get(path, headers=_xff(i)) for i in range(3)]
    assert 429 not in [r.status_code for r in statuses[:2]]
    assert statuses[2].status_code == 429
    assert statuses[2].headers["retry-after"] == "60"


def test_ivr_audio_and_recording_caps_are_separate_buckets(monkeypatch):
    monkeypatch.setattr(config, "IVR_AUDIO_RATE_PER_MIN", 1)
    monkeypatch.setattr(config, "IVR_GLOBAL_RATE_PER_MIN", 1)
    assert client.get("/ivr/menu.wav").status_code != 429
    assert client.post("/ivr/recording").status_code != 429
    assert client.get("/ivr/answer/CA1.wav").status_code == 429
    assert client.post("/ivr/recording").status_code == 429


def test_ivr_audio_cap_zero_disables_it(monkeypatch):
    monkeypatch.setattr(config, "IVR_AUDIO_RATE_PER_MIN", 0)
    assert all(client.get("/ivr/menu.wav").status_code != 429 for _ in range(10))


def test_ivr_recording_429_carries_retry_after(monkeypatch):
    # R13 (c): confirms the recording cap's 429 shape, not just its status.
    monkeypatch.setattr(config, "IVR_GLOBAL_RATE_PER_MIN", 1)
    client.post("/ivr/recording")
    r = client.post("/ivr/recording")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
