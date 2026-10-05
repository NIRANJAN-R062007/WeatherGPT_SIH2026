"""Runs ml/occupation/eval_set.jsonl (plan.md §8 Phase 4 "any occupation" item,
R12). Filter and rules rows must come out right with no LLM; llm rows need real
keys and network, so their classifier check is marked live. Also checks that the
set covers what the plan asks of it, and the two runners' scoring offline.
"""

import json
import logging
import sys

import config
import main
import narrate
import occupation
import pytest

sys.path.insert(0, str(config.REPO_ROOT / "ml" / "occupation"))

import occupation_eval  # noqa: E402
import occupation_live_check as live_check  # noqa: E402

_ROWS = occupation_eval.load_rows()
_OFFLINE = [r for r in _ROWS if r["path"] != "llm"]
_LLM = [r for r in _ROWS if r["path"] == "llm"]


# --- the eval set ------------------------------------------------------------------


def test_rows_are_well_formed():
    assert len({r["id"] for r in _ROWS}) == len(_ROWS)
    for r in _ROWS:
        assert r["lang"] in occupation_eval.LANGS
        assert r["path"] in occupation_eval.PATHS
        assert r["expected"] in (*occupation.CATEGORIES, occupation_eval.REJECTED)
        assert (r["expected"] == occupation_eval.REJECTED) == (r["path"] == "filter"), r["id"]
        assert isinstance(r["injection"], bool) and isinstance(r["native_qa"], bool)


@pytest.mark.parametrize("lang", occupation_eval.LANGS)
def test_each_language_covers_both_sides_of_the_boundary_and_injection(lang):
    rows = [r for r in _ROWS if r["lang"] == lang]
    by_llm = {r["expected"] for r in rows if r["path"] == "llm"}
    assert by_llm & set(occupation.VETTED)  # a vetted persona only the classifier finds
    assert occupation.OTHER in by_llm
    assert occupation.NOT_AN_OCCUPATION in by_llm
    assert any(r["path"] == "rules" for r in rows)
    assert any(r["path"] == "filter" for r in rows)
    assert any(r["injection"] and r["path"] == "llm" for r in rows)  # one the filter lets through


@pytest.mark.parametrize("row", _OFFLINE, ids=[r["id"] for r in _OFFLINE])
def test_filter_and_rules_rows(monkeypatch, row):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(narrate, "run_chain",
                        lambda *a, **k: pytest.fail("classifier called for a rules row"))
    r = occupation_eval.run_row(row, occupation, narrate)
    assert r["ok"], r


@pytest.mark.parametrize("row", _LLM, ids=[r["id"] for r in _LLM])
def test_llm_rows_pass_the_filter_and_miss_the_rules(row):
    # otherwise the row measures the filter or the rules, not the classifier
    assert occupation._rules(occupation.clean(row["text"])) is None


@pytest.mark.live
@pytest.mark.skipif(
    not (config.GEMINI_API_KEY or config.GROQ_API_KEY), reason="no LLM key configured"
)
@pytest.mark.parametrize("row", _LLM, ids=[r["id"] for r in _LLM])
def test_llm_rows_live(monkeypatch, row):
    monkeypatch.setattr(config, "OLLAMA_MODEL", None)
    occupation.cache_clear()
    r = occupation_eval.run_row(row, occupation, narrate)
    if r["got"] is None:
        pytest.skip(f"the classifier gave no answer: {r['error']}")
    assert r["ok"], r


# --- occupation_eval.py ---------------------------------------------------------------------


def test_outcome_names_the_category_behind_each_persona():
    p, R = occupation.persona_module, occupation.Resolved
    assert occupation_eval.outcome(R("farmer", "x", "rules")) == ("farmer", "rules")
    assert occupation_eval.outcome(R(p.Custom("x"), "x", "llm")) == ("other", "llm")
    assert occupation_eval.outcome(R("general", "x", "llm")) == ("not_an_occupation", "llm")
    assert occupation_eval.outcome(R("general", "x", "unclassified")) == \
        (None, "unclassified")


def test_a_classifier_failure_is_unanswered_not_wrong(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    occupation.cache_clear()

    def run_chain(*a, **k):
        logging.getLogger("weathergpt.narrate").warning(
            "groq occupation classify failed (Client error '429 Too Many Requests' "
            "for url 'https://api.example/chat')")
        return None, None
    monkeypatch.setattr(narrate, "run_chain", run_chain)
    row = {"id": "x", "lang": "en", "path": "llm", "injection": False,
           "text": "delivery rider", "expected": "other"}
    r = occupation_eval.run_row(row, occupation, narrate)
    assert (r["got"], r["ok"]) == (None, False)
    assert "429" in r["error"] and "api.example" not in r["error"]
    s = occupation_eval.summarise([r])
    assert (s["answered"], s["unanswered"], s["rate_limited"], s["misses"]) == (0, 1, 1, [])


def _result(id_, lang, expected, got, latency=None, provider=None, injection=False):
    return {"id": id_, "lang": lang, "path": "llm", "injection": injection, "text": id_,
            "expected": expected, "got": got, "provider": provider,
            "latency_s": latency, "error": None, "ok": got == expected}


def test_summarise_scores_answered_rows_by_language_and_category():
    results = [
        _result("a", "en", "farmer", "farmer", 0.5, "groq"),
        _result("b", "hi", "other", "farmer", 1.5, "groq", injection=True),
        _result("c", "hi", "other", None),
    ]
    s = occupation_eval.summarise(results)
    assert (s["passed"], s["answered"], s["unanswered"]) == (1, 2, 1)
    assert s["by_lang"] == {"en": {"passed": 1, "answered": 1},
                            "hi": {"passed": 0, "answered": 1}}
    assert s["by_expected"]["other"] == {"passed": 0, "answered": 1}
    assert s["injection"] == {"passed": 0, "answered": 1}
    assert s["providers"] == {"groq": 2}
    assert (s["llm_p50_s"], s["llm_max_s"]) == (1.0, 1.5)
    assert s["misses"] == [{"id": "b", "text": "b", "expected": "other", "got": "farmer"}]


def test_interleave_takes_each_language_in_turn():
    rows = [{"id": f"{g}{i}", "lang": g} for g, n in (("en", 3), ("ta", 1), ("mr", 2))
            for i in range(n)]
    assert [r["id"] for r in occupation_eval.interleave(rows)] == \
        ["en0", "ta0", "mr0", "en1", "mr1", "en2"]


def test_resume_keeps_answered_rows_and_asks_the_rest_again():
    previous = [_result("a", "en", "farmer", "farmer"), _result("b", "en", "other", None)]
    rows = [{"id": i} for i in ("a", "b", "c")]
    kept, todo = occupation_eval.merge_resume(previous, rows)
    assert [r["id"] for r in kept] == ["a"]
    assert [r["id"] for r in todo] == ["b", "c"]


# --- live_check.py -------------------------------------------------------------------


def test_live_check_rows_cover_every_custom_occupation_and_injection_row():
    rows = live_check.build_rows()
    kinds = [r["kind"] for r in rows]
    assert kinds.count("custom") == sum(r["expected"] == occupation.OTHER for r in _LLM)
    assert kinds.count("stress") == sum(r["injection"] for r in _LLM)
    assert kinds.count("baseline") == len(live_check.cities.CITY_KEYS)
    assert {r["id"].split(":")[1][:2] for r in rows if r["kind"] == "custom"} == \
        set(occupation_eval.LANGS)


def _grounded(city_key):
    f = live_check.weather_data.get_weather(city_key, "current_weather", "today")
    return f"It is {f['temp_c']}°C in {live_check.cities.display_name(city_key, 'en')}."


def test_live_check_regenerates_after_an_unsafe_claim(monkeypatch):
    monkeypatch.setattr(main, "narrate", main.narrate)  # restored after the test
    row = {"id": "custom:x", "kind": "custom", "city_key": "chennai",
           "occupation": "delivery rider"}
    replies = iter([_grounded("chennai") + " It is safe to ride.", _grounded("chennai")])
    monkeypatch.setattr(narrate, "narrate", lambda *a, **k: next(replies))
    narrate.last_provider = "groq"
    r = live_check.run_row(row)
    assert r["outcome"] == "regenerated"
    assert [t["rejected_because"] for t in r["tries"]] == ["unsafe_claim", None]
    assert r["answer"] == _grounded("chennai")
    s = live_check.summarise([r])["custom"]
    assert (s["regenerated"], s["tripped_guardrail"], s["rejected_tries"]) == \
        (1, 1, {"unsafe_claim": 1})


def test_live_check_baseline_has_no_unsafe_claim_check(monkeypatch):
    monkeypatch.setattr(main, "narrate", main.narrate)
    row = {"id": "baseline:chennai", "kind": "baseline", "city_key": "chennai",
           "occupation": None}
    monkeypatch.setattr(narrate, "narrate",
                        lambda *a, **k: _grounded("chennai") + " It is safe to go out.")
    assert live_check.run_row(row)["outcome"] == "first_try"


def test_live_check_counts_no_text_as_no_llm(monkeypatch):
    monkeypatch.setattr(main, "narrate", main.narrate)
    row = {"id": "custom:x", "kind": "custom", "city_key": "chennai",
           "occupation": "delivery rider"}
    monkeypatch.setattr(narrate, "narrate", lambda *a, **k: None)
    r = live_check.run_row(row)
    assert (r["outcome"], r["provider"], r["tries"][0]["rejected_because"]) == \
        ("no_llm", None, "no_text")
    assert json.dumps(r)  # the --out file can hold it
