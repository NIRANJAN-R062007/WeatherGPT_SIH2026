"""Runs ml/nlu/eval_set.jsonl through nlu.parse(). "rules" rows must resolve
correctly with the LLM off; "llm" rows need real keys and network, so they're
marked live.
"""

import json

import cities
import config
import nlu
import pytest

_ROWS = [
    json.loads(line)
    for line in (config.REPO_ROOT / "ml" / "nlu" / "eval_set.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]
_RULES_ROWS = [r for r in _ROWS if r["path"] == "rules"]
_LLM_ROWS = [r for r in _ROWS if r["path"] == "llm"]

# Intents the rules pass must decide outright (source "rules", never
# "rules_fallback"): the P0 weather intents, plus warnings / out_of_scope,
# which short-circuit on the text alone.
_RULES_INTENTS = {
    "current_weather", "forecast", "will_it_rain", "rainfall_so_far_today", "warnings",
    "out_of_scope",
}


def _assert_row(row: dict, pq) -> None:
    expected = row["expected"]
    assert cities.resolve(pq.city) == expected.get("city")
    assert pq.intent == expected.get("intent")
    assert pq.time_window == expected.get("time_window")
    if "days" in expected:
        assert pq.days == expected["days"]
    assert pq.parameter == expected.get("parameter")
    expected_lang = None if row["lang"] == "other" else row["lang"]
    assert pq.language == expected_lang


@pytest.mark.parametrize("row", _RULES_ROWS, ids=[r["id"] for r in _RULES_ROWS])
def test_rules_path_rows(monkeypatch, row):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    pq = nlu.parse(row["text"])
    _assert_row(row, pq)
    if row["expected"]["intent"] in _RULES_INTENTS:
        assert pq.source == "rules"


@pytest.mark.live
@pytest.mark.skipif(
    not (config.GEMINI_API_KEY or config.GROQ_API_KEY), reason="no LLM key configured"
)
@pytest.mark.parametrize("row", _LLM_ROWS, ids=[r["id"] for r in _LLM_ROWS])
def test_llm_path_rows(row):
    pq = nlu.parse(row["text"])
    _assert_row(row, pq)
    assert pq.source == "llm"
