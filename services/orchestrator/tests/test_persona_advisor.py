"""weather_intelligence.persona_advisor (plan.md §8 Phase 9, WIE-7). Synthetic
hourly dicts, shaped like test_window_analyzer.py's, so the window numbers
in these tests are exact and don't depend on what a fixture happens to
contain.
"""

import persona
import pytest
from weather_intelligence import persona_advisor


def hour(local_time, *, rain=10, temp=26, wind=10, condition="clear"):
    return {
        "time_iso": f"2026-10-01T{local_time}:00Z",
        "local_time": local_time,
        "rain_probability_pct": rain,
        "temp_c": temp,
        "wind_kmh": wind,
        "condition": condition,
    }


_HOURS = [hour("09:00", rain=10, temp=26, wind=10), hour("10:00", rain=10, temp=26, wind=10)]


# --- labels and window-wanting ------------------------------------------------


def test_every_vetted_persona_has_a_labels_entry():
    # persona.PERSONAS is the source of truth for what a caller may send;
    # every one of them must resolve to something here, not KeyError.
    for p in persona.PERSONAS:
        assert p in persona_advisor.LABELS


def test_wants_window_true_for_farmer_traveller_general_city_official():
    for p in ("general", "farmer", "traveller", "city_official"):
        assert persona_advisor.wants_window(p) is True


def test_wants_window_false_for_fisherman_and_aviation():
    assert persona_advisor.wants_window("fisherman") is False
    assert persona_advisor.wants_window("aviation") is False


def test_labels_are_farm_travel_or_outdoor():
    assert persona_advisor.LABELS["farmer"] == "farm"
    assert persona_advisor.LABELS["traveller"] == "travel"
    assert persona_advisor.LABELS["general"] == "outdoor"
    assert persona_advisor.LABELS["city_official"] == "outdoor"


# --- advise(): identical numbers, different framing ---------------------------


def test_farmer_traveller_general_give_identical_numbers_from_identical_facts():
    # plan.md's WIE-7 done-when, verbatim: different framing, same numbers.
    farmer = persona_advisor.advise(_HOURS, "farmer")
    traveller = persona_advisor.advise(_HOURS, "traveller")
    general = persona_advisor.advise(_HOURS, "general")
    assert farmer["label"] != traveller["label"] != general["label"]
    assert farmer["window"] == traveller["window"] == general["window"]
    assert farmer["window"]["start_local"] == "09:00"
    assert farmer["window"]["end_local"] == "11:00"


def test_city_official_also_gets_the_outdoor_window():
    general = persona_advisor.advise(_HOURS, "general")
    city_official = persona_advisor.advise(_HOURS, "city_official")
    assert city_official["label"] == "outdoor"
    assert city_official["window"] == general["window"]


def test_no_suitable_window_is_none_not_the_least_bad_hour():
    bad_hours = [hour("09:00", rain=90, temp=40, wind=50)]
    advisory = persona_advisor.advise(bad_hours, "farmer")
    assert advisory["label"] == "farm"
    assert advisory["window"] is None


@pytest.mark.parametrize("p", ["fisherman", "aviation"])
def test_fisherman_and_aviation_get_no_window_and_a_caveat(p):
    advisory = persona_advisor.advise(_HOURS, p)
    assert advisory["label"] is None
    assert advisory["window"] is None
    assert advisory["caveat"] == persona_advisor.CAVEATS[p]


# --- caveat wording never reads as a safety verdict ---------------------------


_UNSAFE_WORDS = ("safe", "unsafe", "risk-free", "no risk")


@pytest.mark.parametrize("p", ["fisherman", "aviation"])
def test_caveat_never_says_safe_or_unsafe(p):
    text = persona_advisor.CAVEATS[p].lower()
    assert not any(w in text for w in _UNSAFE_WORDS)


@pytest.mark.parametrize("p", ["fisherman", "aviation"])
def test_caveat_never_claims_a_warning_is_in_force(p):
    text = persona_advisor.CAVEATS[p].lower()
    assert "warning is" not in text and "alert is" not in text
