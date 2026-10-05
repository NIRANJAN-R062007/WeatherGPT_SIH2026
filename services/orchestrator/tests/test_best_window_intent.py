"""GET /ask's `best_window` intent (plan.md §8 Phase 9, WIE-4): "when is the
best time to go outside tomorrow in Chennai" -> a grounded answer with
provenance, built from the Weather Intelligence Engine's result (WIE-3),
never from free LLM narration — the numeric guardrail doesn't check clock
times yet (WIE-5), so the answer text is a deterministic template, like
warnings' verbatim headline and aviation's METAR/TAF briefings.

nlu-level parsing is tests/test_nlu.py's job; this file is the /ask
response shape, the engine wiring (weather_data.hourly_facts via
router.route) and the persona rule (fisherman/aviation get no window
verdict, R17).
"""

import history
import main
import weather_data
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


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params})


# --- a suitable window -------------------------------------------------------


def test_ask_best_window_answers_with_a_suitable_window(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10), hour("10:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours, day=day))
    r = _ask("when is the best time to go outside tomorrow in Chennai")
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "best_window" and body["city"] == "chennai"
    assert body["status"] == "ok"
    assert body["label"] == "outdoor"
    assert body["window"]["start_local"] == "09:00"
    assert body["window"]["end_local"] == "10:00"
    assert "09:00" in body["response"] and "10:00" in body["response"]
    assert "safe" not in body["response"].lower() and "unsafe" not in body["response"].lower()
    assert body["provenance"] == {
        "source": "fixture",
        "issued": None,
        "is_live": False,
        "retrieved_at": body["provenance"]["retrieved_at"],
    }
    g = body["grounding"]
    assert (g["narration"], g["provider"], g["total"], g["ok"]) == ("verbatim", "feed", 0, True)
    assert body["nlu"]["intent"] == "best_window" and body["nlu"]["source"] == "rules"
    assert "notice" not in body


def test_ask_best_window_response_numbers_match_the_window_exactly(monkeypatch):
    hours = [hour("09:00", rain=12, temp=27.5, wind=9), hour("10:00", rain=8, temp=28.5, wind=11)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside in Chennai").json()
    w = body["window"]
    assert str(w["avg_temp_c"]) in body["response"]
    assert str(w["max_rain_probability_pct"]) in body["response"]
    assert str(w["max_wind_kmh"]) in body["response"]


# --- no suitable window -------------------------------------------------------


def test_ask_best_window_no_suitable_window_is_a_real_negative_answer(monkeypatch):
    hours = [hour("09:00", rain=90, temp=40, wind=50)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside today in Chennai").json()
    assert body["status"] == "no_suitable_window"
    assert body["window"] is None
    assert "no suitable window" in body["response"].lower()
    assert "safe" not in body["response"].lower() and "unsafe" not in body["response"].lower()


# --- unavailable ---------------------------------------------------------------


def test_ask_best_window_no_hourly_data_is_unavailable(monkeypatch):
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: None)
    r = _ask("best time to go outside tomorrow in Chennai")
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "best_window" and body["status"] == "unavailable"
    assert body["message"] == main._MESSAGES["best_window_unavailable"]["en"]
    assert "response" not in body and "provenance" not in body  # never invented


# --- persona: fisherman / aviation get no window verdict (R17) ---------------


def test_ask_best_window_fisherman_gets_no_window_but_a_caveat(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside tomorrow in Chennai", persona="fisherman").json()
    assert body["status"] == "ok"
    assert body["label"] is None and body["window"] is None
    assert "IMD fishermen warning" in body["response"]
    assert "safe" not in body["response"].lower() and "unsafe" not in body["response"].lower()
    assert body["persona"] == "fisherman"


def test_ask_best_window_aviation_persona_gets_no_window_but_a_caveat(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside tomorrow in Chennai", persona="aviation").json()
    assert body["status"] == "ok"
    assert body["label"] is None and body["window"] is None
    assert "airport observation" in body["response"]


def test_ask_best_window_farmer_and_traveller_get_identical_numbers(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10), hour("10:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    farmer = _ask("best time to go outside tomorrow in Chennai", persona="farmer").json()
    traveller = _ask("best time to go outside tomorrow in Chennai", persona="traveller").json()
    assert farmer["label"] == "farm" and traveller["label"] == "travel"
    assert farmer["window"] == traveller["window"]


# --- notices and language -----------------------------------------------------


def test_ask_best_window_answers_in_the_asked_language(monkeypatch):
    # WIE-8: the template answer is in-language, with no "English only" notice.
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside tomorrow in Chennai", lang="hi").json()
    assert "बाहर रहने के लिए सबसे उपयुक्त समय" in body["response"]
    assert "09:00" in body["response"] and "notice" not in body


def test_ask_best_window_uses_the_selected_city_when_none_is_named(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    body = _ask("best time to go outside", city="madurai").json()
    assert body["intent"] == "best_window" and body["city"] == "madurai"


def test_ask_best_window_with_no_city_at_all_asks_which():
    body = _ask("best time to go outside").json()
    assert body["intent"] == "best_window" and "response" not in body
    assert body["message"] == main._msg("need_location", "en")


# --- fixtures-vs-live provenance ----------------------------------------------


def test_ask_best_window_live_is_marked_live(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours, is_live=True))
    body = _ask("best time to go outside tomorrow in Chennai").json()
    assert body["provenance"]["is_live"] is True


# --- history -------------------------------------------------------------------


def test_ask_records_a_signed_in_users_best_window_question(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))
    seen = {}
    monkeypatch.setattr(history, "record", lambda token, **k: seen.update(token=token, **k))
    client.get(
        "/ask",
        params={"text": "best time to go outside tomorrow in Chennai"},
        headers={"Authorization": "Bearer t"},
    )
    assert seen["token"] == "t"
    assert (seen["intent"], seen["city"]) == ("best_window", "chennai")


def test_a_history_failure_does_not_break_the_best_window_answer(monkeypatch):
    hours = [hour("09:00", rain=10, temp=26, wind=10)]
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: _hourly(hours))

    def _boom(*a, **k):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(history, "record", _boom)
    r = client.get(
        "/ask",
        params={"text": "best time to go outside tomorrow in Chennai"},
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200 and r.json()["intent"] == "best_window"


# --- against the real committed fixtures, end to end --------------------------


def test_ask_best_window_against_the_real_fixtures_is_wired_end_to_end():
    body = _ask("best time to go outside today in Chennai").json()
    assert body["intent"] == "best_window"
    assert body["status"] in ("ok", "no_suitable_window", "unavailable")
    if body["status"] == "ok" and body["label"] is not None:
        assert len(body["window"]["start_local"]) == 5
