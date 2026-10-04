"""The sourced crop file the sowing advisory reads (plan.md §11.7, TFA-9/TFA-11).

`data/crops/crops.json` is TFA-9's to write (gathered from TNAU/ICAR/KVK/GKMS
documents); its format is defined here and in `data/crops/README.md`. Until the
file exists no crop is covered, and the answer says "not available".

    {"entries": [
      {"crop": "groundnut",            a key of advisory.slots.CROPS
       "region": "madurai",            a district key, or a state slug ("tamil_nadu")
       "reviewed": false,              true only after the agronomy sign-off (§11.9)
       "values": {
         "sowing_months":            {"value": [6, 7], "source": ..., "url": ..., "quote": ...},
         "temp_range_c":             {"value": {"min": 20, "max": 30}, ...},
         "max_rain_probability_pct": {"value": null, ...}}}]}

A value counts only with a non-empty `source` and `quote`: one without either is
treated as not given (null) and logged, never used. Checking each number against
its quote is the validator's job (TFA-10); this module only refuses what is
plainly unsourced. A district entry wins over its state's entry.
`max_rain_probability_pct` is optional: sources rarely give one, and heavy rain
is judged for every crop without it (advisory/rubric.py `HEAVY_RAIN`).
"""

from __future__ import annotations

import calendar
import json
import logging
import re
from pathlib import Path

import cities
import config

from advisory import slots

_LOG = logging.getLogger("weathergpt.advisory")

PATH: Path = config.DATA_DIR / "crops" / "crops.json"
FIELDS = ("sowing_months", "temp_range_c", "max_rain_probability_pct")
SOURCE = "Crop file (data/crops/crops.json)"

_cache: dict = {"key": None, "entries": []}


def state_slug(district: str) -> str | None:
    """"madurai" -> "tamil_nadu": the state a district key belongs to, as an entry
    names it."""
    city = cities.CITIES.get(district)
    name = (city.region or {}).get("en") if city else None
    return re.sub(r"[^a-z]+", "_", name.lower()).strip("_") if name else None


def _sourced(value: dict | None) -> bool:
    return (isinstance(value, dict) and bool(str(value.get("source") or "").strip())
            and bool(str(value.get("quote") or "").strip()))


def _valid(field: str, value) -> bool:
    if field == "sowing_months":
        return (isinstance(value, list) and bool(value)
                and all(isinstance(m, int) and 1 <= m <= 12 for m in value))
    if field == "temp_range_c":
        return (isinstance(value, dict) and all(isinstance(value.get(k), (int, float))
                                                for k in ("min", "max"))
                and value["min"] < value["max"])
    return isinstance(value, (int, float)) and 0 <= value <= 100


def _flatten(entry: dict) -> dict:
    """One file entry -> the facts the advisory may cite. Months become names, so a
    month number is never mistaken for a figure by the guardrail."""
    out: dict = {"crop": entry["crop"], "region": entry["region"],
                 "reviewed": entry.get("reviewed") is True, "sources": []}
    for field in FIELDS:
        given = (entry.get("values") or {}).get(field)
        value = given.get("value") if isinstance(given, dict) else None
        if value is not None and not _sourced(given):
            _LOG.warning("crop file: %s/%s %s has no source or quote; ignored",
                         entry["crop"], entry["region"], field)
            value = None
        if value is not None and not _valid(field, value):
            _LOG.warning("crop file: %s/%s %s is malformed; ignored",
                         entry["crop"], entry["region"], field)
            value = None
        if value is not None and field == "sowing_months":
            value = [calendar.month_name[m] for m in value]
        out[field] = value
        if value is not None:
            out["sources"].append({"field": field, "source": given["source"],
                                   "url": given.get("url"), "quote": given["quote"]})
    out["source"] = SOURCE + ("" if out["reviewed"] else ", not yet reviewed by an agronomist")
    out["is_live"] = False
    return out


def entries() -> list[dict]:
    """The file's usable entries, flattened; reread when the file changes. A missing
    file is the normal state until TFA-9; a malformed one is logged and covers nothing."""
    try:
        key = (str(PATH), PATH.stat().st_mtime_ns)
    except OSError:
        return []
    if _cache["key"] != key:
        try:
            raw = json.loads(PATH.read_text(encoding="utf-8"))
            found = [_flatten(e) for e in raw["entries"]
                     if isinstance(e, dict) and e.get("crop") in slots.CROPS
                     and isinstance(e.get("region"), str)]
        except (OSError, ValueError, KeyError, TypeError):
            _LOG.exception("crop file %s is unreadable; no crop is covered", PATH)
            found = []
        _cache.update(key=key, entries=found)
    return _cache["entries"]


def lookup(crop: str, region: str) -> dict | None:
    """The entry for `crop` in `region` (a district key; its state's entry is the
    fallback), or None when the file does not cover it."""
    by_region = {e["region"]: e for e in entries() if e["crop"] == crop}
    for key in (region, state_slug(region)):
        if key and key in by_region:
            return by_region[key]
    return None
