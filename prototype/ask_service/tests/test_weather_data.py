"""weather_data.get_weather() dispatches on intent + day and returns a flat facts
dict of exactly the keys an answer may quote. Runs on the committed fixtures.
"""

import pytest
import weather_data

CURRENT_KEYS = {"condition", "temp_c", "feels_like_c", "humidity_pct",
                "wind_kmh", "wind_dir", "source", "issued", "is_live"}
FORECAST_KEYS = {"condition", "rain_probability_pct", "high_c", "low_c",
                 "day", "source", "issued", "is_live"}


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
    assert (rain["rain_probability_pct"], rain["high_c"], rain["low_c"]) == (20, 33.6, 28)


def test_day_selection():
    def rain(day):
        return weather_data.get_weather("chennai", "will_it_rain", day)["rain_probability_pct"]

    assert rain("today") == 30
    assert rain("tomorrow") == 20
    assert rain("tonight") == 45


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
    assert weather_data.get_weather("mumbai") is None
    assert weather_data.get_weather("") is None
    assert weather_data.get_weather(None) is None
