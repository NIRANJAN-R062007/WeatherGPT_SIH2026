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
# The celsius/percent/speed_kmh words were native-speaker reviewed on Sep 13
# (commit fce2ad9); the millimetres rows were not (see the TODO markers on
# guardrail._WORD_UNIT_MARKERS). Neither set was reverse-engineered from real
# translated output the way the Tamil cases above were. These tests only prove
# the guardrail table mechanics are unit-aware for each language; they do not
# prove the marker strings match real Bhashini output, which still needs a
# live-translation QA pass.

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


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
@pytest.mark.parametrize("city", sorted(["chennai", "madurai", "coimbatore"]))
def test_translated_day_labels_add_nothing_for_the_guardrail_to_match(lang, city):
    # i18n.DAY_LABELS renders the multi-day labels in-language (audit 2.1). They
    # are words, not figures, so the only numbers left are "next N days" plus
    # pct/high/low per day — every one grounded, nothing new for _match to learn.
    from weather_data import multi_day_facts

    facts = multi_day_facts(city, 5)
    answer = render("forecast", city.capitalize(), facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok
    assert report.matched == report.total == 1 + 3 * facts["days_counted"]


def test_unmarked_number_cannot_borrow_a_unit_bearing_field():
    raw = {"temp_c": 30, "humidity_pct": 65, "wind_kmh": 12}
    report = guardrail.check("The wind speed is 65 right now.", raw)
    assert report.ok is False
    assert report.figures[0]["path"] is None


def test_unmarked_number_still_grounds_to_a_count_field():
    raw = {"rain_so_far_mm": 0.24, "hours_counted": 16}
    report = guardrail.check("Chennai: 0.24 mm of rain over 16 hours.", raw)
    assert report.ok is True
    assert report.figures[1]["path"] == "hours_counted"


# --- WIE-5: clock times and time ranges ------------------------------------
# Synthetic hours shaped like weather_data.hourly_facts()'s `hours`, so the
# window (and every boundary around it) is exact.


def _hour(local_time, *, rain=10, temp=26, wind=10):
    return {"time_iso": f"2026-10-01T{local_time}:00Z", "local_time": local_time,
            "rain_probability_pct": rain, "temp_c": temp, "wind_kmh": wind}


def _window_raw():
    """Engine result for a day with exactly one suitable run, 08:00-11:00."""
    from weather_intelligence.window_analyzer import find_best_window

    hours = [_hour("06:00", rain=70), _hour("07:00", rain=60),
             _hour("08:00"), _hour("09:00"), _hour("10:00"), _hour("11:00"),
             _hour("12:00", rain=50), _hour("13:00", rain=80)]
    window = find_best_window(hours)
    assert (window["start_local"], window["end_local"]) == ("08:00", "11:00")
    return {"window": window, "hours": hours}


def test_window_the_engine_produced_passes_in_every_time_notation():
    raw = _window_raw()
    for answer in (
        "The best window is 8 AM–11 AM.",
        "The best window is 8 AM-11 AM.",
        "The best window is 8:00 AM to 11:00 AM.",
        "The best window is 08:00–11:00.",
        "Go between 8 AM and 11 AM.",
        "Go from 8am until 11am.",
        "Go from 8 a.m. to 11 a.m.",
        "The best window is 8–11 AM.",
    ):
        report = guardrail.check(answer, raw)
        assert report.ok and report.matched == report.total == 1, answer
        assert report.figures[0]["unit"] == "clock_range", answer
        assert report.figures[0]["value"] == 8 * 60
        assert report.figures[0]["end_value"] == 11 * 60


def test_window_the_engine_did_not_produce_fails():
    # The done-when for WIE-5: 8 AM and 10 AM are both real hours in the
    # result, but 08:00-10:00 is not the window the engine returned.
    raw = _window_raw()
    for answer in (
        "The best window is 8 AM–10 AM.",   # real hours, wrong pair
        "The best window is 9 AM–11 AM.",
        "The best window is 8 AM–12 PM.",   # end of the last hour, not the engine's end
        "The best window is 2 PM–5 PM.",    # no such hours at all
        "The best window is 14:00–17:00.",
        "The best window is 11 AM–8 AM.",   # reversed
        "The best window is 8–10 AM.",
    ):
        report = guardrail.check(answer, raw)
        assert not report.ok, answer
        assert report.figures[0]["path"] is None, answer


def test_window_quoted_when_the_engine_found_none_fails():
    # "No suitable window" must not be quietly overwritten by a narration that
    # names one anyway (plan.md R17).
    hours = [_hour("08:00", rain=60), _hour("09:00", rain=70)]
    raw = {"window": None, "hours": hours}
    report = guardrail.check("The best window is 8 AM–9 AM.", raw)
    assert not report.ok


def test_a_single_time_must_be_a_time_in_the_result():
    raw = _window_raw()
    assert guardrail.check("It starts to clear around 9 AM.", raw).ok
    assert guardrail.check("It starts to clear at 09:00.", raw).ok
    assert guardrail.check("It starts to clear at 12 PM.", raw).ok      # 12:00 is an hour
    assert not guardrail.check("It starts to clear at 4 PM.", raw).ok   # 16:00 isn't
    assert not guardrail.check("It starts to clear at 9:30 AM.", raw).ok


def test_and_only_joins_a_range_after_between():
    raw = _window_raw()
    # Two real, separate hours — not a window. Without "between" they are two
    # lone times, each grounded on its own.
    report = guardrail.check("Showers at 8 AM and 11 AM.", raw)
    assert report.ok and report.total == 2
    assert [f["unit"] for f in report.figures] == ["clock", "clock"]
    # With "between" the same pair is a claimed window, and 8-11 is the engine's.
    assert guardrail.check("Between 8 AM and 11 AM.", raw).ok
    assert not guardrail.check("Between 8 AM and 10 AM.", raw).ok


def test_meridiem_is_read_correctly_around_noon_and_midnight():
    raw = {"hours": [_hour("00:00"), _hour("12:00"), _hour("13:00")]}
    assert guardrail.check("12 AM", raw).ok       # midnight
    assert guardrail.check("12 PM", raw).ok       # noon
    assert guardrail.check("1 PM", raw).ok
    assert not guardrail.check("12 AM", {"hours": [_hour("12:00")]}).ok
    assert not guardrail.check("1 AM", raw).ok


def test_shared_meridiem_range_across_noon():
    raw = {"window": {"start_local": "11:00", "end_local": "13:00"}}
    assert guardrail.check("Go 11–1 PM.", raw).ok  # 11 AM–1 PM
    assert not guardrail.check("Go 11–1 AM.", raw).ok


def test_time_digits_are_not_also_read_as_figures():
    # "8 AM–11 AM" must not leave 8 and 11 behind as unit-less numbers that
    # could ground to a count field by coincidence.
    raw = {"window": {"start_local": "08:00", "end_local": "11:00"}, "hours_counted": 11}
    report = guardrail.check("Best window 8 AM–11 AM.", raw)
    assert report.ok and report.total == 1


def test_a_clock_time_cannot_ground_to_a_number_or_vice_versa():
    # 8 is a unit-less count here; "8 AM" is a time and must not borrow it.
    assert not guardrail.check("It clears by 8 AM.", {"hours_counted": 8}).ok
    # ...and a bare "8" is still a number, not a time.
    raw = {"window": {"start_local": "08:00", "end_local": "11:00"}}
    assert not guardrail.check("Over 8 hours.", raw).ok


def test_invalid_times_are_not_waved_through():
    raw = _window_raw()
    for answer in ("Clears at 25:00.", "Clears at 13 PM.", "Clears at 8:75 AM."):
        assert not guardrail.check(answer, raw).ok, answer


def test_iso_timestamps_and_decimals_are_not_clock_times():
    raw = {"temp_c": 31.5}
    report = guardrail.check("Chennai: 31.5°C.", raw)
    assert report.ok and report.total == 1 and report.figures[0]["unit"] == "celsius"


def test_numbers_beside_a_window_still_ground_independently():
    raw = _window_raw()
    ok = "8 AM–11 AM: around 26.0°C, up to 10% chance of rain, winds up to 10.0 km/h."
    assert guardrail.check(ok, raw).ok
    bad = "8 AM–11 AM: around 26.0°C, up to 40% chance of rain, winds up to 10.0 km/h."
    report = guardrail.check(bad, raw)
    assert not report.ok and report.matched == report.total - 1


def test_the_engines_own_best_window_sentence_passes_the_guardrail():
    # WIE-4's deterministic /ask sentence is the shape an LLM narration of the
    # same window would take; it must ground fully, aggregates included.
    from main import _best_window_text, _no_suitable_window_text

    raw = _window_raw()
    text = _best_window_text("Chennai", "tomorrow", raw["window"])
    report = guardrail.check(text, raw)
    assert report.ok and report.matched == report.total == 4
    assert [f["unit"] for f in report.figures] == ["celsius", "percent", "speed_kmh", "clock_range"]
    # ...and a "no suitable window" sentence has no figures to ground.
    assert guardrail.check(_no_suitable_window_text("Chennai", "tomorrow"), raw).total == 0


def test_translated_answers_with_native_digits_ground_the_same_way():
    raw = _window_raw()
    # Devanagari digits, as Bhashini may emit them; the AM/PM markers are the
    # Latin ones an English template passes through.
    assert guardrail.check("८ AM–११ AM", raw).ok
    assert not guardrail.check("८ AM–१० AM", raw).ok
