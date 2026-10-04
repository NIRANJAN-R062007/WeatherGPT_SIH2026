"""The verdict rules for travel and farming (plan.md §8 TFA-1/7/11, §11.2a, §11.6).

Three jobs: its text goes into the agent's prompt (`prompt.py`); `reference_verdict()`
is the same rule as code, which is the rule-based answer used when the agent is
off, offline or fails (`template.py`) and the verdict the eval set is checked
against; and `hard_override()` is the §11.6 override that runs in code after the
agent returns, whatever it said.

Travel has one rule table per transport mode (TFA-7, `TRAVEL_MODES`); a request
with no mode uses `ANY_MODE`. The thresholds are **drafts** for review (Niranjan,
TFA-7), not sourced figures: they are set so the eval scenarios
(`ml/advisory/scenarios.py`) are unambiguous and the modes differ where their
exposure differs — rail is the least weather-bound, a ferry the most. Farming's
are TFA-11's. Change the scenarios and these together.
"""

from __future__ import annotations

from dataclasses import dataclass

RAIN_CAUTION_PCT = 50     # no mode given: a rain chance at or above this is "caution"
WIND_CAUTION_KMH = 40     # so is a wind at or above this
FARMING_DAYS = 3          # sowing is judged over this many forecast days


@dataclass(frozen=True)
class ModeRules:
    """One transport mode's travel thresholds (TFA-7). `wind_avoid_kmh` is a level the
    code enforces after the agent, like the §11.6 overrides. `needs_marine`: the
    verdict depends on sea state, which the stack has no facts for, so it never
    reaches "go" (missing is never fine, §2 principle 3)."""

    mode: str
    rain_caution_pct: float
    wind_caution_kmh: float
    wind_avoid_kmh: float | None = None
    needs_marine: bool = False


ANY_MODE = ModeRules("any", RAIN_CAUTION_PCT, WIND_CAUTION_KMH)
TRAVEL_MODES: dict[str, ModeRules] = {
    "flight": ModeRules("flight", rain_caution_pct=50, wind_caution_kmh=40),
    "road": ModeRules("road", rain_caution_pct=50, wind_caution_kmh=40),
    "train": ModeRules("train", rain_caution_pct=70, wind_caution_kmh=50),
    "ferry": ModeRules("ferry", rain_caution_pct=40, wind_caution_kmh=30, wind_avoid_kmh=45,
                       needs_marine=True),
}


def mode_rules(mode: str | None) -> ModeRules:
    return TRAVEL_MODES.get(mode or "", ANY_MODE)


def travel_rubric(mode: str | None = None) -> str:
    """The travel rules for one mode, as the agent's prompt states them."""
    r = mode_rules(mode)
    by = f" by {r.mode}" if r.mode != "any" else ""
    avoid_wind = (f"; or a wind_kmh of {r.wind_avoid_kmh:g} or more at the origin or "
                  "destination" if r.wind_avoid_kmh is not None else "")
    marine = ("\n- Sea state (waves, swell) is not in the facts, so a ferry trip is never \"go\":"
              "\n  answer \"caution\" at best and say so in \"cons\"." if r.needs_marine else "")
    return f"""\
Pick exactly one verdict for travel{by}:
- "avoid": an IMD warning with colour "red" at the origin or destination; or, when
  METAR/TAF facts are present, a thunderstorm in the METAR weather at either airport{avoid_wind}.
- "caution": a warning with colour "orange" or "yellow"; or the warnings facts are
  missing (they cannot be confirmed clear, so never answer "go" without them); or a
  rain_probability_pct of {r.rain_caution_pct:g} or more in a forecast; or a wind_kmh of
  {r.wind_caution_kmh:g} or more.
- "go": none of the above, and the warnings are present and green.
- "not_available": the forecast for the origin or the destination is missing.{marine}
Never say a trip is "safe"."""


TRAVEL_RUBRIC = travel_rubric()  # no mode given

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


def max_wind(facts, role: str) -> float | None:
    """The strongest wind the facts give for `role` (now, and each hour), or None."""
    winds = [(_avail(facts, role, "current") or {}).get("wind_kmh")]
    winds += [h.get("wind_kmh") for h in (_avail(facts, role, "hourly") or {}).get("hours", [])]
    winds = [w for w in winds if w is not None]
    return max(winds) if winds else None


def _overrides(facts) -> list[tuple[str, str, float | None]]:
    """(role, why, value) for each rule that forces "avoid"."""
    found = []
    rules = mode_rules(facts.subject.get("mode"))
    for role in ("origin", "destination"):
        if (_avail(facts, role, "warnings") or {}).get("colour") == "red":
            found.append((role, "red_warning", None))
        aviation = _avail(facts, role, "aviation")
        if aviation and _has_thunderstorm(aviation):
            found.append((role, "thunderstorm", None))
        wind = max_wind(facts, role)
        if rules.wind_avoid_kmh is not None and wind is not None and wind >= rules.wind_avoid_kmh:
            found.append((role, "wind", wind))
    return found


def hard_override(facts) -> str | None:
    """The verdict a model may never talk its way past: "avoid" for travel when an
    IMD warning at the origin or destination is red, a METAR shows a thunderstorm
    at either airport (§11.6), or the wind reaches the mode's avoid level (TFA-7,
    ferry only today). None when no override applies (and always for farming)."""
    if facts.kind != "travel":
        return None
    return "avoid" if _overrides(facts) else None


def override_reasons(facts) -> list[str]:
    """Why the override applies, one sentence each, built from fact values only (so
    the sentences ground) — what `template.apply_override` puts first in `cons`."""
    if facts.kind != "travel":
        return []
    mode = mode_rules(facts.subject.get("mode")).mode
    out = []
    for role, why, value in _overrides(facts):
        if why == "red_warning":
            out.append(f"A red IMD warning is in force at the {role}.")
        elif why == "thunderstorm":
            out.append(f"The {role} airport report shows a thunderstorm.")
        else:
            out.append(f"Wind at the {role} reaches {value:g} km/h, too strong for a {mode}.")
    return out


def reference_travel(facts) -> str:
    roles = ("origin", "destination")
    rules = mode_rules(facts.subject.get("mode"))
    if hard_override(facts):
        return "avoid"
    forecasts = {r: _avail(facts, r, "forecast") for r in roles}
    if any(f is None for f in forecasts.values()):
        return "not_available"

    warnings = {r: _avail(facts, r, "warnings") for r in roles}

    if any(w is None or w.get("colour") != "green" for w in warnings.values()):
        return "caution"
    for role in roles:
        if forecasts[role]["rain_probability_pct"] >= rules.rain_caution_pct:
            return "caution"
        if (max_wind(facts, role) or 0) >= rules.wind_caution_kmh:
            return "caution"
    return "caution" if rules.needs_marine else "go"


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
