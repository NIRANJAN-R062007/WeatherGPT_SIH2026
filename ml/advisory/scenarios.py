"""Named weather scenarios for the travel/farming eval set (plan.md §8 TFA-1).

The committed fixtures are one real snapshot per city, so a verdict written
against them would shift whenever a fixture is re-snapshotted. Each scenario
therefore starts from the real collector output (same sections, same shapes,
same provenance) and then pins the fields a verdict depends on: first a calm
baseline, then the one change the scenario is about. The expected verdict in
`eval_set.jsonl` follows from those pinned fields and nothing else.

Everything here is test data. The crop entry in particular is a made-up set of
thresholds labelled as such: the sourced crop file is TFA-9, and nothing in
this module is agronomy.
"""

from __future__ import annotations

import copy
import re
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))

from advisory import facts as facts_module  # noqa: E402
from advisory.facts import AdvisoryFacts, FactSection  # noqa: E402

# Pinned values. The thresholds in advisory/rubric.py are written against these.
CALM_RAIN_PCT = 10
CALM_WIND_KMH = 10
RAINY_PCT = 60
WINDY_KMH = 45
STORM_PCT = 85
HOT_HIGH_C = 41
WINDOW = {"start_local": "08:00", "end_local": "11:00",
          "avg_temp_c": 28.0, "max_rain_probability_pct": 10, "max_wind_kmh": 12.0}
CROP_FIXTURE = {  # made-up thresholds so the farming rows have something to read
    "temp_range_c": {"min": 20, "max": 35},
    "max_rain_probability_pct": 50,
    "source": "EVAL FIXTURE - invented thresholds, not agronomy (the sourced file is TFA-9)",
    "is_live": False,
}

TRAVEL_SCENARIOS = (
    "clear", "clear_window", "rain_showers", "strong_wind", "thunderstorm_metar",
    "red_warning", "orange_warning", "warnings_off", "no_data",
)
FARMING_SCENARIOS = ("sow_ok", "sow_too_wet", "sow_too_hot", "sow_no_forecast", "crop_missing")
SCENARIOS = TRAVEL_SCENARIOS + FARMING_SCENARIOS


# --- helpers --------------------------------------------------------------------


def _replace(facts: AdvisoryFacts, section: FactSection) -> None:
    for i, old in enumerate(facts.sections):
        if (old.role, old.kind) == (section.role, section.kind):
            facts.sections[i] = section
            return
    facts.sections.append(section)


def _drop(facts: AdvisoryFacts, role: str, kind: str, reason: str) -> None:
    _replace(facts, FactSection(role, kind, False, reason=reason))


def _each(facts: AdvisoryFacts, kind: str):
    """(index, section) for each *available* section of this kind."""
    for i, s in enumerate(facts.sections):
        if s.kind == kind and s.available:
            yield i, s


def _patch(facts: AdvisoryFacts, kind: str, fn) -> None:
    for i, s in _each(facts, kind):
        data = copy.deepcopy(s.data)
        fn(data)
        facts.sections[i] = replace(s, data=data)


def _warning(role: str, colour: str) -> FactSection:
    clear = colour == "green"
    return FactSection(role, "warnings", True, {
        "status": "clear" if clear else "active",
        "colour": colour,
        "category": None if clear else "Heavy rainfall",
        "headline": "No warning in force" if clear else f"{colour.title()} alert: heavy rainfall",
        "advice": "" if clear else "Avoid low-lying areas; keep essential travel to a minimum.",
        "valid_from": "2026-09-14T06:00:00+05:30",
        "valid_to": "2026-09-15T06:00:00+05:30",
        "issued_by": "IMD (eval fixture)",
        "source": "fixture",
        "is_live": False,
    }, source="IMD (eval fixture)", is_live=False)


# --- the calm baseline ----------------------------------------------------------


def _calm_current(d: dict) -> None:
    d.update(condition="partly_cloudy", temp_c=29, wind_kmh=CALM_WIND_KMH)


def _calm_forecast(d: dict) -> None:
    d.update(condition="partly_cloudy", rain_probability_pct=CALM_RAIN_PCT, high_c=32, low_c=25)
    for day in d.get("days", []):
        day.update(condition="partly_cloudy", rain_probability_pct=CALM_RAIN_PCT,
                   high_c=32, low_c=25)


def _calm_hourly(d: dict) -> None:
    for hour in d["hours"]:
        hour.update(condition="partly_cloudy", rain_probability_pct=CALM_RAIN_PCT,
                    wind_kmh=CALM_WIND_KMH)


_WEATHER_SENTENCE = re.compile(r" Weather: [^.]*\.")


def _set_metar_weather(metar: dict, text: str | None) -> None:
    """Make the METAR's decoded weather, briefing and lines say `text` (or nothing).
    The coded `raw`/`decoded.raw` strings are left alone: the prompt never shows them."""
    briefing = _WEATHER_SENTENCE.sub("", metar["briefing"])
    lines = [ln for ln in metar["lines"] if not ln.startswith("Weather:")]
    if text is None:
        metar["decoded"]["weather"] = []
    else:
        metar["decoded"]["weather"] = [{"code": "TSRA", "intensity": None, "descriptor": "TS",
                                        "phenomena": ["rain"], "text": text}]
        sentence = f" Weather: {text}."
        briefing = (briefing.replace(" Cloud:", sentence + " Cloud:", 1) if " Cloud:" in briefing
                    else briefing + sentence)
        at = next((i for i, ln in enumerate(lines) if ln.startswith("Cloud:")), len(lines))
        lines.insert(at, f"Weather: {text}.")
    metar["briefing"], metar["lines"] = briefing, lines


def _calm_aviation(d: dict) -> None:
    metar, taf = d["metar"], d["taf"]
    _set_metar_weather(metar, None)
    taf["decoded"]["base"]["weather"] = []
    taf["decoded"]["changes"] = []
    first = taf["briefing"].split(". ")[0].rstrip(".")
    taf["briefing"] = f"{first}. No significant weather expected."
    taf["lines"] = [taf["lines"][0], "No significant weather expected."]


def _calm_rain(d: dict) -> None:
    d.update(condition="partly_cloudy", rain_so_far_mm=0.0, rain_category="none")


def _calm(facts: AdvisoryFacts) -> None:
    _patch(facts, "current", _calm_current)
    _patch(facts, "forecast", _calm_forecast)
    _patch(facts, "hourly", _calm_hourly)
    _patch(facts, "rain", _calm_rain)
    _patch(facts, "aviation", _calm_aviation)
    for role in {s.role for s in facts.sections if s.kind == "warnings"}:
        _replace(facts, _warning(role, "green"))


# --- the scenarios --------------------------------------------------------------


def _thunderstorm_metar(facts: AdvisoryFacts, role: str = "destination") -> None:
    for i, s in _each(facts, "aviation"):
        if s.role == role:
            data = copy.deepcopy(s.data)
            _set_metar_weather(data["metar"], "thunderstorm with rain")
            facts.sections[i] = replace(s, data=data)


def _destination(facts: AdvisoryFacts, kind: str, fn) -> None:
    for i, s in _each(facts, kind):
        if s.role in ("destination", "location"):
            data = copy.deepcopy(s.data)
            fn(data)
            facts.sections[i] = replace(s, data=data)


def _rain_showers(facts: AdvisoryFacts) -> None:
    def forecast(d: dict) -> None:
        d.update(condition="rain", rain_probability_pct=RAINY_PCT)

    def hourly(d: dict) -> None:
        for hour in d["hours"]:
            hour.update(condition="rain", rain_probability_pct=RAINY_PCT)

    _destination(facts, "forecast", forecast)
    _destination(facts, "hourly", hourly)


def _strong_wind(facts: AdvisoryFacts) -> None:
    def current(d: dict) -> None:
        d["wind_kmh"] = WINDY_KMH

    def hourly(d: dict) -> None:
        for hour in d["hours"]:
            hour["wind_kmh"] = WINDY_KMH

    _destination(facts, "current", current)
    _destination(facts, "hourly", hourly)


def _sow_wet(facts: AdvisoryFacts) -> None:
    def forecast(d: dict) -> None:
        for day in d["days"][:3]:
            day.update(condition="thunderstorm", rain_probability_pct=STORM_PCT)

    _destination(facts, "forecast", forecast)


def _sow_hot(facts: AdvisoryFacts) -> None:
    def forecast(d: dict) -> None:
        for day in d["days"]:
            day.update(high_c=HOT_HIGH_C, low_c=30)

    _destination(facts, "forecast", forecast)


def apply(name: str, facts: AdvisoryFacts) -> AdvisoryFacts:
    """A copy of `facts` with scenario `name` applied on a calm baseline."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    facts = AdvisoryFacts(facts.kind, dict(facts.subject), list(facts.sections),
                          facts.collected_at)

    if name == "no_data":
        facts.sections = [FactSection(s.role, s.kind, False, reason="no data (eval scenario)")
                          for s in facts.sections]
        return facts

    _calm(facts)
    if name == "clear_window":
        _replace(facts, FactSection("destination", "window", True, dict(WINDOW),
                                    source="weather_intelligence", is_live=False))
    elif name == "rain_showers":
        _rain_showers(facts)
    elif name == "strong_wind":
        _strong_wind(facts)
    elif name == "thunderstorm_metar":
        _thunderstorm_metar(facts)
    elif name == "red_warning":
        _replace(facts, _warning("destination", "red"))
    elif name == "orange_warning":
        _replace(facts, _warning("destination", "orange"))
    elif name == "warnings_off":
        for role in {s.role for s in facts.sections if s.kind == "warnings"}:
            _drop(facts, role, "warnings", "warnings feed unavailable")
    elif name == "sow_too_wet":
        _sow_wet(facts)
    elif name == "sow_too_hot":
        _sow_hot(facts)
    elif name == "sow_no_forecast":
        for kind in ("forecast", "hourly", "rain"):
            _drop(facts, "location", kind, "forecast unavailable (eval scenario)")
    elif name == "crop_missing":
        pass  # the collector's own state: no crop file yet
    if facts.kind == "farming" and name not in ("crop_missing",):
        crop, region = facts.subject.get("crop"), facts.subject.get("district")
        _replace(facts, FactSection("crop", "entry", True,
                                    {"crop": crop, "region": region, **CROP_FIXTURE},
                                    source=CROP_FIXTURE["source"], is_live=False))
    return facts


def build(kind: str, slots: dict, scenario: str) -> AdvisoryFacts:
    """Collect real fixture facts for `slots`, then apply `scenario`."""
    collector = {"travel": facts_module.TravelFactsCollector,
                 "farming": facts_module.FarmingFactsCollector}[kind]()
    return apply(scenario, collector.collect(slots))
