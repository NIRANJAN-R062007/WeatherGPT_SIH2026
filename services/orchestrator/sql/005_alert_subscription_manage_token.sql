-- Alert subscriptions: per-subscription manage token.
--
-- Ids are sequential (BIGSERIAL), so an id alone must not be enough to
-- delete or list a subscription. POST /alerts/subscribe now mints an
-- unguessable token, returns it once, and stores only its SHA-256 hex
-- digest here. DELETE /alerts/subscribe/{id} and GET /alerts/subscriptions
-- require the token (X-Manage-Token header) and compare it in constant time.
--
-- Rows created before this migration have a NULL hash. Decision: they are
-- KEPT and keep receiving alerts, but a NULL hash never matches any token, so
-- they cannot be deleted or listed through the API. Only an operator with SQL
-- access can remove them (DELETE FROM alert_subscriptions WHERE ...).

ALTER TABLE alert_subscriptions
    ADD COLUMN IF NOT EXISTS manage_token_hash TEXT;
