"""TFA-8: travel-only destinations in data/cities.json.

Done-when: a domestic route beyond the 8 demo cities returns a grounded verdict
through POST /advisory/travel. The new places are known to the travel advisory
only; /ask, /cities, offline mode and the hotlines still see the demo cities."""

import gzip
import json

import aviation
import cities
import config
import guardrail
import main
import pytest
from advisory import agent
from fastapi.testclient import TestClient

client = TestClient(main.app)
TRAVEL_ONLY = sorted(k for k, c in cities.TRAVEL_CITIES.items() if c.travel_only)
KINDS = ("current_conditions", "forecast_days", "forecast_hours", "history_hours")


@pytest.fixture(autouse=True)
def _agent_off(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)


# --- the registry ---------------------------------------------------------------------


def test_the_demo_cities_are_unchanged_and_the_destinations_are_extra():
    assert len(cities.CITIES) == 8 and not any(c.travel_only for c in cities.CITIES.values())
    assert len(TRAVEL_ONLY) == 14
    assert cities.CITY_KEYS | set(TRAVEL_ONLY) == cities.TRAVEL_KEYS
    assert set(TRAVEL_ONLY).isdisjoint(c["key"] for c in client.get("/cities").json()["cities"])


def test_only_the_travel_path_knows_them():
    assert cities.resolve("Goa") is None and cities.mentions("Chennai to Goa") == [
        ("chennai", 0, 7)]
    assert cities.resolve("Goa", travel=True) == "panaji"
    assert cities.resolve("Andaman", travel=True) == "port_blair"
    assert cities.resolve("Sri Vijaya Puram", travel=True) == "port_blair"


@pytest.mark.parametrize("key", TRAVEL_ONLY)
def test_every_destination_matches_the_gazetteer_and_has_every_name(key):
    city = cities.TRAVEL_CITIES[key]
    assert set(city.names) == {"en", "ta", "hi", "te", "mr"} and all(city.names.values())
    places = json.loads(gzip.open(config.DATA_DIR / "gazetteer" / "in_places.json.gz").read())
    (place,) = [p for p in places["places"] if p["id"] == city.place_id]
    assert abs(place["lat"] - city.lat) < 0.01 and abs(place["lon"] - city.lon) < 0.01


@pytest.mark.parametrize("key", TRAVEL_ONLY)
def test_every_destination_has_weather_fixtures(key):
    for kind in KINDS:
        path = config.FIXTURES_DIR / "google_weather" / f"{kind}.{key}.json"
        meta = json.loads(path.read_text(encoding="utf-8"))["_meta"]
        assert meta["city"] == key and meta["request"]["key"] == "REDACTED"


def test_every_destination_but_pune_has_an_airport():
    no_airport = [k for k in TRAVEL_ONLY if k not in aviation.CITY_STATION]
    assert no_airport == ["pune"]  # VAPO returned no METAR on 2026-10-05
    assert aviation.station_for("Goa") == "VOGO"
    assert aviation.station_for("Trichy") == "VOTR"


# --- matching short names -------------------------------------------------------------


@pytest.mark.parametrize("text", ["லேசான மழை பெய்யுமா", "மேலே மேகம்",
                                  "is it safe for my goats", "what is the goal"])
def test_a_short_name_inside_another_word_is_not_a_place(text):
    assert cities.mentions(text, travel=True) == []
    assert cities.resolve(text, travel=True) is None


@pytest.mark.parametrize("text, key", [("will it rain in Leh", "leh"), ("லே பயணம்", "leh"),
                                       ("to Goa", "panaji"), ("திருச்சியில் மழை", "tiruchirappalli")])
def test_a_short_name_on_its_own_is_found(text, key):
    assert [k for k, _, _ in cities.mentions(text, travel=True)] == [key]


# --- the done-when --------------------------------------------------------------------


@pytest.mark.parametrize("text, origin, destination", [
    ("Can I go from Chennai to Goa today by flight?", "chennai", "panaji"),
    ("from Kolkata to Guwahati tomorrow by train", "kolkata", "guwahati"),
    ("Chennai to Port Blair today by ferry", "chennai", "port_blair"),
])
def test_a_route_beyond_the_demo_cities_gets_a_grounded_verdict(text, origin, destination):
    body = client.post("/advisory/travel", json={"text": text}).json()
    assert body["status"] == "ok"
    assert (body["slots"]["origin"], body["slots"]["destination"]) == (origin, destination)
    answer = body["answer"]
    assert answer["verdict"] in ("go", "caution", "avoid")  # judged, not "not available"
    provenance = {p["section"] for p in body["provenance"]}
    assert {"origin.forecast", "destination.forecast"} <= provenance
    facts = agent.COLLECTORS["travel"].collect(body["slots"])
    assert guardrail.check_advisory(answer, facts).ok


def test_a_multi_leg_route_through_the_destinations_is_judged_at_every_stop():
    # TFA-8's route legs (TFA-6): travel-only places as a stop and as the end.
    body = client.post("/advisory/travel", json={
        "text": "Chennai to Guwahati via Kolkata tomorrow by flight"}).json()
    assert body["status"] == "ok"
    slots = body["slots"]
    assert (slots["origin"], slots.get("via"), slots["destination"]) == (
        "chennai", "kolkata", "guwahati")
    answer = body["answer"]
    assert answer["verdict"] in ("go", "caution", "avoid")
    provenance = {p["section"] for p in body["provenance"]}
    assert {"origin.forecast", "stop_1.forecast", "destination.forecast"} <= provenance
    facts = agent.COLLECTORS["travel"].collect(slots)
    assert guardrail.check_advisory(answer, facts).ok


def test_a_place_still_not_covered_is_named_back():
    body = client.post("/advisory/travel", json={"text": "to Shimla today from Chennai"}).json()
    assert body["status"] == "ask_back" and body["unsupported"] == {"destination": "shimla"}
