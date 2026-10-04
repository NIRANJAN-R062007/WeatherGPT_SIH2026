"""guardrail.check_advisory + advisory/schema.py (plan.md §8 Phase 10, TFA-5):
a travel/farming answer in the verdict/pros/cons/window shape is rejected if
anything in it is outside the facts. Facts come from the real collectors
(committed fixtures; conftest sets WEATHER_MODE=fixtures), with an engine
window section added the way TFA-7/TFA-11 will add one.
"""

import json

import guardrail
import pytest
from advisory import facts as facts_module
from advisory import schema
from advisory.facts import AdvisoryFacts, FactSection, FarmingFactsCollector, TravelFactsCollector

TRIP = {"origin": "chennai", "destination": "madurai", "day": "today"}
WINDOW = {"start_local": "08:00", "end_local": "11:00",
          "avg_temp_c": 26.0, "max_rain_probability_pct": 10, "max_wind_kmh": 12.5}


def travel_facts(window=WINDOW) -> AdvisoryFacts:
    facts = TravelFactsCollector().collect(TRIP)
    if window is not None:
        facts.sections.append(FactSection("destination", "window", True, window,
                                          source="weather_intelligence", is_live=False))
    return facts


def answer(**over) -> dict:
    base = {"verdict": "go", "pros": ["Dry for most of the day."], "cons": [],
            "window": None, "cites": []}
    return {**base, **over}


# --- a grounded answer passes -------------------------------------------------


def test_grounded_travel_answer_passes():
    facts = travel_facts()
    raw = facts.raw()
    temp = raw["origin"]["current"]["temp_c"]
    out = answer(
        pros=[f"Chennai is {temp}°C now.", "The best window is 8 AM–11 AM."],
        cons=[f"Up to {WINDOW['max_rain_probability_pct']}% chance of rain in it."],
        window={"start_local": "08:00", "end_local": "11:00"},
        cites=["origin.current.temp_c", "destination.window.max_wind_kmh"],
    )
    report = guardrail.check_advisory(out, facts)
    assert report.ok, report.problems
    assert report.grounding.ok and report.grounding.matched == report.grounding.total == 3
    assert [f["field"] for f in report.grounding.figures] == ["pros[0]", "pros[1]", "cons[0]"]


def test_grounded_farming_answer_passes():
    facts = FarmingFactsCollector().collect({"district": "madurai", "crop": "groundnut"})
    day = facts.raw()["location"]["forecast"]["days"][0]
    out = answer(verdict="suitable",
                 pros=[f"{day['rain_probability_pct']}% chance of rain, high {day['high_c']}°C."],
                 cites=["location.forecast.days[0].high_c"])
    report = guardrail.check_advisory(out, facts)
    assert report.ok, report.problems


def test_not_available_with_nothing_to_cite_passes():
    facts = FarmingFactsCollector().collect({"district": "madurai", "crop": "groundnut"})
    out = answer(verdict="not_available", pros=[], cons=["The crop file has no entry."])
    assert guardrail.check_advisory(out, facts).ok


# --- the WIE-5/TFA-5 done-when: a number or field not in the facts fails -------


def test_a_number_not_in_the_facts_fails():
    out = answer(pros=["Chennai is 99°C now."])
    report = guardrail.check_advisory(out, travel_facts())
    assert not report.ok
    assert report.problems == ["pros[0]: '99°C' is not in the facts"]
    assert report.grounding.figures[0]["field"] == "pros[0]" and not report.grounding.ok


def test_a_number_in_cons_fails_too():
    out = answer(pros=[], cons=["Winds up to 80 km/h."])
    assert not guardrail.check_advisory(out, travel_facts()).ok


def test_a_field_not_in_the_facts_fails():
    out = answer(cites=["origin.current.dewpoint_c"])
    report = guardrail.check_advisory(out, travel_facts())
    assert report.problems == ["cites 'origin.current.dewpoint_c', which is not in the facts"]


@pytest.mark.parametrize("path", [
    "", ".", "origin..current", "origin.current.", "origin.current.temp_c.x",
    "origin.hourly.hours[999].temp_c", "nowhere.current", "origin.current temp_c",
])
def test_malformed_or_dangling_cites_fail(path):
    assert not guardrail.check_advisory(answer(cites=[path]), travel_facts()).ok


def test_indexed_cites_resolve():
    out = answer(cites=["destination.hourly.hours[0].temp_c", "origin.hourly.hours[0]"])
    assert guardrail.check_advisory(out, travel_facts()).ok


def test_citing_an_unavailable_section_fails():
    # The warnings feed is off by default: that section is absent, and a model
    # can neither quote it nor cite it as if it had said "clear".
    facts = travel_facts()
    assert facts.section("origin", "warnings").available is False
    assert not guardrail.check_advisory(answer(cites=["origin.warnings.colour"]), facts).ok


def test_an_unavailable_section_may_be_cited_by_its_exact_name():
    """TFA-19: the prompt asks for a missing section to be named in `cons`; that
    sentence's honest source is the NOT AVAILABLE entry, spelled as missing() spells it."""
    facts = travel_facts()
    assert {"section": "origin.warnings", "reason": "warnings feed unavailable"} in facts.missing()
    out = answer(verdict="caution", cons=["IMD warnings are not available for Chennai."],
                 cites=["origin.warnings", "destination.warnings"])
    assert guardrail.check_advisory(out, facts).ok


def test_a_made_up_section_name_still_fails():
    out = answer(cites=["origin.cyclone_track"])
    assert not guardrail.check_advisory(out, travel_facts()).ok


def test_a_figure_from_an_unavailable_section_fails(monkeypatch):
    facts = travel_facts()
    first = facts.raw()["destination"]["hourly"]["hours"][0]
    line = f"It is {first['temp_c']}°C at {first['local_time']}."
    assert guardrail.check_advisory(answer(pros=[line]), facts).ok

    monkeypatch.setattr(facts_module.weather_data, "hourly_facts", lambda *a, **k: None)
    gone = travel_facts()
    # The clock time must not ground off another section's "HH:MM" (a TAF's
    # UTC time, say) now that the hourly section is gone.
    assert not guardrail.check_advisory(answer(pros=[f"Clear at {first['local_time']}."]), gone).ok


# --- windows ------------------------------------------------------------------


def test_a_window_the_facts_carry_passes_and_one_they_dont_fails():
    facts = travel_facts()
    ok = answer(window={"start_local": "08:00", "end_local": "11:00"})
    assert guardrail.check_advisory(ok, facts).ok
    for start, end in (("08:00", "10:00"), ("09:00", "11:00"), ("14:00", "17:00")):
        window = {"start_local": start, "end_local": end}
        report = guardrail.check_advisory(answer(window=window), facts)
        assert not report.ok and "is not a window in the facts" in report.problems[0]


def test_a_window_with_no_window_in_the_facts_fails():
    out = answer(window={"start_local": "08:00", "end_local": "11:00"})
    assert not guardrail.check_advisory(out, travel_facts(window=None)).ok


def test_a_window_named_in_text_must_be_the_facts_window():
    facts = travel_facts()
    assert guardrail.check_advisory(answer(pros=["Go between 8 AM and 11 AM."]), facts).ok
    report = guardrail.check_advisory(answer(pros=["Go between 8 AM and 10 AM."]), facts)
    assert not report.ok


# --- shape --------------------------------------------------------------------


@pytest.mark.parametrize(("out", "expect"), [
    (answer(verdict="safe"), "verdict 'safe' is not one of"),
    (answer(verdict="suitable"), "verdict 'suitable' is not one of"),  # a farming word on travel
    (answer(reason="It is 99°C"), "unexpected key 'reason'"),
    ({"verdict": "go", "pros": []}, "missing key 'cons'"),
    (answer(pros="Dry."), "pros is not a list"),
    (answer(pros=[""]), "pros[0] is not a non-empty string"),
    (answer(pros=[42]), "pros[0] is not a non-empty string"),
    (answer(cons=["x"] * 9), "cons has more than 8 items"),
    (answer(pros=["x" * 301]), "pros[0] is longer than 300 characters"),
    (answer(window={"start_local": "08:00"}), "window must be null"),
    (answer(window={"start_local": "11:00", "end_local": "08:00"}), "window must be null"),
    (answer(window={"start_local": "25:00", "end_local": "26:00"}), "window must be null"),
    (answer(window="8 AM-11 AM"), "window must be null"),
])
def test_wrong_shape_is_rejected(out, expect):
    report = guardrail.check_advisory(out, travel_facts())
    assert not report.ok
    assert any(expect in p for p in report.problems), report.problems


def test_farming_has_its_own_verdicts():
    facts = FarmingFactsCollector().collect({"district": "madurai", "crop": "groundnut"})
    assert guardrail.check_advisory(answer(verdict="suitable"), facts).ok
    assert not guardrail.check_advisory(answer(verdict="go"), facts).ok
    assert not guardrail.check_advisory(answer(verdict="avoid"), facts).ok


def test_non_object_output_is_rejected():
    for bad in ([], None, 3, ["go"]):
        assert not guardrail.check_advisory(bad, travel_facts()).ok


def test_a_raw_model_reply_is_parsed_including_a_code_fence():
    facts = travel_facts()
    body = json.dumps(answer())
    assert guardrail.check_advisory(body, facts).ok
    assert guardrail.check_advisory(f"```json\n{body}\n```", facts).ok
    report = guardrail.check_advisory("Sure! Here is the verdict: go.", facts)
    assert not report.ok and report.problems == ["output is not valid JSON"]
    assert not guardrail.check_advisory("[1, 2]", facts).ok


def test_schema_parse_and_minutes():
    assert schema.parse('{"a": 1}') == {"a": 1}
    assert schema.parse("```\n{}\n```") == {}
    assert schema.parse("not json") is None and schema.parse(5) is None
    assert schema.minutes("08:00") == 480 and schema.minutes("24:00") is None
    assert schema.minutes("8:5") is None and schema.minutes(None) is None


def test_unknown_kind_is_rejected():
    facts = AdvisoryFacts("surfing", {}, [])
    assert guardrail.check_advisory(answer(), facts).problems == ["unknown advisory kind 'surfing'"]
