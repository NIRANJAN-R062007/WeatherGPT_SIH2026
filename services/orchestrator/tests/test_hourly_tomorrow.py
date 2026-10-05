"""Issue #65: "tomorrow" in the hourly series is a whole day or it is unavailable.

The committed hourly snapshots hold 24 hours from one fetch (10:00 for every demo
city), so only 00:00-09:00 of tomorrow is in them. hourly_facts used to hand that over
as the whole day, and the best window, the what-if, the persona advisory, the forecast
change and the travel advisory judged tomorrow by its night and early morning. Now the
day comes back unavailable, and each consumer says so. These tests run against the real
snapshots; when they are refreshed with 48 hours (snapshot_google_weather.py) tomorrow
is a whole day and they skip, the unit tests in test_weather_data.py still cover the rule.
"""

import google_weather
import main
import pytest
from advisory.facts import TravelFactsCollector
from fastapi.testclient import TestClient

client = TestClient(main.app)

_SERIES = google_weather.snapshot("forecast_hours", "chennai").payload["forecastHours"]
pytestmark = pytest.mark.skipif(
    len(_SERIES) >= 48, reason="the snapshots hold 48 hours: tomorrow is a whole day"
)


def test_tomorrows_best_window_is_unavailable_not_a_window_of_the_night():
    body = client.get("/intelligence/best-window", params={"city": "chennai"}).json()  # tomorrow
    assert body["status"] == "unavailable" and body["window"] is None
    today = {"city": "chennai", "day": "today"}
    body = client.get("/intelligence/best-window", params=today).json()
    assert body["status"] in ("ok", "no_suitable_window")  # today still has its hours


def test_tomorrows_persona_advisory_and_what_if_are_unavailable():
    body = client.post("/intelligence/advisory",
                       json={"city": "chennai", "persona": "farmer", "day": "tomorrow"}).json()
    assert body["status"] == "unavailable" and body["window"] is None
    scenario = {"city": "chennai", "day": "tomorrow", "times": ["03:00", "17:00"]}
    body = client.post("/intelligence/scenario", json=scenario).json()
    assert body["status"] == "unavailable"


def test_ask_for_the_best_time_tomorrow_says_there_is_no_hourly_forecast():
    body = client.get("/ask", params={"text": "best time to go outside tomorrow in Chennai"}).json()
    assert body["intent"] == "best_window" and body["status"] == "unavailable"
    assert body["message"] == main._MESSAGES["best_window_unavailable"]["en"]
    assert "window" not in body


def test_ask_what_changed_tomorrow_is_unavailable():
    text = "has the forecast changed for tomorrow in Chennai"
    body = client.get("/ask", params={"text": text}).json()
    assert body["intent"] == "forecast_change" and body["status"] == "unavailable"


def test_a_trip_tomorrow_has_no_hourly_section_and_says_no_wind_forecast():
    facts = TravelFactsCollector().collect(
        {"origin": "chennai", "destination": "madurai", "day": "tomorrow", "mode": "road"})
    for role in ("origin", "destination"):
        hourly = facts.section(role, "hourly")
        assert not hourly.available and hourly.reason == "no hourly forecast for tomorrow"
    today = TravelFactsCollector().collect(
        {"origin": "chennai", "destination": "madurai", "day": "today", "mode": "road"})
    assert today.section("destination", "hourly").available
