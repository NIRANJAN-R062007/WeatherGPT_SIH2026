"""WIE-2: the suitable-hour rule and per-activity threshold variants.

Every threshold lives in this one file, so "our rules decide, the LLM only
words it" (plan.md §2 principle 7) points at one place a jury can be shown.
Only the "outdoor" activity is defined here — WIE-7's persona-weighted
variants (farmer/traveller/general framing) are not built (plan.md §8
Phase 9); an unrecognised activity name falls back to "outdoor" rather than
422, so a client can't accidentally dead-end a demo on an unknown name.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    max_rain_probability_pct: float
    min_temp_c: float
    max_temp_c: float
    max_wind_kmh: float


# plan.md §4's starting rule: rain < 20%, 20-32 degC, wind < 25 km/h.
OUTDOOR = Thresholds(max_rain_probability_pct=20, min_temp_c=20, max_temp_c=32, max_wind_kmh=25)

ACTIVITIES: dict[str, Thresholds] = {
    "outdoor": OUTDOOR,
}

DEFAULT_ACTIVITY = "outdoor"


def thresholds_for(activity: str | None) -> Thresholds:
    key = (activity or DEFAULT_ACTIVITY).strip().lower()
    return ACTIVITIES.get(key, OUTDOOR)


def is_suitable_hour(hour: dict, activity: str | None = DEFAULT_ACTIVITY) -> bool:
    """True when rain, temperature and wind all pass the activity's
    thresholds. A missing figure (None) never passes — an hour the engine
    can't fully check is never called suitable (window_analyzer treats it
    as a gap, not a maybe)."""
    t = thresholds_for(activity)
    rain = hour.get("rain_probability_pct")
    temp = hour.get("temp_c")
    wind = hour.get("wind_kmh")
    if rain is None or temp is None or wind is None:
        return False
    return (
        rain < t.max_rain_probability_pct
        and t.min_temp_c <= temp <= t.max_temp_c
        and wind < t.max_wind_kmh
    )
