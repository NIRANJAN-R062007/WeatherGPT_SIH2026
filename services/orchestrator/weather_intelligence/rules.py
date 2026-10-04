"""WIE-2: the suitable-hour rule and per-activity threshold variants.

Every threshold lives in this one file, so "our rules decide, the LLM only
words it" (plan.md §2 principle 7) points at one place a jury can be shown.
An unrecognised activity name falls back to "outdoor" rather than 422, so a
client can't accidentally dead-end a demo on an unknown name.

WIE-7's persona advisory labels ("farm" for farmer, "travel" for traveller)
are activities here too, so a future per-persona tuning is a one-line edit
in this file, not a change anywhere persona_advisor.py or window_analyzer.py
reads from. They start out pointing at the exact same Thresholds as
"outdoor" — plan.md's WIE-7 done-when requires identical numbers across
personas for the same facts, and no persona-specific values have been
agreed yet, so there is nothing to differ on yet.
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
    # WIE-7: farmer's and traveller's advisory labels. Same values as
    # "outdoor" today (see module docstring) — tune independently here
    # whenever persona-specific thresholds are agreed.
    "farm": OUTDOOR,
    "travel": OUTDOOR,
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


# WIE-10: how far a figure must move between two retrievals of the forecast
# for the same hour before it is reported as a change. Below these it is
# noise between model runs, not news: "no significant change" is a valid
# answer, a 2-point wobble is not a headline.
CHANGE_THRESHOLDS: dict[str, float] = {
    "rain_probability_pct": 20,  # percentage points
    "temp_c": 3,
    "wind_kmh": 10,
}
