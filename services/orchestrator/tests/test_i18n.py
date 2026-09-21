"""The enriched templates read from the facts dict and every figure they emit
grounds. Missing optional facts degrade to a shorter sentence, not a KeyError.
"""

import copy
import re

import cities
import google_weather
import guardrail
import i18n
import pytest
import weather_data

NON_ENGLISH = ["ta", "hi", "te", "mr"]
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")  # the lone "C" of °C is allowed


def _patch_forecast(monkeypatch, mutate):
    orig = google_weather.snapshot

    def _snapshot(kind, city_key, **kw):
        snap = orig(kind, city_key, **kw)
        if kind == "forecast_days":
            payload = copy.deepcopy(snap.payload)
            mutate(payload["forecastDays"])
            return google_weather.Snapshot(snap.kind, snap.city, payload,
                                           snap.is_live, snap.retrieved_at, snap.source)
        return snap

    monkeypatch.setattr(google_weather, "snapshot", _snapshot)


def _break_display_date(days):
    for entry in days[2:]:
        entry["displayDate"] = {"year": "2026", "month": None}


def _break_display_date_and_start(days):
    _break_display_date(days)
    for entry in days[2:]:
        entry["interval"] = {}


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_current_template_grounds_four_figures(lang):
    # temp, feels-like, humidity, UV index
    facts = weather_data.get_weather("chennai", "current_weather", "today")
    answer = i18n.render("current_weather", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total == 4


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_forecast_template_grounds_three_figures(lang):
    facts = weather_data.get_weather("chennai", "will_it_rain", "tomorrow")
    answer = i18n.render("will_it_rain", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total == 3


def test_missing_optionals_degrade_gracefully():
    minimal = {"condition": "cloudy", "temp_c": 28}
    answer = i18n.render("current_weather", "Chennai", minimal, "en")
    assert answer == "Chennai: cloudy, 28°C right now."
    assert guardrail.check(answer, minimal).ok

    rain_min = {"condition": "rain", "rain_probability_pct": 40}
    answer = i18n.render("will_it_rain", "Madurai", rain_min, "ta")
    assert "40%" in answer and answer.endswith(".")
    assert guardrail.check(answer, rain_min).ok


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_multi_day_template_grounds(lang):
    facts = weather_data.multi_day_facts("chennai", 5)
    answer = i18n.render("forecast", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total >= 1
    if lang == "en":
        assert "forecast beyond that isn't available yet" not in answer


def test_multi_day_template_notes_cap_when_asked_beyond_fixture():
    # 7 requested, only FORECAST_DAYS available -> the template says so
    facts = weather_data.multi_day_facts("chennai", 7)
    answer = i18n.render("forecast", "Chennai", facts, "en")
    assert guardrail.check(answer, facts).ok
    assert "forecast beyond that isn't available yet" in answer


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_rain_so_far_template_grounds(lang):
    facts = weather_data.rain_so_far("chennai")
    answer = i18n.render("rainfall_so_far_today", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total >= 1


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_rain_last_24h_fallback_template_grounds(lang):
    facts = {"source": "x", "is_live": False, "issued": "2026-09-10T22:00Z",
             "rain_last_24h_mm": 1.96, "hours_counted": 24, "condition": "cloudy"}
    answer = i18n.render("rainfall_so_far_today", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total >= 1


def test_unknown_condition_key_falls_through():
    facts = {"condition": "frog_storm", "temp_c": 20}
    answer = i18n.render("current_weather", "Chennai", facts, "en")
    assert "frog_storm" in answer


# --- day labels (audit 2.1 / 2.2) ---

def test_day_labels_cover_every_key_weather_data_emits():
    keys = {"today", "tomorrow", *weather_data._WEEKDAYS, weather_data._LATER}
    for lang in i18n.SUPPORTED_LANGUAGES:
        assert set(i18n.DAY_LABELS[lang]) == keys
        assert all(value.strip() for value in i18n.DAY_LABELS[lang].values())


@pytest.mark.parametrize("lang", NON_ENGLISH)
def test_multi_day_template_translates_day_labels(lang):
    facts = weather_data.multi_day_facts("chennai", 5)
    answer = i18n.render("forecast", cities.display_name("chennai", lang), facts, lang)
    assert not LATIN_WORD.search(answer), answer  # no "today"/"wednesday" leaking through
    for day in facts["days"]:
        assert i18n.DAY_LABELS[lang][day["label"]] in answer
    assert guardrail.check(answer, facts).ok


def test_multi_day_template_capitalises_english_weekdays():
    facts = weather_data.multi_day_facts("chennai", 5)
    answer = i18n.render("forecast", "Chennai", facts, "en")
    for day in facts["days"][2:]:
        assert day["label"].capitalize() in answer
    assert answer.startswith("Chennai, next 5 days: today ")


def test_unknown_day_label_falls_through():
    facts = {"days": [{"label": "someday", "condition": "rain", "rain_probability_pct": 40}],
             "days_counted": 1}
    answer = i18n.render("forecast", "Chennai", facts, "ta")
    assert "someday" in answer and "40%" in answer


@pytest.mark.parametrize("lang", ["en", *NON_ENGLISH])
@pytest.mark.parametrize("mutate", [_break_display_date, _break_display_date_and_start])
def test_multi_day_template_grounds_with_malformed_display_date(monkeypatch, lang, mutate):
    # Regression: the old "day{index}" fallback label put a bare "3" in the text
    # that no unit-less field could ground, refusing a perfectly good forecast.
    _patch_forecast(monkeypatch, mutate)
    facts = weather_data.multi_day_facts("chennai", 5)
    answer = i18n.render("forecast", cities.display_name("chennai", lang), facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok
    # "next 5 days" + pct/high/low per day, and nothing else numeric
    assert report.matched == report.total == 1 + 3 * facts["days_counted"]
    if lang != "en":
        assert not LATIN_WORD.search(answer), answer
