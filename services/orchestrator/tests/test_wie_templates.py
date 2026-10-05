"""WIE-8: the Weather Intelligence Engine's answers render in en/hi/ta/te/mr
from i18n.py's templates with no LLM (plan.md §15's "No LLM" row) — the
best window, "no suitable window", the persona caveat, the forecast change
and the what-if comparison. Every figure and clock time stays as the engine
produced it, so the sentences ground the same way in every language."""

import guardrail
import i18n
import main
import narrate
import pytest
import weather_data
from fastapi.testclient import TestClient
from weather_intelligence import persona_advisor
from weather_intelligence.window_analyzer import find_best_window

client = TestClient(main.app)
LANGS = i18n.SUPPORTED_LANGUAGES


def _hour(t, *, rain=10, temp=26.0, wind=10.0):
    return {"time_iso": f"2026-10-01T{t}:00Z", "local_time": t, "rain_probability_pct": rain,
            "temp_c": temp, "wind_kmh": wind, "condition": "clear"}


HOURS = [_hour("06:00", rain=70), _hour("07:00", rain=60), _hour("08:00"), _hour("09:00"),
         _hour("10:00"), _hour("11:00"), _hour("12:00", rain=50), _hour("13:00", rain=80)]
WINDOW = find_best_window(HOURS)
CHANGES = {"status": "ok", "changes": [
    {"metric": "rain_probability_pct", "direction": "rose", "from": 30, "to": 70,
     "start_local": "14:00", "end_local": "17:00"},
    {"metric": "temp_c", "direction": "fell", "from": 31.5, "to": 28, "start_local": "15:00",
     "end_local": "15:00"},
]}
SCENARIO = {"hours": [
    {"time": "09:00", "available": True, "temp_c": 26.0, "rain_probability_pct": 10,
     "wind_kmh": 10.0},
    {"time": "17:00", "available": True, "temp_c": 29.0, "rain_probability_pct": 60,
     "wind_kmh": 18.0},
    {"time": "23:00", "available": False},
], "better_time": "09:00"}


def _no_placeholders(text):
    assert "{" not in text and "}" not in text


# --- every shape in every language -------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
def test_best_window_renders_and_grounds_in_every_language(lang):
    text = i18n.best_window_text("Chennai", "tomorrow", WINDOW, lang)
    _no_placeholders(text)
    assert "08:00–12:00" in text  # hours 08:00-11:00 are suitable; the window ends at 12:00
    report = guardrail.check(text, {"window": WINDOW, "hours": HOURS})
    assert report.ok and report.matched == report.total == 4
    assert "safe" not in text.lower()


@pytest.mark.parametrize("lang", LANGS)
def test_a_one_hour_window_reads_as_that_hour_in_every_language(lang):
    hours = [_hour(f"{h:02d}:00", rain=60) for h in range(10, 20)]
    hours[4] = _hour("14:00")
    window = find_best_window(hours)
    text = i18n.best_window_text("Chennai", "today", window, lang)
    assert "14:00–15:00" in text and "14:00–14:00" not in text
    assert guardrail.check(text, {"window": window, "hours": hours}).ok


@pytest.mark.parametrize("lang", LANGS)
def test_no_suitable_window_renders_with_no_figures(lang):
    text = i18n.no_suitable_window_text("Chennai", "today", lang)
    _no_placeholders(text)
    assert guardrail.check(text, {"window": None, "hours": HOURS}).total == 0


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("persona", ["fisherman", "aviation"])
def test_persona_caveat_renders_in_every_language(lang, persona):
    text = i18n.persona_caveat(persona, lang)
    _no_placeholders(text)
    if persona == "fisherman":
        assert "IMD" in text


@pytest.mark.parametrize("lang", LANGS)
def test_forecast_change_renders_both_values_and_both_times(lang):
    text = i18n.changes_text("Chennai", "tomorrow", CHANGES, "2026-10-04 06:00 UTC",
                             "2026-10-04 07:00 UTC", lang)
    _no_placeholders(text)
    for piece in ("30%", "70%", "31.5°C", "28°C", "14:00–17:00", "15:00",
                  "2026-10-04 06:00 UTC", "2026-10-04 07:00 UTC"):
        assert piece in text


@pytest.mark.parametrize("lang", LANGS)
def test_no_significant_change_still_names_both_times(lang):
    text = i18n.changes_text("Chennai", "today", {"status": "no_significant_change",
                                                  "changes": []},
                             "2026-10-04 06:00 UTC", "2026-10-04 07:00 UTC", lang)
    _no_placeholders(text)
    assert "06:00 UTC" in text and "07:00 UTC" in text


@pytest.mark.parametrize("lang", LANGS)
def test_what_if_renders_each_hour_and_never_invents_a_missing_one(lang):
    text = i18n.scenario_text("Chennai", "tomorrow", SCENARIO, lang)
    _no_placeholders(text)
    for piece in ("09:00", "26°C", "10%", "17:00", "29°C", "60%", "18 km/h", "23:00"):
        assert piece in text
    assert text.count("09:00") == 2  # its figures, then named as the lower rain chance
    tie = {**SCENARIO, "better_time": None}
    assert i18n.scenario_text("Chennai", "tomorrow", tie, lang).count("09:00") == 1


# --- English is unchanged from the WIE-4/WIE-11 sentences ----------------------


def test_english_sentences_are_unchanged():
    assert i18n.best_window_text("Chennai", "tomorrow", WINDOW, "en") == (
        "Chennai: the most suitable window to be outdoors tomorrow is 08:00–12:00 "
        f"(around {WINDOW['avg_temp_c']}°C, up to 10% chance of rain, winds up to "
        f"{WINDOW['max_wind_kmh']} km/h)."
    )
    assert i18n.changes_text("Chennai", "tomorrow", CHANGES, "A", "B", "en") == (
        "Chennai: tomorrow's chance of rain rose from 30% to 70% (mostly 14:00–17:00); "
        "temperature fell from 31.5°C to 28°C (around 15:00) "
        "since the forecast retrieved A (now B)."
    )


def test_english_caveats_match_the_persona_advisor():
    for persona, caveat in persona_advisor.CAVEATS.items():
        assert i18n.persona_caveat(persona, "en") == caveat


def test_an_unsupported_language_falls_back_to_english():
    assert i18n.best_window_text("Chennai", "today", WINDOW, "xx") == \
        i18n.best_window_text("Chennai", "today", WINDOW, "en")


# --- /ask with the LLM off ----------------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("persona", ["general", "fisherman"])
def test_ask_best_window_with_no_llm_answers_in_language(monkeypatch, lang, persona):
    monkeypatch.setattr(narrate, "is_configured", lambda: False)
    monkeypatch.setattr(weather_data, "hourly_facts",
                        lambda key, day: {"source": "fixture", "is_live": False, "day": day,
                                          "hours": HOURS})
    body = client.get("/ask", params={"text": "best time to go outside tomorrow in Chennai",
                                      "lang": lang, "persona": persona}).json()
    assert body["intent"] == "best_window" and "notice" not in body
    assert body["grounding"]["provider"] == "feed"
    if persona == "fisherman":
        assert body["response"] == i18n.persona_caveat("fisherman", lang)
    else:
        assert body["response"] == i18n.best_window_text(
            main.cities.display_name("chennai", lang), "tomorrow", WINDOW, lang)


@pytest.mark.parametrize("lang", LANGS)
def test_ask_best_window_unavailable_is_in_language(monkeypatch, lang):
    monkeypatch.setattr(weather_data, "hourly_facts", lambda key, day: None)
    body = client.get("/ask", params={"text": "best time to go outside tomorrow in Chennai",
                                      "lang": lang}).json()
    assert body["message"] == main._MESSAGES["best_window_unavailable"][lang]
