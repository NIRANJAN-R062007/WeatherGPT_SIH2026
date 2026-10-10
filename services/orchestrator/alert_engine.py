"""Proactive alerts (plan.md §8 Phase 4, P1 item 8): "CAP polygon -> geofenced
push, with a 'why you got this' explanation." — **Niranjan**

Real CAP/SACHET polygons don't exist yet (plan.md §3.3 / Phase 4's "Proactive
alerts — CAP parsing" is Syed's still-open item) — imd_warnings.py only ever
reads a hand-written per-city fixture (district name + colour), not a
geometry. So "geofence match" here is necessarily city-grained, not
polygon-grained: a subscriber is either pinned to a registered city directly,
or to a raw lat/lon that gets resolved to the nearest registered city within
`config.ALERT_MAX_SUBSCRIPTION_RADIUS_KM` via weather_store.nearest_city()
(cities.geog / ST_DWithin — the spatial query sql/003_cities.sql's comment
says this table exists to serve). When real CAP polygons land, the natural
upgrade is ST_Intersects(subscriber_point, warning_polygon) instead of
nearest-city — the subscription/dispatch machinery below doesn't change.

Dispatch is a small pluggable interface, one channel implemented:

- **webhook**: POST the alert payload to an arbitrary URL. Works with no new
  external account (a Discord/Slack incoming webhook, webhook.site for
  testing, or the mobile app's own backend once it has one) — this is the
  channel exercised by tests and the live smoke check.
- **fcm**: Firebase Cloud Messaging device push. **Not implemented** — needs
  a Firebase project + service-account JWT signing, real infra setup on the
  order of the Exotel/Bhashini accounts this project already needed, out of
  scope for this pass. Subscribing with channel="fcm" is accepted (the row
  is stored, so it's ready once FCM is wired up) but every dispatch attempt
  logs and no-ops — see _dispatch_fcm. It counts as a failed dispatch, so
  the row is retried with backoff (at most hourly) and gets the current
  alert once FCM is wired up.

Change detection is colour-based, not "is there a warning": a subscription's
`last_notified_colour` only updates on a dispatch that succeeded, so a
standing alert doesn't re-fire every poll tick, but any change (new alert,
escalation, de-escalation, or clearing back to green/unavailable) does.
A failed dispatch leaves it unchanged and is retried on a later poll, with
backoff (_RETRY_BASE_SECONDS doubling up to _RETRY_MAX_SECONDS) so a target
that is down for good isn't posted to every tick. The backoff state is per
process and resets on restart, which only costs one early retry.
"""

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time

import config
import httpx
import imd_warnings
import netguard
import weather_store
from sqlalchemy import text

_LOG = logging.getLogger("weathergpt.alert_engine")

_worker: threading.Thread | None = None
_worker_pid: int | None = None
_worker_lock = threading.Lock()
_monotonic = time.monotonic  # test seam

_RETRY_BASE_SECONDS = 60.0
_RETRY_MAX_SECONDS = 3600.0
# subscription id -> (colour that failed, failures so far, monotonic time of next try)
_retry: dict[int, tuple[str | None, int, float]] = {}


class SubscriptionError(ValueError):
    pass


def subscribe(
    *,
    channel: str,
    target: str,
    city_key: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    lang: str = "en",
) -> tuple[int, str]:
    """Registers a subscription. Exactly one of `city_key` or
    `(lat, lon, radius_km)` must be given — mirrors the DB CHECK constraint,
    checked here too so a bad request gets a clean error instead of an
    IntegrityError. Returns `(id, manage_token)`; the token is shown to the
    caller only here (just its SHA-256 hash is stored) and is required by
    unsubscribe() / list_subscriptions().
    """
    if channel not in ("webhook", "fcm"):
        raise SubscriptionError(f"channel must be 'webhook' or 'fcm', got {channel!r}")
    if not target:
        raise SubscriptionError("target is required")
    if channel == "webhook":
        try:
            netguard.validate_public_https_url(
                target, allow_private=config.ALERT_WEBHOOK_ALLOW_PRIVATE,
            )
        except netguard.UnsafeURLError as exc:
            raise SubscriptionError(f"invalid webhook target: {exc}") from exc

    by_city = city_key is not None
    by_point = lat is not None and lon is not None and radius_km is not None
    if by_city == by_point:  # both or neither
        raise SubscriptionError(
            "give exactly one of city_key, or all of lat/lon/radius_km",
        )
    if by_city and city_key not in weather_store.cities.CITY_KEYS:
        raise SubscriptionError(f"unknown city {city_key!r}")
    if by_point and not (0 < radius_km <= config.ALERT_MAX_SUBSCRIPTION_RADIUS_KM):
        raise SubscriptionError(
            f"radius_km must be between 0 and {config.ALERT_MAX_SUBSCRIPTION_RADIUS_KM}",
        )

    manage_token = secrets.token_urlsafe(32)
    weather_store._ensure_schema()
    with weather_store._engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO alert_subscriptions
                    (city_key, lat, lon, radius_km, lang, channel, target, manage_token_hash)
                VALUES (:city_key, :lat, :lon, :radius_km, :lang, :channel, :target,
                        :token_hash)
                RETURNING id
            """),
            {
                "city_key": city_key, "lat": lat, "lon": lon, "radius_km": radius_km,
                "lang": lang, "channel": channel, "target": target,
                "token_hash": _hash_token(manage_token),
            },
        ).fetchone()
    return row[0], manage_token


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_matches(stored_hash: str | None, token: str | None) -> bool:
    """Constant-time check; a NULL stored hash (pre-token row) or a missing
    token never matches."""
    if not stored_hash or not token:
        return False
    return hmac.compare_digest(stored_hash, _hash_token(token))


def unsubscribe(sub_id: int, token: str | None) -> bool:
    """Deletes a subscription if `token` is its manage token. Returns whether
    a row was deleted; a wrong/missing token is indistinguishable from an
    unknown id (callers answer 404 either way)."""
    weather_store._ensure_schema()
    with weather_store._engine.begin() as conn:
        row = conn.execute(
            text("SELECT manage_token_hash FROM alert_subscriptions WHERE id = :id"),
            {"id": sub_id},
        ).fetchone()
        if row is None or not _token_matches(row[0], token):
            return False
        result = conn.execute(
            text("DELETE FROM alert_subscriptions WHERE id = :id AND manage_token_hash = :h"),
            {"id": sub_id, "h": row[0]},
        )
    return result.rowcount > 0


def list_subscriptions(target: str, token: str | None) -> list[dict]:
    """Subscriptions for a dispatch target (a webhook URL or FCM token) whose
    manage token is `token`. Rows without a matching token are never
    returned."""
    weather_store._ensure_schema()
    with weather_store._engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, city_key, lat, lon, radius_km, lang, channel, target,
                       last_notified_colour, last_notified_at, created_at,
                       manage_token_hash
                FROM alert_subscriptions WHERE target = :target ORDER BY created_at DESC
            """),
            {"target": target},
        ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        if _token_matches(d.pop("manage_token_hash"), token):
            out.append(d)
    return out


def _all_subscriptions() -> list[dict]:
    weather_store._ensure_schema()
    with weather_store._engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, city_key, lat, lon, radius_km, lang, channel, target, last_notified_colour
            FROM alert_subscriptions
        """)).mappings().all()
    return [dict(r) for r in rows]


def _resolve_city(sub: dict) -> str | None:
    if sub["city_key"] is not None:
        return sub["city_key"]
    return weather_store.nearest_city(sub["lat"], sub["lon"], sub["radius_km"])


def _why(sub: dict, city_key: str, verdict: dict) -> str:
    name = weather_store.cities.display_name(city_key, sub["lang"])
    if sub["city_key"] is not None:
        return f"You're subscribed to weather alerts for {name}."
    return (
        f"You're subscribed to alerts near ({sub['lat']:.3f}, {sub['lon']:.3f}), "
        f"within {sub['radius_km']:.0f} km — the nearest matching city is {name}."
    )


def _build_payload(sub: dict, city_key: str, verdict: dict) -> dict:
    warning = verdict["warning"]
    return {
        "subscription_id": sub["id"],
        "city": city_key,
        "status": verdict["status"],
        "colour": warning["colour"] if warning else None,
        "colour_label": warning["colour_label"] if warning else None,
        "headline": warning["headline"] if warning else None,
        "advice": warning["advice"] if warning else None,
        "why": _why(sub, city_key, verdict),
    }


def _dispatch_webhook(target: str, payload: dict) -> bool:
    host = netguard.url_host(target)
    try:
        # Re-validate at send time: DNS may have changed since subscribe.
        netguard.validate_public_https_url(
            target, allow_private=config.ALERT_WEBHOOK_ALLOW_PRIVATE,
        )
    except netguard.UnsafeURLError as exc:
        _LOG.warning("alert webhook to host %s blocked: %s", host, exc)
        return False
    try:
        resp = httpx.post(
            target, json=payload, timeout=5.0, follow_redirects=False,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        _LOG.warning(
            "alert webhook dispatch to host %s failed: %s", host, type(exc).__name__,
        )
        return False


def _dispatch_fcm(target: str, payload: dict) -> bool:
    _LOG.warning(
        "alert dispatch: channel=fcm not implemented yet (token sha256=%s) — "
        "subscription stored, nothing sent. See alert_engine.py's module docstring.",
        hashlib.sha256(target.encode()).hexdigest()[:8],
    )
    return False


# Channel -> function *name*, resolved via globals() at call time rather than
# a dict of direct references — so monkeypatching alert_engine._dispatch_webhook
# in tests (or swapping it at runtime) actually takes effect.
_DISPATCHERS = {"webhook": "_dispatch_webhook", "fcm": "_dispatch_fcm"}


def _mark_notified(sub_id: int, colour: str | None) -> None:
    with weather_store._engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE alert_subscriptions
                SET last_notified_colour = :colour, last_notified_at = now()
                WHERE id = :id
            """),
            {"colour": colour, "id": sub_id},
        )


def _backing_off(sub_id: int, colour: str | None) -> bool:
    entry = _retry.get(sub_id)
    if entry is None:
        return False
    failed_colour, _, retry_at = entry
    if failed_colour != colour:  # the alert changed: try the new one now
        del _retry[sub_id]
        return False
    return _monotonic() < retry_at


def _record_failure(sub_id: int, colour: str | None) -> None:
    entry = _retry.get(sub_id)
    failures = entry[1] + 1 if entry and entry[0] == colour else 1
    delay = min(_RETRY_BASE_SECONDS * 2 ** (failures - 1), _RETRY_MAX_SECONDS)
    _retry[sub_id] = (colour, failures, _monotonic() + delay)


def check_once() -> int:
    """One pass over every subscription: resolve its city, check
    imd_warnings for a colour change, dispatch and update dedupe state if
    the dispatch succeeded. Returns how many dispatches were attempted (sent
    or not — a failed webhook still counts as "the engine tried", distinct
    from "nothing to report" for check_once()'s caller/tests). Never raises:
    one subscription failing (bad city, dispatch error, DB hiccup) must not
    stop the rest.
    """
    attempted = 0
    for sub in _all_subscriptions():
        try:
            city_key = _resolve_city(sub)
            if city_key is None:
                continue
            verdict = imd_warnings.public(city_key, sub["lang"])
            colour = verdict["warning"]["colour"] if verdict["warning"] else verdict["status"]
            if colour == sub["last_notified_colour"]:
                _retry.pop(sub["id"], None)
                continue  # no change since we last told this subscriber anything
            if _backing_off(sub["id"], colour):
                continue
            payload = _build_payload(sub, city_key, verdict)
            dispatcher = globals()[_DISPATCHERS[sub["channel"]]]
            sent = dispatcher(sub["target"], payload)
            attempted += 1
            if sent:
                _retry.pop(sub["id"], None)
                _mark_notified(sub["id"], colour)
            else:  # not marked, so a later poll retries it
                _record_failure(sub["id"], colour)
        except Exception:
            _LOG.exception("alert_engine: check failed for subscription %s", sub.get("id"))
    return attempted


def _worker_loop() -> None:
    while True:
        try:
            check_once()
        except Exception:
            _LOG.exception("alert_engine: poll cycle failed")
        time.sleep(config.ALERT_POLL_SECONDS)


def ensure_worker() -> None:
    """Starts the poll thread on first use. No-op unless ALERT_ENGINE_ENABLED
    — a repo clone with no alert subscribers configured doesn't get a
    background thread hammering imd_warnings for nothing. pid-aware like
    weather_store._ensure_worker(), for the same fork-vs-spawn reason."""
    if not config.ALERT_ENGINE_ENABLED:
        return
    global _worker, _worker_pid
    with _worker_lock:
        pid = os.getpid()
        if _worker is not None and _worker_pid == pid and _worker.is_alive():
            return
        _worker_pid = pid
        _worker = threading.Thread(target=_worker_loop, name="alert-engine-poll", daemon=True)
        _worker.start()
