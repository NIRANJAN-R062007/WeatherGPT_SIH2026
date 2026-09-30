"""alert_engine.py: geofence-match -> push dispatch (plan.md §8 Phase 4).

Same convention as test_weather_store.py: CI has no live Postgres, so DB
access (_all_subscriptions, _mark_notified, subscribe/unsubscribe's actual
INSERT/DELETE) is monkeypatched at the function boundary rather than mocked
through SQLAlchemy — real-DB behaviour (the SQL itself, the CHECK
constraints, nearest_city's ST_DWithin query) was verified manually against
a throwaway PostGIS container, same as weather_store's Phase 1 work.
"""

import alert_engine
import config
import httpx
import imd_warnings
import pytest
import weather_store


@pytest.fixture(autouse=True)
def _allow_private_webhooks(monkeypatch):
    # These tests use fake hosts and mock the transport; the SSRF guard has
    # its own tests in test_netguard.py.
    monkeypatch.setattr(config, "ALERT_WEBHOOK_ALLOW_PRIVATE", True)


def _sub(**overrides):
    base = {
        "id": 1, "city_key": "chennai", "lat": None, "lon": None, "radius_km": None,
        "lang": "en", "channel": "webhook", "target": "https://example.test/hook",
        "last_notified_colour": None,
    }
    base.update(overrides)
    return base


def _recorder(sink: list):
    """A stand-in _dispatch_webhook: appends the payload to `sink`, returns True."""
    def _record(target, payload):
        sink.append(payload)
        return True
    return _record


def _refuse_dispatch(*a):
    pytest.fail("must not dispatch")


def _marker(sink: list):
    """A stand-in _mark_notified: records (sub_id, colour) pairs into `sink`."""
    def _mark(sub_id, colour):
        sink.append((sub_id, colour))
    return _mark


def _verdict(colour="orange", status="active"):
    return {
        "status": status,
        "warning": None if status == "unavailable" else {
            "colour": colour, "colour_label": colour.title(),
            "headline": f"{colour} alert for Chennai", "advice": "stay indoors",
        },
        "legend": [],
    }


# ---- subscribe() validation (no DB touched on these paths) -------------------

def test_subscribe_rejects_bad_channel():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(channel="sms", target="x", city_key="chennai")


def test_subscribe_rejects_empty_target():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(channel="webhook", target="", city_key="chennai")


def test_subscribe_rejects_neither_location_mode():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(channel="webhook", target="x")


def test_subscribe_rejects_both_location_modes():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(
            channel="webhook", target="x", city_key="chennai",
            lat=13.0, lon=80.2, radius_km=50,
        )


def test_subscribe_rejects_unknown_city():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(channel="webhook", target="x", city_key="atlantis")


def test_subscribe_rejects_radius_out_of_range(monkeypatch):
    monkeypatch.setattr(alert_engine.config, "ALERT_MAX_SUBSCRIPTION_RADIUS_KM", 200.0)
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(
            channel="webhook", target="x", lat=13.0, lon=80.2, radius_km=500,
        )


# ---- _resolve_city -----------------------------------------------------------

def test_resolve_city_direct():
    assert alert_engine._resolve_city(_sub(city_key="madurai")) == "madurai"


def test_resolve_city_via_nearest(monkeypatch):
    monkeypatch.setattr(weather_store, "nearest_city", lambda lat, lon, km: "coimbatore")
    sub = _sub(city_key=None, lat=11.0, lon=76.9, radius_km=50)
    assert alert_engine._resolve_city(sub) == "coimbatore"


def test_resolve_city_via_nearest_no_match(monkeypatch):
    monkeypatch.setattr(weather_store, "nearest_city", lambda lat, lon, km: None)
    sub = _sub(city_key=None, lat=0.0, lon=0.0, radius_km=10)
    assert alert_engine._resolve_city(sub) is None


# ---- _dispatch_webhook / _dispatch_fcm ---------------------------------------

def test_dispatch_webhook_success(monkeypatch):
    calls = []

    class _Resp:
        def raise_for_status(self):
            pass

    def _post(url, json=None, timeout=None, **kw):
        calls.append((url, json))
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    assert alert_engine._dispatch_webhook("https://example.test/hook", {"a": 1}) is True
    assert calls == [("https://example.test/hook", {"a": 1})]


def test_dispatch_webhook_failure(monkeypatch):
    def _post(url, json=None, timeout=None, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", _post)
    assert alert_engine._dispatch_webhook("https://example.test/hook", {}) is False


def test_dispatch_fcm_not_implemented():
    assert alert_engine._dispatch_fcm("some-token", {}) is False


# ---- check_once() -------------------------------------------------------------

def test_check_once_dispatches_on_new_alert(monkeypatch):
    sub = _sub(last_notified_colour=None)
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [sub])
    monkeypatch.setattr(imd_warnings, "public", lambda city, lang: _verdict("orange"))
    sent = []
    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _recorder(sent))
    marked = []
    monkeypatch.setattr(alert_engine, "_mark_notified", _marker(marked))

    assert alert_engine.check_once() == 1
    assert sent[0]["city"] == "chennai"
    assert sent[0]["colour"] == "orange"
    assert "subscribed to weather alerts for" in sent[0]["why"]
    assert marked == [(1, "orange")]


def test_check_once_skips_unchanged_colour(monkeypatch):
    sub = _sub(last_notified_colour="orange")
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [sub])
    monkeypatch.setattr(imd_warnings, "public", lambda city, lang: _verdict("orange"))
    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _refuse_dispatch)

    assert alert_engine.check_once() == 0


def test_check_once_dispatches_on_colour_change(monkeypatch):
    sub = _sub(last_notified_colour="orange")
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [sub])
    monkeypatch.setattr(imd_warnings, "public", lambda city, lang: _verdict("red"))
    sent = []
    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _recorder(sent))
    monkeypatch.setattr(alert_engine, "_mark_notified", lambda *a: None)

    assert alert_engine.check_once() == 1
    assert sent[0]["colour"] == "red"


def test_check_once_dispatches_on_clearing(monkeypatch):
    sub = _sub(last_notified_colour="orange")
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [sub])
    monkeypatch.setattr(imd_warnings, "public", lambda city, lang: _verdict(status="unavailable"))
    sent = []
    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _recorder(sent))
    marked = []
    monkeypatch.setattr(alert_engine, "_mark_notified", _marker(marked))

    assert alert_engine.check_once() == 1
    assert sent[0]["colour"] is None
    assert marked == [(1, "unavailable")]


def test_check_once_skips_unresolvable_city(monkeypatch):
    sub = _sub(city_key=None, lat=0.0, lon=0.0, radius_km=10, last_notified_colour=None)
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [sub])
    monkeypatch.setattr(weather_store, "nearest_city", lambda *a: None)
    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _refuse_dispatch)

    assert alert_engine.check_once() == 0


def test_check_once_survives_one_subscription_raising(monkeypatch):
    # First subscription's dispatch blows up; the second must still be
    # processed and counted rather than the whole poll cycle aborting.
    bad = _sub(id=1, last_notified_colour=None)
    good = _sub(id=2, last_notified_colour=None)
    monkeypatch.setattr(alert_engine, "_all_subscriptions", lambda: [bad, good])
    monkeypatch.setattr(imd_warnings, "public", lambda city, lang: _verdict("orange"))
    monkeypatch.setattr(alert_engine, "_mark_notified", lambda *a: None)
    sent = []
    calls = {"n": 0}

    def _flaky(target, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        sent.append(payload)
        return True

    monkeypatch.setattr(alert_engine, "_dispatch_webhook", _flaky)
    assert alert_engine.check_once() == 1  # only `good` counted; `bad`'s dispatch raised
    assert len(sent) == 1
