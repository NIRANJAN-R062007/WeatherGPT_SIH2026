"""TFA-23: the rule-based advisory answer in all five languages (advisory/wording.py).

Done-when: each answer shape renders in en/hi/ta/te/mr with the agent off. Every
shape is built from the eval scenarios, and each answer must still pass the
advisory guardrail, so a translated sentence can't lose or change a figure."""

import sys

import config
import guardrail
import pytest
from advisory import agent, rubric, template, wording

sys.path.insert(0, str(config.REPO_ROOT / "ml" / "advisory"))

import scenarios  # noqa: E402

LANGS = ("en", "hi", "ta", "te", "mr")
TRIP = {"origin": "chennai", "destination": "madurai", "day": "today"}
SOW = {"district": "madurai", "crop": "groundnut"}

# (kind, slots, scenario, verdict): every verdict each kind has, and the reasons
# that lead to it (warnings, wind, storms, sea, season, rain, missing data).
SHAPES = [
    ("travel", TRIP, "clear", "go"),
    ("travel", TRIP, "rain_showers", "caution"),
    ("travel", TRIP, "orange_warning", "caution"),
    ("travel", TRIP, "warnings_off", "caution"),
    ("travel", TRIP, "red_warning", "avoid"),
    ("travel", TRIP, "thunderstorm_metar", "avoid"),
    ("travel", {**TRIP, "mode": "ferry"}, "strong_wind", "avoid"),
    ("travel", {**TRIP, "mode": "ferry"}, "clear", "caution"),
    ("travel", TRIP, "no_data", "not_available"),
    ("farming", SOW, "sow_ok", "suitable"),
    ("farming", SOW, "sow_too_wet", "not_suitable"),
    ("farming", SOW, "sow_too_hot", "not_suitable"),
    ("farming", SOW, "sow_out_of_season", "not_suitable"),
    ("farming", SOW, "sow_no_forecast", "not_available"),
    ("farming", SOW, "crop_missing", "not_available"),
]


def _facts(kind, slots, scenario):
    return scenarios.build(kind, slots, scenario)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind, slots, scenario, verdict", SHAPES,
                         ids=[f"{k}-{s.get('mode', 'any')}-{sc}" for k, s, sc, _ in SHAPES])
def test_every_shape_renders_and_grounds_in_every_language(kind, slots, scenario, verdict, lang):
    facts = _facts(kind, slots, scenario)
    answer = template.template_answer(facts, lang)
    assert answer["verdict"] == verdict
    sentences = answer["pros"] + answer["cons"]
    assert sentences
    if lang != "en":
        # Every sentence is in the asked language: none is the English one.
        english = template.template_answer(facts, "en")
        assert not set(sentences) & set(english["pros"] + english["cons"])
        assert all(not s.isascii() for s in sentences)
    report = guardrail.check_advisory(answer, facts)
    assert report.ok, report.problems


@pytest.mark.parametrize("lang", LANGS)
def test_the_answer_says_the_same_figures_in_every_language(lang):
    facts = _facts("farming", SOW, "sow_too_wet")
    figures = [s for s in template.template_answer(facts, "en")["cons"] if "%" in s]
    translated = [s for s in template.template_answer(facts, lang)["cons"] if "%" in s]
    digits = lambda s: sorted(c for c in s if c.isdigit())  # noqa: E731
    assert [digits(s) for s in figures] == [digits(s) for s in translated]


def test_english_is_word_for_word_what_it_was():
    facts = _facts("travel", TRIP, "orange_warning")
    cons = template.template_answer(facts)["cons"]
    assert "An orange IMD warning is in force at the destination." in cons
    farm = template.template_answer(_facts("farming", SOW, "sow_ok"))["pros"]
    assert any(p.startswith("The forecast falls within the crop file's sowing months (")
               for p in farm)


@pytest.mark.parametrize("lang", LANGS)
def test_the_override_adds_its_reason_once_in_the_asked_language(lang):
    facts = _facts("travel", TRIP, "red_warning")
    model = {"verdict": "go", "pros": ["Fine."], "cons": [], "window": None, "cites": []}
    answer = template.finish(facts, model, lang)
    assert answer["verdict"] == "avoid"
    reasons = rubric.override_reasons(facts, lang)
    assert reasons and answer["cons"][:len(reasons)] == reasons
    # The template's own red-warning sentence is the override's, so it isn't doubled.
    full = template.finish(facts, template.template_answer(facts, lang), lang)
    assert len(full["cons"]) == len(set(full["cons"]))


@pytest.mark.parametrize("lang", LANGS)
def test_the_unreviewed_crop_caveat_is_in_the_asked_language(lang):
    facts = _facts("farming", SOW, "sow_ok")
    model = {"verdict": "suitable", "pros": ["x"], "cons": [], "window": None, "cites": []}
    cons = template.finish(facts, model, lang)["cons"]
    assert cons[-1] == template.crop_not_reviewed(lang)


def test_agent_off_answers_in_the_asked_language(monkeypatch):
    monkeypatch.setattr(config, "ADVISORY_AGENT_ENABLED", False)
    advice = agent.advise("farming", {"district": "madurai", "crop": "groundnut"}, "ta")
    assert advice.path == "template"
    assert all(not s.isascii() for s in advice.answer["cons"])


def test_an_unknown_language_falls_back_to_english():
    assert wording.say("forecast_unavailable", "fr") == "The forecast is not available."
    assert wording.month("June", "fr") == "June"


def test_every_message_has_every_language_and_the_same_fields():
    import string

    for key, by_lang in wording.MESSAGES.items():
        assert set(by_lang) == set(LANGS), key
        fields = {lang: {f for _, f, _, _ in string.Formatter().parse(text) if f}
                  for lang, text in by_lang.items()}
        # English may carry its article; every other field must be in every language.
        assert all(fields[lang] == fields["en"] - {"article"} for lang in LANGS[1:]), key


@pytest.mark.parametrize("table", [wording.ROLES, wording.COLOURS, wording.MODES])
def test_every_word_table_has_every_language(table):
    assert all(set(row) == set(LANGS) for row in table.values())


def test_months_and_days_translate():
    assert wording.months(["June", "July"], "ta") == "ஜூன் மற்றும் ஜூலை"
    assert all(len(wording.MONTHS[lang].split()) == 12 for lang in LANGS[1:])
    assert wording.when("tomorrow", "hi") == "कल"
    assert wording.when("wednesday", "en") == "on Wednesday"
