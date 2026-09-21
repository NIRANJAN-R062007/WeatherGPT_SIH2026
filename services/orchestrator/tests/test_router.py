"""router.route(): the intent+time_window -> weather_data call table, and
narration_facts(): the parameter-scoped subset of facts sent to the prompt
(the guardrail always checks the FULL facts, never this trimmed dict).
"""

import router
import weather_data
from google_weather import FORECAST_DAYS
from nlu import ParsedQuery


def _pq(**kw) -> ParsedQuery:
    base = dict(intent="current_weather", city="chennai", time_window="today", days=None,
                parameter="general", language="en", source="rules", confidence=0.9)
    base.update(kw)
    return ParsedQuery(**base)


def test_current_weather_today():
    data = router.route(_pq(intent="current_weather", time_window="today"), "chennai")
    assert data is not None and "temp_c" in data


def test_current_weather_tonight_and_tomorrow():
    for tw in ("tonight", "tomorrow"):
        data = router.route(_pq(intent="current_weather", time_window=tw), "chennai")
        assert data is not None and "high_c" in data


def test_forecast_today():
    data = router.route(_pq(intent="forecast", time_window="today"), "chennai")
    assert data is not None and "high_c" in data


def test_day_after_tomorrow_resolves_with_five_day_fixture():
    data = router.route(_pq(intent="forecast", time_window="day_after_tomorrow"), "chennai")
    assert data is not None and "high_c" in data


def test_forecast_day_strict_none_beyond_fixture():
    # FORECAST_DAYS (5) worth of days are snapshotted; offset == FORECAST_DAYS is
    # one past the last available index. STRICT: no clamping to another day.
    assert weather_data.forecast_day("chennai", FORECAST_DAYS) is None


def test_will_it_rain_today_tonight_tomorrow():
    for tw in ("today", "tonight", "tomorrow"):
        data = router.route(_pq(intent="will_it_rain", time_window=tw), "chennai")
        assert data is not None and "rain_probability_pct" in data


def test_forecast_next_n_days_caps_at_available():
    data = router.route(
        _pq(intent="forecast", time_window="next_n_days", days=7), "chennai"
    )
    assert data["days_counted"] == FORECAST_DAYS and data["days_requested"] == 7


def test_will_it_rain_next_n_days():
    data = router.route(
        _pq(intent="will_it_rain", time_window="next_n_days", days=2), "chennai"
    )
    assert data is not None and "days" in data


def test_rainfall_so_far_today_any_time_window():
    data = router.route(_pq(intent="rainfall_so_far_today", time_window="tomorrow"), "chennai")
    assert data is not None and ("rain_so_far_mm" in data or "rain_last_24h_mm" in data)


def test_out_of_scope_returns_none():
    data = router.route(_pq(intent="out_of_scope"), "chennai")
    assert data is None


def test_legacy_day_passthrough():
    assert router.legacy_day(_pq(time_window="tomorrow")) == "tomorrow"


def test_legacy_day_next_n_days():
    pq = _pq(time_window="next_n_days", days=3)
    assert router.legacy_day(pq) == "next_3_days"


def test_legacy_day_next_n_days_defaults_forecast_days():
    import google_weather

    pq = _pq(time_window="next_n_days", days=None)
    assert router.legacy_day(pq) == f"next_{google_weather.FORECAST_DAYS}_days"


def test_narration_facts_filters_temperature():
    facts = router.route(_pq(intent="current_weather", time_window="today"), "chennai")
    trimmed = router.narration_facts(facts, "temperature")
    assert "temp_c" in trimmed and "humidity_pct" not in trimmed
    assert "source" in trimmed  # meta preserved


def test_narration_facts_general_returns_full():
    facts = router.route(_pq(intent="current_weather", time_window="today"), "chennai")
    assert router.narration_facts(facts, "general") == facts


def test_narration_facts_falls_back_to_full_when_no_numeric_leaf():
    facts = router.route(_pq(intent="current_weather", time_window="tomorrow"), "chennai")
    trimmed = router.narration_facts(facts, "humidity")  # forecast facts have no humidity_pct
    assert trimmed == facts


def test_narration_facts_filters_multi_day():
    facts = router.route(
        _pq(intent="forecast", time_window="next_n_days", days=2), "chennai"
    )
    trimmed = router.narration_facts(facts, "rain")
    for day in trimmed["days"]:
        assert "high_c" not in day and "rain_probability_pct" in day
    assert trimmed["days_counted"] == facts["days_counted"]


def test_narration_facts_passes_day_labels_through_unchanged():
    # Labels are weather_data's canonical keys (weekday / "later"); the trim
    # must neither drop nor rewrite them — i18n and narrate render them.
    facts = router.route(
        _pq(intent="forecast", time_window="next_n_days", days=5), "chennai"
    )
    facts["days"][4]["label"] = "later"
    trimmed = router.narration_facts(facts, "temperature")
    assert [d["label"] for d in trimmed["days"]] == [d["label"] for d in facts["days"]]
