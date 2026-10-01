"""GET /intelligence/best-window and POST /intelligence/scenario (plan.md
§8 Phase 9, WIE-4/WIE-6 view-only slice backing WIE-13/WIE-14). The error
paths (unknown city, bad day) and the response wiring are tested against a
monkeypatched `main.hourly_facts` for exact, fixture-independent values;
a smoke test against the real committed fixtures checks the endpoints are
wired end to end.
"""

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


def _hourly(hours, *, source="fixture", is_live=False, day="today"):
    return {"source": source, "is_live": is_live, "day": day, "hours": hours}


def hour(local_time, *, rain=10, temp=26, wind=10, condition="clear"):
    return {
        "time_iso": f"2026-10-01T{local_time}:00Z",
        "local_time": local_time,
        "rain_probability_pct": rain,
        "temp_c": temp,
        "wind_kmh": wind,
        "condition": condition,
    }


# --- GET /intelligence/best-window ------------------------------------------


def test_best_window_unknown_city_is_404():
    resp = client.get("/intelligence/best-window", params={"city": "narnia"})
    assert resp.status_code == 404


def test_best_window_bad_day_is_422():
    resp = client.get("/intelligence/best-window", params={"city": "chennai", "day": "someday"})
    assert resp.status_code == 422


def test_best_window_no_hourly_data_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "hourly_facts", lambda key, day: None)
    resp = client.get("/intelligence/best-window", params={"city": "chennai", "day": "tomorrow"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["window"] is None
    assert body["provenance"] is None


def test_best_window_with_a_suitable_run(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10), hour("10:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(main, "hourly_facts", lambda key, day: _hourly(hours))
    params = {"city": "chennai", "day": "today", "activity": "outdoor"}
    resp = client.get("/intelligence/best-window", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["window"]["start_local"] == "09:00"
    assert body["window"]["end_local"] == "10:00"
    assert body["provenance"] == {"source": "fixture", "is_live": False}
    assert body["city"] == "chennai"
    assert body["activity"] == "outdoor"


def test_best_window_no_suitable_hour_is_a_distinct_status(monkeypatch):
    hours = [hour("09:00", rain=90, temp=40, wind=50)]
    monkeypatch.setattr(main, "hourly_facts", lambda key, day: _hourly(hours))
    resp = client.get("/intelligence/best-window", params={"city": "chennai", "day": "today"})
    body = resp.json()
    assert body["status"] == "no_suitable_window"
    assert body["window"] is None


def test_best_window_against_the_real_fixtures_is_wired_end_to_end():
    # No monkeypatch: exercises weather_data.hourly_facts + window_analyzer
    # against the committed forecast_hours fixtures (WEATHER_MODE=fixtures,
    # the suite default). Only checks shape/invariants — not exact values,
    # since the fixtures get refreshed independently of this test.
    resp = client.get("/intelligence/best-window", params={"city": "chennai", "day": "today"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "no_suitable_window", "unavailable")
    if body["status"] == "ok":
        w = body["window"]
        assert len(w["start_local"]) == 5 and len(w["end_local"]) == 5
        assert w["hours"]


# --- POST /intelligence/scenario --------------------------------------------


def test_scenario_unknown_city_is_404():
    resp = client.post("/intelligence/scenario", json={"city": "narnia", "times": ["09:00"]})
    assert resp.status_code == 404


def test_scenario_bad_day_is_422():
    body = {"city": "chennai", "day": "whenever", "times": ["09:00"]}
    resp = client.post("/intelligence/scenario", json=body)
    assert resp.status_code == 422


def test_scenario_requires_at_least_one_time():
    resp = client.post("/intelligence/scenario", json={"city": "chennai", "times": []})
    assert resp.status_code == 422  # pydantic min_length


def test_scenario_no_hourly_data_reports_every_time_unavailable(monkeypatch):
    monkeypatch.setattr(main, "hourly_facts", lambda key, day: None)
    body = {"city": "chennai", "times": ["09:00", "17:00"]}
    resp = client.post("/intelligence/scenario", json=body)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["hours"] == [
        {"time": "09:00", "available": False},
        {"time": "17:00", "available": False},
    ]
    assert body["better_time"] is None


def test_scenario_compares_two_times(monkeypatch):
    hours = [hour("09:00", rain=10, temp=24, wind=8), hour("17:00", rain=40, temp=33, wind=20)]
    monkeypatch.setattr(main, "hourly_facts", lambda key, day: _hourly(hours))
    body = {"city": "chennai", "times": ["09:00", "17:00"]}
    resp = client.post("/intelligence/scenario", json=body)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["better_time"] == "09:00"
    assert body["provenance"] == {"source": "fixture", "is_live": False}
