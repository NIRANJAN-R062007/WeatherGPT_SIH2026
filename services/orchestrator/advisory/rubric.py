"""The verdict rules for travel and farming (plan.md §8 TFA-1/7/11, §11.2a, §11.6).

Three jobs: its text goes into the agent's prompt (`prompt.py`); `reference_verdict()`
is the same rule as code, which is the rule-based answer used when the agent is
off, offline or fails (`template.py`) and the verdict the eval set is checked
against; and `hard_override()` is the §11.6 override that runs in code after the
agent returns, whatever it said.

The thresholds are **first drafts**, chosen so the eval scenarios
(`ml/advisory/scenarios.py`) are unambiguous. TFA-7 (travel Go/Caution/Avoid
thresholds) and TFA-11 (farming, sourced crop thresholds) own the real numbers
and tune them against the eval set; change the scenarios and these together.
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


def hard_override(facts) -> str | None:
    """The one verdict a model may never talk its way past (§11.6): "avoid" for
    travel when an IMD warning at the origin or destination is red, or a METAR
    shows a thunderstorm at either airport. None when no override applies (and
    always for farming)."""
    if facts.kind != "travel":
        return None
    for role in ("origin", "destination"):
        if (_avail(facts, role, "warnings") or {}).get("colour") == "red":
            return "avoid"
        aviation = _avail(facts, role, "aviation")
        if aviation and _has_thunderstorm(aviation):
            return "avoid"
    return None


def reference_travel(facts) -> str:
    roles = ("origin", "destination")
    if hard_override(facts):
        return "avoid"
    forecasts = {r: _avail(facts, r, "forecast") for r in roles}
    if any(f is None for f in forecasts.values()):
        return "not_available"

    warnings = {r: _avail(facts, r, "warnings") for r in roles}

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
