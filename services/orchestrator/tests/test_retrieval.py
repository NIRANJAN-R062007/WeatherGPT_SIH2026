"""retrieval.py: BM25 over the IMD reference corpus (Task C, plan.md §14).

Also covers narrate.build_prompt's reference-block injection and a guardrail
sanity check documenting why the prompt forbids quoting reference numbers.
"""

import config
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
FACTS_UV = {"condition": "sunny", "uv_index": 9, "temp_c": 34}


def test_retrieve_will_it_rain_ranks_rainfall_category_first():
    retrieval.clear_cache()
    passages = retrieval.retrieve("will_it_rain", FACTS_RAIN)
    assert passages
    assert passages[0].topic == "rainfall_category"


def test_retrieve_current_weather_surfaces_uv_band():
    retrieval.clear_cache()
    passages = retrieval.retrieve("current_weather", FACTS_UV)
    assert any(p.topic == "uv_band" for p in passages)


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
