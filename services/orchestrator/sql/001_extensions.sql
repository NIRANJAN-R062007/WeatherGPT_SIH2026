-- Postgres extensions the data layer depends on (plan.md §8 Phase 1,
-- "Schema/infra support for the data layer").
--
-- PostGIS is what 003_cities.sql's geography column and the Phase 4 geofence
-- (alert engine: "which cities fall inside this warning polygon") are built
-- on, and it is what services/gateway/main.py's /health probes with
-- SELECT PostGIS_Version(). Nothing created it before this file existed: the
-- docker-compose/k8s `postgis/postgis:16-3.4` image ships the extension
-- pre-created in its default database, which hid the gap locally, but a
-- managed Postgres (Render's `weathergpt-postgres`, render.yaml) starts with
-- a bare `postgres` database and no PostGIS at all.
--
-- Applied by weather_store._ensure_schema() in its own transaction, so a
-- role without CREATE EXTENSION rights costs us PostGIS (logged, and the
-- geography column in 003) but never weather_facts in 002 — the one thing
-- on the demo path.

CREATE EXTENSION IF NOT EXISTS postgis;
