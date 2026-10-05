"""retrieval.py: BM25 over the IMD reference corpus (Task C, plan.md §14).

Also covers narrate.build_prompt's reference-block injection and a guardrail
sanity check documenting why the prompt forbids quoting reference numbers.
"""

import config
import google_weather
import guardrail
import narrate
import pytest
import retrieval

# --- corpus -------------------------------------------------------------

def test_corpus_loads_and_entries_are_well_formed():
    retrieval.clear_cache()
    corpus = retrieval._build_corpus()
    assert len(corpus.docs) >= 15
    for doc in corpus.docs:
        p = doc.passage
        assert p.id
        assert p.topic
        assert p.text
        assert isinstance(p.keywords, list)
        assert p.source


# --- retrieve() -----------------------------------------------------------

FACTS_RAIN = {"condition": "showers", "rain_probability_pct": 80, "temp_c": 27}
FACTS_UV = {"condition": "sunny", "uv_index": 9, "uv_band": "very_high", "temp_c": 34}
_BANDED = {"uv_band": "uv_band", "rainfall_category": "rain_category", "wind": "wind_kmh"}


def _ids(passages, topic):
    return [p.id for p in passages if p.topic == topic]


def test_retrieve_rain_so_far_gets_only_its_own_rainfall_category():
    retrieval.clear_cache()
    facts = {"condition": "rain", "rain_so_far_mm": 30, "rain_category": "moderate"}
    passages = retrieval.retrieve("rainfall_so_far_today", facts)
    assert _ids(passages, "rainfall_category") == ["rain_moderate"]


def test_retrieve_a_chance_of_rain_gets_no_rainfall_category():
    # a probability says nothing about millimetres: no "extremely heavy" for 80%
    retrieval.clear_cache()
    passages = retrieval.retrieve("will_it_rain", FACTS_RAIN)
    assert _ids(passages, "rainfall_category") == []
    assert "glossary_chance_vs_so_far" in [p.id for p in passages]


def test_retrieve_current_weather_surfaces_uv_band():
    retrieval.clear_cache()
    passages = retrieval.retrieve("current_weather", FACTS_UV)
    assert _ids(passages, "uv_band") == ["uv_very_high"]


@pytest.mark.parametrize("band", [b["key"] for b in google_weather.load_bands("uv_bands")])
def test_retrieve_gets_the_passage_for_the_facts_uv_band_only(band):
    retrieval.clear_cache()
    passages = retrieval.retrieve("current_weather", {"uv_index": 1, "uv_band": band})
    assert _ids(passages, "uv_band") == [f"uv_{band}"]


def test_retrieve_suggests_no_sun_protection_at_a_low_uv_index():
    # persona answers turned "UV index 0" into "sunglasses helpful" (plan.md,
    # "any occupation" item, 2026-10-05)
    retrieval.clear_cache()
    facts = {"condition": "cloudy", "uv_index": 0, "uv_band": "low", "wind_kmh": 21}
    text = " ".join(p.text for p in retrieval.retrieve("current_weather", facts)).lower()
    assert "sunglasses" not in text and "sunscreen" not in text


@pytest.mark.parametrize("kmh,expected", [
    (0, ["wind_calm"]), (3, []), (10, ["wind_light"]), (20, ["wind_moderate"]),
    (38, ["wind_moderate"]), (39, ["wind_strong"]), (70, ["wind_gale"]),
])
def test_retrieve_gets_the_wind_passage_for_the_facts_speed_only(kmh, expected):
    retrieval.clear_cache()
    passages = retrieval.retrieve("current_weather", {"wind_kmh": kmh}, k=5)
    assert _ids(passages, "wind") == expected


def test_every_banded_passage_names_its_band():
    retrieval.clear_cache()
    keys = {
        "uv_band": {b["key"] for b in google_weather.load_bands("uv_bands")},
        "rain_category": {b["key"] for b in google_weather.load_bands("precipitation_categories")},
    }
    for doc in retrieval._build_corpus().docs:
        p = doc.passage
        if p.topic not in _BANDED:
            continue
        assert list(p.when) == [_BANDED[p.topic]], p.id
        want = p.when[_BANDED[p.topic]]
        if p.topic == "wind":
            low, high = want
            assert low is None or high is None or low < high, p.id
        else:
            assert want in keys[_BANDED[p.topic]], p.id


def test_applies_needs_the_fact_and_a_matching_value():
    p = retrieval.Passage("x", "t", "text", when={"uv_band": "low", "wind_kmh": [6, 20]})
    assert retrieval._applies(p, {"uv_band": "low", "wind_kmh": 6})
    assert not retrieval._applies(p, {"uv_band": "low", "wind_kmh": 20})  # max is exclusive
    assert not retrieval._applies(p, {"uv_band": "high", "wind_kmh": 10})
    assert not retrieval._applies(p, {"uv_band": "low"})                  # missing fact
    assert not retrieval._applies(p, {"uv_band": "low", "wind_kmh": True})
    assert not retrieval._applies(p, {"uv_band": "low", "wind_kmh": "10"})
    assert retrieval._applies(retrieval.Passage("y", "t", "text"), {})    # no condition


def test_retrieve_missing_corpus_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAG_CORPUS_DIR", tmp_path / "does_not_exist")
    retrieval.clear_cache()
    try:
        assert retrieval.retrieve("will_it_rain", FACTS_RAIN) == []
    finally:
        retrieval.clear_cache()


def test_retrieve_empty_corpus_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAG_CORPUS_DIR", tmp_path)
    retrieval.clear_cache()
    try:
        assert retrieval.retrieve("will_it_rain", FACTS_RAIN) == []
    finally:
        retrieval.clear_cache()


def test_format_context_empty_is_none():
    assert retrieval.format_context([]) is None


def test_format_context_nonempty_has_source():
    retrieval.clear_cache()
    passages = retrieval.retrieve("will_it_rain", FACTS_RAIN)
    ctx = retrieval.format_context(passages)
    assert ctx is not None
    assert "source:" in ctx


# --- build_prompt() reference block ---------------------------------------

def test_build_prompt_with_context_has_reference_block_and_no_numbers_rule():
    prompt = narrate.build_prompt(
        "will_it_rain", "Chennai", FACTS_RAIN,
        context="- Heavy rain means 64.5 mm or more. (source: x)",
    )
    assert "Reference" in prompt
    assert "do NOT quote any number from it" in prompt
    assert "64.5 mm" in prompt  # the reference text itself is passed through
    assert "Intent:" in prompt


def test_build_prompt_without_context_has_no_reference_block():
    prompt = narrate.build_prompt("will_it_rain", "Chennai", FACTS_RAIN)
    assert "Reference" not in prompt


# --- narrate() with RAG_ENABLED False mirrors prior behaviour -------------

FACTS = {"condition": "cloudy", "temp_c": 28, "feels_like_c": 32.5,
         "humidity_pct": 81, "source": "x", "issued": "2026-09-10T22:00Z", "is_live": False}


def test_narrate_with_rag_disabled_still_works(monkeypatch):
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(narrate, "generate",
                         lambda *a, **k: "Chennai: cloudy, 28°C right now.")
    out = narrate.narrate("current_weather", "Chennai", FACTS, "en")
    assert out == "Chennai: cloudy, 28°C right now."


def test_narrate_with_rag_disabled_never_calls_retrieve(monkeypatch):
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")

    def _boom(*a, **k):
        raise AssertionError("retrieval.retrieve() was called")

    monkeypatch.setattr(retrieval, "retrieve", _boom)
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: "Chennai: cloudy, 28°C right now.")
    out = narrate.narrate("current_weather", "Chennai", FACTS, "en")
    assert out == "Chennai: cloudy, 28°C right now."


def test_narrate_retrieval_failure_does_not_break_narration(monkeypatch):
    monkeypatch.setattr(config, "RAG_ENABLED", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")

    def _boom(*a, **k):
        raise RuntimeError("retriever bug")

    monkeypatch.setattr(retrieval, "retrieve", _boom)
    monkeypatch.setattr(narrate, "generate", lambda *a, **k: "Chennai: cloudy, 28°C right now.")
    out = narrate.narrate("current_weather", "Chennai", FACTS, "en")
    assert out == "Chennai: cloudy, 28°C right now."


# --- guardrail sanity: why the prompt forbids quoting reference numbers ---

def test_guardrail_rejects_a_number_quoted_from_the_reference_corpus():
    raw_weather_facts_without_that_number = {"condition": "showers", "rain_probability_pct": 80}
    report = guardrail.check(
        "Heavy rain means 64.5 mm or more", raw_weather_facts_without_that_number
    )
    assert report.ok is False
    unmatched = [f for f in report.figures if not f["matched"]]
    assert any(f["value"] == pytest.approx(64.5) for f in unmatched)
