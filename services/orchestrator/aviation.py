"""Airport METAR / TAF: fetch, decode, cache, and fall back to fixtures
(plan.md §3.5, §6 P2 item 10). The source is NOAA's aviationweather.gov data
API, which is free, needs no key, and carries the reports Indian airports
(VOMM, VABB, VIDP, ...) publish; metar.py and taf.py decode them.

Like google_weather.py, config.WEATHER_MODE decides where reports come from:
"auto" (default) fetches live and falls back to the snapshots in
data/fixtures/aviation/ when the fetch fails; "live" never falls back;
"fixtures" (and OFFLINE_MODE) never touch the network. A live report is cached
for config.TTL_METAR / TTL_TAF; a fixture is not, so the next call retries the
network. Every part says whether it is live, and a snapshot is dated by when it
was taken — an old report is never presented as current (plan.md §2).

A station the service answers for is one of the demo cities' airports
(metar.STATIONS): the fetch host and the station ids are always our own, never
a caller's.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import cities
import config
import httpx
import metar
import taf

_LOG = logging.getLogger("weathergpt.aviation")

BASE_URL = "https://aviationweather.gov/api/data"
SOURCE = "aviationweather.gov"
TIMEOUT = 8.0
DISCLAIMER = ("For awareness only, not for flight planning. Use the official AAI / IMD "
              "aviation briefing before flying.")

CITY_STATION = {name.lower(): icao for icao, name in metar.STATIONS.items()}
_DECODERS = {"metar": (metar.decode, metar.briefing), "taf": (taf.decode, taf.briefing)}
_REPORT_START = re.compile(r"(?m)^(?=(?:METAR|SPECI|TAF)\s)")

_CACHE: dict[tuple[str, str], tuple[float, "Report"]] = {}
_monotonic = time.monotonic


@dataclass
class Report:
    raw: str
    is_live: bool
    #: When this text was fetched (a snapshot's own date when it is a fixture).
    retrieved_at: str


def ttl_seconds(kind: str) -> int:
    return config.TTL_METAR if kind == "metar" else config.TTL_TAF


def station_for(city_or_station: str) -> str | None:
    """The ICAO code for a demo city key/name or a known station code."""
    code = city_or_station.strip().upper()
    if code in metar.STATIONS:
        return code
    key = cities.resolve(city_or_station)
    return CITY_STATION.get(key) if key else None


def _first_report(body: str, station: str) -> str | None:
    """The report for `station` out of an API body (a TAF spans several lines)."""
    for block in _REPORT_START.split(body):
        flat = " ".join(block.split())
        if re.match(rf"^(?:METAR|SPECI|TAF)(?:\s+(?:AMD|COR))?\s+{station}\s", flat + " "):
            return flat
    return None


class NoReport(Exception):
    """The service answered: this station has no current report."""


def _live(kind: str, station: str) -> Report:
    resp = httpx.get(
        f"{BASE_URL}/{kind}", params={"ids": station, "format": "raw"}, timeout=TIMEOUT,
    )
    if resp.status_code == 204 or not resp.text.strip():
        raise NoReport(station)
    resp.raise_for_status()
    raw = _first_report(resp.text, station)
    if raw is None:
        raise NoReport(station)
    return Report(raw, True, datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _fixture(kind: str, station: str) -> Report | None:
    path = config.FIXTURES_DIR / "aviation" / f"{station}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = doc.get(kind)
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Report(raw, False, str(doc.get("fetched_at") or ""))


def report(kind: str, station: str) -> Report | None:
    """The current METAR (`kind` "metar") or TAF ("taf") for `station`, or None
    when there is none to show."""
    if config.WEATHER_MODE == "fixtures":
        return _fixture(kind, station)

    cached = _CACHE.get((kind, station))
    if cached and _monotonic() - cached[0] < ttl_seconds(kind):
        return cached[1]

    try:
        fresh = _live(kind, station)
    except NoReport:
        return None  # the service is up and has nothing: an old snapshot would mislead
    except (httpx.HTTPError, ValueError) as exc:
        if config.WEATHER_MODE == "live":
            _LOG.warning("live %s for %s failed (%s); no fallback in live mode", kind, station, exc)
            return None
        _LOG.warning("live %s for %s failed (%s); replaying fixture", kind, station, exc)
        return _fixture(kind, station)

    _CACHE[(kind, station)] = (_monotonic(), fresh)
    return fresh


def cache_clear() -> None:
    _CACHE.clear()


def _part(kind: str, station: str) -> dict | None:
    rep = report(kind, station)
    if rep is None:
        return None
    decode, briefing = _DECODERS[kind]
    try:
        decoded = decode(rep.raw)
    except ValueError as exc:
        _LOG.warning("undecodable %s for %s (%s)", kind, station, exc)
        return None
    return {
        "raw": rep.raw,
        "decoded": decoded,
        "briefing": briefing(decoded),
        "is_live": rep.is_live,
        "retrieved_at": rep.retrieved_at,
        "source": SOURCE,
    }


def public(station: str) -> dict:
    """METAR and TAF for one station. `status` is "ok" when at least one report
    is available and "unavailable" when neither is — which a UI must show as
    "not available", never as fair weather (plan.md §2 principle 3)."""
    parts = {"metar": _part("metar", station), "taf": _part("taf", station)}
    name = metar.STATIONS.get(station)
    return {
        "station": station,
        "station_name": name,
        "city": name.lower() if name else None,
        "status": "ok" if any(parts.values()) else "unavailable",
        **parts,
        "disclaimer": DISCLAIMER,
    }


def issued_iso(part: dict) -> str | None:
    """When the report was observed (METAR) or issued (TAF), as an ISO UTC
    timestamp. Reports carry only day-of-month and UTC time, so the month and
    year come from when the text was fetched: the latest such moment that
    isn't after it."""
    decoded = part["decoded"]
    stamp = decoded.get("observed") or decoded.get("issued")
    try:
        ref = datetime.fromisoformat(part["retrieved_at"])
        hh, mm = (int(x) for x in stamp["time_utc"].split(":"))
        moment = ref.replace(day=stamp["day"], hour=hh, minute=mm, second=0, microsecond=0)
        if moment > ref:  # the report is from last month
            year, month = (ref.year, ref.month - 1) if ref.month > 1 else (ref.year - 1, 12)
            moment = moment.replace(year=year, month=month)
    except (TypeError, ValueError, KeyError):
        return None
    return moment.isoformat(timespec="minutes")


def want_from_text(text: str) -> str:
    """Which report a question asks for: "taf" when it says TAF, "metar" when
    it says METAR, else "both"."""
    if re.search(r"\btaf\b", text, re.IGNORECASE):
        return "taf"
    if re.search(r"\bmetar\b", text, re.IGNORECASE):
        return "metar"
    return "both"


def answer_text(result: dict, want: str = "both") -> str | None:
    """The English text /ask replies with: the requested briefing(s), a note
    when a report is a snapshot rather than live, and the disclaimer. None if
    there is nothing to say."""
    pieces = []
    for kind in ("metar", "taf"):
        part = result.get(kind)
        if part is None or want not in ("both", kind):
            continue
        text = part["briefing"]
        if not part["is_live"]:
            when = part["retrieved_at"][:10] or "an earlier date"
            text = f"Snapshot taken {when}, not a live report. {text}"
        pieces.append(text)
    if not pieces:
        return None
    return " ".join(pieces + [result["disclaimer"]])
