"""history.py: Supabase PostgREST calls made with the caller's own token.

Following test_bhashini.py's pattern, the "success" path here mocks
httpx.post/httpx.get directly rather than hitting real Supabase.
"""

import config
import history
import httpx
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "anon-key")


def test_record_posts_row_without_user_id(monkeypatch):
    seen = {}

    def _post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _post)
    history.record("user-token", query="weather in chennai", intent="current_weather",
                    city="chennai", lang="en", response="Chennai: cloudy, 28°C.")

    assert seen["url"] == "https://example.supabase.co/rest/v1/history"
    assert seen["headers"]["Authorization"] == "Bearer user-token"
    assert seen["headers"]["apikey"] == "anon-key"
    assert "user_id" not in seen["json"]  # column defaults to auth.uid() server-side
    assert seen["json"]["query"] == "weather in chennai"


def test_record_raises_on_failure(monkeypatch):
    def _post(url, headers=None, json=None, timeout=None):
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _post)
    with pytest.raises(httpx.HTTPStatusError):
        history.record("bad-token", query="q", intent=None, city=None, lang=None, response=None)


def test_record_without_credentials_raises_config_error(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    with pytest.raises(config.ConfigError):
        history.record("t", query="q", intent=None, city=None, lang=None, response=None)


def test_list_for_user_returns_rows(monkeypatch):
    rows = [{"id": "1", "query": "weather in chennai", "created_at": "2026-09-13T00:00:00Z"}]

    def _get(url, headers=None, params=None, timeout=None):
        assert params["order"] == "created_at.desc"
        return httpx.Response(200, json=rows, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", _get)
    assert history.list_for_user("user-token") == rows


def test_list_for_user_raises_on_failure(monkeypatch):
    def _get(url, headers=None, params=None, timeout=None):
        return httpx.Response(403, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", _get)
    with pytest.raises(httpx.HTTPStatusError):
        history.list_for_user("user-token")


def test_get_history_requires_token():
    assert client.get("/history").status_code == 401


def test_get_history_returns_rows(monkeypatch):
    rows = [{"id": "1", "query": "weather in chennai"}]
    monkeypatch.setattr(history, "list_for_user", lambda token, **k: rows)
    r = client.get("/history", headers={"Authorization": "Bearer user-token"})
    assert r.status_code == 200
    assert r.json() == {"history": rows}


def test_get_history_propagates_auth_failure(monkeypatch):
    def _boom(token, **k):
        raise httpx.HTTPStatusError("nope", request=httpx.Request("GET", "https://x"),
                                     response=httpx.Response(401))

    monkeypatch.setattr(history, "list_for_user", _boom)
    r = client.get("/history", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401


def test_ask_without_token_does_not_touch_history(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")

    def _boom(*a, **k):
        raise AssertionError("history.record called with no signed-in user")

    monkeypatch.setattr(history, "record", _boom)
    r = client.get("/ask", params={"text": "what's the weather in Chennai"})
    assert r.status_code == 200


def test_ask_with_token_logs_to_history(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")
    seen = {}
    monkeypatch.setattr(history, "record", lambda token, **k: seen.update(token=token, **k))
    r = client.get("/ask", params={"text": "what's the weather in Chennai"},
                    headers={"Authorization": "Bearer user-token"})
    assert r.status_code == 200
    assert seen["token"] == "user-token"
    assert seen["city"] == "chennai"
    assert seen["response"] == r.json()["response"]


def test_ask_swallows_history_write_failure(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")

    def _boom(*a, **k):
        raise httpx.HTTPStatusError("nope", request=httpx.Request("POST", "https://x"),
                                     response=httpx.Response(500))

    monkeypatch.setattr(history, "record", _boom)
    r = client.get("/ask", params={"text": "what's the weather in Chennai"},
                    headers={"Authorization": "Bearer user-token"})
    assert r.status_code == 200  # the weather answer must survive a broken history write
