"""WIE-10: what changed between two retrievals of the same forecast.

Compares the hours of the latest forecast with the same target hours in an
earlier snapshot and reports only moves that reach rules.CHANGE_THRESHOLDS.
Three outcomes are kept apart, because they are different statements:

- "no_baseline": there is no earlier forecast for these hours to compare with
  (nothing stored, or nothing that overlaps). Never reported as "no change".
- "no_significant_change": there is a baseline, it was compared, and nothing
  moved by a reportable amount.
- "ok": one entry per figure that moved, with both values and the hours.

This module decides nothing about wording: the numbers it returns are the
only ones an answer may quote.
"""

from datetime import datetime

import forecast_snapshots

from . import rules as rules_module

METRICS = ("rain_probability_pct", "temp_c", "wind_kmh")


def _clock(local_time: str) -> datetime:
    return datetime.strptime(local_time, "%H:%M")


def detect_changes(hours: list[dict], baseline: dict | None) -> dict:
    """`hours` is weather_data.hourly_facts()'s `hours` (each with `time_iso`
    and `local_time`); `baseline` is forecast_snapshots.previous()'s result or
    None."""
    if baseline is None:
        return {"status": "no_baseline", "changes": [], "compared_hours": 0}

    old_by_time = baseline["hours"]
    pairs = []
    for hour in hours:
        when = forecast_snapshots.normalize_time(hour.get("time_iso"))
        old = old_by_time.get(when)
        if old is not None:
            pairs.append((hour, old))
    if not pairs:
        return {"status": "no_baseline", "changes": [], "compared_hours": 0}

    changes = []
    for metric in METRICS:
        threshold = rules_module.CHANGE_THRESHOLDS[metric]
        moved = []
        for hour, old in pairs:
            new_v, old_v = hour.get(metric), old.get(metric)
            if new_v is None or old_v is None:
                continue
            delta = new_v - old_v
            if abs(delta) >= threshold:
                moved.append((hour, old_v, new_v, delta))
        if not moved:
            continue
        # Report the hour that moved most; its before/after are the headline.
        # Opposite-sign moves in one day are summarised by the larger one.
        peak_hour, old_v, new_v, delta = max(moved, key=lambda m: abs(m[3]))
        same_way = [m for m in moved if (m[3] > 0) == (delta > 0)]
        changes.append({
            "metric": metric,
            "direction": "rose" if delta > 0 else "fell",
            "from": old_v,
            "to": new_v,
            "delta": round(delta, 1),
            "peak_local": peak_hour["local_time"],
            "start_local": min((m[0]["local_time"] for m in same_way), key=_clock),
            "end_local": max((m[0]["local_time"] for m in same_way), key=_clock),
            "hours_changed": len(same_way),
        })

    return {
        "status": "ok" if changes else "no_significant_change",
        "changes": changes,
        "compared_hours": len(pairs),
    }
