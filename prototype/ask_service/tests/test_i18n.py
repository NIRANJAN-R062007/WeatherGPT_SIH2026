"""The enriched templates read from the facts dict and every figure they emit
grounds. Missing optional facts degrade to a shorter sentence, not a KeyError.
"""

import guardrail
import i18n
import pytest
import weather_data


@pytest.mark.parametrize("lang", ["en", "ta"])
def test_current_template_grounds_three_figures(lang):
    facts = weather_data.get_weather("chennai", "current_weather", "today")
    answer = i18n.render("current_weather", "Chennai", facts, lang)
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total == 3


@pytest.mark.parametrize("lang", ["en", "ta"])
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


def test_unknown_condition_key_falls_through():
    facts = {"condition": "frog_storm", "temp_c": 20}
    answer = i18n.render("current_weather", "Chennai", facts, "en")
    assert "frog_storm" in answer
