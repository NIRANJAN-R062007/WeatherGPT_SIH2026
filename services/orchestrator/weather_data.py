"""Intent-aware weather facts for /ask, decoded from the Google Weather API.

get_weather() dispatches on intent + day and returns a FLAT dict of the numbers
an answer may quote (the guardrail validates against these keys). Fetch, cache
and the offline fixture fallback live in google_weather.

- current_weather + today  -> current conditions
- current_weather + future -> that day's forecast (asked & answered: "weather
  tomorrow" should not return today's numbers)
- will_it_rain             -> that day's forecast
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import cities
import google_weather

_DAY_INDEX = {"today": 0, "tonight": 0, "tomorrow": 1, "day_after_tomorrow": 2}
_DAY_BY_OFFSET = {0: "today", 1: "tomorrow", 2: "day_after_tomorrow"}
_DAY_PERIOD = {"tonight": "nighttimeForecast"}
_FORECAST_DAYS = ("tomorrow", "tonight")

# Canonical day keys (multi_day_facts `label`, forecast_day `day`): "today" /
# "tomorrow" by position, then the weekday, then "later" when the entry's date
# is unparseable. Never a bare number — "day3" reads as a figure with no unit,
# which guardrail._match can't ground, failing a perfectly good forecast.
# i18n.DAY_LABELS renders these; narrate._DAY_PHRASES phrases them for the LLM.
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_LATER = "later"


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
    uv_index = _dig(r, "uvIndex")
    _put(facts, "uv_index", uv_index)
    _put(facts, "uv_band", google_weather.decode_uv_band(uv_index))
    return facts


def _entry_facts(entry: dict, period_name: str) -> dict:
    period = (entry.get(period_name) or entry.get("daytimeForecast")
              or entry.get("nighttimeForecast") or {})
    facts: dict = {}
    _put(facts, "issued", _dig(entry, "interval.startTime"))
    _put(facts, "condition", google_weather.decode_condition(_dig(period, "weatherCondition.type")))
    _put(facts, "rain_probability_pct", _dig(period, "precipitation.probability.percent"))
    _put(facts, "high_c", _dig(entry, "maxTemperature.degrees"))
    _put(facts, "low_c", _dig(entry, "minTemperature.degrees"))
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

    facts: dict = {"source": snap.source, "is_live": snap.is_live, "day": day}
    facts.update(_entry_facts(entry, period_name))
    return facts


def forecast_day(key: str, offset: int, period: str = "daytimeForecast") -> dict | None:
    """A single forecast day at a fixed index, STRICT: None beyond what's available
    (no clamping) — used for day_after_tomorrow, where guessing another day is wrong.
    """
    snap = google_weather.snapshot("forecast_days", key)
    if snap is None:
        return None
    days = _dig(snap.payload, "forecastDays") or []
    if offset >= len(days):
        return None

    facts: dict = {"source": snap.source, "is_live": snap.is_live,
                   "day": _DAY_BY_OFFSET.get(offset, _day_label(key, offset, days[offset]))}
    facts.update(_entry_facts(days[offset], period))
    return facts


def _day_label(key: str, index: int, entry: dict) -> str:
    if index == 0:
        return "today"
    if index == 1:
        return "tomorrow"
    d = entry.get("displayDate")
    if d:
        try:
            return _WEEKDAYS[datetime(d["year"], d["month"], d["day"]).weekday()]
        except (KeyError, ValueError, TypeError):
            pass
    start = _dig(entry, "interval.startTime")
    if start:
        try:  # a day's interval starts in the local morning, so read the date in city time
            return _WEEKDAYS[_parse_ts(start).astimezone(_city_timezone(key)).weekday()]
        except (ValueError, TypeError):
            pass
    return _LATER


def multi_day_facts(key: str, days_requested: int) -> dict | None:
    snap = google_weather.snapshot("forecast_days", key)
    if snap is None:
        return None
    days = _dig(snap.payload, "forecastDays") or []
    if not days:
        return None

    counted = min(days_requested, len(days))
    out_days = []
    for i in range(counted):
        ef = _entry_facts(days[i], "daytimeForecast")
        out_days.append({
            "label": _day_label(key, i, days[i]),
            "condition": ef.get("condition"),
            "rain_probability_pct": ef.get("rain_probability_pct"),
            "high_c": ef.get("high_c"),
            "low_c": ef.get("low_c"),
        })

    return {
        "source": snap.source,
        "is_live": snap.is_live,
        "issued": _dig(days[0], "interval.startTime"),
        "days_requested": days_requested,
        "days_counted": counted,
        "days": out_days,
    }


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", s))


def _rain_last_24h(key: str) -> dict | None:
    snap = google_weather.snapshot("current_conditions", key)
    if snap is None:
        return None
    r = snap.payload
    mm = _dig(r, "currentConditionsHistory.qpf.quantity")
    if mm is None:
        return None
    return {
        "source": snap.source,
        "is_live": snap.is_live,
        "issued": _dig(r, "currentTime"),
        "rain_last_24h_mm": mm,
        "rain_category": google_weather.decode_precip_category(mm),
        "hours_counted": 24,
        "condition": google_weather.decode_condition(_dig(r, "weatherCondition.type")),
    }


def _city_timezone(key: str):
    try:
        return ZoneInfo(cities.CITIES[key].timezone)
    except ZoneInfoNotFoundError:  # slim images may lack tzdata; every demo city is IST
        return timezone(timedelta(hours=5, minutes=30))


def rain_so_far(key: str, *, now: datetime | None = None) -> dict | None:
    """Rain accumulated since local midnight, summed from history/hours:lookup.

    Falls back to the 24h rolling total in currentConditionsHistory when no
    history_hours snapshot is available (fixture missing, live call failed).
    """
    snap = google_weather.snapshot("history_hours", key)
    hours = _dig(snap.payload, "historyHours") if snap else None
    if not hours:
        return _rain_last_24h(key)

    tz = _city_timezone(key)
    end_times = [_parse_ts(h["interval"]["endTime"]) for h in hours]
    now = now or max(end_times)
    midnight = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    total = 0.0
    hours_counted = 0
    for h in hours:
        start = _parse_ts(h["interval"]["startTime"])
        if midnight <= start < now:
            qpf = _dig(h, "precipitation.qpf.quantity")
            if qpf is not None:
                total += qpf
                hours_counted += 1

    return {
        "source": snap.source,
        "is_live": snap.is_live,
        "issued": now.isoformat(),
        "since": midnight.isoformat(),
        "rain_so_far_mm": round(total, 2),
        "rain_category": google_weather.decode_precip_category(total),
        "hours_counted": hours_counted,
        "condition": google_weather.decode_condition(_dig(hours[0], "weatherCondition.type")),
    }
