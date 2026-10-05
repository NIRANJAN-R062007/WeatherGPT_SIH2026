"""WIE-9: the baseline store behind forecast change detection.

Every live `forecast_hours` fetch is flattened into one row per forecast hour
and kept two ways: in a small in-process ring (so the comparison works on a
bare `uvicorn main:app` with no database at all) and, off the request path,
in Postgres `forecast_snapshots` (sql/007) through weather_store's worker (so
a restart does not lose the baseline). previous() asks for the most recent
retrieval made BEFORE a given one, which is the forecast the user is being
told has changed.

The committed fixtures are one frozen snapshot, so in WEATHER_MODE=fixtures
there is nothing earlier to compare with. WIE-12: sample() reads a hand-made
earlier forecast per demo city (data/fixtures/forecast_snapshots/, written by
seed_sample_snapshots.py) so change detection can be shown offline. It is
marked `"sample": True` and every answer built on it says so; it is never
used against a live forecast.
"""

import json
import threading
from datetime import datetime, timezone

import cities
import config
import weather_store

KIND = "forecast_snapshot"
# Per cell. The L1 cache refetches a cell at most once per TTL (>= 15 min), so
# eight is a couple of hours of history; the baseline is the newest earlier one.
_MEMORY_PER_CELL = 8

_memory: dict[str, list[dict]] = {}
_lock = threading.Lock()


def normalize_time(value) -> str | None:
    """Any ISO timestamp (or datetime) -> UTC ISO string, so a forecast hour
    from the live payload and the same hour read back from Postgres compare
    equal."""
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _dig(node, path: str):
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def rows_from_payload(payload: dict) -> list[dict]:
    """The raw `forecastHours` payload -> one flat row per hour (the columns
    of sql/007), keyed by the normalised hour start."""
    rows = []
    for h in (payload or {}).get("forecastHours") or []:
        when = normalize_time(_dig(h, "interval.startTime"))
        if when is None:
            continue
        rows.append({
            "forecast_time": when,
            "temp_c": _dig(h, "temperature.degrees"),
            "rain_probability_pct": _dig(h, "precipitation.probability.percent"),
            "wind_kmh": _dig(h, "wind.speed.value"),
            "condition": _dig(h, "weatherCondition.type"),
            "uv_index": _dig(h, "uvIndex"),
        })
    return rows


def record(cell: str, lat: float, lon: float, payload: dict, retrieved_at: str) -> None:
    """Remember one live forecast_hours fetch. Never raises: a broken store
    must not break the fetch that called it."""
    try:
        when = normalize_time(retrieved_at)
        rows = rows_from_payload(payload)
        if when is None or not rows:
            return
        with _lock:
            ring = _memory.setdefault(cell, [])
            if any(s["retrieved_at"] == when for s in ring):
                return
            ring.append({"retrieved_at": when, "hours": {r["forecast_time"]: r for r in rows}})
            ring.sort(key=lambda s: s["retrieved_at"])
            del ring[:-_MEMORY_PER_CELL]
        weather_store.persist(KIND, cell, {
            "latitude": lat, "longitude": lon, "retrieved_at": when, "rows": rows,
        })
    except Exception:
        weather_store._LOG.exception("forecast snapshot not recorded for %s", cell)


def previous(cell: str, before: str) -> dict | None:
    """The latest snapshot of `cell` retrieved strictly before `before`:
    {"retrieved_at": iso, "hours": {forecast_time: row}}, or None when there
    is no earlier one anywhere (never an empty "no change")."""
    cutoff = normalize_time(before)
    if cutoff is None:
        return None
    with _lock:
        earlier = [s for s in _memory.get(cell, []) if s["retrieved_at"] < cutoff]
    if earlier:
        return earlier[-1]
    return weather_store.read_snapshot_before(cell, cutoff)


SAMPLE_DIR = config.FIXTURES_DIR / "forecast_snapshots"


def sample_path(city_key: str):
    return SAMPLE_DIR / f"SAMPLE_previous.{city_key}.json"


def sample(city_key: str, before: str) -> dict | None:
    """WIE-12: the labelled sample baseline for a demo city, shaped like
    previous()'s result plus `"sample": True`, or None when the city has no
    sample or the sample is not earlier than `before`."""
    cutoff = normalize_time(before)
    if city_key not in cities.CITY_KEYS or cutoff is None:
        return None
    path = sample_path(city_key)
    if not path.exists():
        return None
    env = json.loads(path.read_text(encoding="utf-8"))
    when = normalize_time(env["_meta"]["retrieved_at"])
    if when is None or when >= cutoff:
        return None
    return {"retrieved_at": when, "hours": {r["forecast_time"]: r for r in env["rows"]},
            "sample": True}


def clear() -> None:
    """Test seam."""
    with _lock:
        _memory.clear()
