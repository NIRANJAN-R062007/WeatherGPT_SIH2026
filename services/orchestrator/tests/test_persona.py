"""Persona-aware advisories — profile-flag plumbing (plan.md §8 Phase 4, P1
item 9). Niranjan's item is the plumbing: /ask accepts and validates
`persona`, threads it through to narrate.build_prompt(), and echoes it back
in the response when non-default. persona.py's actual per-persona wording is
Mahesh's "prompt/template logic" item; the wiring tests here don't pin the
exact hint text, the wording tests at the end check its rules.
"""

import config
import main
import narrate
import occupation
import persona
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GOOGLE_WEATHER_API_KEY", "test-key")


def _ask(text, **params):
    return client.get("/ask", params={"text": text, **params}).json()


# ---- persona.py ---------------------------------------------------------------

def test_default_is_general():
    assert persona.DEFAULT == "general"
    assert persona.DEFAULT in persona.PERSONAS


def test_is_valid():
    assert persona.is_valid("farmer") is True
    assert persona.is_valid("general") is True
    assert persona.is_valid("astronaut") is False
    assert persona.is_valid(None) is False


def test_traveller_is_a_vetted_persona_but_not_an_occupation():
    # WIE-7: traveller is reachable directly via persona=traveller, never
    # through occupation.py's free-text classifier — "traveller" isn't a
    # job title, so it stays out of occupation.VETTED on purpose.
    assert persona.is_valid("traveller") is True
    assert "traveller" in persona.PERSONAS
    assert "traveller" not in occupation.VETTED


def test_hint_general_is_empty():
    assert persona.hint("general") == ""


def test_hint_known_personas_are_nonempty():
    for p in persona.PERSONAS - {"general"}:
        assert persona.hint(p) != ""


def test_hint_unknown_persona_is_empty_not_raising():
    assert persona.hint("not-a-real-persona") == ""


# ---- narrate.build_prompt() ----------------------------------------------------

def test_build_prompt_includes_persona_hint():
    facts = {"temp_c": 30, "day": "today"}
    prompt = narrate.build_prompt("current_weather", "Chennai", facts, persona="farmer")
    assert persona.hint("farmer") in prompt


def test_build_prompt_omits_persona_block_for_general():
    facts = {"temp_c": 30, "day": "today"}
    with_general = narrate.build_prompt("current_weather", "Chennai", facts, persona="general")
    without = narrate.build_prompt("current_weather", "Chennai", facts, persona=None)
    assert with_general == without  # "general" carries no hint, same as omitting persona


def test_build_prompt_different_personas_change_the_prompt():
    facts = {"temp_c": 30, "day": "today"}
    farmer = narrate.build_prompt("current_weather", "Chennai", facts, persona="farmer")
    fisherman = narrate.build_prompt("current_weather", "Chennai", facts, persona="fisherman")
    assert farmer != fisherman


# ---- /ask endpoint --------------------------------------------------------------

def test_ask_rejects_unknown_persona():
    resp = client.get("/ask", params={"text": "what's the weather in Chennai", "persona": "wizard"})
    assert resp.status_code == 422


def test_ask_default_persona_omits_field_from_response(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 28°C.")
    body = _ask("what's the weather in Chennai")
    assert "persona" not in body


def test_ask_non_default_persona_echoed_in_response(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 28°C.")
    body = _ask("what's the weather in Chennai", persona="farmer")
    assert body["persona"] == "farmer"


def test_ask_threads_persona_into_narrate(monkeypatch):
    seen = []

    def _narrate(intent, city, facts, lang, **kw):
        seen.append(kw.get("persona"))
        return "Chennai: 28°C."

    monkeypatch.setattr(main, "narrate", _narrate)
    _ask("what's the weather in Chennai", persona="fisherman")
    assert seen == ["fisherman"]


def test_ask_persona_has_no_effect_on_template_fallback(monkeypatch):
    # narrate() unavailable -> template path. persona must not appear in the
    # response text (persona.py's docstring: no effect on the fallback).
    monkeypatch.setattr(main, "narrate", lambda *a, **k: None)
    general = _ask("what's the weather in Chennai")
    farmer = _ask("what's the weather in Chennai", persona="farmer")
    assert general["response"] == farmer["response"]
    assert general["grounding"]["narration"] == "template"
    assert farmer["grounding"]["narration"] == "template"


# ---- persona wording (Mahesh's prompt/template item) ---------------------------

NAMED = sorted(persona.PERSONAS - {persona.DEFAULT})


@pytest.mark.parametrize("p", NAMED)
def test_every_hint_carries_the_shared_rules(p):
    h = persona.hint(p)
    assert "Do not add any number, time, duration, threshold or place" in h
    assert "Never say conditions are safe" in h
    assert "never say a warning or alert is in force" in h


@pytest.mark.parametrize("p", NAMED)
def test_hints_contain_no_digits(p):
    # A figure in the hint could be echoed into the answer, where the
    # guardrail would reject it as ungrounded.
    assert not any(ch.isdigit() for ch in persona.hint(p))


def test_farmer_hint_frames_field_work():
    h = persona.hint("farmer")
    assert "spraying" in h and "harvesting" in h and "lowest rain chance" in h
    assert "Never name a crop" in h


def test_fisherman_hint_rules_out_sea_state_and_points_to_imd():
    h = persona.hint("fisherman")
    assert "never mention waves, swell, tides or currents" in h
    assert "official IMD fishermen warning" in h


def test_aviation_hint_rules_out_aerodrome_figures():
    h = persona.hint("aviation")
    assert "never mention any" in h and "cloud base" in h
    assert "city forecast, not an airport observation" in h


def test_city_official_hint_is_operational():
    h = persona.hint("city_official")
    assert "waterlogging" in h and "outdoor workers" in h


def test_traveller_hint_frames_travel():
    h = persona.hint("traveller")
    assert "going out now or waiting" in h and "better one to travel" in h
    assert "Never name a destination" in h


def test_personas_get_a_bigger_word_cap():
    facts = {"temp_c": 30, "day": "today"}
    base = narrate.build_prompt("current_weather", "Chennai", facts)
    farmer = narrate.build_prompt("current_weather", "Chennai", facts, persona="farmer")
    assert "max 25 words" in base
    assert f"max {25 + persona.EXTRA_WORDS} words" in farmer


def test_persona_answer_gets_a_bigger_char_cap(monkeypatch):
    long = "Chennai: " + "calm and dry weather " * 20 + "today."
    monkeypatch.setattr(narrate, "run_chain", lambda *a, **k: (long, "gemini"))
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    facts = {"temp_c": 30, "day": "today"}
    plain = narrate.narrate("current_weather", "Chennai", facts)
    farmer = narrate.narrate("current_weather", "Chennai", facts, persona="farmer")
    assert len(plain) <= narrate.MAX_CHARS
    assert narrate.MAX_CHARS < len(farmer) <= narrate.MAX_CHARS + persona.EXTRA_CHARS


# ---- unvetted Custom persona: claim check ---------------------------------------

_FACTS = {"temp_c": 28}
_CUSTOM = persona.Custom("beekeeper")


def _grounded(monkeypatch, text, who):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: text)
    return main._narrate_grounded("current_weather", "Chennai", _FACTS, _FACTS, who)


@pytest.mark.parametrize("claim", [
    "Chennai: 28°C, a cyclone warning is in force.",
    "Chennai: 28°C and conditions are safe.",
    "Chennai: 28°C, unsafe outside.",
    "Chennai: 28°C, it is risk-free.",
    "Chennai: 28°C, there is no risk.",
    "Chennai: 28°C, an alert has been issued.",
    "Chennai: 28°C, you should evacuate.",
])
def test_custom_persona_claim_falls_back_to_template(monkeypatch, claim):
    text, _report, attempted, attempts, _ = _grounded(monkeypatch, claim, _CUSTOM)
    assert text is None and attempted and attempts == 2


def test_custom_persona_benign_text_passes(monkeypatch):
    text, _report, _, attempts, _ = _grounded(
        monkeypatch, "Chennai: 28°C, so plan outdoor work for the cooler hours.", _CUSTOM)
    assert text is not None and attempts == 1


def test_vetted_persona_may_point_to_official_warning(monkeypatch):
    said = "Chennai: 28°C; check the official IMD fishermen warning before going out."
    text, *_ = _grounded(monkeypatch, said, "fisherman")
    assert text == said


def test_custom_claim_in_ask_serves_template(monkeypatch):
    monkeypatch.setattr(main, "narrate", lambda *a, **k: "Chennai: 28°C, conditions are safe.")
    monkeypatch.setattr(main.occupation_module, "resolve",
                        lambda *a, **k: main.occupation_module.Resolved(
                            _CUSTOM, "beekeeper", "llm"))
    body = _ask("what's the weather in Chennai", occupation="beekeeper")
    assert body["grounding"]["narration"] == "template"
    assert "safe" not in body["response"].lower()
