"""advisory/rubric.py's travel rule table per transport mode (plan.md TFA-7).

Facts are the real fixture collector output with an eval scenario pinned on top
(ml/advisory/scenarios.py), so each verdict follows from the pinned values only.
"""

import calendar
import copy
import json
import sys
from dataclasses import replace
from datetime import date, timedelta

import config
import guardrail
import pytest
from advisory import agent, rubric, template
from advisory.facts import FactSection

sys.path.insert(0, str(config.REPO_ROOT / "ml" / "advisory"))

import scenarios  # noqa: E402

MODES = (None, "flight", "road", "train", "ferry")
GO_ANSWER = {"verdict": "go", "pros": ["The trip looks fine."], "cons": [], "window": None,
             "cites": []}


def _facts(scenario: str, mode: str | None):
    slots = {"origin": "chennai", "destination": "madurai", "day": "today"}
    if mode:
        slots["mode"] = mode
    return scenarios.build("travel", slots, scenario)


# --- the table --------------------------------------------------------------------


def test_every_mode_has_rules_and_no_mode_falls_back_to_any():
    assert set(rubric.TRAVEL_MODES) == {"flight", "road", "train", "ferry"}
    assert rubric.mode_rules(None) is rubric.ANY_MODE
    assert rubric.mode_rules("hovercraft") is rubric.ANY_MODE
    assert rubric.mode_rules("train").mode == "train"


def test_the_calm_baseline_is_below_every_modes_caution_level():
    """Otherwise a 'clear' row would not mean clear for some mode."""
    for rules in (rubric.ANY_MODE, *rubric.TRAVEL_MODES.values()):
        assert scenarios.CALM_RAIN_PCT < rules.rain_caution_pct
        assert scenarios.CALM_WIND_KMH < rules.wind_caution_kmh


@pytest.mark.parametrize("scenario, mode, verdict", [
    ("clear", None, "go"),
    ("clear", "train", "go"),
    ("clear", "ferry", "caution"),          # no sea-state facts: never "go"
    ("rain_showers", "road", "caution"),    # 60% >= 50
    ("rain_showers", "train", "go"),        # 60% < 70: rail is the least weather-bound
    ("rain_showers", "ferry", "caution"),
    ("strong_wind", "flight", "caution"),   # 45 km/h >= 40
    ("strong_wind", "train", "go"),         # 45 < 50
    ("strong_wind", "ferry", "avoid"),      # 45 >= the ferry's avoid level
])
def test_the_verdict_follows_the_modes_table(scenario, mode, verdict):
    assert rubric.reference_travel(_facts(scenario, mode)) == verdict


def test_the_prompt_states_the_requests_mode_only():
    ferry, train = rubric.travel_rubric("ferry"), rubric.travel_rubric("train")
    assert "travel by ferry" in ferry and "never \"go\"" in ferry and "39 or more" in ferry
    assert "rain_probability_pct of 70 or more" in train and "ferry" not in train
    assert rubric.TRAVEL_RUBRIC == rubric.travel_rubric(None)


# --- the hard overrides (TFA-7 done-when) -------------------------------------------


def _forced(scenario: str, mode: str | None) -> dict:
    facts = _facts(scenario, mode)
    answer = template.apply_override(facts, dict(GO_ANSWER))
    assert guardrail.check_advisory(answer, facts).ok, guardrail.check_advisory(answer, facts)
    return answer


@pytest.mark.parametrize("mode", MODES)
def test_a_red_warning_forces_avoid_whatever_the_model_said(mode):
    answer = _forced("red_warning", mode)
    assert answer["verdict"] == "avoid"
    assert answer["cons"][0] == "A red IMD warning is in force at the destination."


@pytest.mark.parametrize("mode", [None, "flight"])  # the modes METAR/TAF is gathered for
def test_a_thunderstorm_metar_forces_avoid_whatever_the_model_said(mode):
    answer = _forced("thunderstorm_metar", mode)
    assert answer["verdict"] == "avoid"
    assert answer["cons"][0] == "The destination airport report shows a thunderstorm."


def test_a_ferry_in_avoid_level_wind_is_forced_to_avoid():
    answer = _forced("strong_wind", "ferry")
    assert answer["verdict"] == "avoid"
    assert answer["cons"][0] == (
        f"Wind at the destination reaches {scenarios.WINDY_KMH} km/h, too strong for a ferry.")


def test_the_same_wind_does_not_force_avoid_for_other_modes():
    for mode in (None, "flight", "road", "train"):
        assert rubric.hard_override(_facts("strong_wind", mode)) is None


def test_the_override_beats_the_agent_end_to_end(monkeypatch):
    """Through agent.advise: a model that says "go" in a red warning still answers avoid."""
    facts = _facts("red_warning", "train")
    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", True)
    monkeypatch.setattr(agent.COLLECTORS["travel"], "collect", lambda slots: facts)
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: json.dumps(GO_ANSWER))
    advice = agent.advise("travel", facts.subject, models=[("gemini", None)])
    assert advice.path == "agent:gemini"
    assert advice.answer["verdict"] == "avoid"


# --- a later day is judged by that day (Niranjan's TFA-7 review) -------------------


def _trip(scenario: str, mode: str | None, day: str):
    slots = {"origin": "chennai", "destination": "madurai", "day": day}
    if mode:
        slots["mode"] = mode
    return scenarios.build("travel", slots, scenario)


def _now_wind(facts, kmh: float):
    scenarios._destination(facts, "current", lambda d: d.update(wind_kmh=kmh))
    return facts


@pytest.mark.parametrize("mode, now_kmh, verdict", [
    ("ferry", 50, "caution"),   # was "avoid": 50 km/h now, calm tomorrow
    ("road", 45, "go"),         # was "caution"
])
def test_todays_wind_does_not_decide_tomorrows_trip(mode, now_kmh, verdict):
    facts = _now_wind(_trip("clear", mode, "tomorrow"), now_kmh)
    assert rubric.hard_override(facts) is None
    assert rubric.reference_travel(facts) == verdict
    assert template.template_answer(facts)["verdict"] == verdict
    # the same wind on a trip today still counts
    assert rubric.max_wind(_now_wind(_trip("clear", mode, "today"), now_kmh),
                           "destination") == now_kmh


def test_todays_metar_thunderstorm_does_not_decide_tomorrows_flight():
    facts = _trip("clear", "flight", "tomorrow")
    scenarios._destination(facts, "aviation", lambda d: scenarios._set_metar_weather(
        d["metar"], "thunderstorm with rain"))
    assert rubric.hard_override(facts) is None and rubric.reference_travel(facts) == "go"
    assert not any("thunderstorm" in c for c in template.template_answer(facts)["cons"])


def test_a_taf_thunderstorm_on_the_trip_day_forces_avoid():
    answer = _forced_on("thunderstorm_metar", "flight", "tomorrow")
    assert answer["verdict"] == "avoid"
    assert answer["cons"][0] == (
        "The destination airport forecast (TAF) shows a thunderstorm on the trip day.")


def test_a_taf_thunderstorm_on_another_day_does_not():
    facts = _trip("clear", "flight", "tomorrow")
    day_before = rubric.trip_date(facts) - timedelta(days=1)
    scenarios._destination(facts, "aviation",
                           lambda d: scenarios._taf_thunderstorm(d["taf"], day_before))
    assert rubric.hard_override(facts) is None


def test_a_taf_thunderstorm_later_today_forces_avoid_for_a_trip_today():
    facts = _trip("clear", "flight", "today")
    scenarios._destination(facts, "aviation", lambda d: scenarios._taf_thunderstorm(
        d["taf"], rubric.trip_date(facts)))
    assert rubric.thunderstorm_source(facts, "destination") == "taf"
    assert rubric.hard_override(facts) == "avoid"


def test_an_old_taf_snapshot_never_matches_the_trip_day():
    facts = _trip("thunderstorm_metar", "flight", "tomorrow")
    scenarios._destination(facts, "aviation", lambda d: d["taf"].update(
        retrieved_at="2025-01-01T00:00:00+00:00"))
    assert rubric.thunderstorm_source(facts, "destination") is None


def test_no_wind_for_the_trip_day_is_caution_not_go():
    """The day after tomorrow is past the 24 h hourly series: the wind is unknown,
    and unknown is never calm."""
    facts = _trip("clear", "road", "day_after_tomorrow")
    assert not facts.section("destination", "hourly").available
    assert rubric.max_wind(facts, "destination") is None
    assert rubric.reference_travel(facts) == "caution"
    answer = template.template_answer(facts)
    assert answer["verdict"] == "caution"
    assert "No wind forecast for the trip day is available for the destination." in answer["cons"]
    assert guardrail.check_advisory(answer, facts).ok


def test_hourly_facts_never_returns_another_days_hours():
    import weather_data

    assert weather_data.hourly_facts("chennai", "today")["day"] == "today"
    assert weather_data.hourly_facts("chennai", "day_after_tomorrow") is None  # 24 h series
    assert weather_data.hourly_facts("chennai", "next_week") is None  # was today's hours


def test_the_prompt_says_which_day_decides():
    later = rubric.travel_rubric("flight", "tomorrow")
    assert "trip day's hourly forecast only" in later and "covers the trip day" in later
    assert "the METAR weather" in rubric.travel_rubric("flight", "today")
    assert rubric.travel_rubric("flight") == rubric.travel_rubric("flight", "today")


def _forced_on(scenario: str, mode: str | None, day: str) -> dict:
    facts = _trip(scenario, mode, day)
    answer = template.apply_override(facts, dict(GO_ANSWER))
    assert guardrail.check_advisory(answer, facts).ok, guardrail.check_advisory(answer, facts)
    return answer


# --- the template answer and the prompt use the mode -------------------------------


@pytest.mark.parametrize("scenario, mode", [
    ("rain_showers", "train"), ("rain_showers", "road"), ("strong_wind", "ferry"),
    ("clear", "ferry"), ("orange_warning", None), ("red_warning", "flight"),
])
def test_the_template_answer_matches_the_table_and_grounds(scenario, mode):
    facts = _facts(scenario, mode)
    answer = template.template_answer(facts)
    assert answer["verdict"] == rubric.reference_travel(facts)
    assert guardrail.check_advisory(answer, facts).ok


def test_rain_below_the_trains_level_is_a_pro_not_a_con():
    answer = template.template_answer(_facts("rain_showers", "train"))
    assert f"Rain chance at the destination is {scenarios.RAINY_PCT}%." in answer["pros"]
    assert answer["verdict"] == "go"


def test_a_ferry_answer_says_sea_conditions_are_not_available():
    answer = template.template_answer(_facts("clear", "ferry"))
    assert answer["verdict"] == "caution"
    assert any("Sea conditions are not in the facts" in c for c in answer["cons"])


def test_warning_sentences_take_the_right_article():
    assert "An orange IMD warning is in force at the destination." in template.template_answer(
        _facts("orange_warning", None))["cons"]
    assert "A red IMD warning is in force at the destination." in template.template_answer(
        _facts("red_warning", None))["cons"]


def test_the_prompt_carries_the_requests_mode_rules():
    from advisory import prompt

    facts = _facts("clear", "ferry")
    text = prompt.build("travel", facts.subject, "en", facts)
    assert rubric.travel_rubric("ferry") in text
    assert rubric.travel_rubric(None) not in text


# --- a forecast figure the feed left out: never read as fine ------------------------


def _without_rain_chance(facts, role: str):
    """weather_data.forecast_day() leaves a figure out of the dict when the feed has none."""
    forecast = facts.section(role, "forecast")
    data = {k: v for k, v in forecast.data.items() if k != "rain_probability_pct"}
    scenarios._replace(facts, replace(forecast, data=data))
    return facts


@pytest.mark.parametrize("role", ["origin", "destination"])
@pytest.mark.parametrize("mode", [None, "train"])
def test_a_forecast_with_no_rain_chance_is_caution_never_go(role, mode):
    facts = _without_rain_chance(_facts("clear", mode), role)
    assert rubric.reference_travel(facts) == "caution"
    answer = template.template_answer(facts)
    assert answer["verdict"] == "caution"
    assert f"The rain chance for the {role} is not available." in answer["cons"]
    assert not any("None" in s for s in answer["pros"] + answer["cons"])
    assert f"{role}.forecast.rain_probability_pct" not in answer["cites"]
    assert guardrail.check_advisory(answer, facts).ok


def test_the_prompt_says_a_missing_rain_chance_is_caution():
    for mode in MODES:
        text = rubric.travel_rubric(mode)
        assert "with no rain_probability_pct (the chance cannot be confirmed low)" in text


# --- farming: the crop file decides (TFA-11) -----------------------------------------

SOWING = {"district": "madurai", "crop": "groundnut"}
SUITABLE = {"verdict": "suitable", "pros": ["Conditions look suitable."], "cons": [],
            "window": None, "cites": []}


def _crop(**over) -> dict:
    month = date.fromisoformat(_sow("sow_ok", crop=None).raw()["location"]["forecast"]
                               ["days"][0]["date"]).month
    base = {"crop": "groundnut", "region": "madurai", "reviewed": False,
            "temp_range_c": {"min": 20, "max": 35}, "max_rain_probability_pct": 50,
            "sowing_months": [calendar.month_name[month]],
            "sources": [], "source": "TEST FIXTURE crop entry", "is_live": False}
    return {**base, **over}


def _sow(scenario: str, crop: dict | None = "default", window: dict | None = None):
    facts = scenarios.build("farming", SOWING, scenario)
    if crop is not None:
        entry = _crop() if crop == "default" else crop
        scenarios._replace(facts, FactSection("crop", "entry", True, entry,
                                              source=entry["source"], is_live=False))
    if window is not None:
        scenarios._replace(facts, FactSection("location", "window", True, window,
                                              source="weather_intelligence", is_live=False))
    return facts


def _other_month(facts) -> str:
    month = date.fromisoformat(facts.raw()["location"]["forecast"]["days"][0]["date"]).month
    return calendar.month_name[month % 12 + 1]


def test_in_season_and_inside_the_thresholds_is_suitable_with_the_window():
    window = dict(scenarios.WINDOW)
    facts = _sow("sow_ok", window=window)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "suitable" == answer["verdict"]
    assert answer["window"] == {"start_local": "08:00", "end_local": "11:00"}
    assert any("within the crop file's sowing months" in p for p in answer["pros"])
    assert guardrail.check_advisory(answer, facts).ok


def test_outside_the_sowing_months_is_not_suitable_and_says_why():
    probe = _sow("sow_ok")
    facts = _sow("sow_ok", crop=_crop(sowing_months=[_other_month(probe)]),
                 window=dict(scenarios.WINDOW))
    answer = template.template_answer(facts)
    assert answer["verdict"] == "not_suitable" and answer["window"] is None
    assert any("sowing months are" in c for c in answer["cons"])
    assert guardrail.check_advisory(answer, facts).ok


def test_a_rain_chance_at_the_crops_limit_is_not_suitable():
    facts = _sow("sow_ok", crop=_crop(max_rain_probability_pct=scenarios.CALM_RAIN_PCT))
    assert rubric.reference_farming(facts) == "not_suitable"


def test_a_missing_temperature_range_is_not_available_never_guessed():
    facts = _sow("sow_ok", crop=_crop(temp_range_c=None))
    answer = template.template_answer(facts)
    assert answer["verdict"] == "not_available"
    assert "The crop file gives no temperature range for this crop." in answer["cons"]
    assert guardrail.check_advisory(answer, facts).ok


def test_a_crop_with_no_rain_limit_is_still_judged_by_the_heavy_rain_rule():
    """Sources rarely give a rain-chance limit, so it is optional (TFA-9)."""
    facts = _sow("sow_ok", crop=_crop(max_rain_probability_pct=None))
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "suitable" == answer["verdict"]
    assert guardrail.check_advisory(answer, facts).ok


def _with_rain(facts, day: int, mm: float | None, category: str | None):
    forecast = facts.section("location", "forecast")
    data = copy.deepcopy(forecast.data)
    data["days"][day].update(rain_mm=mm, rain_category=category)
    scenarios._replace(facts, replace(forecast, data=data))
    return facts


@pytest.mark.parametrize("category", rubric.HEAVY_RAIN)
def test_heavy_rain_on_a_judged_day_is_not_suitable_whatever_the_crop(category):
    facts = _with_rain(_sow("sow_ok", crop=_crop(max_rain_probability_pct=None)),
                       1, 80.5, category)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "not_suitable" == answer["verdict"]
    assert answer["window"] is None
    assert any("Heavy rain is forecast" in c and "80.5 mm" in c for c in answer["cons"])
    assert guardrail.check_advisory(answer, facts).ok


def test_heavy_rain_after_the_judged_days_does_not_count():
    facts = _with_rain(_sow("sow_ok"), rubric.FARMING_DAYS, 80.5, "heavy")
    assert rubric.reference_farming(facts) == "suitable"


def test_moderate_rain_is_not_the_heavy_rain_rule():
    facts = _with_rain(_sow("sow_ok", crop=_crop(max_rain_probability_pct=None)),
                       0, 40.0, "moderate")
    assert rubric.reference_farming(facts) == "suitable"


def test_a_judged_day_with_no_rain_amount_is_not_available_never_read_as_dry():
    facts = _with_rain(_sow("sow_ok"), 2, None, None)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "not_available" == answer["verdict"]
    assert any("no rain amount" in c for c in answer["cons"])
    assert guardrail.check_advisory(answer, facts).ok


def test_no_sowing_months_means_the_season_is_said_to_be_unchecked():
    answer = template.template_answer(_sow("sow_ok", crop=_crop(sowing_months=None)))
    assert answer["verdict"] == "suitable"
    assert any("season was not checked" in c for c in answer["cons"])


def test_an_unreviewed_crop_is_named_as_such_and_a_reviewed_one_is_not():
    assert template.CROP_NOT_REVIEWED in template.template_answer(_sow("sow_ok"))["cons"]
    reviewed = template.template_answer(_sow("sow_ok", crop=_crop(reviewed=True)))
    assert template.CROP_NOT_REVIEWED not in reviewed["cons"]


@pytest.mark.parametrize("scenario, crop, verdict", [
    ("crop_missing", None, "not_available"),
    ("sow_ok", "default_no_temp", "not_available"),
    ("sow_no_forecast", "default", "not_available"),
    ("sow_ok", "out_of_season", "not_suitable"),
])
def test_a_model_saying_suitable_is_overruled_where_it_would_be_guessing(scenario, crop, verdict):
    if crop == "default_no_temp":
        crop = _crop(temp_range_c=None)
    elif crop == "out_of_season":
        crop = _crop(sowing_months=[_other_month(_sow("sow_ok"))])
    facts = _sow(scenario, crop=crop)
    answer = template.finish(facts, {**SUITABLE, "window": {"start_local": "08:00",
                                                             "end_local": "11:00"}})
    assert answer["verdict"] == verdict and answer["window"] is None
    assert answer["cons"][0] in rubric.override_reasons(facts)


def test_finish_adds_the_review_caveat_to_an_agent_answer_once():
    facts = _sow("sow_ok")
    once = template.finish(facts, dict(SUITABLE))
    assert once["cons"] == [template.CROP_NOT_REVIEWED]
    assert template.finish(facts, once)["cons"] == [template.CROP_NOT_REVIEWED]
    assert template.finish(_sow("sow_ok", crop=_crop(reviewed=True)),
                           dict(SUITABLE))["cons"] == []


def test_the_farming_prompt_rules_carry_no_numbers_of_their_own():
    """Every farming threshold is the crop file's, so it is a fact the answer may
    quote; the rubric itself names fields, not figures."""
    digits = [c for c in rubric.FARMING_RUBRIC.replace(str(rubric.FARMING_DAYS), "") if c.isdigit()]
    assert digits == []


# --- farming: a forecast figure the feed left out is not read as mild or dry ----------


def _with_figure(facts, day: int, field: str, value):
    forecast = facts.section("location", "forecast")
    data = copy.deepcopy(forecast.data)
    data["days"][day][field] = value
    scenarios._replace(facts, replace(forecast, data=data))
    return facts


@pytest.mark.parametrize("field", ["high_c", "low_c"])
def test_a_judged_day_with_no_high_or_low_is_not_available_never_read_as_mild(field):
    facts = _with_figure(_sow("sow_ok"), 0, field, None)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "not_available" == answer["verdict"]
    assert "The forecast gives no high or low temperature for today." in answer["cons"]
    assert not any("None" in s for s in answer["pros"] + answer["cons"])
    assert guardrail.check_advisory(answer, facts).ok


def test_a_judged_day_with_no_rain_chance_is_not_available_when_the_crop_has_a_limit():
    facts = _with_figure(_sow("sow_ok"), 1, "rain_probability_pct", None)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "not_available" == answer["verdict"]
    assert "The forecast gives no rain chance for tomorrow." in answer["cons"]
    assert guardrail.check_advisory(answer, facts).ok


def test_a_missing_rain_chance_is_said_but_not_judged_when_the_crop_gives_no_limit():
    facts = _with_figure(_sow("sow_ok", crop=_crop(max_rain_probability_pct=None)),
                         0, "rain_probability_pct", None)
    answer = template.template_answer(facts)
    assert rubric.reference_farming(facts) == "suitable" == answer["verdict"]
    assert "Rain today is 1.2 mm, with a high of 32°C and a low of 25°C." in answer["pros"]
    assert "The forecast gives no rain chance for today." in answer["cons"]
    assert not any("None" in s for s in answer["pros"] + answer["cons"])
    assert not any(c.endswith(".rain_probability_pct") for c in answer["cites"])
    assert guardrail.check_advisory(answer, facts).ok


def test_each_missing_figure_is_a_sentence_of_its_own():
    facts = _with_figure(_with_figure(_sow("sow_ok"), 0, "high_c", None),
                         1, "rain_probability_pct", None)
    assert rubric.forecast_gaps(_crop(), facts.raw()["location"]["forecast"]) == [
        "The forecast gives no high or low temperature for today.",
        "The forecast gives no rain chance for tomorrow."]


def test_figures_after_the_judged_days_are_not_needed():
    facts = _sow("sow_ok")
    for field in ("high_c", "low_c", "rain_probability_pct"):
        _with_figure(facts, rubric.FARMING_DAYS, field, None)
    assert rubric.reference_farming(facts) == "suitable"


def test_a_model_saying_suitable_is_overruled_when_a_judged_figure_is_missing():
    facts = _with_figure(_sow("sow_ok"), 0, "high_c", None)
    answer = template.finish(facts, dict(SUITABLE))
    assert answer["verdict"] == "not_available"
    assert answer["cons"][0] == "The forecast gives no high or low temperature for today."
    assert guardrail.check_advisory(answer, facts).ok


def test_the_farming_prompt_says_a_missing_figure_is_not_available():
    assert "no rain_category, no high_c or no low_c" in rubric.FARMING_RUBRIC
    assert "no rain_probability_pct when the crop facts give" in rubric.FARMING_RUBRIC
