"""Google Weather API client: fetch, decode, cache, and fall back to fixtures.

Replaces the hardcoded stub in weather_data.py's data path.

- TTL cache (plan.md §5): current conditions 15 min, daily forecast 6 h.
- L1 is an in-memory module dict, checked first — zero network, so a single
  --workers=1 uvicorn process (the local/offline demo shape) never needs
  Redis reachable at all. Running with --workers > 1 gives each worker its
  own L1 and multiplies API calls between them, same as before.
- L2 is Redis (weather_store.py), shared across workers/replicas/restarts —
  provisioned for real in Render (render.yaml) and k8s (k8s/base/redis.yaml)
  as of plan.md §8 Phase 1, not just docker-compose's dev-only container.
  Both L1 and L2 are best-effort: a dead/unreachable Redis is caught and
  logged inside weather_store.py, never raised, so this stays safe to run
  anywhere Redis isn't (yet) provisioned. Live snapshots are also handed to
  weather_store.persist() for the Postgres audit log — enqueue-only, written
  by its worker thread, so a dead Postgres costs the request nothing.
- On any live-call failure (timeout, non-200, no key) the committed snapshots
  in data/fixtures/google_weather/ are replayed, so the demo needs no network
  (plan.md §2.5 offline-degradable, R5 venue-wifi). Only live results are
  cached; a fixture fallback is not, so the next call retries the network.

config.WEATHER_MODE: "auto" (default) | "live" (no fallback, fail loud) |
"fixtures" (never touch the network — the demo-morning kill switch).
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import cities
import config
import httpx
import weather_store

ENDPOINTS = {
    "current_conditions": "currentConditions:lookup",
    "forecast_hours": "forecast/hours:lookup",
    "forecast_days": "forecast/days:lookup",
    "history_hours": "history/hours:lookup",
}
TTL_SECONDS = {
    "current_conditions": 900, "forecast_hours": 3600,
    "forecast_days": 21600, "history_hours": 3600,
}
FORECAST_DAYS = 5
FORECAST_HOURS = 24
HISTORY_HOURS = 24
TIMEOUT = 10.0

_monotonic = time.monotonic  # test seam
_LOG = logging.getLogger("weathergpt.google_weather")

_FIXTURE_DIR = config.FIXTURES_DIR / "google_weather"
_DECODER_DIR = config.DATA_DIR / "decoders"

_CACHE: dict[tuple[str, str], tuple[float, "Snapshot"]] = {}
_FIXTURE_CACHE: dict[tuple[str, str], dict] = {}
_DECODERS: dict[str, dict] = {}


@dataclass(frozen=True)
class Snapshot:
    kind: str
    city: str
    payload: dict
    is_live: bool
    retrieved_at: str
    source: str


def fetch_json(path: str, params: dict, timeout: float = TIMEOUT) -> dict:
    """The one outbound HTTP call. Tests monkeypatch THIS, never httpx itself."""
    resp = httpx.get(f"{config.GOOGLE_WEATHER_BASE}/{path}", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _redacted(exc: BaseException) -> str:
    """httpx puts the full request URL — key= included — in its error text."""
    text = f"{type(exc).__name__}: {exc}"
    key = config.GOOGLE_WEATHER_API_KEY
    return text.replace(key, "REDACTED") if key else text


def _params(kind: str, city_key: str) -> dict:
    city = cities.CITIES[city_key]
    key = config.require("GOOGLE_WEATHER_API_KEY", config.GOOGLE_WEATHER_API_KEY)
    params = {
        "location.latitude": city.lat,
        "location.longitude": city.lon,
        "unitsSystem": "METRIC",
        "key": key,
    }
    if kind == "forecast_days":
        params["days"] = FORECAST_DAYS
    if kind == "forecast_hours":
        params["hours"] = FORECAST_HOURS
    if kind == "history_hours":
        params["hours"] = HISTORY_HOURS
    return params


def _live(kind: str, city_key: str) -> Snapshot:
    payload = fetch_json(ENDPOINTS[kind], _params(kind, city_key))
    return Snapshot(
        kind=kind,
        city=city_key,
        payload=payload,
        is_live=True,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source="Google Weather API (live)",
    )


def _fixture(kind: str, city_key: str) -> Snapshot | None:
    cache_key = (kind, city_key)
    env = _FIXTURE_CACHE.get(cache_key)
    if env is None:
        path = _FIXTURE_DIR / f"{kind}.{city_key}.json"
        if not path.exists():
            return None
        env = json.loads(path.read_text(encoding="utf-8"))
        _FIXTURE_CACHE[cache_key] = env
    retrieved_at = env["_meta"]["retrieved_at"]
    return Snapshot(
        kind=kind,
        city=city_key,
        payload=env["response"],
        is_live=False,
        retrieved_at=retrieved_at,
        source=f"Google Weather API (snapshot {retrieved_at[:10]}, not live)",
    )


def snapshot(kind: str, city_key: str, *, force_refresh: bool = False) -> Snapshot | None:
    if kind not in ENDPOINTS or city_key not in cities.CITY_KEYS:
        return None

    if config.WEATHER_MODE == "fixtures":
        return _fixture(kind, city_key)

    cache_key = (kind, city_key)
    if not force_refresh:
        cached = _CACHE.get(cache_key)
        if cached and _monotonic() - cached[0] < TTL_SECONDS[kind]:
            return cached[1]

        # L2: Redis, shared across processes/replicas and survives a restart
        # the in-memory dict wouldn't. Populates L1 so the next call in this
        # process skips Redis entirely.
        remote = weather_store.redis_get(kind, city_key)
        if remote is not None:
            snap = Snapshot(kind=kind, city=city_key, **remote)
            _CACHE[cache_key] = (_monotonic(), snap)
            return snap

    try:
        snap = _live(kind, city_key)
    except (httpx.HTTPError, config.ConfigError, ValueError, KeyError) as exc:
        if config.WEATHER_MODE == "live":
            raise
        _LOG.warning("live %s for %s failed (%s); replaying fixture",
                     kind, city_key, _redacted(exc))
        return _fixture(kind, city_key)

    _CACHE[cache_key] = (_monotonic(), snap)
    fields = {"payload": snap.payload, "is_live": snap.is_live,
              "retrieved_at": snap.retrieved_at, "source": snap.source}
    weather_store.redis_set(kind, city_key, fields, TTL_SECONDS[kind])
    weather_store.persist(kind, city_key, fields)  # enqueue only; the INSERT is off-thread
    return snap


def cache_clear() -> None:
    _CACHE.clear()
    _FIXTURE_CACHE.clear()


def cache_stats() -> dict:
    live = sum(1 for _, snap in _CACHE.values() if snap.is_live)
    return {"entries": len(_CACHE), "live": live, "snapshot": len(_CACHE) - live}


def load_decoder(name: str) -> dict:
    table = _DECODERS.get(name)
    if table is None:
        table = json.loads((_DECODER_DIR / f"{name}.json").read_text(encoding="utf-8"))["map"]
        _DECODERS[name] = table
    return table


def decode_condition(raw_type: str | None) -> str:
    if not raw_type:
        return "unknown"
    mapped = load_decoder("weather_conditions").get(raw_type)
    if mapped:
        return mapped
    _LOG.info("unmapped weatherCondition.type %r; using %s", raw_type, raw_type.lower())
    return raw_type.lower()


def decode_cardinal(raw: str | None) -> str:
    if not raw:
        return ""
    return load_decoder("wind_cardinals").get(raw, "")
