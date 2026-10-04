"""advisory/rubric.py's travel rule table per transport mode (plan.md TFA-7).

Facts are the real fixture collector output with an eval scenario pinned on top
(ml/advisory/scenarios.py), so each verdict follows from the pinned values only.
"""

import json
import sys

import config
import guardrail
import pytest
from advisory import agent, rubric, template

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
    assert "travel by ferry" in ferry and "never \"go\"" in ferry and "45 or more" in ferry
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
