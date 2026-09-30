"""Alert subscription manage tokens: ids alone must not delete/list rows.

No live Postgres in CI, so a tiny in-memory fake stands in for the SQLAlchemy
engine, dispatching on the statement text alert_engine issues.
"""

import alert_engine
import main
import pytest
import weather_store
from fastapi.testclient import TestClient


class _Result:
    def __init__(self, rows=(), rowcount=0):
        self._rows, self.rowcount = list(rows), rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self):
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.lstrip().startswith("INSERT"):
            i = self.next_id
            self.next_id += 1
            self.rows[i] = {
                "id": i, "city_key": params["city_key"], "lat": None, "lon": None,
                "radius_km": None, "lang": params["lang"], "channel": params["channel"],
                "target": params["target"], "last_notified_colour": None,
                "last_notified_at": None, "created_at": i,
                "manage_token_hash": params["token_hash"],
            }
            return _Result([(i,)])
        if sql.lstrip().startswith("SELECT manage_token_hash"):
            r = self.rows.get(params["id"])
            return _Result([(r["manage_token_hash"],)] if r else [])
        if sql.lstrip().startswith("DELETE"):
            r = self.rows.get(params["id"])
            if r and r["manage_token_hash"] == params["h"]:
                del self.rows[params["id"]]
                return _Result(rowcount=1)
            return _Result()
        if "WHERE target" in sql:
            return _Result([dict(r) for r in self.rows.values() if r["target"] == params["target"]])
        raise AssertionError(sql)


@pytest.fixture
def db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(weather_store, "_engine", fake, raising=False)
    monkeypatch.setattr(weather_store, "_ensure_schema", lambda: None)
    # Webhook-target validation has its own tests (test_netguard.py); these
    # use placeholder targets and are only about the manage token.
    monkeypatch.setattr(alert_engine.netguard, "validate_public_https_url",
                        lambda url, **kw: url)
    return fake


def test_subscribe_stores_only_hash(db):
    sub_id, token = alert_engine.subscribe(
        channel="webhook", target="https://example.test/h", city_key="chennai",
    )
    stored = db.rows[sub_id]["manage_token_hash"]
    assert token and token != stored
    assert stored == alert_engine._hash_token(token)


def test_unsubscribe_requires_matching_token(db):
    sub_id, token = alert_engine.subscribe(
        channel="webhook", target="https://example.test/h", city_key="chennai",
    )
    assert not alert_engine.unsubscribe(sub_id, None)
    assert not alert_engine.unsubscribe(sub_id, "wrong")
    assert sub_id in db.rows
    assert alert_engine.unsubscribe(sub_id, token)
    assert sub_id not in db.rows


def test_legacy_row_without_hash_is_kept_and_undeletable(db):
    db.rows[7] = {"id": 7, "target": "t", "manage_token_hash": None}
    assert not alert_engine.unsubscribe(7, "anything")
    assert not alert_engine.unsubscribe(7, "")
    assert alert_engine.list_subscriptions("t", "anything") == []
    assert 7 in db.rows


def test_list_only_returns_rows_matching_token(db):
    _, t1 = alert_engine.subscribe(channel="webhook", target="u", city_key="chennai")
    alert_engine.subscribe(channel="webhook", target="u", city_key="chennai")
    subs = alert_engine.list_subscriptions("u", t1)
    assert len(subs) == 1
    assert "manage_token_hash" not in subs[0]


def test_routes_use_404_and_token_header(db):
    client = TestClient(main.app)
    r = client.post("/alerts/subscribe", json={
        "channel": "webhook", "target": "https://example.test/h", "city_key": "chennai",
    })
    assert r.status_code == 200
    sub_id, token = r.json()["id"], r.json()["manage_token"]

    assert client.delete(f"/alerts/subscribe/{sub_id}").status_code == 404
    assert client.delete(
        f"/alerts/subscribe/{sub_id}", headers={"X-Manage-Token": "nope"},
    ).status_code == 404
    h = {"X-Manage-Token": token}
    assert client.delete("/alerts/subscribe/9999", headers=h).status_code == 404

    p = {"target": "https://example.test/h"}
    assert client.get("/alerts/subscriptions", params=p).status_code == 404
    ok = client.get(
        "/alerts/subscriptions", params={"target": "https://example.test/h"},
        headers={"X-Manage-Token": token},
    )
    assert ok.status_code == 200 and ok.json()["subscriptions"][0]["id"] == sub_id

    assert client.delete(
        f"/alerts/subscribe/{sub_id}", headers={"X-Manage-Token": token},
    ).status_code == 200


def test_migration_005_is_discovered():
    names = [p.name for p in weather_store.migration_files()]
    assert "005_alert_subscription_manage_token.sql" in names
