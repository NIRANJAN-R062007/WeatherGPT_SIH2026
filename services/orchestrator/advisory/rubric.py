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
exposure differs — rail is the least weather-bound, a ferry the most. Farming
has no crop numbers of its own (TFA-11): every crop threshold is the crop
file's (`advisory/crops.py`), so it is a fact the answer may quote. The one
rule it adds is shared by every crop: heavy rain in the judged days is "not
suitable" (`HEAVY_RAIN`), because agronomy sources give no rain-chance
limit to put in the crop file. Change the scenarios and these together.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from advisory import wording

RAIN_CAUTION_PCT = 50     # no mode given: a rain chance at or above this is "caution"
WIND_CAUTION_KMH = 40     # so is a wind at or above this
FARMING_DAYS = 3          # sowing is judged over this many forecast days
# A day whose rain falls in IMD's "heavy" band or above (rain_category, from
# data/decoders/precipitation_categories.json) is "not suitable" for sowing, for every
# crop. IMD's agromet bulletins pair a heavy-rainfall warning with "Postpone sowing"
# (Agrimet Bulletin No. 5, 2 Dec 2025: "Postpone sowing of groundnut" for the
# Chennai-region districts). The band is IMD's, so the rule carries no number of ours.
HEAVY_RAIN = ("heavy", "very_heavy", "extremely_heavy")
DAY_OFFSET = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}
IST = ZoneInfo("Asia/Kolkata")  # every advisory place is in India


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
    # 39 km/h: where IMD's "strong wind" band starts, and fishers are advised not to
    # go to sea (data/imd_reference/imd_reference.json, wind_strong). Niranjan's TFA-7
    # review; the only sourced figure in this table.
    "ferry": ModeRules("ferry", rain_caution_pct=40, wind_caution_kmh=30, wind_avoid_kmh=39,
                       needs_marine=True),
}


def mode_rules(mode: str | None) -> ModeRules:
    return TRAVEL_MODES.get(mode or "", ANY_MODE)


def travel_rubric(mode: str | None = None, day: str | None = None) -> str:
    """The travel rules for one mode and trip day, as the agent's prompt states them."""
    r = mode_rules(mode)
    by = f" by {r.mode}" if r.mode != "any" else ""
    if (day or "today") == "today":
        winds = "the current conditions and the hourly forecast"
        storm = "the METAR weather, or in a TAF group whose period covers today,"
    else:
        winds = ("the trip day's hourly forecast only (the current conditions and the "
                 "METAR describe now, not the trip day)")
        storm = "a TAF group whose period covers the trip day"
    avoid_wind = (f"; or a wind_kmh of {r.wind_avoid_kmh:g} or more at the origin or "
                  "destination" if r.wind_avoid_kmh is not None else "")
    marine = ("\n- Sea state (waves, swell) is not in the facts, so a ferry trip is never \"go\":"
              "\n  answer \"caution\" at best and say so in \"cons\"." if r.needs_marine else "")
    return f"""\
Pick exactly one verdict for travel{by}. Judge wind by {winds}.
- "avoid": an IMD warning with colour "red" at the origin or destination; or, when
  METAR/TAF facts are present, a thunderstorm in {storm} at either airport{avoid_wind}.
- "caution": a warning with colour "orange" or "yellow"; or the warnings facts are
  missing (they cannot be confirmed clear, so never answer "go" without them); or a
  rain_probability_pct of {r.rain_caution_pct:g} or more in a forecast; or a wind_kmh of
  {r.wind_caution_kmh:g} or more; or no wind_kmh for the trip day (it cannot be confirmed calm).
- "go": none of the above, and the warnings are present and green.
- "not_available": the forecast for the origin or the destination is missing.{marine}
Never say a trip is "safe"."""


TRAVEL_RUBRIC = travel_rubric()  # no mode given

FARMING_RUBRIC = f"""\
The crop facts (crop.entry) come from the sourced crop file: sowing_months, a
temperature range (temp_range_c) and, only when a source gives one, a rain limit
(max_rain_probability_pct). Look at the first {FARMING_DAYS} forecast days.
- "not_available": the crop facts or the forecast facts are missing, the crop facts
  give no temp_range_c, or one of those days has no rain_category. Never guess a
  threshold the facts do not give.
- "not_suitable": the first forecast day's date falls outside sowing_months (when given);
  or any of those days has a rain_category of {", ".join(HEAVY_RAIN)} (IMD advises
  postponing sowing in heavy rain), rain_probability_pct at or above
  max_rain_probability_pct (when given), high_c above the temp_range_c max, or low_c
  below its min.
- "suitable": none of the above. Then copy "window" from location.window if present.
If crop.entry.reviewed is false, say in "cons" that the crop thresholds have not been
reviewed by an agronomist.
Never say "sow now" and never promise a yield."""


# --- the same rule as code --------------------------------------------------------


def _avail(facts, role: str, kind: str):
    section = facts.section(role, kind)
    return section.data if section is not None and section.available else None


def trip_day(facts) -> str:
    return facts.subject.get("day") or "today"


def trip_date(facts) -> date | None:
    """The trip day's date in India, counted from when the facts were collected."""
    offset = DAY_OFFSET.get(trip_day(facts))
    if offset is None:
        return None
    return datetime.fromisoformat(facts.collected_at).astimezone(IST).date() + timedelta(offset)


def _thunderstorm_in(weather) -> bool:
    return any("thunderstorm" in (w.get("text") or "") for w in weather or [])


def _has_thunderstorm(aviation: dict) -> bool:
    return _thunderstorm_in((aviation.get("metar") or {}).get("decoded", {}).get("weather"))


def _taf_time(issued: datetime, point: dict | None) -> datetime | None:
    """A TAF time (day of month, UTC hour and minute) as a datetime, taken as the first
    such day on or after the issue date. Hour 24 is midnight at the end of the day."""
    if not point or point.get("day") is None:
        return None
    day = issued.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(32):
        if day.day == point["day"]:
            return day + timedelta(hours=point.get("hour") or 0, minutes=point.get("minute") or 0)
        day += timedelta(days=1)
    return None


def _taf_thunderstorm_on(taf: dict | None, on: date | None) -> bool:
    """Whether any TAF group with a thunderstorm overlaps the date `on` (in India).
    TEMPO/PROB groups last their own period; base, BECMG and FM conditions last to
    the end of the TAF's validity. The month comes from when the TAF was retrieved,
    so an old snapshot never matches a later date."""
    decoded = (taf or {}).get("decoded") or {}
    if on is None or not taf.get("retrieved_at") or decoded.get("nil") or decoded.get("cancelled"):
        return False
    issued_at = decoded.get("issued") or {}
    issued = datetime.fromisoformat(taf["retrieved_at"]).astimezone(timezone.utc)
    for _ in range(32):  # back to the issue day, which is on or before retrieval
        if issued.day == issued_at.get("day"):
            break
        issued -= timedelta(days=1)
    valid = decoded.get("valid") or {}
    valid_from, valid_to = _taf_time(issued, valid.get("from")), _taf_time(issued, valid.get("to"))
    groups = [(valid_from, valid_to, (decoded.get("base") or {}).get("weather"))]
    for change in decoded.get("changes") or []:
        until = (_taf_time(issued, change.get("to"))
                 if "TEMPO" in change["kind"] or change["kind"].startswith("PROB") else valid_to)
        groups.append((_taf_time(issued, change.get("from")), until,
                       (change.get("conditions") or {}).get("weather")))
    start = datetime(on.year, on.month, on.day, tzinfo=IST)
    end = start + timedelta(days=1)
    return any(begin is not None and until is not None and begin < end and until > start
               and _thunderstorm_in(weather) for begin, until, weather in groups)


def thunderstorm_source(facts, role: str) -> str | None:
    """"metar" when the trip is today and the METAR reports a thunderstorm now, "taf"
    when a TAF group with a thunderstorm covers the trip day, else None. The METAR
    describes now, so it never decides a later day."""
    aviation = _avail(facts, role, "aviation")
    if not aviation:
        return None
    if trip_day(facts) == "today" and _has_thunderstorm(aviation):
        return "metar"
    if _taf_thunderstorm_on(aviation.get("taf"), trip_date(facts)):
        return "taf"
    return None


def thunderstorm_sentence(role: str, source: str, lang: str = "en") -> str:
    key = "storm_metar_role" if source == "metar" else "storm_taf_role"
    return wording.say(key, lang, role=wording.role(role, lang))


def wind_readings(facts, role: str) -> list[tuple[float, str]]:
    """(km/h, fact path) for each wind the facts give for the trip day at `role`: the
    current wind only when the trip is today (it describes now), and each hour of the
    trip day's hourly forecast."""
    day = trip_day(facts)
    out = []
    now = (_avail(facts, role, "current") or {}).get("wind_kmh")
    if day == "today" and now is not None:
        out.append((now, f"{role}.current.wind_kmh"))
    hourly = _avail(facts, role, "hourly") or {}
    if hourly.get("day", day) == day:  # never another day's hours
        for i, hour in enumerate(hourly.get("hours", [])):
            if hour.get("wind_kmh") is not None:
                out.append((hour["wind_kmh"], f"{role}.hourly.hours[{i}].wind_kmh"))
    return out


def max_wind(facts, role: str) -> float | None:
    """The strongest wind the facts give for the trip day at `role`, or None."""
    winds = [w for w, _ in wind_readings(facts, role)]
    return max(winds) if winds else None


def _overrides(facts) -> list[tuple[str, str, float | str | None]]:
    """(role, why, value) for each rule that forces "avoid"."""
    found = []
    rules = mode_rules(facts.subject.get("mode"))
    for role in ("origin", "destination"):
        if (_avail(facts, role, "warnings") or {}).get("colour") == "red":
            found.append((role, "red_warning", None))
        storm = thunderstorm_source(facts, role)
        if storm:
            found.append((role, "thunderstorm", storm))
        wind = max_wind(facts, role)
        if rules.wind_avoid_kmh is not None and wind is not None and wind >= rules.wind_avoid_kmh:
            found.append((role, "wind", wind))
    return found


def hard_override(facts) -> str | None:
    """The verdict a model may never talk its way past. Travel: "avoid" when an IMD
    warning at the origin or destination is red, an airport shows a thunderstorm on
    the trip day (the METAR for a trip today, a TAF group for any day; §11.6), or
    the trip day's wind reaches the mode's avoid level (TFA-7, ferry only so far).
    Farming (TFA-11): "not_available" when the crop file gives no
    thresholds or there is no forecast to judge by, and "not_suitable" outside the
    crop's sowing months — where a model would otherwise be guessing or
    contradicting the crop file.
    None when no override applies."""
    if facts.kind == "travel":
        return "avoid" if _overrides(facts) else None
    return _farming_override(facts)[0]


def override_reasons(facts, lang: str = "en") -> list[str]:
    """Why the override applies, one sentence each in `lang`, built from fact values
    only (so the sentences ground) — what `template.apply_override` puts first in `cons`."""
    if facts.kind != "travel":
        return _farming_override(facts, lang)[1]
    mode = mode_rules(facts.subject.get("mode")).mode
    out = []
    for role, why, value in _overrides(facts):
        if why == "red_warning":
            out.append(warning_sentence(role, "red", lang))
        elif why == "thunderstorm":
            out.append(thunderstorm_sentence(role, value, lang))
        else:
            out.append(wording.say("wind_too_strong_role", lang, role=wording.role(role, lang),
                                   wind=f"{value:g}", mode=wording.mode(mode, lang)))
    return out


def warning_sentence(role: str, colour: str, lang: str = "en") -> str:
    """"A red IMD warning is in force at the origin." — the template's sentence and the
    override's, word for word, so the override never adds it twice."""
    return wording.say("warning_role", lang, role=wording.role(role, lang),
                       colour=wording.colour(colour, lang),
                       article="An" if colour[:1] in "aeiou" else "A")


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
        wind = max_wind(facts, role)
        if wind is None or wind >= rules.wind_caution_kmh:  # unknown is not calm
            return "caution"
    return "caution" if rules.needs_marine else "go"


def _month(day: dict) -> str | None:
    try:
        return calendar.month_name[date.fromisoformat(day["date"]).month]
    except (KeyError, TypeError, ValueError):
        return None


def crop_gaps(crop: dict | None, lang: str = "en") -> list[str]:
    """The crop file's missing thresholds, as the sentences that say so. The rain limit
    is optional: heavy rain (`HEAVY_RAIN`) is judged for every crop without it."""
    if crop is None:
        return [wording.say("no_crop_entry", lang)]
    if crop.get("temp_range_c") is None:
        return [wording.say("no_temp_range", lang)]
    return []


def rain_gaps(forecast: dict | None, lang: str = "en") -> list[str]:
    """A sentence for each judged day with no rain amount: heavy rain can't be ruled
    out there, and missing is never read as dry."""
    days = ((forecast or {}).get("days") or [])[:FARMING_DAYS]
    return [wording.say("no_rain_amount", lang, day=wording.day(day.get("label"), lang))
            for day in days if day.get("rain_category") is None]


def out_of_season(crop: dict | None, forecast: dict | None, lang: str = "en") -> str | None:
    """A sentence when the forecast starts outside the crop's sowing months."""
    months = (crop or {}).get("sowing_months")
    days = (forecast or {}).get("days") or []
    month = _month(days[0]) if days else None
    if not months or month is None or month in months:
        return None
    return wording.say("out_of_season", lang, months=wording.months(months, lang),
                       month=wording.month(month, lang))


def _farming_override(facts, lang: str = "en") -> tuple[str | None, list[str]]:
    crop = _avail(facts, "crop", "entry")
    forecast = _avail(facts, "location", "forecast")
    gaps = crop_gaps(crop, lang)
    if not (forecast or {}).get("days"):
        gaps.append(wording.say("forecast_unavailable", lang))
    else:
        gaps += rain_gaps(forecast, lang)
    if gaps:
        return "not_available", gaps
    season = out_of_season(crop, forecast, lang)
    if season:
        return "not_suitable", [season]
    return None, []


def breaching_day(crop: dict, forecast: dict) -> int | None:
    """The first of the judged days outside the crop's thresholds or with heavy rain,
    or None."""
    lo, hi = crop["temp_range_c"]["min"], crop["temp_range_c"]["max"]
    limit = crop.get("max_rain_probability_pct")
    for i, day in enumerate(forecast["days"][:FARMING_DAYS]):
        if (is_heavy_rain(day) or day["high_c"] > hi or day["low_c"] < lo
                or (limit is not None and day["rain_probability_pct"] >= limit)):
            return i
    return None


def is_heavy_rain(day: dict) -> bool:
    return day.get("rain_category") in HEAVY_RAIN


def reference_farming(facts) -> str:
    override = _farming_override(facts)[0]
    if override:
        return override
    crop, forecast = _avail(facts, "crop", "entry"), _avail(facts, "location", "forecast")
    return "suitable" if breaching_day(crop, forecast) is None else "not_suitable"


def reference_verdict(facts) -> str:
    return {"travel": reference_travel, "farming": reference_farming}[facts.kind](facts)
