"""rules.is_suitable_hour + window_analyzer.find_best_window (plan.md §8
Phase 9, WIE-2/WIE-3). Synthetic hourly dicts — shaped exactly like
weather_data.hourly_facts()'s `hours` entries — so every boundary and gap
case is exact and doesn't depend on what a fixture happens to contain.
"""

from weather_intelligence import rules
from weather_intelligence.window_analyzer import find_best_window


def hour(local_time, *, rain=10, temp=26, wind=10, condition="clear"):
    return {
        "time_iso": f"2026-10-01T{local_time}:00Z",
        "local_time": local_time,
        "rain_probability_pct": rain,
        "temp_c": temp,
        "wind_kmh": wind,
        "condition": condition,
    }


# --- WIE-2: is_suitable_hour boundaries -------------------------------------


def test_suitable_hour_passes_well_inside_thresholds():
    assert rules.is_suitable_hour(hour("09:00", rain=10, temp=26, wind=10)) is True


def test_rain_exactly_at_threshold_fails():
    # rules.py: rain < 20, so rain == 20 fails.
    assert rules.is_suitable_hour(hour("09:00", rain=20)) is False


def test_rain_just_under_threshold_passes():
    assert rules.is_suitable_hour(hour("09:00", rain=19)) is True


def test_temp_exactly_at_each_bound_passes():
    # rules.py: min_temp_c <= temp <= max_temp_c, so both 20 and 32 pass.
    assert rules.is_suitable_hour(hour("09:00", temp=20)) is True
    assert rules.is_suitable_hour(hour("09:00", temp=32)) is True


def test_temp_just_outside_each_bound_fails():
    assert rules.is_suitable_hour(hour("09:00", temp=19.9)) is False
    assert rules.is_suitable_hour(hour("09:00", temp=32.1)) is False


def test_wind_exactly_at_threshold_fails():
    # rules.py: wind < 25, so wind == 25 fails.
    assert rules.is_suitable_hour(hour("09:00", wind=25)) is False


def test_wind_just_under_threshold_passes():
    assert rules.is_suitable_hour(hour("09:00", wind=24.9)) is True


def test_missing_figure_never_passes():
    h = hour("09:00")
    del h["wind_kmh"]
    assert rules.is_suitable_hour(h) is False


def test_unknown_activity_falls_back_to_outdoor():
    assert rules.thresholds_for("skydiving") == rules.OUTDOOR
    assert rules.thresholds_for(None) == rules.OUTDOOR


def test_wie7_persona_activities_match_outdoor_today():
    # farm (farmer) and travel (traveller) start out identical to outdoor —
    # no persona-specific thresholds have been agreed yet (weather_intelligence
    # /persona_advisor.py's docstring), so the same hour passes or fails the
    # same way under every one of them.
    assert rules.thresholds_for("farm") == rules.OUTDOOR
    assert rules.thresholds_for("travel") == rules.OUTDOOR


# --- WIE-3: find_best_window -------------------------------------------------


def test_clear_window_is_returned_with_justifying_values():
    hours = [
        hour("08:00", rain=40, temp=26, wind=10),  # unsuitable: rain too high
        hour("09:00", rain=10, temp=24, wind=8),
        hour("10:00", rain=15, temp=28, wind=12),
        hour("11:00", rain=5, temp=30, wind=6),
        hour("12:00", rain=50, temp=26, wind=10),  # unsuitable: rain too high
    ]
    window = find_best_window(hours)
    assert window is not None
    assert window["start_local"] == "09:00"
    assert window["end_local"] == "11:00"
    assert window["max_rain_probability_pct"] == 15
    assert window["max_wind_kmh"] == 12
    assert window["avg_temp_c"] == round((24 + 28 + 30) / 3, 1)
    assert [h["local_time"] for h in window["hours"]] == ["09:00", "10:00", "11:00"]


def test_split_day_picks_the_longer_run():
    hours = [
        hour("06:00", rain=10, temp=26, wind=10),  # suitable, lone hour
        hour("07:00", rain=60, temp=26, wind=10),  # breaks it
        hour("14:00", rain=10, temp=26, wind=10),  # suitable, 3-hour run
        hour("15:00", rain=10, temp=26, wind=10),
        hour("16:00", rain=10, temp=26, wind=10),
    ]
    window = find_best_window(hours)
    assert window is not None
    assert (window["start_local"], window["end_local"]) == ("14:00", "16:00")


def test_fully_unsuitable_day_returns_none_not_the_least_bad_hour():
    hours = [hour("09:00", rain=90, temp=40, wind=50), hour("10:00", rain=90, temp=40, wind=50)]
    assert find_best_window(hours) is None


def test_empty_hours_returns_none():
    assert find_best_window([]) is None


def test_window_never_spans_a_missing_hour():
    # 09:00 and 11:00 are both suitable, but 10:00 is absent from the list
    # entirely (not just unsuitable) — the run must not bridge the gap.
    hours = [hour("09:00", rain=10, temp=26, wind=10), hour("11:00", rain=10, temp=26, wind=10)]
    window = find_best_window(hours)
    assert window is not None
    # Both hours are length-1 runs; the earlier one wins the tie.
    assert window["start_local"] == window["end_local"] == "09:00"


def test_a_tied_length_run_keeps_the_earliest():
    hours = [
        hour("06:00", rain=10, temp=26, wind=10),
        hour("07:00", rain=10, temp=26, wind=10),
        hour("08:00", rain=90, temp=26, wind=10),  # break
        hour("14:00", rain=10, temp=26, wind=10),
        hour("15:00", rain=10, temp=26, wind=10),
    ]
    window = find_best_window(hours)
    assert window is not None
    assert (window["start_local"], window["end_local"]) == ("06:00", "07:00")
