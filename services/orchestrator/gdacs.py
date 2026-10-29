"""GDACS tropical-cyclone events near India: fetch, parse, cache, and fall back
to fixtures (plan.md §3.3, §6 P2 item 11, task CYC-2). The source is GDACS, the
UN / European Commission Global Disaster Awareness and Coordination System. It is
free and needs no key. It is NOT an IMD product: for this region GDACS builds
its events from JTWC / NOAA / Météo-France bulletins, so every result carries
`source` "GDACS" and the attribution GDACS asks for, and nothing here may be
presented as IMD data (plan.md §2). The terms, endpoints and update frequency
used below were verified in CYC-1 (plan.md §8 Phase 5, 2026-10-29).

Like aviation.py, config.WEATHER_MODE decides where events come from: "auto"
(default) fetches live and falls back to the snapshot in
data/fixtures/gdacs/cyclones.json when the fetch fails; "live" never falls
back; "fixtures" (and OFFLINE_MODE) never touch the network. A live result is
cached for TTL_SECONDS (GDACS refreshes its feeds every 6 minutes); a fixture
is not cached. After a failed live fetch the network is left alone for
FAILURE_BACKOFF_SECONDS, because GDACS can hang or answer HTTP 400 when its own
backend is overloaded, and retrying on every request would stall each caller.
Every result says whether it is live, and a snapshot is dated by when it was
taken.

A failed fetch is never an empty list. `public()` answers status "unavailable"
with `events` None when nothing could be read, and "no cyclones" may only be
said when `no_cyclones_confirmed()` is true: a live, complete, successful
answer with no event near India. A snapshot can never confirm that, and neither
can an answer holding any feature we could not read: it might have been a
cyclone, so it is counted in `unreadable_features` and `complete` is False.

"Near India" is a geographic test, not just GDACS's country tag, because many
events carry no `iso3` until GDACS expects an effect on a country. An event is
kept when its position is inside INDIA_BOX (our own North Indian Ocean box,
applied to the GeoJSON Point GDACS documents), OR its `iso3` is IND, OR India is
in its `affectedcountries`; `matched_by` says which. The documented
`eventsbyarea` endpoint was not used: on 2026-10-29 it took 26 s, returned every
hazard type and covers at most 30 days, against about 2 s for `SEARCH`.

The fetch host is fixed (www.gdacs.org, https only, no redirects followed) and
every request URL is built from our own constants and integer ids that were
parsed out of a response — never from a caller's text. Responses are read in a
stream and dropped past MAX_BYTES, and one refresh has a total time budget.

Alert levels are passed through exactly as GDACS gives them (`alert_level`
"Green" / "Orange" / "Red" with `alert_score` 1 / 2 / 3 were observed); mapping
them to canonical keys for the five-language layer is the decoder's job (CYC-3).

`python gdacs.py` (from this directory) refreshes the fixture from the live
service.
"""

import copy
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import httpx

_LOG = logging.getLogger("weathergpt.gdacs")

HOST = "www.gdacs.org"
API_BASE = f"https://{HOST}/gdacsapi/api"
SOURCE = "GDACS"
#: The wording GDACS's API quick-start asks us to acknowledge the source with.
SOURCE_NAME = "Global Disaster Awareness and Coordination System, GDACS"
SOURCE_URL = f"https://{HOST}/"
TERMS_URL = f"https://{HOST}/documents/2025/GDACS_Terms_of_use_Mar_25.pdf"
ATTRIBUTION = f"Cyclone data: {SOURCE_NAME}. Not an IMD product."
DISCLAIMER = ("GDACS cyclone alerts are produced automatically, are not reviewed by human "
              "experts and do not replace official warnings. Follow IMD and your state "
              "disaster authority.")

#: North Indian Ocean and the subcontinent: Arabian Sea, Bay of Bengal, Sri Lanka,
#: Lakshadweep, Andaman and Nicobar. (lon_min, lon_max, lat_min, lat_max), inclusive.
#: Our own choice, not a GDACS-defined region.
INDIA_BOX = (55.0, 100.0, 0.0, 30.0)
INDIA_ISO3 = "IND"

LOOKBACK_DAYS = 14
PAGE_SIZE = 100            # GDACS returns at most 100 records per call
MAX_PAGES = 3
MAX_TRACKS = 5             # events whose track/geometry we fetch per refresh
TIMEOUT = 10.0             # per network operation, seconds
DEADLINE_SECONDS = 30.0    # total budget for one refresh (all requests together)
MAX_BYTES = 2_000_000      # cap on one response body, after decompression
MAX_FEATURES = 500         # cap on features read from one document
MAX_POINTS = 5000          # cap on coordinates read from one geometry
MAX_ID = 2**53             # event / episode ids must be smaller (exact in JavaScript too)
TTL_SECONDS = 600          # live results are cached this long (GDACS refreshes every 6 min)
#: After a failed live fetch the network is left alone this long. GDACS has been seen
#: to hang for 40+ s and to answer HTTP 400 "connection pool exhausted" (2026-10-29);
#: retrying on every request would stall each caller and add load while it struggles.
FAILURE_BACKOFF_SECONDS = 60

_CACHE: dict[str, tuple[float, "Snapshot"]] = {}
_BACKOFF = {"until": 0.0}  # time.monotonic() before which no new live fetch is tried
_monotonic = time.monotonic


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Snapshot:
    #: Events near India, current ones first, newest first. May be empty.
    events: list[dict]
    is_live: bool
    #: When this data was fetched (a fixture's own date when it is a fixture).
    retrieved_at: str
    #: False when the search stopped at MAX_PAGES with more records left, or when
    #: any feature could not be read (see `unreadable`).
    complete: bool
    #: Features that were neither read as a cyclone nor recognisably another hazard,
    #: plus any past MAX_FEATURES. Each might have been a cyclone near India.
    unreadable: int = 0


class FetchError(Exception):
    """A response that cannot be used: too large, too slow, not the JSON shape
    GDACS documents."""


# --- fetching -----------------------------------------------------------------


def _get_json(path: str, params: dict, deadline: float) -> dict:
    if _monotonic() > deadline:  # don't even start another request past the budget
        raise FetchError("time budget for one refresh used up")
    url = f"{API_BASE}/{path}"
    with httpx.stream("GET", url, params=params, timeout=TIMEOUT, follow_redirects=False) as resp:
        resp.raise_for_status()  # a redirect is an error too: we never follow one
        declared = resp.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BYTES:
            raise FetchError(f"response of {declared} bytes is over the {MAX_BYTES} cap")
        body = bytearray()
        for chunk in resp.iter_bytes():
            if _monotonic() > deadline:
                raise FetchError("time budget for one refresh used up")
            body += chunk
            if len(body) > MAX_BYTES:
                raise FetchError(f"response is over the {MAX_BYTES} byte cap")
    try:
        doc = json.loads(bytes(body))
    except (ValueError, RecursionError) as exc:  # RecursionError: absurdly nested JSON
        raise FetchError("response is not JSON") from exc
    if not isinstance(doc, dict):
        raise FetchError("response is not a JSON object")
    return doc


def _search_params(day_from, day_to, page: int) -> dict:
    return {
        "eventlist": "TC",
        "alertlevel": "red;orange;green",
        "fromdate": day_from.isoformat(),
        "todate": day_to.isoformat(),
        "pageSize": PAGE_SIZE,
        "pageNumber": page,
    }


def _fetch_raw(now: datetime) -> dict:
    """The raw GDACS documents behind one refresh, in the shape the fixture is
    saved in. Raises httpx.HTTPError or FetchError when the event search fails;
    a failed track fetch only leaves that event without a track."""
    deadline = _monotonic() + DEADLINE_SECONDS
    # One day past today: GDACS filters on dates, and it is not documented whether a
    # storm formed later today counts as inside a window that ends today. The extra
    # day costs nothing; a missed new storm would read as "no cyclones".
    day_to = now.date() + timedelta(days=1)
    day_from = now.date() - timedelta(days=LOOKBACK_DAYS)

    features: list = []
    complete = False
    for page in range(1, MAX_PAGES + 1):
        doc = _get_json("events/geteventlist/SEARCH", _search_params(day_from, day_to, page),
                        deadline)
        page_features = doc.get("features")
        if not isinstance(page_features, list):
            raise FetchError("event search has no feature list")
        features.extend(page_features)
        if len(page_features) < PAGE_SIZE:
            complete = True
            break
    search = {"type": "FeatureCollection", "features": features}

    geometry: dict[str, dict] = {}
    for event in _events_from(search)[:MAX_TRACKS]:
        if event["episode_id"] is None:
            continue
        if _monotonic() > deadline:
            _LOG.warning("time budget used up; no track for the remaining events")
            break
        params = {"eventtype": "TC", "eventid": event["event_id"],
                  "episodeid": event["episode_id"]}
        try:
            geometry[str(event["event_id"])] = _get_json("polygons/getgeometry", params, deadline)
        except (httpx.HTTPError, FetchError) as exc:
            _LOG.warning("no track for event %s (%s)", event["event_id"], type(exc).__name__)

    return {
        "source": f"{SOURCE_NAME} ({HOST}), snapshot",
        "fetched_at": now.isoformat(timespec="seconds"),
        "request": {"url": f"{API_BASE}/events/geteventlist/SEARCH",
                    "params": _search_params(day_from, day_to, 1)},
        "complete": complete,
        "search": search,
        "geometry": geometry,
    }


# --- parsing ------------------------------------------------------------------


def _finite(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        value = float(x)
    except OverflowError:  # an int too large for a float
        return None
    return value if math.isfinite(value) else None


def _int(x) -> int | None:
    """An id: a real int, small enough to survive a round trip through JavaScript."""
    if isinstance(x, bool) or not isinstance(x, int) or abs(x) >= MAX_ID:
        return None
    return x


def _flag(x) -> bool | None:
    """True / False for a boolean or "true" / "false"; None for anything else, so
    an unexpected value is never read as a definite answer."""
    if isinstance(x, bool):
        return x
    if isinstance(x, str) and x.strip().lower() in ("true", "false"):
        return x.strip().lower() == "true"
    return None


def _text(x, limit: int = 200) -> str | None:
    if not isinstance(x, str):
        return None
    clean = "".join(ch for ch in x if ch.isprintable()).strip()[:limit]
    return clean or None


def _utc_iso(x) -> str | None:
    """GDACS writes UTC times without a zone ("2026-10-26T00:00:00"; checked against
    the same instants in its GMT-labelled RSS feed, CYC-1)."""
    text = _text(x, 40)
    if text is None:
        return None
    try:
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError):  # not a date, or a zone shift past year 1 / 9999
        return None


def _lonlat(pair) -> tuple[float, float] | None:
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return None
    lon, lat = _finite(pair[0]), _finite(pair[1])
    if lon is None or lat is None or not -180 <= lon <= 180 or not -90 <= lat <= 90:
        return None
    return lon, lat


def _iso3(x) -> str | None:
    text = _text(x, 3)
    return text.upper() if text and len(text) == 3 and text.isalpha() else None


def in_india_box(lon: float, lat: float) -> bool:
    lon_min, lon_max, lat_min, lat_max = INDIA_BOX
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def _affected(raw) -> list[dict]:
    out = []
    for item in raw[:50] if isinstance(raw, list) else []:
        if isinstance(item, dict):
            out.append({"iso2": _text(item.get("iso2"), 2), "iso3": _iso3(item.get("iso3")),
                        "name": _text(item.get("countryname"), 80)})
    return out


def parse_event(feature) -> dict | None:
    """One GeoJSON feature from the event search as a flat event, or None when it
    is not a usable tropical-cyclone Point. Never raises."""
    if not isinstance(feature, dict):
        return None
    props, geo = feature.get("properties"), feature.get("geometry")
    if not isinstance(props, dict) or not isinstance(geo, dict):
        return None
    if props.get("eventtype") != "TC" or geo.get("type") != "Point":
        return None
    event_id = _int(props.get("eventid"))
    position = _lonlat(geo.get("coordinates"))
    if event_id is None or event_id <= 0 or position is None:
        return None
    episode_id = _int(props.get("episodeid"))
    severity = props.get("severitydata") if isinstance(props.get("severitydata"), dict) else {}
    episode = "" if episode_id is None else f"&episodeid={episode_id}"
    report = f"https://{HOST}/report.aspx?eventid={event_id}{episode}&eventtype=TC"
    return {
        "event_id": event_id,
        "episode_id": episode_id,
        "name": _text(props.get("eventname"), 80),
        "title": _text(props.get("name"), 120),
        "glide": _text(props.get("glide"), 40),
        "alert_level": _text(props.get("alertlevel"), 20),
        "alert_score": _finite(props.get("alertscore")),
        "episode_alert_level": _text(props.get("episodealertlevel"), 20),
        "episode_alert_score": _finite(props.get("episodealertscore")),
        "is_current": _flag(props.get("iscurrent")) is True,
        "from_date": _utc_iso(props.get("fromdate")),
        "to_date": _utc_iso(props.get("todate")),
        "date_modified": _utc_iso(props.get("datemodified")),
        "lon": position[0],
        "lat": position[1],
        "country_iso3": _iso3(props.get("iso3")),
        "affected_countries": _affected(props.get("affectedcountries")),
        #: The agency GDACS took the bulletin from (JTWC, NOAA, RSMC ...), not GDACS itself.
        "source_agency": _text(props.get("source"), 40),
        "severity": {
            "value": _finite(severity.get("severity")),
            "unit": _text(severity.get("severityunit"), 20),
            "text": _text(severity.get("severitytext")),
        },
        "report_url": report,
        "track": None,
        "matched_by": [],
        "source": SOURCE,
    }


def india_match(event: dict) -> list[str]:
    """Why an event counts as near India; empty when it does not."""
    why = []
    if in_india_box(event["lon"], event["lat"]):
        why.append("in_area")
    if event["country_iso3"] == INDIA_ISO3:
        why.append("country_iso3")
    if any(c["iso3"] == INDIA_ISO3 for c in event["affected_countries"]):
        why.append("affected_country")
    return why


def _is_other_hazard(feature) -> bool:
    """True for a feature that says, in a readable `eventtype`, that it is not a
    tropical cyclone. Anything else we cannot read might have been one."""
    props = feature.get("properties") if isinstance(feature, dict) else None
    kind = props.get("eventtype") if isinstance(props, dict) else None
    return isinstance(kind, str) and kind.strip().upper() != "TC"


def _read_events(search: dict) -> tuple[list[dict], int]:
    """The events near India in one search document, and how many features could
    not be read. A feature that is dropped without being a recognisable other
    hazard counts, so a cyclone lost to a bad field is never mistaken for none."""
    features = search.get("features")
    features = features if isinstance(features, list) else []
    unreadable = max(0, len(features) - MAX_FEATURES)
    events, seen = [], set()
    for feature in features[:MAX_FEATURES]:
        event = parse_event(feature)
        if event is None:
            if not _is_other_hazard(feature):
                unreadable += 1
            continue
        event["matched_by"] = india_match(event)
        key = (event["event_id"], event["episode_id"])
        if not event["matched_by"] or key in seen:
            continue
        seen.add(key)
        events.append(event)
    events.sort(key=lambda e: (e["date_modified"] or "", e["event_id"]), reverse=True)
    events.sort(key=lambda e: not e["is_current"])  # stable: current events first
    return events, unreadable


def _events_from(search: dict) -> list[dict]:
    return _read_events(search)[0]


def _line(coords) -> list[list[float]] | None:
    if not isinstance(coords, list) or not 2 <= len(coords) <= MAX_POINTS:
        return None
    points = [_lonlat(c) for c in coords]
    return None if None in points else [[lon, lat] for lon, lat in points]


def _rings(coords) -> list[list[list[float]]] | None:
    if not isinstance(coords, list) or not 1 <= len(coords) <= 20:
        return None
    rings = []
    for ring in coords:
        points = _line(ring)
        if points is None or len(points) < 3:
            return None
        rings.append(points)
    return rings if sum(len(r) for r in rings) <= MAX_POINTS else None


def parse_track(doc) -> dict | None:
    """The geometry document of one event (track lines, uncertainty cones, wind
    areas) with GDACS's own labels, or None when it is not that document.
    Features it cannot read are skipped, never guessed.

    `segments` are the track pieces: `category` is GDACS's label (TD / TS / HU ...)
    and `is_forecast` its `forecast` flag (None if absent). `cones` are the
    uncertainty cones. `areas` are the remaining polygons — wind-radius areas
    with GDACS's `Class` (Poly_Green ...), `featuretype` (WindRadii, PointRadii,
    or None) and label (a wind speed or a "dd/mm hh:mm" time). All coordinates
    are [lon, lat]."""
    features = doc.get("features") if isinstance(doc, dict) else None
    if not isinstance(features, list):
        return None
    segments, cones, areas = [], [], []
    polygon_date = None
    for feature in features[:MAX_FEATURES]:
        if not isinstance(feature, dict):
            continue
        geo, props = feature.get("geometry"), feature.get("properties")
        if not isinstance(geo, dict) or not isinstance(props, dict):
            continue
        polygon_date = polygon_date or _utc_iso(props.get("polygondate"))
        kind, label = geo.get("type"), _text(props.get("polygonlabel"), 60)
        if kind == "LineString":
            line = _line(geo.get("coordinates"))
            if line is not None:
                segments.append({"category": label, "is_forecast": _flag(props.get("forecast")),
                                 "coordinates": line})
        elif kind == "Polygon":
            rings = _rings(geo.get("coordinates"))
            if rings is None:
                continue
            if props.get("Class") == "Poly_Cones":
                cones.append({"coordinates": rings})
            else:
                areas.append({"class": _text(props.get("Class"), 40),
                              "feature_type": _text(props.get("featuretype"), 40),
                              "label": label, "coordinates": rings})
    return {"segments": segments, "cones": cones, "areas": areas,
            "polygon_date": polygon_date, "source": SOURCE}


# --- snapshots, modes, cache --------------------------------------------------


def fixture_path() -> Path:
    return config.FIXTURES_DIR / "gdacs" / "cyclones.json"


def _snapshot_from_raw(raw: dict, is_live: bool) -> Snapshot | None:
    """Parse the raw documents of one refresh; None if they are not the shape
    _fetch_raw produces."""
    if not isinstance(raw, dict) or not isinstance(raw.get("search"), dict):
        return None
    if not isinstance(raw["search"].get("features"), list):
        return None
    fetched_at = _utc_iso(raw.get("fetched_at"))
    if fetched_at is None:
        return None
    geometry = raw.get("geometry") if isinstance(raw.get("geometry"), dict) else {}
    events, unreadable = _read_events(raw["search"])
    for event in events:
        doc = geometry.get(str(event["event_id"]))
        event["track"] = parse_track(doc) if doc is not None else None
    return Snapshot(events, is_live, fetched_at,
                    raw.get("complete") is True and unreadable == 0, unreadable)


def _live() -> Snapshot:
    snap = _snapshot_from_raw(_fetch_raw(_utcnow()), True)
    if snap is None:  # _fetch_raw only returns what _snapshot_from_raw accepts
        raise FetchError("unreadable refresh")
    return snap


def _fixture() -> Snapshot | None:
    try:
        raw = json.loads(fixture_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _snapshot_from_raw(raw, False)


def snapshot() -> Snapshot | None:
    """Events near India from the current mode's source, or None when there is
    nothing to show (which is not the same as "no cyclones")."""
    if config.WEATHER_MODE == "fixtures":
        return _fixture()

    now = _monotonic()
    cached = _CACHE.get("events")
    if cached and now - cached[0] < TTL_SECONDS:
        return cached[1]

    if now >= _BACKOFF["until"]:
        try:
            fresh = _live()
        except (httpx.HTTPError, FetchError) as exc:
            _BACKOFF["until"] = _monotonic() + FAILURE_BACKOFF_SECONDS
            _LOG.warning("live GDACS fetch failed (%s: %s); not retrying for %ds",
                         type(exc).__name__, exc, FAILURE_BACKOFF_SECONDS)
        else:
            _CACHE["events"] = (_monotonic(), fresh)
            return fresh

    # The live fetch failed just now, or is being left alone after a recent failure.
    if config.WEATHER_MODE == "live":
        return None  # live mode never replays a snapshot
    return _fixture()


def cache_clear() -> None:
    _CACHE.clear()
    _BACKOFF["until"] = 0.0


def public() -> dict:
    """Cyclone events near India with the source metadata every surface must
    show. `status` is "ok" when GDACS data (live, or a dated snapshot when
    `is_live` is false) was read and "unavailable" when none could be — then
    `events` is None, which a UI must show as "not available", never as "no
    cyclones" (plan.md §2 principle 3). Use no_cyclones_confirmed() before
    saying there are none.

    `unreadable_features` counts search features that could not be read (None
    when unavailable); when it is above zero `complete` is False, though the
    readable events are still returned. A snapshot says so in `notice` (None for
    live data and when unavailable) and on each event's `is_live`, because an
    event's `is_current` only describes the moment the snapshot was taken."""
    snap = snapshot()
    result = {
        "status": "unavailable",
        "events": None,
        "count": None,
        "is_live": False,
        "retrieved_at": None,
        "complete": False,
        "unreadable_features": None,
        "notice": None,
        "source": SOURCE,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "terms_url": TERMS_URL,
        "attribution": ATTRIBUTION,
        "disclaimer": DISCLAIMER,
        "area": {"lon_min": INDIA_BOX[0], "lon_max": INDIA_BOX[1],
                 "lat_min": INDIA_BOX[2], "lat_max": INDIA_BOX[3], "iso3": INDIA_ISO3},
        "window_days": LOOKBACK_DAYS,
    }
    if snap is not None:
        events = copy.deepcopy(snap.events)  # the cache and fixture data stay unmarked
        for event in events:
            event["is_live"] = snap.is_live
        result.update(
            status="ok", events=events, count=len(events),
            is_live=snap.is_live, retrieved_at=snap.retrieved_at, complete=snap.complete,
            unreadable_features=snap.unreadable,
            notice=None if snap.is_live else (
                f"Snapshot taken {snap.retrieved_at}, not live; events may have ended "
                "or changed."),
        )
    return result


def no_cyclones_confirmed(result: dict) -> bool:
    """True only for a live, complete, successful answer with no event near
    India. A failed fetch, a snapshot, a truncated search or one with features
    we could not read (`complete` is then False) never confirms it."""
    return (result.get("status") == "ok" and result.get("is_live") is True
            and result.get("complete") is True and result.get("events") == [])


# --- fixture refresh ----------------------------------------------------------


def write_fixture(path: Path | None = None) -> Path:
    """Fetch the live service and save the raw documents as the fixture. Raises
    when the fetch fails, so a failed refresh never overwrites a good snapshot."""
    target = Path(path) if path is not None else fixture_path()
    raw = _fetch_raw(_utcnow())
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    os.replace(tmp, target)
    return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(write_fixture())
