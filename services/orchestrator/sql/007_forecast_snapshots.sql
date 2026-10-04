-- WIE-9: the read side of forecast change detection (plan.md §15).
--
-- weather_facts keeps raw JSON as a write-only audit log. Change detection
-- has to ask "what did the forecast for 3 PM say the last time we looked?",
-- so every live forecast_hours fetch is also flattened into one row per
-- forecast hour here. `city` is the cache cell key (the same key
-- weather_facts uses, e.g. "pt:13.10,80.25"); latitude/longitude record the
-- point the forecast was fetched for.
--
-- Written off the request path by weather_store.py's worker. A plain table:
-- nothing here needs TimescaleDB, and the retention sweep (weather_store.
-- prune(), WEATHER_FACTS_RETENTION_DAYS) keeps it from growing without bound.

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    id BIGSERIAL PRIMARY KEY,
    city TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    forecast_time TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    temp_c DOUBLE PRECISION,
    rain_probability_pct DOUBLE PRECISION,
    wind_kmh DOUBLE PRECISION,
    condition TEXT,
    uv_index DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS forecast_snapshots_lookup_idx
    ON forecast_snapshots (city, forecast_time, retrieved_at DESC);

-- "latest retrieval before T" and the retention sweep both filter on
-- retrieved_at alone or after city.
CREATE INDEX IF NOT EXISTS forecast_snapshots_retrieved_idx
    ON forecast_snapshots (retrieved_at);
