"""The draft rubric the eval set is scored against (plan.md §8 TFA-1, §11.5/§11.6).

Two jobs: its text goes into the model's prompt (`prompt.py`), and
`reference_verdict()` is the same rule as code, so every row's expected verdict
can be checked against the facts it is about, and the `oracle` candidate has
something to answer with.

This is **eval scaffolding, not the production rule table**. TFA-7 (travel
Go/Caution/Avoid thresholds, with the §11.6 hard overrides) and TFA-11 (farming,
sourced crop thresholds) own the real numbers, and the real overrides run in
code regardless of what a model says. The thresholds below are first drafts
chosen so the eval scenarios (scenarios.py) are unambiguous; change them there
and here together.
"""

from __future__ import annotations

RAIN_CAUTION_PCT = 50     # a rain chance at or above this is "caution"
WIND_CAUTION_KMH = 40     # so is a wind at or above this
FARMING_DAYS = 3          # sowing is judged over this many forecast days

TRAVEL_RUBRIC = f"""\
Pick exactly one verdict:
- "avoid": an IMD warning with colour "red" at the origin or destination; or, when
  METAR/TAF facts are present, a thunderstorm in the METAR weather at either airport.
- "caution": a warning with colour "orange" or "yellow"; or the warnings facts are
  missing (they cannot be confirmed clear, so never answer "go" without them); or a
  rain_probability_pct of {RAIN_CAUTION_PCT} or more in a forecast; or a wind_kmh of
  {WIND_CAUTION_KMH} or more.
- "go": none of the above, and the warnings are present and green.
- "not_available": the forecast for the origin or the destination is missing.
Never say a trip is "safe"."""

FARMING_RUBRIC = f"""\
The crop facts give a temperature range and a maximum rain chance. Look at the first
{FARMING_DAYS} forecast days.
- "not_suitable": any of those days has rain_probability_pct above the crop's
  max_rain_probability_pct, or high_c above its temp_range_c max, or low_c below its
  temp_range_c min.
- "suitable": none of the above.
- "not_available": the crop facts or the forecast facts are missing. Never guess a
  threshold the facts do not give.
Never say "sow now" and never promise a yield."""


# --- the same rule as code --------------------------------------------------------


def _avail(facts, role: str, kind: str):
    section = facts.section(role, kind)
    return section.data if section is not None and section.available else None


def _has_thunderstorm(aviation: dict) -> bool:
    weather = (aviation.get("metar") or {}).get("decoded", {}).get("weather") or []
    return any("thunderstorm" in (w.get("text") or "") for w in weather)


def reference_travel(facts) -> str:
    roles = ("origin", "destination")
    forecasts = {r: _avail(facts, r, "forecast") for r in roles}
    if any(f is None for f in forecasts.values()):
        return "not_available"

    warnings = {r: _avail(facts, r, "warnings") for r in roles}
    if any((w or {}).get("colour") == "red" for w in warnings.values()):
        return "avoid"
    for role in roles:
        aviation = _avail(facts, role, "aviation")
        if aviation and _has_thunderstorm(aviation):
            return "avoid"

    if any(w is None or w.get("colour") != "green" for w in warnings.values()):
        return "caution"
    for role in roles:
        if forecasts[role]["rain_probability_pct"] >= RAIN_CAUTION_PCT:
            return "caution"
        winds = [(_avail(facts, role, "current") or {}).get("wind_kmh", 0)]
        hours = (_avail(facts, role, "hourly") or {}).get("hours", [])
        winds += [h.get("wind_kmh", 0) for h in hours]
        if max(winds) >= WIND_CAUTION_KMH:
            return "caution"
    return "go"


def reference_farming(facts) -> str:
    crop = _avail(facts, "crop", "entry")
    forecast = _avail(facts, "location", "forecast")
    if crop is None or forecast is None:
        return "not_available"
    lo, hi = crop["temp_range_c"]["min"], crop["temp_range_c"]["max"]
    for day in forecast["days"][:FARMING_DAYS]:
        if (day["rain_probability_pct"] > crop["max_rain_probability_pct"]
                or day["high_c"] > hi or day["low_c"] < lo):
            return "not_suitable"
    return "suitable"


def reference_verdict(facts) -> str:
    return {"travel": reference_travel, "farming": reference_farming}[facts.kind](facts)
