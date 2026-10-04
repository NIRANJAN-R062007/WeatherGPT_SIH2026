"""TFA-4: the facts-collector interface travel and farming both implement.

A collector turns already-resolved slots (cities, day, crop — slot parsing and
ask-back are TFA-3, not here) into one typed `AdvisoryFacts`: the sections of
weather / forecast / METAR+TAF / warnings / crop data the answer may quote,
each saying where it came from and whether it exists at all. The model never
supplies a fact of its own (§11.6); whatever it cites must trace to
`AdvisoryFacts.raw()`, which is the dict `guardrail.check()` indexes.

Missing data is a first-class state, not a gap: a source that has nothing
yields an unavailable section with a reason, and `raw()` leaves it out so a
narration citing it fails grounding — "not available", never fair weather
(plan.md §2 principle 3). The gatherers below only wrap what the stack already
has (weather_data, aviation, imd_warnings); they add no data source.

The two concrete collectors are deliberately minimal — origin and destination
city only for travel, one district for farming. Route legs and the airports
along them are TFA-6; the crop file (TFA-9) is read through `crop_lookup`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import aviation
import cities
import imd_warnings
import weather_data
from google_weather import FORECAST_DAYS
from weather_intelligence import rules
from weather_intelligence.window_analyzer import find_best_window

from advisory import crops

_LOG = logging.getLogger("weathergpt.advisory")

_DAY_OFFSET = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}


@dataclass(frozen=True)
class FactSection:
    """One block of facts: `role` is who it is about ("origin", "destination",
    "location", "crop"), `kind` is what it is ("current", "forecast", "hourly",
    "aviation", "warnings", ...). `data` is the source's own decoded dict —
    never reworded — and is None exactly when `available` is False."""

    role: str
    kind: str
    available: bool
    data: dict | None = None
    source: str | None = None
    is_live: bool | None = None
    reason: str | None = None  # why it is unavailable

    @property
    def name(self) -> str:
        return f"{self.role}.{self.kind}"


@dataclass
class AdvisoryFacts:
    """Everything one advisory answer may cite. `subject` echoes the slots the
    facts were collected for."""

    kind: str  # "travel" | "farming"
    subject: dict
    sections: list[FactSection]
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def raw(self) -> dict:
        """`{role: {kind: data}}` for the available sections only — what the
        grounding guardrail indexes. An unavailable section is absent on
        purpose, so a number or time quoted from it never grounds."""
        out: dict[str, dict] = {}
        for s in self.sections:
            if s.available:
                out.setdefault(s.role, {})[s.kind] = s.data
        return out

    def missing(self) -> list[dict]:
        """The unavailable sections and why — for the answer's "not available"
        wording and for the rule table to refuse to guess."""
        return [{"section": s.name, "reason": s.reason} for s in self.sections if not s.available]

    def section(self, role: str, kind: str) -> FactSection | None:
        return next((s for s in self.sections if s.role == role and s.kind == kind), None)

    def provenance(self) -> list[dict]:
        return [
            {"section": s.name, "source": s.source, "is_live": s.is_live}
            for s in self.sections if s.available
        ]

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "collected_at": self.collected_at,
            "facts": self.raw(),
            "missing": self.missing(),
            "provenance": self.provenance(),
        }


# --- gatherers: one per existing source --------------------------------------


def _unavailable(role: str, kind: str, reason: str) -> FactSection:
    return FactSection(role, kind, False, reason=reason)


def _gather(role: str, kind: str, fetch: Callable[[], dict | None], reason: str) -> FactSection:
    """Run one source call. None means the source has nothing; an exception is
    a source failure. Both become an unavailable section — a collector never
    raises because one source is down."""
    try:
        data = fetch()
    except Exception:  # noqa: BLE001 — any one source failing must not sink the rest
        _LOG.warning("advisory source %s.%s failed", role, kind, exc_info=True)
        return _unavailable(role, kind, "source error")
    if data is None:
        return _unavailable(role, kind, reason)
    return FactSection(role, kind, True, data, source=data.get("source"),
                       is_live=data.get("is_live"))


def current_weather(role: str, city: str) -> FactSection:
    return _gather(role, "current",
                   lambda: weather_data.get_weather(city, "current_weather", "today"),
                   "no current conditions")


def daily_forecast(role: str, city: str, day: str) -> FactSection:
    offset = _DAY_OFFSET.get(day)
    if offset is None:
        return _unavailable(role, "forecast", f"unsupported day {day!r}")
    return _gather(role, "forecast", lambda: weather_data.forecast_day(city, offset),
                   f"no forecast for {day}")


def multi_day_forecast(role: str, city: str, days: int = FORECAST_DAYS) -> FactSection:
    return _gather(role, "forecast", lambda: weather_data.multi_day_facts(city, days),
                   "no multi-day forecast")


def hourly_forecast(role: str, city: str, day: str) -> FactSection:
    return _gather(role, "hourly", lambda: weather_data.hourly_facts(city, day),
                   f"no hourly forecast for {day}")


def rain_so_far(role: str, city: str) -> FactSection:
    return _gather(role, "rain", lambda: weather_data.rain_so_far(city), "no rainfall history")


def aviation_reports(role: str, city: str) -> FactSection:
    """METAR + TAF for the city's airport, if it has one."""
    def fetch() -> dict | None:
        station = aviation.station_for(city)
        if station is None:
            return None
        result = aviation.public(station)
        if result["status"] != "ok":
            return None
        parts = [p for p in (result["metar"], result["taf"]) if p]
        # aviation.public() carries per-report sources; the section's own is the feed.
        return {**result, "source": aviation.SOURCE,
                "is_live": all(p["is_live"] for p in parts)}

    return _gather(role, "aviation", fetch, "no METAR/TAF available")


def warnings(role: str, city: str) -> FactSection:
    """The city's IMD warning. The feed being off is *unavailable*, not an
    all-clear; a green "nothing in force" is still returned, as a checked clear."""
    def fetch() -> dict | None:
        verdict = imd_warnings.public(city, "en")
        warning = verdict["warning"]
        if warning is None:
            return None
        return {"status": verdict["status"], **warning,
                "is_live": warning["source"] != "fixture"}

    return _gather(role, "warnings", fetch, "warnings feed unavailable")


# (crop, region) -> the sourced crop file's entry, or None when the crop/region
# isn't covered (advisory/crops.py; the file itself is TFA-9). Until the file
# exists no crop is, and the section says so rather than letting a model fill
# the gap from memory.
crop_lookup: Callable[[str, str], dict | None] = crops.lookup


def crop_entry(crop: str, region: str) -> FactSection:
    return _gather("crop", "entry", lambda: crop_lookup(crop, region),
                   "crop/region not in the sourced crop file")


# --- the interface ------------------------------------------------------------


class FactsCollector(ABC):
    """What travel and farming each implement. `collect()` never raises for
    missing data and never invents any: it returns whatever sections the
    sources could fill, the rest marked unavailable."""

    kind: str

    @abstractmethod
    def sections(self, slots: dict) -> list[FactSection]:
        """The sections this feature needs for `slots` (already resolved)."""

    def collect(self, slots: dict) -> AdvisoryFacts:
        return AdvisoryFacts(self.kind, dict(slots), self.sections(slots))


class TravelFactsCollector(FactsCollector):
    """slots: `origin`, `destination` (city keys), `day` ("today"/"tomorrow"/
    "day_after_tomorrow", default today) and optional `mode`. METAR/TAF are
    gathered for flights, or when no mode is given."""

    kind = "travel"

    def sections(self, slots: dict) -> list[FactSection]:
        day = slots.get("day", "today")
        flying = slots.get("mode") in (None, "flight")
        out: list[FactSection] = []
        for role in ("origin", "destination"):
            city = cities.resolve(slots.get(role), travel=True)
            if city is None:
                out.append(_unavailable(role, "location", f"unknown {role} {slots.get(role)!r}"))
                continue
            out += [
                current_weather(role, city),
                daily_forecast(role, city, day),
                hourly_forecast(role, city, day),
                warnings(role, city),
            ]
            if flying:
                out.append(aviation_reports(role, city))
        return out


class FarmingFactsCollector(FactsCollector):
    """slots: `district` (city key), `crop`, and optional `region` for the crop
    file (defaults to the district). The forecast is the multi-day one, since a
    sowing window is judged over days, plus today's hourly series and rainfall
    to date."""

    kind = "farming"

    def sections(self, slots: dict) -> list[FactSection]:
        city = cities.resolve(slots.get("district"))
        if city is None:
            out = [_unavailable("location", "location",
                                f"unknown district {slots.get('district')!r}")]
        else:
            out = [
                multi_day_forecast("location", city),
                hourly_forecast("location", city, "today"),
                rain_so_far("location", city),
                warnings("location", city),
            ]
        crop = slots.get("crop")
        if not crop:
            entry = _unavailable("crop", "entry", "no crop given")
        else:
            entry = crop_entry(crop, slots.get("region") or slots.get("district") or "")
        out.append(entry)
        hourly = next((s for s in out if s.kind == "hourly"), None)
        out.append(sowing_window(entry, hourly))
        return out


def sowing_window(entry: FactSection, hourly: FactSection | None) -> FactSection:
    """TFA-11: today's best contiguous hours by the crop's own thresholds
    (rules.crop_thresholds over the window engine), or unavailable with the
    reason — never the least-bad hours, and never on generic thresholds."""
    thresholds = rules.crop_thresholds(entry.data if entry.available else None)
    if thresholds is None:
        return _unavailable("location", "window", "no crop thresholds to score hours against")
    if hourly is None or not hourly.available:
        return _unavailable("location", "window", "no hourly forecast for today")
    found = find_best_window(hourly.data["hours"], thresholds)
    if found is None:
        return _unavailable("location", "window", "no hour today meets the crop's thresholds")
    data = {k: found[k] for k in ("start_local", "end_local", "avg_temp_c",
                                  "max_rain_probability_pct", "max_wind_kmh")}
    data.update(source=hourly.source, is_live=hourly.is_live)
    return FactSection("location", "window", True, data, source=hourly.source,
                       is_live=hourly.is_live)
