-- The India gazetteer in `cities` (plan.md §8 Phase 1; location.py).
--
-- 003 made `cities` the queryable mirror of the eight demo cities. This adds
-- what a GeoNames-sized gazetteer needs on the same table: the GeoNames
-- place_id that data/cities.json, data/gazetteer/in_places.json.gz and this
-- table all agree on, population (ranking and the ambiguity rule), district
-- and state names per language, and two match columns written at upsert time
-- by weather_store.sync_places():
--   - names_norm: every normalised name, for exact lookup (GIN array index)
--   - names_text: the same names as one plain string, for pg_trgm. A plain
--     column on purpose, not one generated over the JSONB.
-- Additive only: existing rows keep their values and get the defaults until
-- the next sync. Demo rows keep their city key; gazetteer rows are keyed by
-- place_id.
--
-- pg_trgm on this image (postgis/postgis:16-3.4, en_US.utf8) was checked on
-- Tamil, Devanagari and Telugu as well as Latin: vowel signs count as word
-- characters, so trigrams span the whole word. A database with the C locale
-- would split Indic words at every vowel sign. If CREATE EXTENSION fails here
-- (a role without the rights), this file is retried on the next boot and
-- location.py keeps answering from the gazetteer file.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE cities ADD COLUMN IF NOT EXISTS place_id TEXT;
ALTER TABLE cities ADD COLUMN IF NOT EXISTS population BIGINT NOT NULL DEFAULT 0;
ALTER TABLE cities ADD COLUMN IF NOT EXISTS admin1 JSONB NOT NULL DEFAULT '{}';
ALTER TABLE cities ADD COLUMN IF NOT EXISTS admin2 JSONB NOT NULL DEFAULT '{}';
ALTER TABLE cities ADD COLUMN IF NOT EXISTS names_norm TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cities ADD COLUMN IF NOT EXISTS names_text TEXT NOT NULL DEFAULT '';

CREATE UNIQUE INDEX IF NOT EXISTS cities_place_id_idx ON cities (place_id);
CREATE INDEX IF NOT EXISTS cities_names_norm_idx ON cities USING GIN (names_norm);
CREATE INDEX IF NOT EXISTS cities_names_text_trgm_idx ON cities USING GIN (names_text gin_trgm_ops);
