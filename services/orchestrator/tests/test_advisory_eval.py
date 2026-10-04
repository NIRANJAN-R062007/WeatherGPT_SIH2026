"""ml/advisory (plan.md §8 TFA-1, TFA-17): the travel/farming eval set and its harness.

No model is called. These tests keep the set honest: every row is well formed,
each row's expected verdict follows from the facts of its scenario under the
draft rubric, the `oracle` candidate scores 100% (so the set, scenarios and
harness agree), and the scorer really does fail an ungrounded, wrong or
malformed reply.
"""

import collections
import json
import sys

import config
import pytest

sys.path.insert(0, str(config.REPO_ROOT / "ml" / "advisory"))

import run_eval  # noqa: E402
import scenarios  # noqa: E402
from advisory import agent, prompt, rubric, schema, template  # noqa: E402

ROWS = run_eval.load_rows()
ANSWERS = [r for r in ROWS if r["type"] == "answer"]
BY_ID = {r["id"]: r for r in ROWS}


# --- the set ---------------------------------------------------------------------


def test_the_set_has_the_size_and_spread_the_plan_asks_for():
    assert 30 <= len(ROWS) <= 80
    assert len({r["id"] for r in ROWS}) == len(ROWS)
    assert {r["kind"] for r in ROWS} == {"travel", "farming"}
    assert {r["type"] for r in ROWS} == {"answer", "ask_back"}
    langs = {r["lang"] for r in ROWS}
    assert {"en", "hi", "ta", "te", "mr", "hi-latn"} <= langs
    verdicts = collections.Counter(v for r in ANSWERS for v in r["expected"]["verdict"])
    assert {"go", "caution", "avoid", "not_available", "suitable", "not_suitable"} <= set(verdicts)


_VERDICT_CLASSES = {
    "travel": ("go", "caution", "avoid", "not_available"),
    "farming": ("suitable", "not_suitable", "not_available"),
}


@pytest.mark.parametrize("lang", ["hi", "ta", "te", "mr"])
def test_each_indic_language_has_enough_rows_to_score_on(lang):
    """One row is 12% of a language's score at 8 rows, 25% at 4: keep it readable."""
    answers = [r for r in ANSWERS if r["lang"] == lang]
    assert len(answers) >= 8
    for kind, verdicts in _VERDICT_CLASSES.items():
        seen = {v for r in answers if r["kind"] == kind for v in r["expected"]["verdict"]}
        assert set(verdicts) <= seen, (lang, kind, set(verdicts) - seen)
    assert any(r["expected"]["window"] for r in answers)
    assert sum(r["type"] == "ask_back" for r in ROWS if r["lang"] == lang) >= 1


def test_every_travel_mode_is_scored():
    """TFA-7: each mode's table is exercised by at least one answer row."""
    modes = {r["slots"].get("mode") for r in ANSWERS if r["kind"] == "travel"}
    assert set(rubric.TRAVEL_MODES) <= modes


def test_non_english_rows_are_flagged_as_not_native_reviewed():
    """Same convention as ml/nlu/eval_set.jsonl: author-written, no native QA yet."""
    assert {r["native_qa"] for r in ROWS if r["lang"] != "en"} == {False}


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_every_row_is_well_formed(row):
    assert run_eval.validate_row(row) == []


def test_validate_row_rejects_a_bad_row():
    good = dict(BY_ID["trv-en-01"])
    assert run_eval.validate_row({**good, "scenario": "sow_ok"})            # farming scenario
    assert run_eval.validate_row({**good, "expected": {"verdict": ["suitable"], "window": False}})
    assert run_eval.validate_row({**good, "slots": {"origin": "chennai"}})  # slots missing
    assert run_eval.validate_row({**BY_ID["trv-ask-01"], "missing": []})
    assert run_eval.validate_row({"id": "x"})


# --- scenarios and the rubric ------------------------------------------------------


def test_scenario_values_sit_on_the_right_side_of_the_rubric_thresholds():
    assert scenarios.CALM_RAIN_PCT < rubric.RAIN_CAUTION_PCT <= scenarios.RAINY_PCT
    assert scenarios.CALM_WIND_KMH < rubric.WIND_CAUTION_KMH <= scenarios.WINDY_KMH
    assert scenarios.CROP_FIXTURE["max_rain_probability_pct"] < scenarios.STORM_PCT
    assert scenarios.HOT_HIGH_C > scenarios.CROP_FIXTURE["temp_range_c"]["max"]
    assert 25 >= scenarios.CROP_FIXTURE["temp_range_c"]["min"]  # the calm low must pass
    lo, hi = scenarios.CROP_FIXTURE["temp_range_c"].values()
    assert lo <= scenarios.CALM_HOUR_C <= hi  # so a calm day has sowing hours


@pytest.mark.parametrize("row", ANSWERS, ids=[r["id"] for r in ANSWERS])
def test_the_expected_verdict_follows_from_the_scenario_facts(row):
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    assert rubric.reference_verdict(facts) in row["expected"]["verdict"]
    # The rule-based answer carries a window exactly when the row expects one (farming:
    # only a "suitable" verdict with a sowing window, TFA-11).
    assert bool(template.template_answer(facts)["window"]) == row["expected"]["window"]


def test_only_the_thunderstorm_scenario_has_a_thunderstorm_in_the_facts():
    slots = {"origin": "chennai", "destination": "madurai", "day": "today"}
    for name in scenarios.TRAVEL_SCENARIOS:
        facts = scenarios.build("travel", slots, name)
        blob = json.dumps(facts.raw()).lower()
        assert ("thunder" in blob) == (name == "thunderstorm_metar"), name


def test_scenarios_never_mutate_the_collected_facts():
    from advisory.facts import TravelFactsCollector
    slots = {"origin": "chennai", "destination": "madurai", "day": "today"}
    base = TravelFactsCollector().collect(slots)
    before = json.dumps(base.raw(), sort_keys=True)
    for name in scenarios.TRAVEL_SCENARIOS:
        scenarios.apply(name, base)
    assert json.dumps(base.raw(), sort_keys=True) == before


def test_unavailable_scenarios_really_remove_the_sections():
    slots = {"origin": "chennai", "destination": "madurai", "day": "today"}
    assert scenarios.build("travel", slots, "warnings_off").raw()["origin"].get("warnings") is None
    assert scenarios.build("travel", slots, "no_data").raw() == {}
    farm = {"district": "madurai", "crop": "groundnut"}
    assert "crop" not in scenarios.build("farming", farm, "crop_missing").raw()
    assert "forecast" not in scenarios.build("farming", farm, "sow_no_forecast").raw()["location"]
    with pytest.raises(ValueError):
        scenarios.apply("sunny", scenarios.build("farming", farm, "sow_ok"))


def test_the_invented_crop_entry_is_labelled_as_a_fixture():
    facts = scenarios.build("farming", {"district": "madurai", "crop": "groundnut"}, "sow_ok")
    crop = facts.raw()["crop"]["entry"]
    assert "EVAL FIXTURE" in crop["source"] and "not agronomy" in crop["source"]


# --- the oracle and the scorer -----------------------------------------------------


def test_the_oracle_passes_every_row():
    results = [run_eval.run_row(r, run_eval.Oracle()) for r in ROWS]
    failed = [(r["id"], r["model"]["problems"]) for r in results
              if "model" in r and not r["model"]["passed"]]
    assert failed == []
    assert run_eval.summarise(results)["passed"] == len(ANSWERS)


def _score(row_id: str, reply) -> dict:
    row = BY_ID[row_id]
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    text = reply if isinstance(reply, str) else json.dumps(reply)
    return run_eval.score_reply(row, facts, text)


def _oracle(row_id: str) -> dict:
    row = BY_ID[row_id]
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    return template.template_answer(facts)


def test_an_ungrounded_number_fails_the_guardrail_but_not_json_or_rubric():
    reply = _oracle("trv-en-01")
    reply["pros"].append("It is 99°C at the destination.")
    score = _score("trv-en-01", reply)
    assert score["valid_json"] and score["rubric"] and not score["guardrail"]
    assert not score["passed"]


def test_the_wrong_verdict_fails_the_rubric_only():
    reply = _oracle("trv-en-02")
    reply["verdict"] = "go"  # a thunderstorm at the airport
    score = _score("trv-en-02", reply)
    assert score["valid_json"] and score["guardrail"] and not score["rubric"]
    assert "expected one of ['avoid']" in score["problems"][0]


def test_go_with_the_warnings_feed_off_is_wrong():
    reply = _oracle("trv-en-06")
    reply["verdict"] = "go"
    assert not _score("trv-en-06", reply)["rubric"]


def test_a_required_window_must_be_present_and_exact():
    reply = _oracle("trv-en-08")
    assert _score("trv-en-08", reply)["passed"]
    assert not _score("trv-en-08", {**reply, "window": None})["rubric"]
    off = {**reply, "window": {"start_local": "08:00", "end_local": "12:00"}}
    assert not _score("trv-en-08", off)["guardrail"]


@pytest.mark.parametrize("reply", [
    "Sure! The verdict is go.", "[]", "", '{"verdict": "go"}',
    '{"verdict": "go", "pros": [], "cons": [], "extra": 1}',
])
def test_malformed_replies_fail_json(reply):
    score = _score("trv-en-01", reply)
    assert not score["valid_json"] and not score["passed"]


def test_a_fenced_reply_is_accepted():
    reply = "```json\n" + json.dumps(_oracle("trv-en-01")) + "\n```"
    assert _score("trv-en-01", reply)["passed"]


def test_a_failing_call_is_scored_as_a_failure_not_a_crash():
    class Down(run_eval.Candidate):
        name = "down"

        def __call__(self, row, facts):
            raise agent.AgentError("refused")

    result = run_eval.run_row(BY_ID["trv-en-01"], Down())
    assert result["model"]["passed"] is False
    assert result["model"]["problems"][0].startswith("call failed: AgentError")


# --- the slot stage ---------------------------------------------------------------


def test_the_slot_stage_has_no_unexpected_failures():
    stages = {r["id"]: run_eval.slot_stage(r) for r in ROWS}
    assert [i for i, s in stages.items() if s["status"] == "fail"] == []
    # A known gap that starts to pass must have its marker removed.
    assert [i for i, s in stages.items() if s["status"] == "gap_closed"] == []


def test_known_gaps_are_the_rows_that_say_so():
    gaps = {r["id"] for r in ROWS if r.get("known_gap")}
    assert gaps == {"trv-en-08", "trv-hi-02", "trv-hl-01", "trv-hl-02", "trv-hl-03",
                    "trv-ask-04", "frm-ask-02", "frm-mr-03"}
    for row_id in gaps:
        assert run_eval.slot_stage(BY_ID[row_id])["status"] == "known_gap"


# --- the prompt -------------------------------------------------------------------


def _prompt(row_id: str, **kw) -> str:
    row = BY_ID[row_id]
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    return prompt.build(row["kind"], row["slots"], row["lang"], facts, **kw)


def test_the_prompt_carries_facts_rubric_and_slots_but_never_the_users_words():
    row = BY_ID["trv-en-10"]  # the injection row
    text = _prompt("trv-en-10")
    assert rubric.travel_rubric(row["slots"].get("mode"), row["slots"].get("day")) in text
    assert row["text"] not in text and json.dumps(row["text"]) not in text
    assert json.dumps(row["slots"], sort_keys=True) in text
    assert '"temp_c"' in text
    assert "briefing" in text and '"decoded"' not in text  # slimmed, not hidden from the guardrail


def test_the_prompt_lists_what_is_not_available():
    assert '"origin.warnings": "warnings feed unavailable"' in _prompt("trv-en-06")
    clear = _prompt("trv-en-01")
    assert "NOT AVAILABLE\nnothing" in clear and "warnings feed unavailable" not in clear


def test_the_prompt_forbids_quoting_thresholds_and_paths_into_missing_sections():
    """TFA-18/19: the live models quoted rubric thresholds ("20", "25") as facts and
    cited a section listed as not available; both failed the guardrail."""
    text = _prompt("trv-en-06")
    assert "Never quote a number from VERDICT RULES" in text
    assert f"at most {schema.MAX_ITEMS} paths" in text
    assert "cited by its name (the key, without the reason)" in text


def test_the_prompt_asks_for_the_row_language():
    assert "Write the sentences in Tamil" in _prompt("trv-ta-01")
    assert "Hindi" in _prompt("trv-hl-01")


def test_the_tools_section_is_only_there_for_the_agent():
    assert "\nTOOLS\n" in _prompt("trv-en-01", tools=True)
    assert "\nTOOLS\n" not in _prompt("trv-en-01")


@pytest.mark.parametrize("kind", ["travel", "farming"])
def test_the_json_schema_matches_the_python_schema(kind):
    spec = prompt.json_schema(kind)
    assert spec["properties"]["verdict"]["enum"] == list(schema.VERDICTS[kind])
    assert set(spec["properties"]) == set(schema.KEYS)
    assert spec["required"] == list(schema.REQUIRED)


# --- candidates -------------------------------------------------------------------


def test_make_candidate_knows_oracle_and_the_strands_providers(monkeypatch):
    assert run_eval.make_candidate("oracle", timeout=1).name == "oracle"
    monkeypatch.setattr(agent, "make_model", lambda provider, model_id=None: object())
    assert run_eval.make_candidate("strands:gemini", timeout=1).name == "strands:gemini"
    ollama = run_eval.make_candidate("strands:ollama:llama3.2:3b", timeout=1)
    assert ollama.name == "strands:ollama:llama3.2:3b"


def test_make_candidate_rejects_unknown_specs():
    for spec in ("gpt", "ollama:qwen3:8b", "openai:m", "oracle:x", "strands:", "strands:bedrock"):
        with pytest.raises(SystemExit):
            run_eval.make_candidate(spec, timeout=1)


def test_the_strands_candidate_applies_the_hard_override(monkeypatch):
    """A model that says "go" under a red warning is scored as the override leaves it."""
    row = BY_ID["trv-en-04"]  # the red-warning row
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    monkeypatch.setattr(agent, "make_model", lambda provider, model_id=None: object())
    monkeypatch.setattr(agent, "run_agent", lambda model, box, system, timeout: json.dumps(
        {"verdict": "go", "pros": [], "cons": [], "window": None}))
    cand = run_eval.make_candidate("strands:gemini", timeout=1)
    assert json.loads(cand(row, facts))["verdict"] == "avoid"
    assert cand.last_tool_calls == 0


# --- the summary (TFA-18) ---------------------------------------------------------


def _scored(row_id: str, *, tool_calls, latency=1.0, error=None) -> dict:
    return {"id": row_id, "lang": "en", "kind": "travel", "type": "answer",
            "slots": {"status": "pass"}, "latency_s": latency, "tool_calls": tool_calls,
            "error": error,
            "model": {"valid_json": True, "rubric": True, "guardrail": True, "passed": True}}


def test_the_summary_reports_tool_calls_per_row():
    results = [_scored("a", tool_calls=0), _scored("b", tool_calls=2),
               _scored("c", tool_calls=2), _scored("d", tool_calls=4)]
    summary = run_eval.summarise(results)
    assert summary["tool_calls_mean"] == 2
    assert summary["tool_calls_max"] == 4
    assert summary["tool_calls_per_row"] == {"0": 1, "2": 2, "4": 1}


def test_the_oracle_has_no_tool_call_figures():
    """No agent, no tool calls: the summary leaves them out instead of claiming zero."""
    results = [run_eval.run_row(BY_ID["trv-en-01"], run_eval.Oracle())]
    assert "tool_calls_mean" not in run_eval.summarise(results)


@pytest.mark.parametrize("error, kind", [
    (None, None),
    ("AgentError: ModelThrottledException: 429 RESOURCE_EXHAUSTED", "rate_limited"),
    ("AgentError: no reply within 8s", "timeout"),
    ("AgentError: ServerError: 503 UNAVAILABLE", "provider_unavailable"),
    ("AgentError: ValueError: bad thing", "other"),
])
def test_call_errors_are_sorted_by_why(error, kind):
    assert run_eval.error_kind(error) == kind


def test_the_summary_counts_call_errors_by_kind():
    results = [_scored("a", tool_calls=0),
               _scored("b", tool_calls=0, error="AgentError: no reply within 8s"),
               _scored("c", tool_calls=0, error="AgentError: 429 Too Many Requests"),
               _scored("d", tool_calls=0, error="AgentError: 429 Too Many Requests")]
    assert run_eval.summarise(results)["call_errors"] == {"rate_limited": 2, "timeout": 1}


def test_rate_limited_rows_are_left_out_of_the_latency_and_counted_apart():
    results = [_scored("a", tool_calls=0, latency=2.0),
               _scored("b", tool_calls=0, latency=4.0),
               _scored("c", tool_calls=0, latency=0.3, error="AgentError: 429 Too Many Requests")]
    results[2]["model"] = {**results[2]["model"], "passed": False}
    summary = run_eval.summarise(results)
    assert summary["latency_p50_s"] == 3.0
    assert (summary["answered"], summary["answered_passed"]) == (2, 2)


def test_pause_spaces_out_only_the_rows_that_call_a_model():
    rows = [BY_ID["trv-en-01"], ROWS[[r["type"] for r in ROWS].index("ask_back")],
            BY_ID["trv-en-02"], BY_ID["frm-en-01"]]
    slept = []
    results = run_eval.run_rows(rows, run_eval.Oracle(), pause=3, sleep=slept.append)
    assert len(results) == 4
    assert slept == [3, 3]  # before the 2nd and 3rd answer rows; never before the first


def test_no_pause_never_sleeps():
    slept = []
    run_eval.run_rows(ANSWERS[:3], run_eval.Oracle(), sleep=slept.append)
    assert slept == []


# --- resuming a run across days (TFA-18) ---------------------------------------------


class _Counting(run_eval.Oracle):
    """The oracle, remembering which rows it was asked."""

    def __init__(self):
        self.asked = []

    def __call__(self, row, facts):
        self.asked.append(row["id"])
        return super().__call__(row, facts)


def _earlier_run(*errors) -> dict:
    """An earlier run of the first answer rows, by id; row i failed with errors[i]."""
    out = {}
    for row, error in zip(ANSWERS, errors):
        result = run_eval.run_row(row, run_eval.Oracle())
        result["error"] = error
        out[row["id"]] = result
    return out


def test_resume_asks_only_the_rate_limited_and_missing_rows():
    previous = _earlier_run(None, "AgentError: 429 RESOURCE_EXHAUSTED", None)
    cand = _Counting()
    results = run_eval.run_rows(ANSWERS[:4], cand, previous=previous)
    assert cand.asked == [ANSWERS[1]["id"], ANSWERS[3]["id"]]
    assert [r["id"] for r in results] == [r["id"] for r in ANSWERS[:4]]
    assert results[0]["ran_on"] == previous[ANSWERS[0]["id"]]["ran_on"]


def test_resume_keeps_a_timeout_and_a_503_as_measurements():
    previous = _earlier_run("AgentError: no reply within 8s",
                            "AgentError: ServerError: 503 UNAVAILABLE")
    cand = _Counting()
    results = run_eval.run_rows(ANSWERS[:2], cand, previous=previous)
    assert cand.asked == []
    assert run_eval.summarise(results)["call_errors"] == {
        "provider_unavailable": 1, "timeout": 1}


def test_resume_asks_again_for_a_row_edited_since():
    previous = _earlier_run(None)
    edited = {**ANSWERS[0], "text": ANSWERS[0]["text"] + " please"}
    cand = _Counting()
    run_eval.run_rows([edited], cand, previous=previous)
    assert cand.asked == [edited["id"]]


def test_resume_refuses_a_file_from_another_model_or_budget(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"model": "strands:groq", "timeout_s": 8.0, "rows": []}),
                    encoding="utf-8")
    with pytest.raises(SystemExit):
        run_eval.load_previous(path, "strands:gemini", 8.0)
    with pytest.raises(SystemExit):
        run_eval.load_previous(path, "strands:groq", 5.0)
    assert run_eval.load_previous(path, "strands:groq", 8.0) == {}


def test_resume_from_a_file_not_written_yet_asks_every_row(tmp_path):
    assert run_eval.load_previous(tmp_path / "gemini.json", "strands:gemini", 8.0) == {}


def test_progress_reports_each_answer_row_and_whether_it_was_kept():
    previous = _earlier_run(None)
    rows = [ANSWERS[0], ROWS[[r["type"] for r in ROWS].index("ask_back")], ANSWERS[1]]
    seen = []
    run_eval.run_rows(rows, run_eval.Oracle(), previous=previous,
                      progress=lambda result, kept: seen.append((result["id"], kept)))
    assert seen == [(ANSWERS[0]["id"], True), (ANSWERS[1]["id"], False)]


def test_the_summary_says_which_day_each_row_ran():
    results = [{**_scored("a", tool_calls=0), "ran_on": "2026-10-05"},
               {**_scored("b", tool_calls=0), "ran_on": "2026-10-06"},
               {**_scored("c", tool_calls=0), "ran_on": "2026-10-06"}]
    assert run_eval.summarise(results)["ran_on"] == {"2026-10-05": 1, "2026-10-06": 2}
