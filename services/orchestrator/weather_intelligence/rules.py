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

TFA-11: when the crop is known (the sowing advisory), its sourced thresholds
replace the "farm" placeholder — crop_thresholds() builds them from the crop
file's entry. "farm" stays for the farmer persona's window, which has no crop.
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


def thresholds_for(activity: "str | Thresholds | None") -> Thresholds:
    """An activity's thresholds; a Thresholds passes straight through (a crop's)."""
    if isinstance(activity, Thresholds):
        return activity
    key = (activity or DEFAULT_ACTIVITY).strip().lower()
    return ACTIVITIES.get(key, OUTDOOR)


def crop_thresholds(entry: dict | None) -> Thresholds | None:
    """A crop file entry (advisory/crops.py) as hour thresholds, or None when the
    entry lacks the temperature range or the rain limit — a missing threshold is
    never filled in. The rain limit is optional in the crop file (sources rarely
    give one), so a crop without it is judged by day but has no hourly window.
    The crop file has no wind figure, so wind is the "farm" activity's field-work
    limit (a working condition, not agronomy)."""
    if not entry:
        return None
    temp, rain = entry.get("temp_range_c"), entry.get("max_rain_probability_pct")
    if temp is None or rain is None:
        return None
    return Thresholds(max_rain_probability_pct=rain, min_temp_c=temp["min"],
                      max_temp_c=temp["max"], max_wind_kmh=ACTIVITIES["farm"].max_wind_kmh)


def is_suitable_hour(hour: dict, activity: "str | Thresholds | None" = DEFAULT_ACTIVITY) -> bool:
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
