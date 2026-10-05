"""WIE-11: GET /intelligence/changes and /ask's `forecast_change` intent, end
to end — a seeded pair of snapshots produces the "rose from 30% to 70%" answer
(plan.md §15). The earlier forecast goes in through forecast_snapshots.record()
exactly as a live fetch would put it there; the current hourly forecast is the
one weather_data hands back."""

import forecast_snapshots
import google_weather
import history
import main
import weather_store
from fastapi.testclient import TestClient

client = TestClient(main.app)

EARLIER = "2026-10-04T06:00:00+00:00"
NOW = "2026-10-04T07:00:00+00:00"


def _payload(rain_by_hour):
    return {"forecastHours": [
        {"interval": {"startTime": f"2026-10-04T{h:02d}:00:00Z"},
         "temperature": {"degrees": 27.0}, "precipitation": {"probability": {"percent": rain}},
         "wind": {"speed": {"value": 10.0}}}
        for h, rain in rain_by_hour.items()
    ]}


def _hour(h, rain):
    return {"time_iso": f"2026-10-04T{h:02d}:00:00Z", "local_time": f"{h:02d}:00",
            "temp_c": 27.0, "rain_probability_pct": rain, "wind_kmh": 10.0}


def _hourly(rain_by_hour, *, day="today", retrieved_at=NOW):
    return {"source": "Google Weather API", "is_live": True, "day": day,
            "retrieved_at": retrieved_at,
            "hours": [_hour(h, r) for h, r in rain_by_hour.items()]}


def _seed(monkeypatch, *, earlier, now, day="today"):
    """An earlier retrieval in the store; `now` is what the forecast says today."""
    monkeypatch.setattr(weather_store, "persist", lambda *a, **k: None)
    cell = google_weather.cell_for("chennai")
    if earlier is not None:
        forecast_snapshots.record(cell, 13.08, 80.27, _payload(earlier), EARLIER)
    monkeypatch.setattr(main, "hourly_facts",
                        lambda key, d: _hourly(now, day=d))


# --- GET /intelligence/changes ----------------------------------------------


def test_a_seeded_pair_reports_the_rain_rise(monkeypatch):
    _seed(monkeypatch, earlier={14: 30, 15: 30, 16: 30}, now={14: 70, 15: 70, 16: 30})
    body = client.get("/intelligence/changes", params={"city": "chennai", "day": "today"}).json()
    assert body["status"] == "ok" and body["city"] == "chennai"
    (change,) = body["changes"]
    assert (change["metric"], change["from"], change["to"]) == ("rain_probability_pct", 30, 70)
    assert (change["start_local"], change["end_local"]) == ("14:00", "15:00")
    assert body["baseline"] == {"retrieved_at": EARLIER}
    assert body["provenance"]["retrieved_at"] == NOW
    assert body["compared_hours"] == 3


def test_no_earlier_snapshot_says_so_and_never_no_change(monkeypatch):
    monkeypatch.setattr(weather_store, "read_snapshot_before", lambda cell, before: None)
    _seed(monkeypatch, earlier=None, now={14: 70})
    body = client.get("/intelligence/changes", params={"city": "chennai", "day": "today"}).json()
    assert body["status"] == "no_baseline"
    assert body["changes"] == [] and body["baseline"] is None


def test_a_sub_threshold_wobble_is_no_significant_change(monkeypatch):
    _seed(monkeypatch, earlier={14: 30}, now={14: 38})
    body = client.get("/intelligence/changes", params={"city": "chennai", "day": "today"}).json()
    assert body["status"] == "no_significant_change" and body["changes"] == []
    assert body["baseline"] == {"retrieved_at": EARLIER}


def test_a_fixtures_mode_request_has_no_baseline():
    """The committed fixtures are one frozen snapshot: nothing earlier exists."""
    body = client.get("/intelligence/changes", params={"city": "chennai", "day": "today"}).json()
    assert body["status"] in ("no_baseline", "unavailable")
    assert body["changes"] == []


def test_no_hourly_forecast_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "hourly_facts", lambda key, d: None)
    body = client.get("/intelligence/changes", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable" and body["changes"] == []


def test_changes_validates_day_and_city():
    assert client.get("/intelligence/changes", params={"city": "chennai", "day": "x"}
                      ).status_code == 422
    assert client.get("/intelligence/changes", params={"city": "atlantis"}).status_code == 404


# --- /ask forecast_change ----------------------------------------------------


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params})


def test_ask_answers_with_both_values_and_both_retrieval_times(monkeypatch):
    _seed(monkeypatch, earlier={14: 30, 15: 30, 16: 30}, now={14: 70, 15: 70, 16: 30})
    r = _ask("has the forecast changed in Chennai")
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "forecast_change" and body["city"] == "chennai"
    assert body["status"] == "ok"
    assert "rose from 30% to 70%" in body["response"]
    assert "14:00–15:00" in body["response"]
    assert "2026-10-04 06:00 UTC" in body["response"] and "2026-10-04 07:00 UTC" in body["response"]
    assert body["changes"][0]["from"] == 30 and body["changes"][0]["to"] == 70
    assert body["baseline"] == {"retrieved_at": EARLIER}
    assert body["grounding"]["narration"] == "verbatim" and body["grounding"]["provider"] == "feed"
    assert body["provenance"]["is_live"] is True
    assert body["nlu"]["intent"] == "forecast_change" and body["nlu"]["source"] == "rules"


def test_ask_with_no_earlier_forecast_is_an_honest_no_baseline(monkeypatch):
    monkeypatch.setattr(weather_store, "read_snapshot_before", lambda cell, before: None)
    _seed(monkeypatch, earlier=None, now={14: 70})
    body = _ask("what changed in Chennai's forecast").json()
    assert body["intent"] == "forecast_change" and body["status"] == "no_baseline"
    assert "no earlier forecast" in body["message"].lower()
    assert "no change" not in body["message"].lower()
    assert "response" not in body


def test_ask_with_a_small_move_says_no_significant_change(monkeypatch):
    _seed(monkeypatch, earlier={14: 30}, now={14: 35})
    body = _ask("has the forecast changed in Chennai").json()
    assert body["status"] == "no_significant_change"
    assert "no significant change" in body["response"]


def test_ask_with_no_hourly_data_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "hourly_facts", lambda key, d: None)
    body = _ask("has the forecast changed in Chennai").json()
    assert body["intent"] == "forecast_change" and body["status"] == "unavailable"


def test_ask_uses_the_selected_city_when_none_is_named(monkeypatch):
    _seed(monkeypatch, earlier={14: 30}, now={14: 80})
    body = _ask("any changes in today's weather", city="chennai").json()
    assert body["intent"] == "forecast_change" and body["city"] == "chennai"
    assert body["status"] == "ok"


def test_ask_in_another_language_answers_in_that_language(monkeypatch):
    # WIE-8: in-language template, no "English only" notice any more.
    _seed(monkeypatch, earlier={14: 30}, now={14: 80})
    body = _ask("has the forecast changed in Chennai", lang="hi").json()
    assert body["intent"] == "forecast_change"
    assert "बारिश की संभावना में बढ़ोतरी: 30% से 80%" in body["response"]
    assert "notice" not in body


def test_ask_records_a_signed_in_users_change_question(monkeypatch):
    _seed(monkeypatch, earlier={14: 30}, now={14: 80})
    seen = {}
    monkeypatch.setattr(history, "record", lambda token, **k: seen.update(token=token, **k))
    client.get("/ask", params={"text": "has the forecast changed in Chennai"},
               headers={"Authorization": "Bearer t"})
    assert seen["token"] == "t"
    assert (seen["intent"], seen["city"]) == ("forecast_change", "chennai")


def test_a_plain_rain_question_is_not_a_change_question():
    body = _ask("will it rain tomorrow in Chennai").json()
    assert body["intent"] == "will_it_rain"


# --- the live-fetch hook -----------------------------------------------------


def test_a_live_forecast_hours_fetch_is_recorded_as_a_baseline(monkeypatch):
    import config

    queued = []
    monkeypatch.setattr(config, "WEATHER_MODE", "live")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "k")
    monkeypatch.setattr(weather_store, "redis_get", lambda *a: None)
    monkeypatch.setattr(weather_store, "redis_set", lambda *a: None)
    monkeypatch.setattr(weather_store, "persist", lambda kind, cell, fields: queued.append(kind))
    monkeypatch.setattr(google_weather, "fetch_json", lambda *a, **k: _payload({8: 30}))
    google_weather.snapshot("forecast_hours", "chennai")
    assert forecast_snapshots.KIND in queued
    cell = google_weather.cell_for("chennai")
    assert forecast_snapshots.previous(cell, "2999-01-01T00:00:00Z") is not None
