"""Apply the data-layer schema by hand (plan.md §8 Phase 1).

The service applies sql/*.sql itself, lazily, on the first durable write — so
nothing *needs* this. It exists for the cases where waiting for that first
write is the wrong shape:

    python migrate.py                 # apply sql/*.sql, report what ran
    python migrate.py --sync-cities   # ... and upsert data/cities.json
    python migrate.py --prune         # ... and run the retention sweep now
    python migrate.py --status        # read-only: what has this DB seen?

Run it from services/orchestrator/ (flat imports, same as main.py), with
DATABASE_URL pointing at the target — a fresh Render deploy, a kubectl
port-forward, or docker-compose's local Postgres.

Unlike the request path, this exits non-zero when something fails: silent
degradation is right for /ask and wrong for an operator asking whether the
database is actually set up.
"""

import argparse
import logging
import sys

import weather_store
from sqlalchemy import text


def _status() -> int:
    with weather_store._engine.connect() as conn:
        applied = {row[0] for row in conn.execute(
            text("SELECT filename FROM schema_migrations")).fetchall()}
        postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar()
    print(f"postgis: {postgis}")
    for path in weather_store.migration_files():
        print(f"{'applied' if path.name in applied else 'PENDING':>8}  {path.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-cities", action="store_true",
                        help="upsert data/cities.json into the cities table")
    parser.add_argument("--prune", action="store_true",
                        help="delete weather_facts rows past the retention window")
    parser.add_argument("--status", action="store_true",
                        help="report applied migrations and PostGIS version, change nothing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        if args.status:
            return _status()

        weather_store._ensure_schema()
        if not weather_store._SCHEMA_READY:
            print("one or more migrations failed — see the log above", file=sys.stderr)
            return 1
        print(f"schema up to date ({len(weather_store.migration_files())} files)")

        if args.sync_cities:
            print(f"synced {weather_store.sync_cities()} cities")
        if args.prune:
            print(f"pruned {weather_store.prune()} weather_facts rows")
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
