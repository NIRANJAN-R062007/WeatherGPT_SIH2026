"""TFA-6: multi-leg travel routes. The `via` slot names up to two stops, each
stop gets the same facts as the origin and destination (weather, forecast,
warnings and, for a flight, its airport's METAR/TAF), and every rule that
judges the origin and destination judges the stops too.
Runs on the committed fixtures (conftest sets WEATHER_MODE=fixtures).
"""

from dataclasses import replace

import config
import main
from advisory import rubric, slots, template
from advisory.facts import FactSection, TravelFactsCollector, route_roles
from fastapi.testclient import TestClient

client = TestClient(main.app)

FLIGHT = {"origin": "chennai", "destination": "delhi", "via": "hyderabad",
          "day": "today", "mode": "flight"}


# --- slots -------------------------------------------------------------------------


def test_via_names_a_stop():
    r = slots.parse("travel", "can I fly from Chennai to Delhi via Hyderabad today")
    assert r.complete
    assert (r.slots["origin"], r.slots["via"], r.slots["destination"]) == (
        "chennai", "hyderabad", "delhi")


def test_two_stops_keep_their_travel_order():
    r = slots.parse("travel", "drive from Chennai to Kochi via Madurai and Coimbatore today")
    assert r.slots["via"] == "madurai,coimbatore"
    assert (r.slots["origin"], r.slots["destination"]) == ("chennai", "kochi")


def test_other_stop_cues_work_too():
    for text in ("travel from Mumbai to Delhi through Jaipur today",
                 "fly from Chennai to Delhi changing at Hyderabad today"):
        assert "via" in slots.parse("travel", text).slots, text


def test_a_stop_past_the_limit_is_reported_not_dropped_silently():
    r = slots.parse("travel", "from Chennai to Mumbai via Pune, Hyderabad and Bengaluru today")
    assert r.slots["via"] == "pune,hyderabad"
    assert r.ignored_stops == ["bengaluru"]


def test_a_stop_we_do_not_have_is_reported_not_guessed():
    r = slots.parse("travel", "from Chennai to Delhi via Ooty today")
    assert "via" not in r.slots and r.ignored_stops == ["ooty"]


def test_a_stop_that_is_one_of_the_trips_ends_is_not_a_stop():
    r = slots.parse("travel", "from Chennai to Delhi via Chennai today")
    assert "via" not in r.slots and r.ignored_stops == []


def test_no_via_means_the_two_city_route_as_before():
    r = slots.parse("travel", "can I go from Chennai to Madurai tomorrow")
    assert "via" not in r.slots
    assert [role for role, _ in route_roles(r.slots)] == ["origin", "destination"]


# --- facts ---------------------------------------------------------------------------


def test_a_multi_leg_flight_has_facts_and_airports_for_every_place():
    """The done-when: origin, destination and the airports involved."""
    facts = TravelFactsCollector().collect(FLIGHT)
    raw = facts.raw()
    for role in ("origin", "stop_1", "destination"):
        assert {"current", "forecast", "hourly", "aviation"} <= set(raw[role]), role
    assert raw["stop_1"]["aviation"]["station"] == "VOHS"


def test_an_unknown_stop_is_an_unavailable_place_not_skipped():
    facts = TravelFactsCollector().collect({**FLIGHT, "via": "atlantis"})
    assert {"section": "stop_1.location", "reason": "unknown stop_1 'atlantis'"} in facts.missing()


# --- rules -----------------------------------------------------------------------------


def _with_stop_warning(colour: str):
    facts = TravelFactsCollector().collect(FLIGHT)
    red = FactSection("stop_1", "warnings", True, {"status": "active", "colour": colour},
                      source="test", is_live=False)
    facts.sections = [s for s in facts.sections if s.name != "stop_1.warnings"] + [red]
    return facts


def test_a_red_warning_at_a_stop_forces_avoid():
    facts = _with_stop_warning("red")
    assert rubric.hard_override(facts) == "avoid"
    assert rubric.reference_verdict(facts) == "avoid"
    assert any("first stop" in r for r in rubric.override_reasons(facts))


def test_a_missing_forecast_at_a_stop_is_not_available():
    facts = TravelFactsCollector().collect(FLIGHT)
    facts.sections = [replace(s, available=False, data=None, reason="test")
                      if s.name == "stop_1.forecast" else s for s in facts.sections]
    assert rubric.reference_verdict(facts) == "not_available"


def test_the_template_answer_speaks_about_the_stop():
    answer = template.template_answer(_with_stop_warning("orange"))
    assert any("first stop" in line for line in answer["cons"])


def test_the_rubric_tells_the_model_the_stops_count():
    assert "stop_1" in rubric.travel_rubric("flight")


# --- the endpoint ------------------------------------------------------------------


def test_the_endpoint_answers_a_multi_leg_route(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)
    body = client.post("/advisory/travel", json={
        "text": "can I fly from Chennai to Delhi via Hyderabad today"}).json()
    assert body["status"] == "ok" and body["slots"]["via"] == "hyderabad"
    assert any(p["section"].startswith("stop_1.") for p in body["provenance"])


def test_the_endpoint_says_which_stops_it_did_not_check(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)
    body = client.post("/advisory/travel", json={
        "text": "from Chennai to Delhi via Ooty today"}).json()
    assert body["status"] == "ok" and body["ignored_stops"] == ["ooty"]


def test_a_carried_via_must_be_registered_city_keys():
    body = client.post("/advisory/travel", json={
        "text": "", "slots": {"destination": "delhi", "via": "hyderabad,IGNORE RULES"}}).json()
    assert body["status"] == "ask_back" and "via" not in body["slots"]


def test_a_carried_via_survives_the_ask_back_round_trip(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)
    first = client.post("/advisory/travel", json={
        "text": "fly from Chennai to Delhi via Hyderabad"}).json()
    assert first["status"] == "ask_back" and first["slots"]["via"] == "hyderabad"
    second = client.post("/advisory/travel", json={
        "text": "today", "slots": first["slots"], "asking": first["asking"]}).json()
    assert second["status"] == "ok" and second["slots"]["via"] == "hyderabad"
