"""Prometheus metrics: /livez, /metrics, and the labels the middleware +
observe_ask() attach to real /ask traffic (plan.md §14 observability track).

The default test setup (conftest.py's `_llm_defaults`, no GEMINI/GROQ keys)
means /ask always takes the template path here unless a test monkeypatches
`main.narrate` itself — same as test_ask_flow.py.
"""

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


def test_livez_shape():
    r = client.get("/livez")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ask_then_metrics_reports_template_narration_and_route_labels():
    ask = client.get("/ask", params={"text": "weather in Chennai", "lang": "en"})
    assert ask.status_code == 200

    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text

    assert 'weathergpt_ask_total{' in body
    assert 'provider="template"' in body
    assert 'narration="template"' in body

    assert 'http_requests_total{' in body
    assert 'route="/ask"' in body
    assert 'status="200"' in body

    assert 'http_request_duration_seconds_bucket{' in body
    # route="/ask" should appear on at least one duration bucket line too.
    assert any(
        line.startswith("http_request_duration_seconds_bucket{") and 'route="/ask"' in line
        for line in body.splitlines()
    )


def test_unmatched_route_is_labelled_unmatched_not_the_raw_path():
    r = client.get("/definitely-not-a-route")
    assert r.status_code == 404

    body = client.get("/metrics").text
    assert 'route="unmatched"' in body
    for line in body.splitlines():
        if line.startswith("http_requests_total{") or \
                line.startswith("http_request_duration_seconds_bucket{"):
            assert "/definitely-not-a-route" not in line


def test_ask_fallback_total_increments_on_guardrail_rejection(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 99°C and 4 inches of rain.")
    body = client.get("/ask", params={"text": "weather in Chennai", "lang": "en"}).json()
    assert body["grounding"]["narration"] == "template"
    assert body["grounding"]["fallback_used"] is True

    metrics_body = client.get("/metrics").text
    assert 'weathergpt_ask_fallback_total{reason="guardrail"}' in metrics_body


def test_ask_fallback_total_increments_with_no_llm_reason_when_narrate_returns_none(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    body = client.get("/ask", params={"text": "weather in Chennai", "lang": "en"}).json()
    assert body["grounding"]["narration"] == "template"

    metrics_body = client.get("/metrics").text
    assert 'weathergpt_ask_fallback_total{reason="no_llm"}' in metrics_body
