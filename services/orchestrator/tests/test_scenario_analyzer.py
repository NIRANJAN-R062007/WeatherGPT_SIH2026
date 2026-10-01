"""scenario_analyzer.compare_scenario (plan.md §8 Phase 9, WIE-6)."""

from weather_intelligence.scenario_analyzer import compare_scenario


def hour(local_time, *, rain=10, temp=26, wind=10, condition="clear"):
    return {
        "time_iso": f"2026-10-01T{local_time}:00Z",
        "local_time": local_time,
        "rain_probability_pct": rain,
        "temp_c": temp,
        "wind_kmh": wind,
        "condition": condition,
    }


HOURS = [
    hour("09:00", rain=10, temp=24, wind=8),
    hour("17:00", rain=40, temp=33, wind=20, condition="rain"),
]


def test_nine_am_vs_five_pm_names_the_lower_rain_chance():
    result = compare_scenario(HOURS, ["09:00", "17:00"])
    by_time = {r["time"]: r for r in result["hours"]}
    assert by_time["09:00"]["available"] is True
    assert by_time["09:00"]["temp_c"] == 24
    assert by_time["09:00"]["rain_probability_pct"] == 10
    assert by_time["09:00"]["suitable"] is True
    assert by_time["17:00"]["available"] is True
    assert by_time["17:00"]["suitable"] is False
    assert result["better_time"] == "09:00"


def test_an_hour_outside_the_forecast_range_is_not_available_no_invented_values():
    result = compare_scenario(HOURS, ["03:00"])
    assert result["hours"] == [{"time": "03:00", "available": False}]
    assert result["better_time"] is None


def test_a_single_time_has_no_better_time():
    result = compare_scenario(HOURS, ["09:00"])
    assert result["better_time"] is None


def test_an_exact_tie_names_no_winner():
    tied = [hour("09:00", rain=10), hour("17:00", rain=10)]
    result = compare_scenario(tied, ["09:00", "17:00"])
    assert result["better_time"] is None


def test_both_times_unavailable_is_not_an_error():
    result = compare_scenario(HOURS, ["01:00", "02:00"])
    assert result["hours"] == [
        {"time": "01:00", "available": False},
        {"time": "02:00", "available": False},
    ]
    assert result["better_time"] is None
