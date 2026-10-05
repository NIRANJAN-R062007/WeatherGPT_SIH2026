"""advisory/facts.py (plan.md §8 Phase 10, TFA-4): travel and farming each
return a typed facts object the grounding guardrail can check. Runs against the
committed fixtures (conftest sets WEATHER_MODE=fixtures), so nothing here hits
a network.
"""

import config
import guardrail
import pytest
from advisory import facts as facts_module
from advisory.facts import (
    AdvisoryFacts,
    FactsCollector,
    FactSection,
    FarmingFactsCollector,
    TravelFactsCollector,
)

TRIP = {"origin": "chennai", "destination": "madurai", "day": "today"}
SOWING = {"district": "madurai", "crop": "groundnut"}


def kinds(facts: AdvisoryFacts, role: str) -> set[str]:
    return set(facts.raw().get(role, {}))


@pytest.fixture
def warnings_on(monkeypatch):
    # Off by default (config.py): the fixture is simulated, not a live feed.
    monkeypatch.setattr(config, "WARNINGS_ENABLED", True)


# --- the shape ---------------------------------------------------------------


def test_travel_returns_typed_facts_for_both_ends():
    facts = TravelFactsCollector().collect(TRIP)
    assert isinstance(facts, AdvisoryFacts) and facts.kind == "travel"
    assert facts.subject == TRIP
    for role in ("origin", "destination"):
        assert {"current", "forecast", "hourly", "aviation"} <= kinds(facts, role)


def test_farming_returns_typed_facts_for_the_district():
    facts = FarmingFactsCollector().collect(SOWING)
    assert isinstance(facts, AdvisoryFacts) and facts.kind == "farming"
    assert {"forecast", "hourly", "rain"} <= kinds(facts, "location")


def test_both_collectors_implement_the_one_interface():
    assert issubclass(TravelFactsCollector, FactsCollector)
    assert issubclass(FarmingFactsCollector, FactsCollector)
    with pytest.raises(TypeError):
        FactsCollector()  # abstract: a feature must say which sections it needs


def test_a_new_feature_only_has_to_name_its_sections():
    class Tiny(FactsCollector):
        kind = "tiny"

        def sections(self, slots):
            return [facts_module.current_weather("here", slots["city"])]

    facts = Tiny().collect({"city": "chennai"})
    assert facts.kind == "tiny" and "current" in kinds(facts, "here")


def test_sections_carry_their_source_and_liveness():
    facts = TravelFactsCollector().collect(TRIP)
    section = facts.section("origin", "current")
    assert section.available and section.data is not None
    assert section.source and section.is_live is False  # fixtures
    expected = {"section": "origin.current", "source": section.source, "is_live": False}
    assert expected in facts.provenance()


def test_as_dict_is_json_serialisable():
    import json

    json.dumps(TravelFactsCollector().collect(TRIP).as_dict())
    json.dumps(FarmingFactsCollector().collect(SOWING).as_dict())


# --- the guardrail can check it ----------------------------------------------


def test_a_figure_from_the_facts_grounds_and_an_invented_one_does_not():
    facts = TravelFactsCollector().collect(TRIP)
    temp = facts.raw()["origin"]["current"]["temp_c"]
    ok = guardrail.check(f"Chennai is {temp}°C right now.", facts.raw())
    assert ok.ok and ok.figures[0]["path"] == "origin.current.temp_c"
    assert not guardrail.check("Chennai is 99°C right now.", facts.raw()).ok


def test_a_window_time_from_the_hourly_facts_grounds():
    facts = FarmingFactsCollector().collect(SOWING)
    first = facts.raw()["location"]["hourly"]["hours"][0]["local_time"]
    assert guardrail.check(f"Dry from {first}.", facts.raw()).ok
    assert not guardrail.check("Dry from 03:17.", facts.raw()).ok


# --- missing data is reported, never papered over ----------------------------


def test_warnings_feed_off_is_unavailable_not_an_all_clear():
    facts = TravelFactsCollector().collect(TRIP)
    assert "warnings" not in kinds(facts, "origin")
    assert {"section": "origin.warnings", "reason": "warnings feed unavailable"} in facts.missing()


def test_warnings_feed_on_returns_the_feeds_own_status(warnings_on):
    facts = TravelFactsCollector().collect(TRIP)
    section = facts.section("origin", "warnings")
    assert section.available
    assert section.data["status"] in ("clear", "active") and section.data["colour"]
    assert section.is_live is False  # a fixture, labelled as one


def test_an_unavailable_section_is_absent_so_its_numbers_cannot_ground(monkeypatch):
    with_hourly = FarmingFactsCollector().collect(SOWING)
    first = with_hourly.raw()["location"]["hourly"]["hours"][0]["local_time"]

    monkeypatch.setattr(facts_module.weather_data, "hourly_facts", lambda *a, **k: None)
    without = FarmingFactsCollector().collect(SOWING)
    assert "hourly" not in kinds(without, "location")
    expected = {"section": "location.hourly", "reason": "no hourly forecast for today"}
    assert expected in without.missing()
    assert not guardrail.check(f"Dry from {first}.", without.raw()).ok


def test_one_source_raising_does_not_sink_the_others(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(facts_module.weather_data, "forecast_day", boom)
    facts = TravelFactsCollector().collect(TRIP)
    assert {"section": "origin.forecast", "reason": "source error"} in facts.missing()
    assert {"current", "hourly"} <= kinds(facts, "origin")  # the rest still collected


def test_unknown_city_is_reported_not_guessed():
    facts = TravelFactsCollector().collect({**TRIP, "destination": "atlantis"})
    assert "destination" not in facts.raw()
    assert facts.section("destination", "location").reason == "unknown destination 'atlantis'"
    assert kinds(facts, "origin")  # the other end is unaffected


def test_unsupported_day_is_reported_not_clamped():
    facts = TravelFactsCollector().collect({**TRIP, "day": "next_friday"})
    assert "forecast" not in kinds(facts, "origin")
    assert "unsupported day 'next_friday'" in {m["reason"] for m in facts.missing()}


# --- travel mode / farming crop ----------------------------------------------


def test_metar_taf_only_for_flights_or_an_unspecified_mode():
    assert "aviation" in kinds(TravelFactsCollector().collect({**TRIP, "mode": "flight"}), "origin")
    assert "aviation" in kinds(TravelFactsCollector().collect(TRIP), "origin")
    train = TravelFactsCollector().collect({**TRIP, "mode": "train"})
    assert all("aviation" not in s.name for s in train.sections)


def test_city_without_an_airport_has_no_aviation_section_not_a_fair_one(monkeypatch):
    # Every demo city has a station today; a future destination may not.
    real = facts_module.aviation.station_for
    monkeypatch.setattr(facts_module.aviation, "station_for",
                        lambda c: None if c == "madurai" else real(c))
    facts = TravelFactsCollector().collect(TRIP)
    assert "aviation" not in kinds(facts, "destination")
    assert "aviation" in kinds(facts, "origin")
    expected = {"section": "destination.aviation", "reason": "no METAR/TAF available"}
    assert expected in facts.missing()


def test_no_metar_taf_report_is_unavailable(monkeypatch):
    monkeypatch.setattr(facts_module.aviation, "public",
                        lambda station: {"station": station, "status": "unavailable",
                                         "metar": None, "taf": None})
    facts = TravelFactsCollector().collect(TRIP)
    assert "aviation" not in kinds(facts, "origin")


def test_a_crop_the_crop_file_does_not_cover_is_unavailable():
    facts = FarmingFactsCollector().collect({**SOWING, "crop": "rice"})
    assert "crop" not in facts.raw()
    expected = {"section": "crop.entry", "reason": "crop/region not in the sourced crop file"}
    assert expected in facts.missing()


def test_crop_entry_comes_from_the_plugged_in_lookup(monkeypatch):
    entry = {"source": "TNAU Agritech", "sowing_window": {"from": "06-15", "to": "07-15"}}
    seen = []
    monkeypatch.setattr(facts_module, "crop_lookup",
                        lambda crop, region: seen.append((crop, region)) or entry)
    facts = FarmingFactsCollector().collect({**SOWING, "region": "southern-tn"})
    assert seen == [("groundnut", "southern-tn")]
    assert facts.raw()["crop"]["entry"] == entry
    assert facts.section("crop", "entry").source == "TNAU Agritech"


def test_no_crop_given_is_reported():
    facts = FarmingFactsCollector().collect({"district": "madurai"})
    assert {"section": "crop.entry", "reason": "no crop given"} in facts.missing()


def test_unknown_district_is_reported_and_the_crop_still_looked_up():
    facts = FarmingFactsCollector().collect({"district": "atlantis", "crop": "groundnut"})
    assert "location" not in facts.raw()
    assert facts.section("location", "location").reason == "unknown district 'atlantis'"


def test_fact_section_name():
    assert FactSection("origin", "current", False, reason="x").name == "origin.current"


# --- TFA-21: sections are gathered in parallel ---------------------------------


def test_gather_all_runs_side_by_side_and_keeps_the_order():
    import threading

    barrier = threading.Barrier(3, timeout=5)  # only passes if all three run at once

    def call(i):
        def run():
            barrier.wait()
            return FactSection("origin", f"k{i}", True, {"i": i})
        return run

    out = facts_module.gather_all([call(i) for i in range(3)])
    assert [s.kind for s in out] == ["k0", "k1", "k2"]


def test_parallel_collection_matches_the_sequential_order(monkeypatch):
    parallel = TravelFactsCollector().collect({**TRIP, "mode": "flight"})
    monkeypatch.setattr(facts_module, "gather_all", lambda calls: [c() for c in calls])
    sequential = TravelFactsCollector().collect({**TRIP, "mode": "flight"})
    assert [s.name for s in parallel.sections] == [s.name for s in sequential.sections]
    assert parallel.raw() == sequential.raw()
