"""GET /cyclones: serves gdacs.public() unchanged — the dated fixture snapshot when
offline, and "unavailable" (never an empty list) when GDACS can't be read. No
test touches the real service."""

import config
import gdacs
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _fresh_cache():
    gdacs.cache_clear()
    yield
    gdacs.cache_clear()


def test_cyclones_serves_the_fixture_snapshot_with_the_source_metadata(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    body = client.get("/cyclones").json()
    assert body["status"] == "ok"
    assert body["is_live"] is False
    assert body["count"] == len(body["events"]) >= 1
    assert body["source"] == "GDACS"
    assert "Not an IMD product" in body["attribution"]
    assert body["disclaimer"]
    assert body["terms_url"].startswith("https://www.gdacs.org/")
    event = body["events"][0]
    assert event["track"]["segments"] and event["alert_level"] in {"Green", "Orange", "Red"}


def test_cyclones_unavailable_is_not_an_empty_list(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "live")

    def down(now):
        raise gdacs.FetchError("down")

    monkeypatch.setattr(gdacs, "_fetch_raw", down)
    body = client.get("/cyclones").json()
    assert body["status"] == "unavailable"
    assert body["events"] is None and body["count"] is None
    assert body["disclaimer"] and body["attribution"]


def test_cyclones_takes_no_user_input(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    calls = []
    monkeypatch.setattr(gdacs, "_get_json", lambda *a, **k: calls.append(a))
    client.get("/cyclones", params={"city": "../../etc/passwd", "eventid": "1; DROP"})
    assert calls == []
