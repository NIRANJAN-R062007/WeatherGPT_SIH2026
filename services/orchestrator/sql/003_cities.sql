-- The demo-city registry, in the database (plan.md §8 Phase 1).
--
-- data/cities.json stays the source of truth — it is what cities.py loads at
-- import and what the request path answers from, so /ask keeps working with
-- no database at all. This table is the *queryable* copy, kept in sync by
-- weather_store.sync_cities() (idempotent upsert, see also
-- `python migrate.py --sync-cities`).
--
-- Why it exists at all: Phase 4's alert engine (geofence match → push
-- dispatch) has to answer "which cities fall inside this CAP warning
-- polygon / within N km of this cyclone track", which is a spatial query, not
-- something a three-entry Python dict can serve once districts are real. The
-- stack has shipped a PostGIS image since day one (docker-compose.yml,
-- k8s/base/postgres.yaml) with nothing geospatial in it; this is the first
-- thing to actually use it.
--
-- Lat/lon are stored as plain doubles as well as geography on purpose: if
-- 001_extensions.sql could not create PostGIS (a managed role without the
-- rights), this whole file fails and is retried on the next boot — but the
-- columns that a non-spatial fallback would need are defined here, not
-- derived, so nothing is lost by re-running it later.

CREATE TABLE IF NOT EXISTS cities (
    key        TEXT PRIMARY KEY,
    lat        DOUBLE PRECISION NOT NULL,
    lon        DOUBLE PRECISION NOT NULL,
    names      JSONB NOT NULL,
    region     JSONB NOT NULL,
    timezone   TEXT NOT NULL,
    aliases    TEXT[] NOT NULL DEFAULT '{}',
    -- Generated, not written by the app: it cannot drift from lat/lon, and
    -- sync_cities() never has to know PostGIS exists. geography (not
    -- geometry) so ST_DWithin/ST_Distance are metres on a sphere rather than
    -- degrees — the units a "within 50 km of the track" query wants.
    geog       geography(Point, 4326)
                   GENERATED ALWAYS AS (ST_MakePoint(lon, lat)::geography) STORED,
    synced_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cities_geog_idx ON cities USING GIST (geog);
