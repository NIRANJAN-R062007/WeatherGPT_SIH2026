"""uv_index fact, end to end: weather_data -> router trimming -> i18n rendering
-> guardrail grounding -> nlu parameter extraction. See plan.md §14.
"""

import json
from pathlib import Path

import cities
import guardrail
import i18n
import nlu
import pytest
import router
import weather_data
from nlu import ParsedQuery

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "google_weather"


def _fixture_uv(city: str) -> int:
    payload = json.loads((_FIXTURE_DIR / f"current_conditions.{city}.json").read_text())
    return payload["response"]["uvIndex"]


@pytest.mark.parametrize("city", sorted(cities.CITY_KEYS))
def test_current_facts_includes_uv_index_from_fixture(city):
    facts = weather_data.get_weather(city, "current_weather", "today")
    assert facts is not None
    assert facts["uv_index"] == _fixture_uv(city)


def test_narration_facts_uv_trims_to_uv_and_meta():
    facts = weather_data.get_weather("chennai", "current_weather", "today")
    trimmed = router.narration_facts(facts, "uv")
    assert "uv_index" in trimmed
    assert trimmed["uv_index"] == facts["uv_index"]
    non_meta = set(trimmed) - router._META_KEYS
    assert non_meta == {"uv_index"}


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_i18n_render_includes_uv_figure_and_grounds(lang):
    facts = {"condition": "clear", "temp_c": 30, "uv_index": 7}
    answer = i18n.render("current_weather", "Chennai", facts, lang)
    assert "7" in answer
    report = guardrail.check(answer, facts)
    assert report.ok and report.matched == report.total


@pytest.mark.parametrize("lang", ["en", "ta", "hi", "te", "mr"])
def test_i18n_render_omits_uv_phrase_when_absent(lang):
    facts = {"condition": "clear", "temp_c": 30}
    answer = i18n.render("current_weather", "Chennai", facts, lang)
    assert guardrail.check(answer, facts).ok
    # No UV fact -> nothing in the answer should require a uv_index to ground.
    assert "uv_index" not in facts


def test_guardrail_grounds_uv_index_bare_integer():
    raw = {"uv_index": 7}
    assert guardrail.check("The UV index is 7 today.", raw).ok


def test_guardrail_rejects_wrong_uv_index_value():
    raw = {"uv_index": 3}
    report = guardrail.check("The UV index is 7 today.", raw)
    assert not report.ok


def test_nlu_parse_rules_uv_parameter():
    pq = nlu.parse("UV index in Chennai")
    assert isinstance(pq, ParsedQuery)
    assert pq.parameter == "uv"
