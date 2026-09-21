-- Durable history of every live Google Weather API snapshot the orchestrator
-- fetches (plan.md §8 Phase 1). weather_store.py runs this same statement
-- itself (idempotent, CREATE ... IF NOT EXISTS) on first write, so applying
-- it by hand is only useful for inspecting the schema or running it via a
-- migration tool later — nothing depends on this file being run manually.
--
-- Write-only, and written off the request path by weather_store.py's worker
-- thread: /ask always reads through google_weather.py's in-memory cache /
-- Redis / live API / fixture chain, never from this table. This is an
-- audit/replay log, not a read cache.

CREATE TABLE IF NOT EXISTS weather_facts (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    city TEXT NOT NULL,
    payload JSONB NOT NULL,
    is_live BOOLEAN NOT NULL,
    source TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS weather_facts_kind_city_idx
    ON weather_facts (kind, city, created_at DESC);
