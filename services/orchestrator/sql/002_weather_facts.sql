-- Durable history of every live Google Weather API snapshot the orchestrator
-- fetches (plan.md §8 Phase 1).
--
-- This file is now the single definition of the table: weather_store.py used
-- to carry a second, hand-synced copy of the same CREATE TABLE inline in
-- _ensure_schema(), which could drift from this one silently. _ensure_schema()
-- now executes these files directly, so there is one source of truth and
-- `psql -f` by hand agrees with what the service creates.
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

-- Retention sweep only ever asks "everything older than <cutoff>", which the
-- composite index above can't serve (it leads with kind). See
-- weather_store.prune() / WEATHER_FACTS_RETENTION_DAYS: this table is
-- append-only and unbounded otherwise, on a Render free plan capped at 1 GB.
CREATE INDEX IF NOT EXISTS weather_facts_created_at_idx
    ON weather_facts (created_at);
