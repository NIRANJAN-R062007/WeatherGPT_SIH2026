"""aviation.py: live METAR/TAF fetch, TTL cache, fixture fallback, and how
/aviation and /ask serve them. No test touches the real service — the fetch is
stubbed, and the fixtures are real reports snapshotted from aviationweather.gov.
"""

import json

import aviation
import config
import history
import httpx
import main
import metar
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)

LIVE_METAR = "METAR VOMM 300230Z 24012KT 6000 SCT020 BKN080 31/25 Q1006 NOSIG"
LIVE_TAF = (
    "TAF VOMM 300500Z 3006/3106 25010KT 6000 SCT020\n"
    "  TEMPO 3010/3014 4000 -RA BKN012\n"
)


@pytest.fixture
def auto_mode(monkeypatch):
    """Live-then-fixture, with a stub for the network. `stub.calls` records each
    fetch; `stub.reply` maps kind -> (status, body) or an Exception to raise."""
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")

    class Stub:
        calls: list = []
        reply = {"metar": (200, LIVE_METAR), "taf": (200, LIVE_TAF)}

    stub = Stub()
    stub.calls = []

    def _get(url, params=None, timeout=None, **_):
        kind = url.rsplit("/", 1)[1]
        stub.calls.append((kind, params["ids"], params["format"]))
        reply = stub.reply[kind]
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        return httpx.Response(status, text=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", _get)
    return stub


# --- which station -------------------------------------------------------------


@pytest.mark.parametrize(
    "given, icao",
    [("chennai", "VOMM"), ("Chennai", "VOMM"), ("madras", "VOMM"), ("VOMM", "VOMM"),
     ("vabb", "VABB"), ("thiruvananthapuram", "VOTV")],
)
def test_station_for_known_places(given, icao):
    assert aviation.station_for(given) == icao


@pytest.mark.parametrize("given", ["kolkata", "VECC", "", "nowhere"])
def test_station_for_unknown_place(given):
    assert aviation.station_for(given) is None


def test_every_demo_city_has_a_station_and_a_fixture():
    import cities

    for key in cities.CITIES:
        icao = aviation.station_for(key)
        assert icao, key
        doc = json.loads((config.FIXTURES_DIR / "aviation" / f"{icao}.json").read_text("utf-8"))
        assert doc["metar"] and doc["taf"], icao
        metar.decode(doc["metar"])
        import taf

        assert taf.decode(doc["taf"])["unparsed"] == [], icao


# --- fixtures mode ---------------------------------------------------------------


def test_fixtures_mode_never_touches_the_network(monkeypatch):
    assert config.WEATHER_MODE == "fixtures"  # the suite default (conftest)
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: pytest.fail("fixtures mode must not fetch")
    )
    r = aviation.public("VOMM")
    assert r["status"] == "ok"
    for kind in ("metar", "taf"):
        assert r[kind]["is_live"] is False
        assert r[kind]["retrieved_at"].startswith("2026-09-29")  # the snapshot's own date
        assert r[kind]["source"] == "aviationweather.gov"
    assert r["metar"]["decoded"]["station"] == "VOMM"
    assert r["metar"]["briefing"].startswith("Chennai airport (VOMM)")
    assert r["taf"]["briefing"].startswith("Chennai airport (VOMM), terminal forecast")
    assert "flight planning" in r["disclaimer"]


def test_missing_fixture_is_unavailable_not_fair_weather(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path)
    r = aviation.public("VOMM")
    assert r["status"] == "unavailable"
    assert r["metar"] is None and r["taf"] is None


def test_fixture_with_only_one_report(monkeypatch, tmp_path):
    (tmp_path / "aviation").mkdir()
    (tmp_path / "aviation" / "VOMM.json").write_text(
        json.dumps({"station": "VOMM", "fetched_at": "2026-09-29T21:00:00+00:00",
                    "metar": LIVE_METAR, "taf": None}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path)
    r = aviation.public("VOMM")
    assert r["status"] == "ok" and r["metar"] and r["taf"] is None


# --- live fetch ------------------------------------------------------------------


def test_live_fetch_is_decoded_and_marked_live(auto_mode):
    r = aviation.public("VOMM")
    assert r["status"] == "ok"
    assert r["metar"]["is_live"] and r["taf"]["is_live"]
    assert r["metar"]["raw"] == LIVE_METAR
    # The multi-line TAF is flattened to one line.
    assert r["taf"]["raw"].startswith("TAF VOMM 300500Z 3006/3106 25010KT 6000 SCT020 TEMPO")
    assert r["taf"]["decoded"]["changes"][0]["kind"] == "TEMPO"
    assert sorted(auto_mode.calls) == [("metar", "VOMM", "raw"), ("taf", "VOMM", "raw")]


def test_live_reports_are_cached_until_their_ttl(auto_mode, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(aviation, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(config, "TTL_METAR", 600)
    monkeypatch.setattr(config, "TTL_TAF", 1800)

    aviation.public("VOMM")
    assert len(auto_mode.calls) == 2
    clock[0] += 599
    aviation.public("VOMM")
    assert len(auto_mode.calls) == 2  # both still fresh

    clock[0] += 2  # 601 s: the METAR has expired, the TAF (1800 s) has not
    aviation.public("VOMM")
    assert [c[0] for c in auto_mode.calls[2:]] == ["metar"]

    clock[0] += 1300  # past the TAF's TTL as well
    aviation.public("VOMM")
    assert [c[0] for c in auto_mode.calls[3:]] == ["metar", "taf"]


def test_picks_the_requested_station_out_of_a_multi_report_body(auto_mode):
    auto_mode.reply["metar"] = (
        200,
        "METAR VABB 300230Z 09004KT 3500 BR FEW020 26/23 Q1011\n" + LIVE_METAR + "\n",
    )
    assert aviation.public("VOMM")["metar"]["raw"] == LIVE_METAR


def test_no_report_from_the_service_is_not_replaced_by_an_old_snapshot(auto_mode):
    auto_mode.reply["metar"] = (204, "")
    r = aviation.public("VOMM")
    assert r["metar"] is None  # the service is up and has none; a fixture would mislead
    assert r["taf"] is not None and r["taf"]["is_live"]
    assert r["status"] == "ok"


def test_body_with_only_another_stations_report_counts_as_no_report(auto_mode):
    auto_mode.reply["metar"] = (200, "METAR VABB 300230Z 09004KT 3500 BR Q1011\n")
    assert aviation.public("VOMM")["metar"] is None


def test_network_failure_falls_back_to_the_dated_snapshot(auto_mode):
    auto_mode.reply["metar"] = httpx.ConnectError("boom")
    auto_mode.reply["taf"] = (503, "Service Unavailable")
    r = aviation.public("VOMM")
    assert r["status"] == "ok"
    assert r["metar"]["is_live"] is False and r["taf"]["is_live"] is False
    assert r["metar"]["retrieved_at"].startswith("2026-09-29")


def test_fixture_fallback_is_not_cached_so_the_next_call_retries(auto_mode):
    auto_mode.reply["metar"] = httpx.ConnectError("boom")
    assert aviation.public("VOMM")["metar"]["is_live"] is False
    auto_mode.reply["metar"] = (200, LIVE_METAR)
    assert aviation.public("VOMM")["metar"]["is_live"] is True


def test_live_mode_has_no_fallback(auto_mode, monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "live")
    auto_mode.reply["metar"] = httpx.ConnectError("boom")
    auto_mode.reply["taf"] = httpx.ConnectError("boom")
    r = aviation.public("VOMM")
    assert r["status"] == "unavailable"
    assert r["metar"] is None and r["taf"] is None


def test_upstream_garbage_is_not_shown(auto_mode):
    auto_mode.reply["metar"] = (200, "<html>Bad gateway</html>")
    assert aviation.public("VOMM")["metar"] is None


# --- helpers ---------------------------------------------------------------------


def test_issued_iso_uses_the_fetch_date_for_month_and_year():
    part = {"decoded": {"observed": {"day": 29, "time_utc": "21:30", "time_ist": "03:00"}},
            "retrieved_at": "2026-09-29T21:50:00+00:00"}
    assert aviation.issued_iso(part) == "2026-09-29T21:30+00:00"


def test_issued_iso_rolls_back_a_month_across_the_month_end():
    part = {"decoded": {"observed": {"day": 30, "time_utc": "23:50", "time_ist": "05:20"}},
            "retrieved_at": "2026-10-01T00:05:00+00:00"}
    assert aviation.issued_iso(part) == "2026-09-30T23:50+00:00"


def test_issued_iso_rolls_back_a_year_across_new_year():
    part = {"decoded": {"observed": {"day": 31, "time_utc": "23:50", "time_ist": "05:20"}},
            "retrieved_at": "2027-01-01T00:05:00+00:00"}
    assert aviation.issued_iso(part) == "2026-12-31T23:50+00:00"


def test_issued_iso_for_a_taf_uses_the_issue_time():
    part = {"decoded": {"issued": {"day": 29, "time_utc": "20:00", "time_ist": "01:30"}},
            "retrieved_at": "2026-09-29T21:50:00+00:00"}
    assert aviation.issued_iso(part) == "2026-09-29T20:00+00:00"


def test_issued_iso_gives_up_quietly_on_an_impossible_date():
    part = {"decoded": {"observed": {"day": 31, "time_utc": "10:00", "time_ist": "15:30"}},
            "retrieved_at": "2026-09-29T21:50:00+00:00"}  # September has no day 31
    assert aviation.issued_iso(part) is None
    assert aviation.issued_iso({"decoded": {}, "retrieved_at": ""}) is None


@pytest.mark.parametrize(
    "text, want",
    [("METAR for Chennai", "metar"), ("taf chennai", "taf"), ("TAF and METAR", "taf"),
     ("Chennai airport weather", "both"), ("metars", "both")],
)
def test_want_from_text(text, want):
    assert aviation.want_from_text(text) == want


def test_answer_text_notes_a_snapshot_and_adds_the_disclaimer():
    r = aviation.public("VOMM")  # fixtures mode: snapshots
    text = aviation.answer_text(r, "metar")
    assert text.startswith("Snapshot taken 2026-09-29, not a live report. Chennai airport (VOMM)")
    assert "terminal forecast" not in text
    assert text.endswith(r["disclaimer"])
    both = aviation.answer_text(r, "both")
    assert "routine report" in both and "terminal forecast" in both


def test_answer_text_for_a_live_report_has_no_snapshot_note(auto_mode):
    text = aviation.answer_text(aviation.public("VOMM"), "metar")
    assert text.startswith("Chennai airport (VOMM), routine report")


def test_answer_text_is_none_without_a_requested_report(auto_mode):
    auto_mode.reply["taf"] = (204, "")
    assert aviation.answer_text(aviation.public("VOMM"), "taf") is None


# --- GET /aviation ---------------------------------------------------------------


def test_endpoint_by_city_and_by_station():
    by_city = client.get("/aviation", params={"city": "mumbai"})
    by_station = client.get("/aviation", params={"station": "vabb"})
    assert by_city.status_code == by_station.status_code == 200
    assert by_city.json() == by_station.json()
    body = by_city.json()
    assert (body["station"], body["station_name"], body["city"]) == ("VABB", "Mumbai", "mumbai")
    assert body["status"] == "ok"


def test_endpoint_rejects_unknown_and_missing_places():
    assert client.get("/aviation", params={"city": "kolkata"}).status_code == 404
    assert client.get("/aviation", params={"station": "VECC"}).status_code == 404
    assert client.get("/aviation").status_code == 422


def test_endpoint_never_forwards_a_callers_station_upstream(auto_mode):
    client.get("/aviation", params={"station": "../../etc"})
    client.get("/aviation", params={"station": "KJFK"})
    assert auto_mode.calls == []


def test_endpoint_reports_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path)
    body = client.get("/aviation", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable" and body["metar"] is None and body["taf"] is None


# --- /ask ------------------------------------------------------------------------


def test_ask_metar_answers_from_the_airport_report():
    r = client.get("/ask", params={"text": "METAR for Chennai airport"}).json()
    assert r["intent"] == "aviation" and r["city"] == "chennai" and r["status"] == "ok"
    assert r["response"].startswith("Snapshot taken 2026-09-29, not a live report. Chennai airport")
    assert "terminal forecast" not in r["response"]  # asked for the METAR only
    assert r["aviation"]["station"] == "VOMM"
    assert r["provenance"]["source"] == "aviationweather.gov"
    assert r["provenance"]["is_live"] is False
    assert r["provenance"]["issued"] == "2026-09-29T21:30+00:00"
    g = r["grounding"]
    assert (g["narration"], g["provider"], g["total"], g["ok"]) == ("verbatim", "feed", 0, True)
    assert r["nlu"]["intent"] == "aviation" and r["nlu"]["source"] == "rules"
    assert "notice" not in r


def test_ask_taf_answers_with_the_forecast_only():
    r = client.get("/ask", params={"text": "TAF for Mumbai"}).json()
    assert r["intent"] == "aviation" and r["city"] == "mumbai"
    assert "terminal forecast (TAF)" in r["response"] and "routine report" not in r["response"]
    assert r["provenance"]["issued"] == "2026-09-29T20:00+00:00"


def test_ask_airport_weather_gives_both():
    r = client.get("/ask", params={"text": "Delhi airport weather"}).json()
    assert r["intent"] == "aviation"
    assert "routine report" in r["response"] and "terminal forecast" in r["response"]


def test_ask_uses_the_selected_city_when_none_is_named():
    r = client.get("/ask", params={"text": "metar please", "city": "madurai"}).json()
    assert r["intent"] == "aviation" and r["city"] == "madurai"
    assert r["aviation"]["station"] == "VOMD"


def test_ask_with_no_city_at_all_asks_which():
    r = client.get("/ask", params={"text": "metar please"}).json()
    assert r["intent"] == "aviation" and "response" not in r
    assert r["message"].startswith("Which city?")


def test_ask_in_another_language_gets_an_english_notice():
    r = client.get("/ask", params={"text": "METAR Chennai", "lang": "hi"}).json()
    assert r["intent"] == "aviation"
    assert r["response"].startswith("Snapshot")  # English
    assert r["notice"] == main._MESSAGES["aviation_english_only"]["hi"]


def test_ask_when_no_report_exists_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path)
    r = client.get("/ask", params={"text": "metar Chennai"}).json()
    assert r["intent"] == "aviation" and r["status"] == "unavailable"
    assert r["message"] == main._MESSAGES["aviation_unavailable"]["en"]
    assert "response" not in r and "provenance" not in r  # never shown as fair weather


def test_ask_live_reports_are_marked_live(auto_mode):
    r = client.get("/ask", params={"text": "metar Chennai"}).json()
    assert r["provenance"]["is_live"] is True
    assert not r["response"].startswith("Snapshot")


def test_ask_persona_is_echoed_but_does_not_change_the_briefing():
    plain = client.get("/ask", params={"text": "metar Chennai"}).json()
    pilot = client.get("/ask", params={"text": "metar Chennai", "persona": "aviation"}).json()
    assert pilot["persona"] == "aviation"
    assert pilot["response"] == plain["response"]


def test_ask_records_a_signed_in_users_aviation_question(monkeypatch):
    seen = {}
    monkeypatch.setattr(history, "record", lambda token, **k: seen.update(token=token, **k))
    client.get("/ask", params={"text": "metar Chennai"}, headers={"Authorization": "Bearer t"})
    assert seen["token"] == "t"
    assert (seen["intent"], seen["city"]) == ("aviation", "chennai")
    assert seen["response"].startswith("Snapshot")


def test_a_history_failure_does_not_break_the_aviation_answer(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(history, "record", _boom)
    r = client.get("/ask", params={"text": "metar Chennai"}, headers={"Authorization": "Bearer t"})
    assert r.status_code == 200 and r.json()["intent"] == "aviation"
