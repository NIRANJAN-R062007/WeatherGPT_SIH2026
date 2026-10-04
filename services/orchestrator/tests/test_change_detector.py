"""WIE-10: weather_intelligence.change_detector — what moved between two
retrievals of the same forecast hours. Pure functions, no I/O."""

import forecast_snapshots
from weather_intelligence import change_detector, rules


def _hour(local_time, *, rain=30, temp=28.0, wind=10.0):
    return {
        "time_iso": f"2026-10-04T{local_time}:00Z",
        "local_time": local_time,
        "rain_probability_pct": rain,
        "temp_c": temp,
        "wind_kmh": wind,
    }


def _baseline(hours, retrieved_at="2026-10-04T06:00:00+00:00"):
    return {
        "retrieved_at": retrieved_at,
        "hours": {forecast_snapshots.normalize_time(h["time_iso"]): h for h in hours},
    }


def test_a_significant_rain_rise_is_reported_with_both_values():
    old = [_hour("14:00", rain=30), _hour("15:00", rain=30), _hour("16:00", rain=30)]
    new = [_hour("14:00", rain=70), _hour("15:00", rain=65), _hour("16:00", rain=30)]
    out = change_detector.detect_changes(new, _baseline(old))
    assert out["status"] == "ok" and out["compared_hours"] == 3
    (change,) = out["changes"]
    assert change["metric"] == "rain_probability_pct" and change["direction"] == "rose"
    assert (change["from"], change["to"], change["delta"]) == (30, 70, 40)
    assert (change["start_local"], change["end_local"], change["hours_changed"]) == (
        "14:00", "15:00", 2)


def test_a_change_below_the_threshold_is_not_reported():
    threshold = rules.CHANGE_THRESHOLDS["rain_probability_pct"]
    old = [_hour("14:00", rain=30)]
    new = [_hour("14:00", rain=30 + threshold - 1)]
    out = change_detector.detect_changes(new, _baseline(old))
    assert out["status"] == "no_significant_change" and out["changes"] == []
    assert out["compared_hours"] == 1


def test_a_change_exactly_on_the_threshold_is_reported():
    threshold = rules.CHANGE_THRESHOLDS["rain_probability_pct"]
    out = change_detector.detect_changes(
        [_hour("14:00", rain=30 + threshold)], _baseline([_hour("14:00", rain=30)]))
    assert out["status"] == "ok"


def test_no_earlier_snapshot_is_never_reported_as_no_change():
    out = change_detector.detect_changes([_hour("14:00")], None)
    assert out["status"] == "no_baseline" and out["changes"] == []
    assert out["status"] != "no_significant_change"


def test_a_baseline_with_no_shared_hours_is_no_baseline():
    old = [{**_hour("14:00"), "time_iso": "2026-10-03T14:00:00Z"}]
    out = change_detector.detect_changes([_hour("14:00", rain=90)], _baseline(old))
    assert out["status"] == "no_baseline" and out["compared_hours"] == 0


def test_hours_missing_a_figure_are_skipped_not_invented():
    old = [{**_hour("14:00"), "rain_probability_pct": None}]
    new = [_hour("14:00", rain=90)]
    out = change_detector.detect_changes(new, _baseline(old))
    assert out["status"] == "no_significant_change"


def test_temperature_and_wind_changes_are_reported_independently():
    old = [_hour("09:00", temp=26.0, wind=8.0)]
    new = [_hour("09:00", temp=31.5, wind=8.0)]
    (change,) = change_detector.detect_changes(new, _baseline(old))["changes"]
    assert change["metric"] == "temp_c" and change["delta"] == 5.5
    new = [_hour("09:00", temp=26.0, wind=24.0)]
    (change,) = change_detector.detect_changes(new, _baseline(old))["changes"]
    assert change["metric"] == "wind_kmh" and change["direction"] == "rose"


def test_a_fall_is_reported_as_fell_and_the_peak_hour_is_the_headline():
    old = [_hour("10:00", rain=80), _hour("11:00", rain=60)]
    new = [_hour("10:00", rain=20), _hour("11:00", rain=35)]
    (change,) = change_detector.detect_changes(new, _baseline(old))["changes"]
    assert change["direction"] == "fell"
    assert (change["from"], change["to"], change["peak_local"]) == (80, 20, "10:00")


def test_matching_ignores_how_the_timestamp_is_written():
    """A live payload says "...Z"; Postgres hands back an aware datetime."""
    old = [_hour("14:00", rain=30)]
    base = {"retrieved_at": "2026-10-04T06:00:00+00:00",
            "hours": {"2026-10-04T14:00:00+00:00": old[0]}}
    out = change_detector.detect_changes([_hour("14:00", rain=70)], base)
    assert out["status"] == "ok"
