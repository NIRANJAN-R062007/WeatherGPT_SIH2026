"""Intent-aware weather facts for /ask, decoded from the Google Weather API.

get_weather() dispatches on intent + day and returns a FLAT dict of the numbers
an answer may quote (the guardrail validates against these keys). Fetch, cache
and the offline fixture fallback live in google_weather.

- current_weather + today  -> current conditions
- current_weather + future -> that day's forecast (asked & answered: "weather
  tomorrow" should not return today's numbers)
- will_it_rain             -> that day's forecast
"""

import cities
import google_weather

_DAY_INDEX = {"today": 0, "tonight": 0, "tomorrow": 1}
_DAY_PERIOD = {"tonight": "nighttimeForecast"}
_FORECAST_DAYS = ("tomorrow", "tonight")


def get_weather(city: str, intent: str = "current_weather", day: str = "today") -> dict | None:
    key = (city or "").strip().lower()
    if key not in cities.CITY_KEYS:
        return None
    if intent == "will_it_rain" or day in _FORECAST_DAYS:
        return _day_facts(key, day)
    return _current_facts(key)


def source_status() -> str:
    """'google-weather-api' if any live data has been served, else 'fixtures'."""
    return "google-weather-api" if google_weather.cache_stats()["live"] else "fixtures"


def _dig(node, path: str):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _put(facts: dict, key: str, value) -> None:
    if value is not None:
        facts[key] = value


def _current_facts(key: str) -> dict | None:
    snap = google_weather.snapshot("current_conditions", key)
    if snap is None:
        return None
    r = snap.payload
    facts: dict = {"source": snap.source, "is_live": snap.is_live}
    _put(facts, "issued", _dig(r, "currentTime"))
    _put(facts, "condition", google_weather.decode_condition(_dig(r, "weatherCondition.type")))
    _put(facts, "temp_c", _dig(r, "temperature.degrees"))
    _put(facts, "feels_like_c", _dig(r, "feelsLikeTemperature.degrees"))
    _put(facts, "humidity_pct", _dig(r, "relativeHumidity"))
    _put(facts, "wind_kmh", _dig(r, "wind.speed.value"))
    _put(facts, "wind_dir",
         google_weather.decode_cardinal(_dig(r, "wind.direction.cardinal")) or None)
    return facts


def _day_facts(key: str, day: str) -> dict | None:
    snap = google_weather.snapshot("forecast_days", key)
    if snap is None:
        return None
    days = _dig(snap.payload, "forecastDays") or []
    if not days:
        return None
    idx = min(_DAY_INDEX.get(day, 1), len(days) - 1)
    entry = days[idx]

    period_name = _DAY_PERIOD.get(day, "daytimeForecast")
    period = (entry.get(period_name) or entry.get("daytimeForecast")
              or entry.get("nighttimeForecast") or {})

    facts: dict = {"source": snap.source, "is_live": snap.is_live, "day": day}
    _put(facts, "issued", _dig(entry, "interval.startTime"))
    _put(facts, "condition", google_weather.decode_condition(_dig(period, "weatherCondition.type")))
    _put(facts, "rain_probability_pct", _dig(period, "precipitation.probability.percent"))
    _put(facts, "high_c", _dig(entry, "maxTemperature.degrees"))
    _put(facts, "low_c", _dig(entry, "minTemperature.degrees"))
    return facts
