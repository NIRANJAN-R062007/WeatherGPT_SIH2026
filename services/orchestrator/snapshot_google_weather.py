"""Snapshot real Google Weather API responses into data/fixtures/google_weather/.

Doubles as the key verifier: a clean run proves GOOGLE_WEATHER_API_KEY works.
The ingestion module (services/ingestion/google_weather/) can then be built and
tested against these committed fixtures with no key and no network.

    python services/orchestrator/snapshot_google_weather.py --city all
    python services/orchestrator/snapshot_google_weather.py --city chennai --dry-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone

import config
import httpx
from google_weather import ENDPOINTS, FORECAST_DAYS, FORECAST_HOURS, HISTORY_HOURS

CITIES_PATH = config.DATA_DIR / "cities.json"
OUT_DIR = config.FIXTURES_DIR / "google_weather"

_HINTS = {
    403: "403 — if the message mentions SERVICE_BLOCKED the Weather API is not "
    "enabled on the Cloud project; if it mentions referrers the key has an "
    "HTTP-referrer restriction (server-side calls need None or an IP restriction).",
    400: "400 — key is invalid, malformed, or rotated.",
    429: "429 — quota exceeded; back off. Caching (§5 TTLs) is the Day 2 answer.",
    401: "401 — key rejected. Check GOOGLE_WEATHER_API_KEY in .env.",
}


def _load_cities():
    data = json.loads(CITIES_PATH.read_text(encoding="utf-8"))
    return {c["key"]: c for c in data["cities"]}


def fetch(path: str, lat: float, lon: float, **params) -> tuple[int, dict]:
    key = config.require("GOOGLE_WEATHER_API_KEY", config.GOOGLE_WEATHER_API_KEY)
    query = {"location.latitude": lat, "location.longitude": lon, "key": key, **params}
    resp = httpx.get(f"{config.GOOGLE_WEATHER_BASE}/{path}", params=query, timeout=10)
    try:
        body = resp.json()
    except ValueError:
        body = {"_raw": resp.text}
    return resp.status_code, body


def _envelope(name: str, endpoint: str, city: str, lat: float, lon: float,
              params: dict, status: int, body: dict) -> dict:
    return {
        "_meta": {
            "endpoint": endpoint,
            "request": {"location.latitude": lat, "location.longitude": lon,
                        "key": "REDACTED", **params},
            "city": city,
            "http_status": status,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "produced_by": "services/orchestrator/snapshot_google_weather.py",
        },
        "response": body,
    }


def snapshot(city_key: str, cities: dict, *, days: int, units: str,
             force: bool, dry_run: bool, kind: str = "all") -> list[tuple]:
    c = cities[city_key]
    lat, lon = c["lat"], c["lon"]
    rows = []
    for name, endpoint in ENDPOINTS.items():
        if kind != "all" and name != kind:
            continue
        extra = {"unitsSystem": units}
        if name == "forecast_days":
            extra["days"] = days
        if name == "forecast_hours":
            extra["hours"] = FORECAST_HOURS
        if name == "history_hours":
            extra["hours"] = HISTORY_HOURS
        status, body = fetch(endpoint, lat, lon, **extra)
        env = _envelope(name, endpoint, city_key, lat, lon, extra, status, body)

        key = config.GOOGLE_WEATHER_API_KEY or ""
        blob = json.dumps(env, ensure_ascii=False)
        if key and key in blob:
            raise SystemExit(f"ABORT: API key leaked into {name}.{city_key} payload")

        out = OUT_DIR / f"{name}.{city_key}.json"
        wrote = "-"
        if status == 200 and not dry_run:
            if out.exists() and not force:
                wrote = "exists (use --force)"
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(blob + "\n", encoding="utf-8")
                wrote = str(out.relative_to(config.REPO_ROOT))
        rows.append((city_key, endpoint, status, len(blob), wrote))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--city", default="all",
                    choices=["all", *_load_cities()])
    ap.add_argument("--kind", default="all",
                    choices=["all", "current_conditions", "forecast_hours",
                             "forecast_days", "history_hours"])
    ap.add_argument("--days", type=int, default=FORECAST_DAYS)
    ap.add_argument("--units", default="METRIC")
    ap.add_argument("--force", action="store_true", help="overwrite existing fixtures")
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, do not write")
    args = ap.parse_args()

    cities = _load_cities()
    targets = list(cities) if args.city == "all" else [args.city]

    print(f"key={config.redact(config.GOOGLE_WEATHER_API_KEY)}  "
          f"dry_run={args.dry_run}  out={OUT_DIR.relative_to(config.REPO_ROOT)}\n")
    print(f"{'city':<12}{'endpoint':<28}{'http':<6}{'bytes':<8}output")

    failed = False
    for city_key in targets:
        for city, endpoint, status, size, wrote in snapshot(
            city_key, cities, days=args.days, units=args.units,
            force=args.force, dry_run=args.dry_run, kind=args.kind,
        ):
            print(f"{city:<12}{endpoint:<28}{status:<6}{size:<8}{wrote}")
            if status != 200:
                failed = True
                print(f"    {_HINTS.get(status, 'unexpected status')}")

    if failed:
        print("\nAt least one call failed — fixtures for those are not written.")
        return 1
    print("\nOK" + ("" if args.dry_run else " — fixtures written."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
