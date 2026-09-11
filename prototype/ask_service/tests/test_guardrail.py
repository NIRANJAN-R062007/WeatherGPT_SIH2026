"""Adversarial suite for the grounding guardrail (plan.md §14 / §11 risk R2).

First tests in this repo. Exercises guardrail.check() directly against both
template outputs and hostile answers, plus the full `/ask` path end to end.
"""

import guardrail
from fastapi.testclient import TestClient
from i18n import render
from main import app
from weather_data import get_weather

CHENNAI = get_weather("chennai")                              # current facts
CHENNAI_RAIN = get_weather("chennai", "will_it_rain", "tomorrow")  # forecast facts

client = TestClient(app)


def test_template_current_weather_en_passes():
    answer = render("current_weather", "Chennai", CHENNAI, "en")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok and report.matched == report.total >= 1


def test_template_will_it_rain_en_passes():
    answer = render("will_it_rain", "Chennai", CHENNAI_RAIN, "en")
    report = guardrail.check(answer, CHENNAI_RAIN)
    assert report.ok and report.matched == report.total >= 1


def test_template_current_weather_ta_passes():
    answer = render("current_weather", "Chennai", CHENNAI, "ta")
    report = guardrail.check(answer, CHENNAI)
    assert report.ok and report.matched == report.total >= 1


def test_template_will_it_rain_ta_passes():
    answer = render("will_it_rain", "Chennai", CHENNAI_RAIN, "ta")
    report = guardrail.check(answer, CHENNAI_RAIN)
    assert report.ok and report.matched == report.total >= 1


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


def test_grounds_against_real_nested_forecast_response():
    """A rich forecast answer validates against the raw (nested) Google Weather
    JSON — the paths sit under forecastDays[i], so suffix matching must work.
    """
    import json

    from config import FIXTURES_DIR

    raw = json.loads(
        (FIXTURES_DIR / "google_weather" / "forecast_days.chennai.json").read_text()
    )["response"]
    day = raw["forecastDays"][1]
    answer = (
        f"Chennai tomorrow: {day['daytimeForecast']['precipitation']['probability']['percent']}% "
        f"chance of rain, high {day['maxTemperature']['degrees']}°C, "
        f"low {day['minTemperature']['degrees']}°C."
    )
    report = guardrail.check(answer, raw)
    assert report.ok
    assert report.matched == report.total == 3


def test_unit_swap_still_fails_on_nested_paths():
    raw = {"forecastDays": [{"maxTemperature": {"degrees": 33}, "relativeHumidity": 20}]}
    # 20 is humidity (percent); claiming 20°C must not pass
    report = guardrail.check("high 20°C", raw)
    assert not report.ok


def test_tamil_word_units_are_unit_aware():
    # Bhashini spells units as words ("டிகிரி செல்சியஸ்" / "சதவீதம்"), not
    # °C/%. Without recognizing those markers, these numbers would carry no
    # unit at all and match any field of the right value — reopening the
    # unit-swap bypass this guardrail exists to prevent.
    raw = {"temp_c": 31, "rain_probability_pct": 20}
    answer = "சென்னை: 20 டிகிரி செல்சியஸ்."  # claims humidity's 20 as celsius
    report = guardrail.check(answer, raw)
    assert not report.ok


def test_tamil_word_units_match_correct_field():
    raw = {"temp_c": 28, "humidity_pct": 81}
    answer = "சென்னை: 28 டிகிரி செல்சியஸ், ஈரப்பதம் 81 சதவீதமாக உள்ளது."
    report = guardrail.check(answer, raw)
    assert report.ok and report.matched == report.total == 2
    units = {f["path"]: f["unit"] for f in report.figures}
    assert units == {"temp_c": "celsius", "humidity_pct": "percent"}
