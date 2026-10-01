"""SEC-N15 (plan.md §8 Phase 8): the daily ceiling on paid API calls engages
as a circuit breaker, and every caller degrades the way it does for an outage.
"""

import base64

import bhashini
import budget
import config
import google_weather
import httpx
import main
import narrate
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture
def caps(monkeypatch):
    """Set ceilings per test; anything not named is unlimited."""
    def set_caps(**values):
        monkeypatch.setattr(config, "DAILY_CAPS", {p: values.get(p, 0) for p in budget.PROVIDERS})
    return set_caps


def test_breaker_engages_after_the_ceiling(caps):
    caps(gemini=2)
    budget.charge("gemini")
    budget.charge("gemini")
    with pytest.raises(budget.BudgetExceeded):
        budget.charge("gemini")
    budget.charge("groq")  # other providers are unaffected


def test_breaker_is_an_httpx_error_so_existing_fallbacks_catch_it():
    assert issubclass(budget.BudgetExceeded, httpx.HTTPError)


def test_zero_means_no_ceiling(caps):
    caps()
    for _ in range(50):
        budget.charge("google_weather")


def test_new_utc_day_resets_the_count(caps, monkeypatch):
    caps(bhashini=1)
    monkeypatch.setattr(budget, "_today", lambda: "2026-10-01")
    budget.charge("bhashini")
    with pytest.raises(budget.BudgetExceeded):
        budget.charge("bhashini")
    monkeypatch.setattr(budget, "_today", lambda: "2026-10-02")
    budget.charge("bhashini")


def test_refusals_are_counted_and_logged_once_per_day(caps, caplog):
    caps(groq=1)
    before = budget.BUDGET_REFUSED_TOTAL.labels(provider="groq")._value.get()
    budget.charge("groq")
    for _ in range(3):
        with pytest.raises(budget.BudgetExceeded):
            budget.charge("groq")
    assert budget.BUDGET_REFUSED_TOTAL.labels(provider="groq")._value.get() == before + 3
    assert sum("daily ceiling" in r.message for r in caplog.records) == 1


class _FakeRedis:
    """INCR/EXPIRE through a pipeline, shared like a real Redis would be."""
    def __init__(self):
        self.store, self.ttl = {}, {}

    def pipeline(self):
        fake, ops = self, []

        class _Pipe:
            def incr(self, key):
                ops.append(("incr", key))

            def expire(self, key, ttl):
                ops.append(("expire", key, ttl))

            def execute(self):
                out = []
                for op in ops:
                    if op[0] == "incr":
                        fake.store[op[1]] = fake.store.get(op[1], 0) + 1
                        out.append(fake.store[op[1]])
                    else:
                        fake.ttl[op[1]] = op[2]
                        out.append(True)
                return out
        return _Pipe()


def test_count_is_shared_through_redis(caps, monkeypatch):
    caps(gemini=2)
    fake = _FakeRedis()
    monkeypatch.setattr(budget, "_redis", fake)
    monkeypatch.setattr(budget, "_redis_retry_at", 0.0)
    monkeypatch.setattr(budget, "_today", lambda: "2026-10-01")
    budget.charge("gemini")
    budget.reset()  # another replica: no local state, same Redis
    budget.charge("gemini")
    with pytest.raises(budget.BudgetExceeded):
        budget.charge("gemini")
    assert fake.store["weathergpt:budget:gemini:2026-10-01"] == 3
    assert fake.ttl["weathergpt:budget:gemini:2026-10-01"] == 2 * 24 * 3600


def test_redis_down_falls_back_to_a_local_count(caps, monkeypatch):
    import redis

    class _Down:
        def pipeline(self):
            raise redis.ConnectionError("down")

    caps(gemini=1)
    monkeypatch.setattr(budget, "_redis", _Down())
    monkeypatch.setattr(budget, "_redis_retry_at", 0.0)
    budget.charge("gemini")
    with pytest.raises(budget.BudgetExceeded):
        budget.charge("gemini")


# --- each paid call site engages the breaker before any network I/O --------

def _no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a paid call went out past the breaker")
    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(httpx, "post", boom)


def test_google_weather_breaker_falls_back_to_fixtures(caps, monkeypatch):
    caps(google_weather=1)
    budget.charge("google_weather")
    _no_network(monkeypatch)
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "k")
    google_weather.cache_clear()
    snap = google_weather.snapshot("current_conditions", "chennai", force_refresh=True)
    assert snap is not None and snap.is_live is False


def test_llm_breaker_falls_through_to_the_template(caps, monkeypatch):
    caps(gemini=1, groq=1)
    budget.charge("gemini")
    budget.charge("groq")
    _no_network(monkeypatch)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    assert narrate.run_chain("hello") == (None, None)
    body = client.get("/ask", params={"text": "weather in Chennai", "lang": "en"}).json()
    assert body["response"]  # template answer, not an error


@pytest.mark.parametrize("call", [
    lambda: bhashini.translate("hello", "ta"),
    lambda: bhashini.speech_to_text(base64.b64encode(b"RIFF").decode(), "ta"),
    lambda: bhashini.text_to_speech("vanakkam", "ta"),
])
def test_bhashini_breaker_returns_none(caps, monkeypatch, call):
    caps(bhashini=1)
    budget.charge("bhashini")
    _no_network(monkeypatch)
    monkeypatch.setattr(bhashini, "is_configured", lambda: True)
    assert call() is None
