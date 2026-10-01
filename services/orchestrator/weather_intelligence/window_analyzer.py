"""WIE-3: the best contiguous suitable window in a day's hourly forecast.

This module never decides what "suitable" means — only how to find the
best contiguous run of hours that already pass rules.is_suitable_hour.
Returns None ("no suitable window") rather than the least-bad hours when
nothing passes: a window verdict is never softened into a maybe
(plan.md §2 principle 7 / R17).
"""

from . import rules as rules_module


def _minutes(local_time: str | None) -> int | None:
    """"HH:MM" -> minutes since midnight, for contiguity checks."""
    if not local_time:
        return None
    try:
        h, m = local_time.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def find_best_window(
    hours: list[dict], activity: str | None = rules_module.DEFAULT_ACTIVITY,
) -> dict | None:
    """`hours` is weather_data.hourly_facts()'s `hours` list, already time-
    ordered. Finds the longest contiguous run of suitable hours (ties go to
    the earliest start). A run never bridges a gap — an hour more than 60
    minutes after the previous suitable one starts a new run — so the
    window never silently spans an hour that wasn't actually forecast.
    """
    runs: list[list[dict]] = []
    current: list[dict] = []
    prev_minutes: int | None = None

    for hour in hours:
        minutes = _minutes(hour.get("local_time"))
        suitable = minutes is not None and rules_module.is_suitable_hour(hour, activity)
        contiguous = bool(current) and prev_minutes is not None and minutes == prev_minutes + 60

        if suitable and contiguous:
            current.append(hour)
        else:
            # Either unsuitable, or suitable but after a gap — in both cases
            # the run so far (if any) is finished first.
            if current:
                runs.append(current)
            current = [hour] if suitable else []
        prev_minutes = minutes if suitable else None

    if current:
        runs.append(current)
    if not runs:
        return None

    best = max(runs, key=len)  # longest run; max() keeps the first (earliest) on a length tie

    temps = [h["temp_c"] for h in best]
    rains = [h["rain_probability_pct"] for h in best]
    winds = [h["wind_kmh"] for h in best]
    return {
        "start_local": best[0]["local_time"],
        "end_local": best[-1]["local_time"],
        "avg_temp_c": round(sum(temps) / len(temps), 1),
        "max_rain_probability_pct": max(rains),
        "max_wind_kmh": round(max(winds), 1),
        "hours": best,
    }
