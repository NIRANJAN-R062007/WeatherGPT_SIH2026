"""Adversarial suite for the grounding guardrail (plan.md §14 / §11 risk R2).

First tests in this repo. Exercises guardrail.check() directly against both
template outputs and hostile answers, plus the full `/ask` path end to end.
"""

import guardrail
import pytest
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


def test_tamil_wind_speed_word_unit_is_unit_aware():
    # Same class of bug as the celsius/percent case: "14 கிமீ" carried no
    # marker before, so it could ground against ANY field valued 14.
    raw = {"temp_c": 14, "wind_kmh": 20}
    answer = "சென்னை: மணிக்கு 14 கிமீ வேகத்தில் காற்று வீசுகிறது."
    report = guardrail.check(answer, raw)
    assert not report.ok  # 14 is temp_c, not wind_kmh; must not pass on value alone


def test_mm_unit_is_unit_aware():
    raw = {"rain_so_far_mm": 2, "temp_c": 20}
    answer = "Chennai: 20 mm of rain so far."
    report = guardrail.check(answer, raw)
    assert not report.ok  # 20 is temp_c, not rain_so_far_mm; must not pass on value alone


def test_mm_unit_matches_correct_field():
    raw = {"rain_so_far_mm": 1.97}
    answer = "Chennai: 1.97 mm of rain so far."
    report = guardrail.check(answer, raw)
    assert report.ok and report.matched == report.total == 1
    assert report.figures[0]["unit"] == "millimetres"


def test_nested_qpf_grounds_against_raw_history_fixture():
    import json

    from config import FIXTURES_DIR

    path = FIXTURES_DIR / "google_weather" / "history_hours.chennai.json"
    if not path.exists():
        import pytest

        pytest.skip("history_hours fixture not present")
    raw = json.loads(path.read_text())["response"]
    qty = raw["historyHours"][0]["precipitation"]["qpf"]["quantity"]
    report = guardrail.check(f"Chennai: {qty} mm so far.", raw)
    assert report.ok and report.matched == report.total == 1


def test_tamil_wind_speed_word_unit_matches_correct_field():
    raw = {"wind_kmh": 14}
    answer = "சென்னை: மணிக்கு 14 கிமீ வேகத்தில் காற்று வீசுகிறது."
    report = guardrail.check(answer, raw)
    assert report.ok and report.matched == report.total == 1
    assert report.figures[0]["unit"] == "speed_kmh"
    assert report.figures[0]["path"] == "wind_kmh"


# --- hi/te/mr word-unit coverage (plan.md §13) ---
# First-draft guesses at Bhashini's spelled-out unit words for these three
# languages, NOT reverse-engineered from real translated output the way the
# Tamil cases above were — see the TODO on guardrail._WORD_UNIT_MARKERS.
# These tests only prove the guardrail table mechanics are unit-aware for
# each language; they do not prove the marker strings match real Bhashini
# output, which still needs a native-speaker + live-translation QA pass.

_WORD_UNIT_CASES = [
    ("hi", "चेन्नई: 20 डिग्री सेल्सियस.",
     "चेन्नई: 28 डिग्री सेल्सियस, आर्द्रता 81 प्रतिशत है.",
     "चेन्नई: हवा 14 किमी प्रति घंटा की गति से चल रही है."),
    ("te", "చెన్నై: 20 డిగ్రీల సెల్సియస్.",
     "చెన్నై: 28 డిగ్రీల సెల్సియస్, తేమ 81 శాతం గా ఉంది.",
     "చెన్నై: గంటకు 14 కిమీ వేగంతో గాలి వీస్తోంది."),
    ("mr", "चेन्नई: 20 अंश सेल्सिअस.",
     "चेन्नई: 28 अंश सेल्सिअस, आर्द्रता 81 टक्के आहे.",
     "चेन्नई: वाऱ्याचा वेग ताशी 14 किमी आहे."),
]


@pytest.mark.parametrize(("lang", "unit_swap_answer", "match_answer", "wind_answer"),
                         _WORD_UNIT_CASES)
def test_word_units_are_unit_aware(lang, unit_swap_answer, match_answer, wind_answer):
    # claims humidity's 20 as celsius; must not pass just because 20 exists in raw
    raw = {"temp_c": 31, "rain_probability_pct": 20}
    report = guardrail.check(unit_swap_answer, raw)
    assert not report.ok


@pytest.mark.parametrize(("lang", "unit_swap_answer", "match_answer", "wind_answer"),
                         _WORD_UNIT_CASES)
def test_word_units_match_correct_field(lang, unit_swap_answer, match_answer, wind_answer):
    raw = {"temp_c": 28, "humidity_pct": 81}
    report = guardrail.check(match_answer, raw)
    assert report.ok and report.matched == report.total == 2
    units = {f["path"]: f["unit"] for f in report.figures}
    assert units == {"temp_c": "celsius", "humidity_pct": "percent"}


@pytest.mark.parametrize(("lang", "unit_swap_answer", "match_answer", "wind_answer"),
                         _WORD_UNIT_CASES)
def test_wind_speed_word_unit_is_unit_aware(lang, unit_swap_answer, match_answer, wind_answer):
    raw = {"temp_c": 14, "wind_kmh": 20}
    report = guardrail.check(wind_answer, raw)
    assert not report.ok  # 14 is temp_c, not wind_kmh; must not pass on value alone


@pytest.mark.parametrize(("lang", "unit_swap_answer", "match_answer", "wind_answer"),
                         _WORD_UNIT_CASES)
def test_wind_speed_word_unit_matches_correct_field(lang, unit_swap_answer, match_answer,
                                                    wind_answer):
    raw = {"wind_kmh": 14}
    report = guardrail.check(wind_answer, raw)
    assert report.ok and report.matched == report.total == 1
    assert report.figures[0]["unit"] == "speed_kmh"
    assert report.figures[0]["path"] == "wind_kmh"
