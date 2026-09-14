"""Public-surface guards: body cap, per-client rate limit, input validation."""

import config
import limits
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _template_only(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)


def test_oversized_body_is_rejected_before_the_route(monkeypatch):
    monkeypatch.setattr(config, "MAX_BODY_BYTES", 1000)
    resp = client.post("/asr", json={"audio": "A" * 5000, "lang": "en"})
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


def test_rate_limit_applies_per_client_on_expensive_routes(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 3)
    q = {"text": "weather in Chennai"}
    statuses = [client.get("/ask", params=q).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    assert client.get("/health").status_code == 200  # not a limited path
    other = client.get("/ask", params=q, headers={"x-forwarded-for": "203.0.113.9"})
    assert other.status_code == 200  # a different client has its own window


def test_rate_limit_window_slides(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 1)
    now = [1000.0]
    monkeypatch.setattr(limits, "_monotonic", lambda: now[0])
    q = {"text": "weather in Chennai"}
    assert client.get("/ask", params=q).status_code == 200
    assert client.get("/ask", params=q).status_code == 429
    now[0] += 61
    assert client.get("/ask", params=q).status_code == 200


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
