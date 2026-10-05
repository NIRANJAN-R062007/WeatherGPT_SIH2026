"""weather_data.get_weather() dispatches on intent + day and returns a flat facts
dict of exactly the keys an answer may quote. Runs on the committed fixtures.
"""

import copy
import re
from datetime import datetime, timedelta, timezone

import google_weather
import pytest
import weather_data

CURRENT_KEYS = {"condition", "temp_c", "feels_like_c", "humidity_pct",
                "wind_kmh", "wind_dir", "uv_index", "uv_band", "source", "issued", "is_live"}
FORECAST_KEYS = {"condition", "rain_probability_pct", "high_c", "low_c",
                 "day", "source", "issued", "is_live"}
RAIN_SO_FAR_KEYS = {"source", "is_live", "issued", "since", "rain_so_far_mm", "rain_category",
                     "hours_counted", "condition"}
RAIN_LAST_24H_KEYS = {"source", "is_live", "issued", "rain_last_24h_mm", "rain_category",
                       "hours_counted", "condition"}
DAY_KEYS = {"today", "tomorrow", *weather_data._WEEKDAYS, weather_data._LATER}


def _patch_forecast(monkeypatch, mutate):
    """Serve the fixture forecast with `mutate(forecastDays)` applied to a copy."""
    orig = google_weather.snapshot

    def _snapshot(kind, city_key, **kw):
        snap = orig(kind, city_key, **kw)
        if kind == "forecast_days":
            payload = copy.deepcopy(snap.payload)
            mutate(payload["forecastDays"])
            return google_weather.Snapshot(snap.kind, snap.city, payload,
                                           snap.is_live, snap.retrieved_at, snap.source)
        return snap

    monkeypatch.setattr(google_weather, "snapshot", _snapshot)


def _break_display_date(days):
    for entry in days[2:]:
        entry["displayDate"] = {"year": "2026", "month": None}  # wrong types, no day


def _break_display_date_and_start(days):
    _break_display_date(days)
    for entry in days[2:]:
        entry["interval"] = {"startTime": 20260916}  # not a timestamp string either


@pytest.mark.parametrize("city", ["chennai", "madurai", "coimbatore"])
def test_current_facts_key_set(city):
    facts = weather_data.get_weather(city, "current_weather", "today")
    assert set(facts) == CURRENT_KEYS
    assert facts["is_live"] is False


@pytest.mark.parametrize("city", ["chennai", "madurai", "coimbatore"])
def test_forecast_facts_key_set(city):
    facts = weather_data.get_weather(city, "will_it_rain", "tomorrow")
    assert set(facts) == FORECAST_KEYS


def test_values_match_fixtures():
    cur = weather_data.get_weather("chennai")
    assert (cur["temp_c"], cur["feels_like_c"], cur["humidity_pct"],
            cur["wind_kmh"], cur["wind_dir"]) == (28, 32.5, 81, 16, "SSW")
    rain = weather_data.get_weather("chennai", "will_it_rain", "tomorrow")
    assert (rain["rain_probability_pct"], rain["high_c"], rain["low_c"]) == (5, 32.6, 26.7)


def test_day_selection():
    def rain(day):
        return weather_data.get_weather("chennai", "will_it_rain", day)["rain_probability_pct"]

    assert rain("today") == 25
    assert rain("tomorrow") == 5
    assert rain("tonight") == 0


def test_weather_tomorrow_routes_to_forecast():
    facts = weather_data.get_weather("chennai", "current_weather", "tomorrow")
    assert "high_c" in facts and "temp_c" not in facts  # forecast shape, not current


def test_forecast_index_clamps(monkeypatch):
    import google_weather
    orig = google_weather.snapshot

    def _one_day(kind, city_key, **kw):
        snap = orig(kind, city_key, **kw)
        if kind == "forecast_days":
            trimmed = dict(snap.payload)
            trimmed["forecastDays"] = trimmed["forecastDays"][:1]
            return google_weather.Snapshot(snap.kind, snap.city, trimmed,
                                           snap.is_live, snap.retrieved_at, snap.source)
        return snap

    monkeypatch.setattr(google_weather, "snapshot", _one_day)
    facts = weather_data.get_weather("chennai", "will_it_rain", "tomorrow")
    assert facts is not None  # clamped to index 0, no IndexError


def test_missing_nested_field_omits_key(monkeypatch):
    import google_weather
    orig = google_weather.snapshot

    def _strip_wind(kind, city_key, **kw):
        snap = orig(kind, city_key, **kw)
        if kind == "current_conditions":
            payload = {k: v for k, v in snap.payload.items() if k != "wind"}
            return google_weather.Snapshot(snap.kind, snap.city, payload,
                                           snap.is_live, snap.retrieved_at, snap.source)
        return snap

    monkeypatch.setattr(google_weather, "snapshot", _strip_wind)
    facts = weather_data.get_weather("chennai")
    assert "wind_kmh" not in facts and "wind_dir" not in facts
    assert "temp_c" in facts  # the rest still there


def test_no_args_returns_current():
    assert set(weather_data.get_weather("chennai")) == CURRENT_KEYS


def test_unknown_city():
    assert weather_data.get_weather("patna") is None
    assert weather_data.get_weather("") is None
    assert weather_data.get_weather(None) is None


@pytest.mark.parametrize("city", ["chennai", "madurai", "coimbatore"])
def test_rain_so_far_key_set(city):
    import config

    path = config.FIXTURES_DIR / "google_weather" / f"history_hours.{city}.json"
    if not path.exists():
        pytest.skip(f"history_hours fixture not present for {city}")
    facts = weather_data.rain_so_far(city)
    assert set(facts) == RAIN_SO_FAR_KEYS


def test_rain_so_far_sum_agrees_with_manual_computation():
    import json
    import re

    import config

    path = config.FIXTURES_DIR / "google_weather" / "history_hours.chennai.json"
    if not path.exists():
        pytest.skip("history_hours fixture not present")
    hours = json.loads(path.read_text())["response"]["historyHours"]

    def parse(s):
        return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", s))

    now = max(parse(h["interval"]["endTime"]) for h in hours)
    from zoneinfo import ZoneInfo
    midnight = now.astimezone(ZoneInfo("Asia/Kolkata")).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    expected_total = 0.0
    expected_count = 0
    for h in hours:
        start = parse(h["interval"]["startTime"])
        if midnight <= start < now:
            qty = h["precipitation"]["qpf"]["quantity"]
            expected_total += qty
            expected_count += 1

    facts = weather_data.rain_so_far("chennai")
    assert facts["rain_so_far_mm"] == round(expected_total, 2)
    assert facts["hours_counted"] == expected_count


def test_rain_so_far_midnight_boundary_with_synthetic_payload(monkeypatch):
    import google_weather

    hours = [
        {"interval": {"startTime": "2026-09-10T17:00:00Z", "endTime": "2026-09-10T18:00:00Z"},
         "precipitation": {"qpf": {"quantity": 100}}, "weatherCondition": {"type": "CLOUDY"}},
        {"interval": {"startTime": "2026-09-10T18:00:00Z", "endTime": "2026-09-10T19:00:00Z"},
         "precipitation": {"qpf": {"quantity": 50}}, "weatherCondition": {"type": "CLOUDY"}},
        {"interval": {"startTime": "2026-09-10T18:30:00Z", "endTime": "2026-09-10T19:30:00Z"},
         "precipitation": {"qpf": {"quantity": 5}}, "weatherCondition": {"type": "CLOUDY"}},
        {"interval": {"startTime": "2026-09-11T04:30:00Z", "endTime": "2026-09-11T05:30:00Z"},
         "precipitation": {"qpf": {"quantity": 3}}, "weatherCondition": {"type": "CLOUDY"}},
    ]
    fake = google_weather.Snapshot(
        kind="history_hours", city="chennai", payload={"historyHours": hours},
        is_live=False, retrieved_at="2026-09-11T05:30:00Z", source="fake",
    )

    def _snapshot(kind, city_key, **kw):
        return fake if kind == "history_hours" else None

    monkeypatch.setattr(google_weather, "snapshot", _snapshot)
    now = datetime(2026, 9, 11, 5, 30, tzinfo=timezone.utc)
    facts = weather_data.rain_so_far("chennai", now=now)
    assert facts["rain_so_far_mm"] == 8  # the 18:00Z hour (before midnight 18:30Z) is excluded
    assert facts["hours_counted"] == 2


def test_rain_so_far_falls_back_to_24h_qpf_when_history_none(monkeypatch):
    import google_weather

    orig = google_weather.snapshot

    def _no_history(kind, city_key, **kw):
        return None if kind == "history_hours" else orig(kind, city_key, **kw)

    monkeypatch.setattr(google_weather, "snapshot", _no_history)
    facts = weather_data.rain_so_far("chennai")
    assert set(facts) == RAIN_LAST_24H_KEYS
    assert facts["hours_counted"] == 24


def test_multi_day_facts_caps_at_available_days():
    from google_weather import FORECAST_DAYS

    facts = weather_data.multi_day_facts("chennai", 7)
    assert facts["days_requested"] == 7
    assert facts["days_counted"] == FORECAST_DAYS
    assert len(facts["days"]) == FORECAST_DAYS
    assert facts["days"][0]["label"] == "today"
    assert facts["days"][1]["label"] == "tomorrow"


def test_forecast_day_strict_none_beyond_range():
    from google_weather import FORECAST_DAYS

    assert weather_data.forecast_day("chennai", 0) is not None
    # only FORECAST_DAYS days in the fixture; STRICT, no clamping
    assert weather_data.forecast_day("chennai", FORECAST_DAYS) is None


# --- day labels: canonical keys, never a bare number (audit 2.1 / 2.2) ---

def test_day_labels_are_canonical_keys_with_weekdays_from_display_date():
    facts = weather_data.multi_day_facts("chennai", 5)
    days = google_weather.snapshot("forecast_days", "chennai").payload["forecastDays"]
    for i, day in enumerate(facts["days"][2:], start=2):
        d = days[i]["displayDate"]
        expected = weather_data._WEEKDAYS[datetime(d["year"], d["month"], d["day"]).weekday()]
        assert day["label"] == expected
    assert {d["label"] for d in facts["days"]} <= DAY_KEYS


def test_malformed_display_date_falls_back_to_start_time_in_city_time(monkeypatch):
    def _mutate(days):
        _break_display_date(days)
        # 18:30Z is already 00:00 IST the next day: Wednesday 16 Sep in Chennai,
        # still Tuesday in UTC — the weekday must be read in the city's timezone.
        days[2]["interval"]["startTime"] = "2026-09-15T18:30:00Z"

    _patch_forecast(monkeypatch, _mutate)
    labels = [d["label"] for d in weather_data.multi_day_facts("chennai", 5)["days"]]
    assert labels[2] == "wednesday"
    assert all(label in weather_data._WEEKDAYS for label in labels[2:])
    assert not any(re.search(r"\d", label) for label in labels)


def test_unreadable_date_emits_generic_key_not_a_number(monkeypatch):
    _patch_forecast(monkeypatch, _break_display_date_and_start)
    facts = weather_data.multi_day_facts("chennai", 5)
    labels = [d["label"] for d in facts["days"]]
    assert labels[:2] == ["today", "tomorrow"]
    assert labels[2:] == [weather_data._LATER] * 3
    assert not any(re.search(r"\d", label) for label in labels)  # no "day3" to trip the guardrail


@pytest.mark.parametrize("mutate", [_break_display_date, _break_display_date_and_start])
def test_forecast_day_label_has_no_digit_with_malformed_display_date(monkeypatch, mutate):
    _patch_forecast(monkeypatch, mutate)
    for offset in (3, 4):
        day = weather_data.forecast_day("chennai", offset)["day"]
        assert day in DAY_KEYS and not re.search(r"\d", day)


# --- hourly_facts (plan.md §8 Phase 9, WIE-1) -------------------------------

HOURLY_KEYS = {"time_iso", "local_time", "temp_c", "rain_probability_pct", "wind_kmh", "condition"}


@pytest.mark.parametrize("city", ["chennai", "madurai", "coimbatore"])
def test_hourly_facts_key_set_and_local_time_format(city):
    facts = weather_data.hourly_facts(city, "today")
    assert facts is not None
    assert facts["day"] == "today"
    assert facts["hours"], "every demo city's committed fixture has at least one hour"
    for hour in facts["hours"]:
        assert HOURLY_KEYS <= hour.keys()
        assert re.fullmatch(r"\d{2}:\d{2}", hour["local_time"])


def test_hourly_facts_today_is_the_series_first_hour_regardless_of_real_date():
    # "today" is positional (the series' own first hour), like forecast_day's
    # offset 0 — not tied to the real wall-clock date, so fixture mode (whose
    # hourly series is a past snapshot) behaves the same as live.
    today = weather_data.hourly_facts("chennai", "today")
    # The first "today" hour must be the series' own first entry.
    snap = google_weather.snapshot("forecast_hours", "chennai")
    raw = snap.payload["forecastHours"]
    assert today["hours"][0]["time_iso"] == raw[0]["interval"]["startTime"]


def _serve_series(monkeypatch, start_utc: str, hours: int, *, live: bool = True):
    """hourly_facts reads a synthetic `hours`-long hourly series starting at `start_utc`
    (a test payload built here, not a committed fixture). Chennai is UTC+5:30, so
    "2026-10-05T04:30:00+00:00" is 10:00 there."""
    start = datetime.fromisoformat(start_utc)
    entries = []
    for i in range(hours):
        t = start + timedelta(hours=i)
        entries.append({
            "interval": {"startTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "endTime": (t + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "temperature": {"degrees": 28.0}, "precipitation": {"probability": {"percent": 10}},
            "wind": {"speed": {"value": 9.0}}, "weatherCondition": {"type": "CLEAR"},
        })
    snap = google_weather.Snapshot("forecast_hours", "chennai", {"forecastHours": entries}, live,
                                   start_utc, "test series")
    monkeypatch.setattr(google_weather, "snapshot",
                        lambda kind, key, **kw: snap if kind == "forecast_hours" else None)


def _clock_range(facts):
    times = [h["local_time"] for h in facts["hours"]]
    return times[0], times[-1], len(times)


def test_hourly_facts_never_presents_a_part_day_as_the_whole_day(monkeypatch):
    # Issue #65: 24 hours fetched at 10:00 end at 09:00 tomorrow, so "tomorrow" was
    # 00:00-09:00 and was judged as if it were the whole day.
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 24)
    assert _clock_range(weather_data.hourly_facts("chennai", "today")) == ("10:00", "23:00", 14)
    assert weather_data.hourly_facts("chennai", "tomorrow") is None
    assert weather_data.hourly_facts("chennai", "day_after_tomorrow") is None


def test_hourly_facts_tomorrow_is_the_whole_day_in_a_48_hour_series(monkeypatch):
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 48)
    assert _clock_range(weather_data.hourly_facts("chennai", "today")) == ("10:00", "23:00", 14)
    assert _clock_range(weather_data.hourly_facts("chennai", "tomorrow")) == ("00:00", "23:00", 24)
    assert weather_data.hourly_facts("chennai", "day_after_tomorrow") is None  # 00:00-09:00 only


@pytest.mark.parametrize("start_utc, today, tomorrow", [
    ("2026-10-04T18:30:00+00:00", ("00:00", "23:00", 24), ("00:00", "23:00", 24)),  # 00:00 IST
    ("2026-10-05T17:30:00+00:00", ("23:00", "23:00", 1), ("00:00", "23:00", 24)),   # 23:00 IST
    ("2026-10-05T05:00:00+00:00", ("10:30", "23:30", 14), ("00:30", "23:30", 24)),  # :30 hours
])
def test_hourly_facts_48_hours_cover_tomorrow_from_any_hour_of_the_day(
        monkeypatch, start_utc, today, tomorrow):
    _serve_series(monkeypatch, start_utc, 48)
    assert _clock_range(weather_data.hourly_facts("chennai", "today")) == today
    assert _clock_range(weather_data.hourly_facts("chennai", "tomorrow")) == tomorrow


def test_hourly_facts_a_day_whose_end_the_series_does_not_reach_is_unavailable(monkeypatch):
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 6)  # 10:00-15:00
    assert weather_data.hourly_facts("chennai", "today") is None
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 13)  # to 22:00, no 23:00 hour
    assert weather_data.hourly_facts("chennai", "today") is None
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 14)  # to 23:00: the day is whole
    assert _clock_range(weather_data.hourly_facts("chennai", "today")) == ("10:00", "23:00", 14)


def test_hourly_facts_of_the_committed_snapshots_is_never_a_part_day():
    # The snapshots hold 24 hours from one fetch, so today is the rest of the day and
    # tomorrow is unavailable until they are refreshed with 48 (snapshot_google_weather.py).
    # Whatever a refresh brings, a day is returned whole or not at all.
    for city in ("chennai", "madurai", "coimbatore"):
        assert weather_data.hourly_facts(city, "today") is not None
        for day in ("today", "tomorrow", "day_after_tomorrow"):
            facts = weather_data.hourly_facts(city, day)
            if facts is not None:
                assert facts["hours"][-1]["local_time"].startswith("23:"), (city, day)
                if day != "today":
                    assert facts["hours"][0]["local_time"].startswith("00:"), (city, day)


def test_hourly_facts_today_and_tomorrow_are_disjoint_calendar_days(monkeypatch):
    # Partitioned by LOCAL (Chennai) calendar date, not UTC — late UTC hours
    # are already the next local day at IST (+5:30), so the UTC date alone
    # isn't the right disjointness check.
    _serve_series(monkeypatch, "2026-10-05T04:30:00+00:00", 48)
    tz = weather_data._city_timezone("chennai")
    today = weather_data.hourly_facts("chennai", "today")
    tomorrow = weather_data.hourly_facts("chennai", "tomorrow")

    def _local_date(h):
        return weather_data._parse_ts(h["time_iso"]).astimezone(tz).date()

    today_dates = {_local_date(h) for h in today["hours"]}
    tomorrow_dates = {_local_date(h) for h in tomorrow["hours"]}
    assert today_dates.isdisjoint(tomorrow_dates)
    assert min(tomorrow_dates) == max(today_dates) + timedelta(days=1)


def test_hourly_facts_unknown_city_is_none():
    assert weather_data.hourly_facts("narnia", "today") is None


def test_hourly_facts_no_snapshot_is_none(monkeypatch):
    monkeypatch.setattr(google_weather, "snapshot", lambda kind, city_key, **kw: None)
    assert weather_data.hourly_facts("chennai", "today") is None


def test_hourly_facts_empty_forecast_hours_is_none(monkeypatch):
    orig = google_weather.snapshot

    def _snapshot(kind, city_key, **kw):
        snap = orig(kind, city_key, **kw)
        if kind == "forecast_hours":
            payload = copy.deepcopy(snap.payload)
            payload["forecastHours"] = []
            return google_weather.Snapshot(snap.kind, snap.city, payload,
                                           snap.is_live, snap.retrieved_at, snap.source)
        return snap

    monkeypatch.setattr(google_weather, "snapshot", _snapshot)
    assert weather_data.hourly_facts("chennai", "today") is None


def test_multi_day_facts_dates_each_day_in_city_time():
    """TFA-11 checks a crop's sowing months against these dates."""
    from datetime import date

    days = weather_data.multi_day_facts("madurai", 5)["days"]
    dates = [date.fromisoformat(d["date"]) for d in days]
    assert dates == [dates[0] + timedelta(days=i) for i in range(len(days))]
