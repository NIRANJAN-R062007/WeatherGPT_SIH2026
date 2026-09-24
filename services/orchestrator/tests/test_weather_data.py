"""weather_data.get_weather() dispatches on intent + day and returns a flat facts
dict of exactly the keys an answer may quote. Runs on the committed fixtures.
"""

import copy
import re
from datetime import datetime, timezone

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
    assert weather_data.get_weather("kolkata") is None
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
