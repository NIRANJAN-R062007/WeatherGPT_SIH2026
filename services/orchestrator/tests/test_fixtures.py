"""The committed Google Weather API fixtures are well-formed, key-free, and
carry the field paths the guardrail and the Day 2 decoder rely on.

Runs fully offline against tracked files — no key, no network.
"""

import json
from datetime import datetime

import guardrail
import pytest
from config import FIXTURES_DIR

GW_DIR = FIXTURES_DIR / "google_weather"
CITIES = ["chennai", "madurai", "coimbatore"]
KINDS = ["current_conditions", "forecast_days", "history_hours"]

EXPECTED = [GW_DIR / f"{kind}.{city}.json" for city in CITIES for kind in KINDS]

# FIELD_UNITS promises these; _index() yields them under a nested prefix on real
# forecast JSON, so match on suffix — the same rule guardrail._match needs.
CURRENT_PATHS = ["temperature.degrees", "relativeHumidity",
                 "wind.speed.value", "precipitation.probability.percent"]


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.name)
def test_fixture_exists_and_is_well_formed(path):
    assert path.exists(), f"missing fixture: {path}"
    env = json.loads(path.read_text(encoding="utf-8"))
    meta = env["_meta"]
    assert meta["http_status"] == 200
    assert meta["request"]["key"] == "REDACTED"
    datetime.fromisoformat(meta["retrieved_at"])  # raises if not ISO
    assert isinstance(env["response"], dict) and env["response"]


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.name)
def test_fixture_has_no_api_key(path):
    text = path.read_text(encoding="utf-8")
    assert "AIza" not in text
    assert "AQ.Ab" not in text


@pytest.mark.parametrize("city", CITIES)
def test_current_conditions_has_expected_field_paths(city):
    env = json.loads((GW_DIR / f"current_conditions.{city}.json").read_text(encoding="utf-8"))
    indexed = guardrail._index(env["response"])
    for wanted in CURRENT_PATHS:
        assert any(p == wanted or p.endswith("." + wanted) for p in indexed), \
            f"{city}: no indexed path ends with {wanted}"


@pytest.mark.parametrize("city", CITIES)
def test_forecast_days_has_temperature_and_precip(city):
    env = json.loads((GW_DIR / f"forecast_days.{city}.json").read_text(encoding="utf-8"))
    indexed = guardrail._index(env["response"])
    for wanted in ["maxTemperature.degrees", "minTemperature.degrees",
                   "precipitation.probability.percent"]:
        assert any(p.endswith(wanted) for p in indexed), \
            f"{city}: no indexed forecast path ends with {wanted}"


@pytest.mark.parametrize("city", CITIES)
def test_history_hours_has_qpf_and_interval(city):
    path = GW_DIR / f"history_hours.{city}.json"
    if not path.exists():
        pytest.skip(f"history_hours fixture not present for {city}")
    env = json.loads(path.read_text(encoding="utf-8"))
    hours = env["response"]["historyHours"]
    assert len(hours) >= 1
    for hour in hours:
        assert "startTime" in hour["interval"] and "endTime" in hour["interval"]
        assert "quantity" in hour["precipitation"]["qpf"]


def test_gemini_models_fixture():
    path = FIXTURES_DIR / "gemini" / "models.json"
    if not path.exists():
        pytest.skip("gemini models fixture not present (key not verified)")
    text = path.read_text(encoding="utf-8")
    assert "AIza" not in text and "AQ.Ab" not in text
    data = json.loads(text)
    assert data["_meta"]["chosen_model"]
    assert any(m["name"] == data["_meta"]["chosen_model"] for m in data["models"])
    assert all("generateContent" in m["methods"] for m in data["models"])
