"""Test isolation: no test may touch a real external API, and the weather cache
is reset between tests.

The network kill-switch patches httpx's real transport, not httpx.get/post or
Client.send — Starlette's TestClient *is* an httpx.Client but routes through its
own ASGI transport, so it keeps working while every genuine outbound call raises.

Mark a test `@pytest.mark.live` to opt out (for the deliberate smoke tests).
"""

import config
import httpx
import pytest
import redis

# Default the whole suite to offline fixtures — deterministic, no network, and it
# matches the demo-safe path. Tests that exercise live/auto machinery override this
# per-module (test_google_weather.py) or per-test.
config.WEATHER_MODE = "fixtures"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits a real external API; skipped without a key"
    )


def pytest_runtest_setup(item):
    """`live` tests only run when explicitly selected with -m live."""
    if "live" in item.keywords and "live" not in item.config.getoption("markexpr"):
        pytest.skip("live test — run with -m live")


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    if "live" in request.keywords:
        yield
        return

    def _blocked(self, request):
        raise httpx.ConnectError(f"network disabled in tests ({request.url})")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)
    yield


@pytest.fixture(autouse=True)
def _no_local_datastores(request, monkeypatch):
    """weather_store's Redis and Postgres are external services too, and the
    kill switch above only covers HTTP.

    Without this the suite's result depends on whether the developer happens
    to have `docker compose up` running: a reachable localhost Redis hands
    weather_store.redis_get() a previously cached snapshot, so the live-path
    tests in test_google_weather.py never reach their stub and fail (six of
    them), while CI — which has no Redis — stays green. Postgres is the
    quieter half of the same problem: the tests were writing real rows into
    whatever database DATABASE_URL happened to point at.

    Scoped to weather_store deliberately. limits.py's Redis is already
    isolated by test_limits.py's own autouse `fake_redis`, and its one
    deliberate real-Redis test is `-m live` gated — stubbing the limiter here
    would disable that test instead of protecting it.

    Tests that exercise either backend (test_weather_store.py) monkeypatch
    these same two attributes themselves, which takes precedence per-test.
    """
    if "live" in request.keywords:
        yield
        return

    import weather_store

    class _UnreachableRedis:
        def get(self, *a, **k):
            raise redis.ConnectionError("redis disabled in tests")

        def setex(self, *a, **k):
            raise redis.ConnectionError("redis disabled in tests")

    class _UnreachableEngine:
        def begin(self, *a, **k):
            raise RuntimeError("postgres disabled in tests")

        def connect(self, *a, **k):
            raise RuntimeError("postgres disabled in tests")

    monkeypatch.setattr(weather_store, "_redis", _UnreachableRedis())
    monkeypatch.setattr(weather_store, "_engine", _UnreachableEngine())
    yield


@pytest.fixture(autouse=True)
def _clear_weather_cache():
    import google_weather

    google_weather.cache_clear()
    yield
    google_weather.cache_clear()


@pytest.fixture(autouse=True)
def _clear_bhashini_cache():
    import bhashini

    bhashini.cache_clear()
    yield
    bhashini.cache_clear()


@pytest.fixture(autouse=True)
def _llm_defaults(monkeypatch):
    """Reset offline/Ollama state per test — test_config's importlib.reload()
    would otherwise resurrect the real OLLAMA_MODEL default and silently
    route the `_no_llm` NLU tests through Ollama instead of rules_fallback.
    """
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(config, "OLLAMA_MODEL", None)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 0)  # limiter tests opt in
    import limits
    limits.reset()
    import narrate

    monkeypatch.setattr(narrate, "last_provider", None)
