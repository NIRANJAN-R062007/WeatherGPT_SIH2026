"""GET /forecast/daily, GET /forecast/hourly, /facts' `rain_so_far` and
GET /hotlines: the figures behind the apps' day list, hourly strip, rain
tile and emergency numbers. Runs on the committed fixtures (5 days, 24 hours)
except where a test stubs the snapshot.
"""

import copy
import json
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import cities
import google_weather
import hotlines
import main
import pytest
import weather_data
from config import DATA_DIR
from fastapi.testclient import TestClient

client = TestClient(main.app)


def _fixture_payload(kind, city):
    path = DATA_DIR / "fixtures" / "google_weather" / f"{kind}.{city}.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


# --- GET /forecast/daily -------------------------------------------------


def test_daily_serves_every_snapshotted_day_with_figures_and_sun_events():
    body = client.get("/forecast/daily", params={"city": "Chennai"}).json()
    assert body["city"] == "chennai" and body["status"] == "ok"
    days = body["days"]
    assert len(days) == google_weather.FORECAST_DAYS  # what the fixture holds
    assert [d["label"] for d in days[:2]] == ["today", "tomorrow"]
    dates = [date.fromisoformat(d["date"]) for d in days]
    assert all((b - a).days == 1 for a, b in zip(dates, dates[1:]))
    for d in days:
        for key in ("condition", "condition_label", "high_c", "low_c", "rain_probability_pct",
                    "sunrise", "sunset"):
            assert key in d, (d["label"], key)
        assert d["low_c"] <= d["high_c"]
        assert datetime.fromisoformat(d["sunrise"][:19]) < datetime.fromisoformat(d["sunset"][:19])
    assert body["provenance"]["is_live"] is False
    assert "not live" in body["provenance"]["source"]


def test_daily_rain_mm_is_day_plus_night():
    raw = _fixture_payload("forecast_days", "chennai")["forecastDays"][0]
    expected = round(raw["daytimeForecast"]["precipitation"]["qpf"]["quantity"]
                     + raw["nighttimeForecast"]["precipitation"]["qpf"]["quantity"], 2)
    day = client.get("/forecast/daily", params={"city": "chennai"}).json()["days"][0]
    assert day["rain_mm"] == expected


def test_daily_labels_follow_lang_but_keys_do_not():
    en = client.get("/forecast/daily", params={"city": "madurai"}).json()["days"][0]
    ta = client.get("/forecast/daily", params={"city": "madurai", "lang": "ta"}).json()["days"][0]
    assert ta["condition"] == en["condition"]
    assert ta["condition_label"] != en["condition_label"]


def _daily(**params):
    return client.get("/forecast/daily", params={"city": "chennai", **params})


def _hourly(**params):
    return client.get("/forecast/hourly", params={"city": "chennai", **params})


def test_daily_days_param_trims_and_is_bounded():
    assert len(_daily(days=3).json()["days"]) == 3
    for bad in (0, google_weather.FORECAST_DAYS_FETCHED + 1):
        assert _daily(days=bad).status_code == 422


def test_daily_unknown_city_is_404_and_bad_lang_422():
    assert _daily(city="narnia").status_code == 404
    assert _daily(lang="zz").status_code == 422


def test_daily_with_no_forecast_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "daily_forecast", lambda key, days: None)
    body = client.get("/forecast/daily", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable" and body["days"] == [] and body["provenance"] is None


def test_daily_live_fetch_asks_for_ten_days_in_one_page(monkeypatch):
    monkeypatch.setattr(google_weather.config, "GOOGLE_WEATHER_API_KEY", "test-key")
    params = google_weather._params("forecast_days", "chennai")
    assert params["days"] == params["pageSize"] == google_weather.FORECAST_DAYS_FETCHED == 10


def test_daily_serves_all_ten_days_of_a_ten_day_feed(monkeypatch):
    payload = copy.deepcopy(_fixture_payload("forecast_days", "chennai"))
    payload["forecastDays"] = (payload["forecastDays"] * 2)[:10]
    snap = google_weather.Snapshot("forecast_days", "chennai", payload, True,
                                   "2026-10-03T00:00:00+00:00", "Google Weather API (live)")
    monkeypatch.setattr(google_weather, "snapshot", lambda kind, key, **kw: snap)
    body = client.get("/forecast/daily", params={"city": "chennai"}).json()
    assert len(body["days"]) == 10 and body["provenance"]["is_live"] is True


def test_daily_skips_fields_a_day_lacks(monkeypatch):
    payload = copy.deepcopy(_fixture_payload("forecast_days", "chennai"))
    first = payload["forecastDays"][0]
    for field in ("nighttimeForecast", "sunEvents", "maxTemperature"):
        first.pop(field)
    snap = google_weather.Snapshot("forecast_days", "chennai", payload, False, "x", "fixture")
    monkeypatch.setattr(google_weather, "snapshot", lambda kind, key, **kw: snap)
    day = weather_data.daily_forecast("chennai", 5)["days"][0]
    for gone in ("night_condition", "sunrise", "sunset", "high_c"):
        assert gone not in day
    assert day["rain_mm"] == first["daytimeForecast"]["precipitation"]["qpf"]["quantity"]


# --- GET /forecast/hourly ------------------------------------------------


def test_hourly_serves_the_next_24_hours_across_midnight():
    body = client.get("/forecast/hourly", params={"city": "chennai"}).json()
    assert body["status"] == "ok"
    hours = body["hours"]
    assert len(hours) == google_weather.FORECAST_HOURS
    assert len({h["date"] for h in hours}) == 2  # the strip runs on past midnight
    for h in hours:
        assert re.fullmatch(r"\d\d:\d\d", h["local_time"])
        for key in ("temp_c", "rain_probability_pct", "condition", "condition_label", "is_daytime"):
            assert key in h, (h["local_time"], key)
    assert body["provenance"]["issued"] == hours[0]["time_iso"]


def test_hourly_hours_param_trims_and_is_bounded():
    assert len(_hourly(hours=6).json()["hours"]) == 6
    for bad in (0, google_weather.FORECAST_HOURS + 1):
        assert _hourly(hours=bad).status_code == 422
    assert _hourly(city="narnia").status_code == 404


def test_hourly_live_series_drops_hours_that_have_ended(monkeypatch):
    payload = _fixture_payload("forecast_hours", "chennai")
    snap = google_weather.Snapshot("forecast_hours", "chennai", payload, True, "x", "live")
    monkeypatch.setattr(google_weather, "snapshot", lambda kind, key, **kw: snap)
    third_end = payload["forecastHours"][2]["interval"]["endTime"]
    now = datetime.fromisoformat(third_end.replace("Z", "+00:00"))
    data = weather_data.hourly_forecast("chennai", 24, now=now)
    assert data["hours"][0]["time_iso"] == payload["forecastHours"][3]["interval"]["startTime"]
    assert len(data["hours"]) == len(payload["forecastHours"]) - 3


def test_hourly_fixture_keeps_its_first_hour_however_old():
    payload = _fixture_payload("forecast_hours", "chennai")
    later = datetime(2030, 1, 1, tzinfo=timezone.utc)
    data = weather_data.hourly_forecast("chennai", 24, now=later)
    assert data["hours"][0]["time_iso"] == payload["forecastHours"][0]["interval"]["startTime"]


def test_hourly_with_no_series_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "hourly_forecast", lambda key, hours: None)
    body = client.get("/forecast/hourly", params={"city": "chennai"}).json()
    assert body["status"] == "unavailable" and body["hours"] == [] and body["provenance"] is None


# --- /facts rain_so_far --------------------------------------------------


def test_current_facts_carry_rain_so_far_beside_the_grounded_facts():
    body = client.get("/facts", params={"city": "chennai"}).json()
    rain = body["rain_so_far"]
    assert "rain_so_far_mm" in rain and "since" in rain and "rain_category" in rain
    assert "rain_so_far_mm" not in body["facts"]  # /ask's guardrail facts are unchanged


def test_forecast_facts_have_no_rain_so_far():
    body = client.get("/facts", params={"city": "chennai", "intent": "will_it_rain"}).json()
    assert "rain_so_far" not in body


def test_rain_so_far_falls_back_to_the_24h_total(monkeypatch):
    orig = google_weather.snapshot
    def no_history(kind, key, **kw):
        return None if kind == "history_hours" else orig(kind, key, **kw)

    monkeypatch.setattr(google_weather, "snapshot", no_history)
    rain = client.get("/facts", params={"city": "chennai"}).json()["rain_so_far"]
    assert "rain_last_24h_mm" in rain and "rain_so_far_mm" not in rain


def test_a_malformed_history_series_costs_only_the_rain_tile(monkeypatch):
    def broken(key, **kw):
        raise KeyError("interval")

    monkeypatch.setattr(weather_data, "rain_so_far", broken)
    body = client.get("/facts", params={"city": "chennai"}).json()
    assert "facts" in body and "rain_so_far" not in body


# --- GET /hotlines -------------------------------------------------------

_OFFICIAL = (".gov.in", ".nic.in")


def _all_entries():
    data = json.loads((DATA_DIR / "hotlines.json").read_text(encoding="utf-8"))
    yield from data["national"]
    for entries in data["regions"].values():
        yield from entries
    for entries in data["cities"].values():
        yield from entries


def test_every_hotline_cites_an_official_page_that_shows_the_number():
    for e in _all_entries():
        url = urlparse(e["source_url"])
        assert url.scheme == "https" and url.hostname.endswith(_OFFICIAL), e["source_url"]
        # An STD code ("040 ...") is part of dialling it, not of how pages print it.
        parts = e["number"].split(" ")
        if len(parts) > 1 and parts[0].startswith("0"):
            parts = parts[1:]
        local = "".join(parts)
        assert local in re.sub(r"\D", "", e["source_quote"]), e
        assert e["scope"] in ("national", "state", "district", "city")
        assert e["name"] and e["note"]


def test_hotline_keys_match_the_city_registry():
    data = json.loads((DATA_DIR / "hotlines.json").read_text(encoding="utf-8"))
    regions = {c.region["en"] for c in cities.CITIES.values()}
    assert set(data["regions"]) <= regions
    assert set(data["cities"]) <= cities.CITY_KEYS
    date.fromisoformat(data["checked"])


@pytest.mark.parametrize("key", sorted(cities.CITY_KEYS))
def test_every_city_gets_112_first_and_a_local_line(key):
    body = client.get("/hotlines", params={"city": key}).json()
    lines = body["hotlines"]
    assert lines[0]["dial"] == "112"
    assert len(lines) >= 2, f"{key} has no state, district or city line"
    assert all(line["dial"].isdigit() for line in lines)
    assert len({line["dial"] for line in lines}) == len(lines)
    assert body["checked"] == hotlines.CHECKED


def test_hotlines_dial_strips_the_spaces():
    lines = client.get("/hotlines", params={"city": "hyderabad"}).json()["hotlines"]
    ghmc = next(line for line in lines if line["name"] == "GHMC helpline")
    assert (ghmc["number"], ghmc["dial"]) == ("040 2111 1111", "04021111111")


def test_hotlines_unknown_city_is_404_and_bad_lang_422():
    assert client.get("/hotlines", params={"city": "narnia"}).status_code == 404
    assert client.get("/hotlines", params={"city": "chennai", "lang": "zz"}).status_code == 422
