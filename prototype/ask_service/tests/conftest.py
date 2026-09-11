"""Test isolation: no test may touch a real external API, and the weather cache
is reset between tests.

The network kill-switch patches httpx's real transport, not httpx.get/post or
Client.send — Starlette's TestClient *is* an httpx.Client but routes through its
own ASGI transport, so it keeps working while every genuine outbound call raises.

Mark a test `@pytest.mark.live` to opt out (for the deliberate smoke tests).
"""

import httpx
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits a real external API; skipped without a key"
    )


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
def _clear_weather_cache():
    import google_weather

    google_weather.cache_clear()
    yield
    google_weather.cache_clear()
