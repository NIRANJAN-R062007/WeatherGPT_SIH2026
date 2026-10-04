"""TFA-20: finished advisory answers cached by (kind, slots, lang) — advisory/cache.py.

Done-when: a repeat request is served without a model call, and the TTL never
outlives the hourly forecast."""

from datetime import datetime, timedelta, timezone

import config
import intelligence_cache
import main
import pytest
from advisory import agent, cache
from advisory.agent import Advice
from advisory.facts import AdvisoryFacts, FactSection
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
client = TestClient(main.app)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key], self.ttls[key] = value, ttl


@pytest.fixture
def fake(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(intelligence_cache, "_redis", fake)
    monkeypatch.setattr(intelligence_cache, "_now", lambda: NOW)
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "TTL_FORECAST_HOURS", 3600)
    monkeypatch.setattr(config, "TTL_CURRENT_CONDITIONS", 900)
    monkeypatch.setattr(config, "TTL_METAR", 600)
    monkeypatch.setattr(config, "TTL_TAF", 1800)
    return fake


def _hourly(role="location", age_s=600, live=True) -> FactSection:
    data = {"day": "today", "hours": [], "is_live": live, "source": "Google Weather API",
            "retrieved_at": (NOW - timedelta(seconds=age_s)).isoformat()}
    return FactSection(role, "hourly", True, data, source=data["source"], is_live=live)


def _advice(*sections, path="agent:groq", reason=None, kind="farming") -> Advice:
    facts = AdvisoryFacts(kind, {}, list(sections))
    answer = {"verdict": "not_suitable", "pros": [], "cons": ["x"], "window": None, "cites": []}
    return Advice(kind, answer, facts, path, reason, 0, 0.1)


# --- the key ----------------------------------------------------------------------


def test_the_key_is_kind_lang_and_the_sorted_slots():
    assert cache.key("travel", {"origin": "chennai", "destination": "madurai", "day": "today"},
                     "ta") == ("weathergpt:advisory:travel:ta:day=today:destination=madurai:"
                               "origin=chennai")


# --- the TTL ----------------------------------------------------------------------


def test_the_ttl_never_outlives_the_hourly_forecast(monkeypatch, fake):
    monkeypatch.setattr(config, "TTL_CURRENT_CONDITIONS", 99_999)  # take that cap away
    assert cache.ttl_seconds(_advice(_hourly(age_s=600))) == 3000
    assert cache.ttl_seconds(_advice(_hourly(age_s=3500))) == 100
    assert cache.ttl_seconds(_advice(_hourly(age_s=4000))) == 0


def test_the_oldest_hourly_section_decides(monkeypatch, fake):
    monkeypatch.setattr(config, "TTL_CURRENT_CONDITIONS", 99_999)
    advice = _advice(_hourly("origin", 600), _hourly("destination", 3000), kind="travel")
    assert cache.ttl_seconds(advice) == 600


def test_current_conditions_and_airport_reports_cap_the_ttl(fake):
    assert cache.ttl_seconds(_advice(_hourly(age_s=600))) == 900
    aviation = FactSection("origin", "aviation", True, {"metar": {}}, source="AWC", is_live=True)
    assert cache.ttl_seconds(_advice(_hourly(age_s=600), aviation)) == 600


@pytest.mark.parametrize("advice", [
    _advice(_hourly(live=False)),                                   # fixture forecast
    _advice(),                                                      # no hourly at all
    _advice(FactSection("location", "hourly", False, reason="down")),
    _advice(_hourly(), path="template", reason="gemini: timeout"),  # the agent failed
], ids=["fixture", "no-hourly", "hourly-unavailable", "agent-failed"])
def test_what_is_never_stored(fake, advice):
    assert cache.ttl_seconds(advice) == 0
    cache.put("k", {"answer": 1}, advice)
    assert fake.store == {}


def test_the_template_is_stored_when_the_agent_is_off(fake):
    advice = _advice(_hourly(), path="template", reason=agent.AGENT_OFF)
    cache.put("k", {"answer": 1}, advice)
    assert fake.ttls == {"k": 900}


def test_nothing_is_stored_in_fixtures_mode(monkeypatch, fake):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")
    cache.put("k", {"answer": 1}, _advice(_hourly()))
    assert fake.store == {}


# --- through the endpoints ------------------------------------------------------------


@pytest.fixture
def counted(monkeypatch, fake):
    """advise() stand-in with a live hourly section, counting model calls."""
    calls = []

    def advise(kind, slots, lang="en", **kw):
        calls.append((kind, dict(slots), lang))
        return _advice(_hourly(), kind=kind)

    monkeypatch.setattr(main.advisory_agent, "advise", advise)
    return calls


def test_a_repeat_question_is_served_without_a_model_call(counted):
    first = client.post("/advisory/sowing", json={"text": "when should I sow groundnut in Madurai"})
    again = client.post("/advisory/sowing", json={"text": "groundnut sowing in madurai?"})
    assert first.headers["X-Cache"] == "MISS" and again.headers["X-Cache"] == "HIT"
    assert len(counted) == 1
    assert again.json()["answer"] == first.json()["answer"]


def test_a_different_language_or_place_is_its_own_entry(counted):
    for body in ({"text": "when should I sow groundnut in Madurai"},
                 {"text": "when should I sow groundnut in Madurai", "lang": "ta"},
                 {"text": "when should I sow groundnut in Coimbatore"}):
        assert client.post("/advisory/sowing", json=body).headers["X-Cache"] == "MISS"
    assert len(counted) == 3


def test_the_request_fields_come_from_this_request_not_the_cache(counted, fake):
    import json

    first = client.post("/advisory/travel",
                        json={"text": "from Chennai to Madurai today"}).json()
    (stored,) = fake.store.values()
    assert not {"kind", "status", "slots", "assumed"} & set(json.loads(stored))
    # The same trip reached over two turns: the day arrives as the answer to a question.
    again = client.post("/advisory/travel", json={
        "text": "today", "asking": "day",
        "slots": {"origin": "chennai", "destination": "madurai"}})
    assert again.headers["X-Cache"] == "HIT" and len(counted) == 1
    assert again.json()["slots"] == first["slots"] and again.json()["status"] == "ok"


def test_an_ask_back_is_never_cached(counted, fake):
    body = client.post("/advisory/sowing", json={"text": "when should I sow groundnut"}).json()
    assert body["status"] == "ask_back" and fake.store == {} and counted == []


def test_with_redis_down_every_request_is_answered(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(main.advisory_agent, "advise",
                        lambda kind, slots, lang="en", **kw: calls.append(1) or
                        _advice(_hourly(), kind=kind))
    for _ in range(2):  # conftest's Redis is unreachable
        r = client.post("/advisory/sowing", json={"text": "when should I sow groundnut in Madurai"})
        assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"
    assert len(calls) == 2
