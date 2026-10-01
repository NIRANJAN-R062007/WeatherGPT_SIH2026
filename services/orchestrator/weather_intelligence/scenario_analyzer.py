"""WIE-6: what-if comparison between specific times of day.

Looks up each requested local time ("HH:MM") against the decoded hourly
forecast and reports what the rules make of it. A time outside the
forecast's hours is reported as unavailable — never filled in with an
invented value (plan.md §2 principle 7 / R17's "no window verdict" is a
sibling of this rule: a figure the engine doesn't have is never guessed).
"""

from . import rules as rules_module


def compare_scenario(
    hours: list[dict], times: list[str], activity: str | None = rules_module.DEFAULT_ACTIVITY,
) -> dict:
    by_time = {h["local_time"]: h for h in hours if h.get("local_time")}
    results = []
    for t in times:
        hour = by_time.get(t)
        if hour is None:
            results.append({"time": t, "available": False})
            continue
        results.append({
            "time": t,
            "available": True,
            "temp_c": hour.get("temp_c"),
            "rain_probability_pct": hour.get("rain_probability_pct"),
            "wind_kmh": hour.get("wind_kmh"),
            "condition": hour.get("condition"),
            "suitable": rules_module.is_suitable_hour(hour, activity),
        })

    available = [r for r in results if r["available"] and r["rain_probability_pct"] is not None]
    better_time = None
    if len(available) >= 2:
        lowest = min(r["rain_probability_pct"] for r in available)
        tied = [r["time"] for r in available if r["rain_probability_pct"] == lowest]
        better_time = tied[0] if len(tied) == 1 else None  # an exact tie names no winner

    return {"hours": results, "better_time": better_time}
