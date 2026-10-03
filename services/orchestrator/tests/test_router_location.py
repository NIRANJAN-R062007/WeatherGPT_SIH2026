"""router.route() takes the resolved {lat, lon, label} (location.py), never a
city key: weather is fetched for the point. A demo city's own coordinates map
back to its key, so its snapshots, cache entries and fixtures are unchanged.
"""

import json

import cities
import config
import google_weather
import nlu
import pytest
import router
import weather_data

TRICHY = {"lat": 10.8155, "lon": 78.69651, "label": "Tiruchirappalli, Tamil Nadu"}


def _pq(intent="current_weather", time_window="today", days=None):
    return nlu.ParsedQuery(intent=intent, city=None, time_window=time_window, days=days,
                           parameter="general", language="en", source="rules",
                           confidence=0.9)


def _loc(key):
    c = cities.CITIES[key]
    return {"lat": c.lat, "lon": c.lon, "label": c.names["en"]}


def test_a_demo_city_point_routes_to_its_snapshot():
    facts = router.route(_pq(), _loc("chennai"))
    assert facts == weather_data.get_weather("chennai", "current_weather", "today")


@pytest.mark.parametrize("key", sorted(cities.CITY_KEYS))
def test_every_demo_city_point_maps_back_to_its_key(key):
    c = cities.CITIES[key]
    assert google_weather.point_key(c.lat, c.lon) == key


def test_any_other_point_has_a_point_key():
    key = google_weather.point_key(TRICHY["lat"], TRICHY["lon"])
    assert key.startswith("@") and key not in cities.CITY_KEYS


def test_a_gazetteer_point_is_fetched_live_for_its_coordinates(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")
    seen = []

    def _serve(path, params, timeout=google_weather.TIMEOUT):
        seen.append(params)
        kind = next(k for k, ep in google_weather.ENDPOINTS.items() if ep == path)
        env = (config.FIXTURES_DIR / "google_weather" / f"{kind}.chennai.json")
        return json.loads(env.read_text(encoding="utf-8"))["response"]

    monkeypatch.setattr(google_weather, "fetch_json", _serve)
    for pq in (_pq(), _pq("will_it_rain", "tomorrow"), _pq("forecast", "next_n_days", 3),
               _pq("rainfall_so_far_today"), _pq("best_window")):
        assert router.route(pq, TRICHY) is not None, pq.intent
    assert seen
    for params in seen:
        assert abs(params["location.latitude"] - TRICHY["lat"]) < 0.06
        assert abs(params["location.longitude"] - TRICHY["lon"]) < 0.06


def test_a_point_with_no_live_data_has_no_fixture_to_fall_back_on():
    # Fixture mode (the suite default): only demo cities have snapshots.
    assert router.route(_pq(), TRICHY) is None
