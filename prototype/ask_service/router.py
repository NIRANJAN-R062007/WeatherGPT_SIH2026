"""Intent -> tool-call routing (plan.md §8). Turns a `nlu.ParsedQuery` into the
right `weather_data` call, and trims the resulting facts down to what the
narration prompt needs for the asked parameter (the guardrail still checks
against the FULL facts dict, never this trimmed subset).
"""

import weather_data
from google_weather import FORECAST_DAYS
from nlu import ParsedQuery

_PARAM_KEYS = {
    "temperature": {"temp_c", "feels_like_c", "high_c", "low_c"},
    "humidity": {"humidity_pct"},
    "wind": {"wind_kmh", "wind_dir"},
    "rain": {"rain_probability_pct", "rain_so_far_mm", "rain_last_24h_mm"},
}
_META_KEYS = {
    "source", "issued", "is_live", "day", "condition",
    "hours_counted", "days_counted", "days_requested",
}


def legacy_day(pq: ParsedQuery) -> str:
    if pq.time_window == "next_n_days":
        return f"next_{pq.days or FORECAST_DAYS}_days"
    return pq.time_window


def route(pq: ParsedQuery, key: str) -> dict | None:
    intent, tw = pq.intent, pq.time_window

    if intent == "rainfall_so_far_today":
        return weather_data.rain_so_far(key)

    if tw == "day_after_tomorrow":
        return weather_data.forecast_day(key, 2)  # STRICT: no clamping to another day

    if tw == "next_n_days" and intent in ("forecast", "will_it_rain"):
        return weather_data.multi_day_facts(key, pq.days or FORECAST_DAYS)

    if intent == "forecast" and tw == "today":
        return weather_data.forecast_day(key, 0)

    if intent == "current_weather" and tw == "today":
        return weather_data.get_weather(key, "current_weather", "today")

    if intent in ("current_weather", "forecast") and tw in ("tonight", "tomorrow"):
        return weather_data.get_weather(key, "current_weather", tw)

    if intent == "will_it_rain" and tw in ("today", "tonight", "tomorrow"):
        return weather_data.get_weather(key, "will_it_rain", tw)

    return None


def _filter_day(day: dict, keys: set[str]) -> dict:
    return {k: v for k, v in day.items() if k in keys or k == "label"}


def narration_facts(facts: dict, parameter: str) -> dict:
    """Trim facts to the parameter asked about, plus provenance/meta keys.

    Falls back to the full facts dict when the filtered result has no numeric
    leaf left to talk about (e.g. asking about humidity on a day the fixture
    doesn't carry it, or `uv` — which has no dedicated fact at all).
    """
    keys = _PARAM_KEYS.get(parameter)
    if not keys or facts is None:
        return facts

    if "days" in facts:
        filtered_days = [_filter_day(d, keys) for d in facts["days"]]
        has_numeric = any(
            isinstance(v, (int, float)) for d in filtered_days for k, v in d.items()
            if k != "label"
        )
        if not has_numeric:
            return facts
        return {**{k: v for k, v in facts.items() if k != "days"}, "days": filtered_days}

    trimmed = {k: v for k, v in facts.items() if k in keys or k in _META_KEYS}
    has_numeric = any(isinstance(v, (int, float)) for k, v in trimmed.items()
                      if k not in _META_KEYS)
    if not has_numeric:
        return facts
    return trimmed
