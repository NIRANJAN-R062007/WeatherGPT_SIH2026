-- Proactive alerts: subscriber registry for the geofence -> push alert
-- engine (plan.md §8 Phase 4, alert_engine.py).
--
-- Two subscription modes, exactly one per row:
--   - city_key set: subscribed directly to a registered city (cities.key) --
--     the common case, since data/cities.json is the whole demo geography.
--   - lat/lon/radius_km set: subscribed to a raw point (device GPS), matched
--     at check time to the nearest registered city within radius_km via
--     cities.geog (see weather_store.nearest_city) -- the ST_DWithin query
--     003_cities.sql's comment says this table exists to serve.
--
-- last_notified_colour/last_notified_at are the engine's dedupe state: a
-- standing alert must not re-fire every poll tick, only on a colour change
-- (new alert, escalation, de-escalation, or clearing).

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id              BIGSERIAL PRIMARY KEY,
    city_key        TEXT,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    radius_km       DOUBLE PRECISION,
    lang            TEXT NOT NULL DEFAULT 'en',
    channel         TEXT NOT NULL,             -- 'webhook' | 'fcm' (fcm not yet implemented)
    target          TEXT NOT NULL,             -- webhook URL, or an FCM device token
    user_id         TEXT,                      -- Supabase user id, if the caller was signed in
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_notified_colour TEXT,
    last_notified_at     TIMESTAMPTZ,
    CONSTRAINT alert_subscriptions_channel_check
        CHECK (channel IN ('webhook', 'fcm')),
    CONSTRAINT alert_subscriptions_location_check
        CHECK (
            (city_key IS NOT NULL AND lat IS NULL AND lon IS NULL AND radius_km IS NULL)
            OR (city_key IS NULL AND lat IS NOT NULL AND lon IS NOT NULL AND radius_km IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS alert_subscriptions_city_idx
    ON alert_subscriptions (city_key) WHERE city_key IS NOT NULL;
