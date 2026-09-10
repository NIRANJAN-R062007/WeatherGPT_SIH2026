"""Adversarial suite for the grounding guardrail (plan.md §14 / §11 risk R2).

First tests in this repo. Exercises guardrail.check() directly against both
template outputs and hostile answers, plus the full `/ask` path end to end.
"""

import guardrail
from fastapi.testclient import TestClient
from i18n import render
from main import app
from weather_data import get_weather

CHENNAI = get_weather("chennai")

client = TestClient(app)


def test_template_current_weather_en_passes():
    answer = render("current_weather", "Chennai", CHENNAI, "en")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok
    assert report.matched == report.total == 1


def test_template_will_it_rain_en_passes():
    answer = render("will_it_rain", "Chennai", CHENNAI, "en")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok
    assert report.matched == report.total == 1


def test_template_current_weather_ta_passes():
    answer = render("current_weather", "Chennai", CHENNAI, "ta")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok
    assert report.matched == report.total == 1


def test_template_will_it_rain_ta_passes():
    answer = render("will_it_rain", "Chennai", CHENNAI, "ta")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok
    assert report.matched == report.total == 1


def test_hallucinated_number_fails():
    answer = "Chennai: partly cloudy, 99°C right now."
    report = guardrail.check(answer, CHENNAI)
    assert not report.ok
    assert report.matched == 0
    assert report.total == 1


def test_unit_swap_fails():
    # 20 is only rain_probability_pct (percent); claiming it as celsius must
    # not pass just because the bare number 20 exists somewhere in raw.
    raw = {"temp_c": 31, "rain_probability_pct": 20}
    answer = "Chennai: 20°C right now."
    report = guardrail.check(answer, raw)
    assert not report.ok


def test_rounding_passes():
    raw = {"temp_c": 31.4}
    report = guardrail.check("Chennai: 31°C right now.", raw)
    assert report.ok


def test_false_precision_fails():
    raw = {"temp_c": 31.4}
    report = guardrail.check("Chennai: 31.5°C right now.", raw)
    assert not report.ok


def test_tamil_digits_pass():
    raw = {"temp_c": 31}
    # "31" written with Tamil digits: 3 = ௩, 1 = ௧
    answer = "Chennai: ௩௧°C right now."
    report = guardrail.check(answer, raw)
    assert report.ok


def test_devanagari_digits_pass():
    raw = {"temp_c": 31}
    # "31" written with Devanagari digits: 3 = ३, 1 = १
    answer = "Chennai: ३१°C right now."
    report = guardrail.check(answer, raw)
    assert report.ok


def test_numbers_with_empty_raw_fails_not_vacuous():
    report = guardrail.check("Chennai: 31°C right now.", {})
    assert not report.ok
    assert report.total == 1
    assert report.matched == 0


def test_no_numbers_passes():
    report = guardrail.check("Sorry, I couldn't understand that.", CHENNAI)
    assert report.ok
    assert report.total == 0
    assert report.matched == 0


def test_ask_endpoint_returns_grounding_ok_and_matched_equals_total():
    resp = client.get("/ask", params={"text": "what's the weather in Chennai", "lang": "en"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounding"]["ok"] is True
    assert body["grounding"]["matched"] == body["grounding"]["total"]
    assert body["grounding"]["fallback_used"] is False
