"""Score the travel/farming advisory on the eval set (plan.md §8 TFA-1, TFA-17, §11.5).

    python ml/advisory/run_eval.py --model oracle
    python ml/advisory/run_eval.py --model strands:gemini --out gemini.json
    python ml/advisory/run_eval.py --model strands:groq --pause 4
    python ml/advisory/run_eval.py --model strands:ollama:llama3.2:3b

    # a free tier's daily quota ends the run partway: the next day, ask only the
    # rate-limited rows again and keep the rest (the same command every day)
    python ml/advisory/run_eval.py --model strands:gemini --pause 15 \
        --resume ml/advisory/gemini.json --out ml/advisory/gemini.json

For each `answer` row it builds the facts (real fixture collectors plus one named
weather scenario, scenarios.py), asks the candidate, and scores three things per
plan §11.5:

  valid JSON   the reply is one JSON object in the advisory/schema.py shape
  rubric       the verdict is one the row allows (and carries the window when asked)
  guardrail    guardrail.check_advisory() passes: every number, clock time, window
               and cited path in the reply traces to the facts

A row passes only if all three do. Each row also reports latency and, for an agent,
how many tool calls it made. `strands:<provider>[:<model>]` runs the production agent
(`advisory/agent.py`: same prompt, tools, hard override and Strands model classes) on
the row's pinned facts, so what is scored is what ships; its tools return only what the
pinned facts already hold. `ask_back` rows
have no model call: they check the TFA-3 slot parser, as does the first stage of
every `answer` row. The model scores are results, not a pass/fail gate, unless
`--min-pass` is given; the exit code is 1 for a broken eval set or an unexpected
slot-stage failure.

`oracle` answers from the rule-based template (`advisory/template.py`), so it must
score 100%: it proves the set, the scenarios and the harness agree with each other,
and is the baseline an agent is read against. An agent candidate needs its provider's
key in the environment (GEMINI_API_KEY, GROQ_API_KEY) or a running Ollama.

Row fields: id, lang, kind (travel|farming), type (answer|ask_back), text, slots
(the slots a correct parse yields), then for answers `scenario` and `expected`
{verdict: [allowed...], window: bool}, for ask-backs `missing` (and optionally
`unsupported`). `known_gap` marks a row whose slot stage fails today because of a
TFA-3 gap: it reports as a gap, and flags itself once the gap is fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_SET = HERE / "eval_set.jsonl"
os.environ.setdefault("WEATHER_MODE", "fixtures")  # before config is imported
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "services" / "orchestrator"))

import config  # noqa: E402
import guardrail  # noqa: E402
import scenarios  # noqa: E402
from advisory import agent, prompt, schema, slots, template  # noqa: E402

KINDS = ("travel", "farming")
TYPES = ("answer", "ask_back")


# --- the set --------------------------------------------------------------------


def load_rows(path: Path = EVAL_SET) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def validate_row(row: dict) -> list[str]:
    """Why this row is malformed; empty when it is fine."""
    problems = []
    for key in ("id", "lang", "kind", "type", "text", "slots"):
        if key not in row:
            problems.append(f"missing {key!r}")
    if problems:
        return problems
    if row["kind"] not in KINDS:
        problems.append(f"kind {row['kind']!r}")
    if row["type"] not in TYPES:
        problems.append(f"type {row['type']!r}")
    if row["type"] == "answer":
        allowed = schema.VERDICTS.get(row["kind"], ())
        if row.get("scenario") not in (scenarios.TRAVEL_SCENARIOS if row["kind"] == "travel"
                                       else scenarios.FARMING_SCENARIOS):
            problems.append(f"scenario {row.get('scenario')!r} does not fit kind {row['kind']}")
        verdicts = (row.get("expected") or {}).get("verdict")
        if not verdicts or any(v not in allowed for v in verdicts):
            problems.append(f"expected.verdict {verdicts!r} not in {allowed}")
        if not isinstance((row.get("expected") or {}).get("window"), bool):
            problems.append("expected.window must be a bool")
        if set(row["slots"]) < set(slots.REQUIRED.get(row["kind"], ())):
            problems.append("an answer row needs every required slot")
    elif "missing" not in row or not row["missing"]:
        problems.append("an ask_back row needs a non-empty `missing`")
    return problems


# --- stage 1: slots (TFA-3) ------------------------------------------------------


def slot_stage(row: dict) -> dict:
    result = slots.parse(row["kind"], row["text"])
    problems = []
    if result.slots != row["slots"]:
        problems.append(f"slots: expected {row['slots']}, got {result.slots}")
    expected_missing = row.get("missing", [])
    if result.missing != expected_missing:
        problems.append(f"missing: expected {expected_missing}, got {result.missing}")
    want = {k: v.lower() for k, v in row.get("unsupported", {}).items()}
    got = {k: v.lower() for k, v in result.unsupported.items()}
    if got != want:
        problems.append(f"unsupported: expected {want}, got {got}")
    if not result.complete and not slots.ask_back(result, row["lang"].split("-")[0]):
        problems.append("no follow-up question produced")

    gap = row.get("known_gap")
    status = "pass" if not problems else "fail"
    if gap:
        status = "known_gap" if problems else "gap_closed"
    return {"status": status, "problems": problems, "known_gap": gap}


# --- candidates ------------------------------------------------------------------


class Candidate:
    name = "?"
    last_tool_calls: int | None = None

    def __call__(self, row: dict, facts) -> str:
        raise NotImplementedError


class Oracle(Candidate):
    name = "oracle"

    def __call__(self, row, facts):
        return json.dumps(template.template_answer(facts), ensure_ascii=False)


class StrandsAgent(Candidate):
    """The production agent on the row's pinned facts (advisory/agent.py)."""

    def __init__(self, provider: str, model_id: str | None, timeout: float):
        self.name = f"strands:{provider}" + (f":{model_id}" if model_id else "")
        self.model = agent.make_model(provider, model_id)
        self.timeout = timeout

    def __call__(self, row, facts):
        box = agent.Toolbox(facts, agent.no_fetch, config.ADVISORY_AGENT_MAX_TOOL_CALLS)
        system = prompt.build(row["kind"], row["slots"], row["lang"], facts, tools=True)
        try:
            reply = agent.run_agent(self.model, box, system, self.timeout)
        finally:
            self.last_tool_calls = box.calls
        parsed = schema.parse(reply)
        # The cite trim, hard override and caveats run after the agent in production,
        # so they are scored too.
        if parsed is None:
            return reply
        return json.dumps(template.finish(facts, schema.trim_cites(parsed)),
                          ensure_ascii=False)


def make_candidate(spec: str, *, timeout: float) -> Candidate:
    kind, _, rest = spec.partition(":")
    if kind == "oracle" and not rest:
        return Oracle()
    provider, _, model_id = rest.partition(":")
    if kind == "strands" and provider in ("gemini", "groq", "ollama"):
        return StrandsAgent(provider, model_id or None, timeout)
    raise SystemExit(
        f"unknown --model {spec!r}: use oracle or strands:<gemini|groq|ollama>[:<model>]")


# --- stage 2: the model ------------------------------------------------------------


def score_reply(row: dict, facts, reply: str) -> dict:
    parsed = schema.parse(reply)
    shape = schema.validate(parsed, row["kind"]) if parsed is not None else ["not a JSON object"]
    valid_json = parsed is not None and not shape

    verdict = parsed.get("verdict") if parsed else None
    rubric_ok = verdict in row["expected"]["verdict"]
    if rubric_ok and row["expected"]["window"]:
        rubric_ok = bool(parsed.get("window"))

    report = guardrail.check_advisory(reply, facts)
    problems = list(shape) if not valid_json else []
    if not rubric_ok:
        problems.append(f"verdict {verdict!r}, expected one of {row['expected']['verdict']}"
                        + (" with a window" if row["expected"]["window"] else ""))
    problems += report.problems
    return {"valid_json": valid_json, "rubric": rubric_ok, "guardrail": report.ok,
            "passed": valid_json and rubric_ok and report.ok, "verdict": verdict,
            "problems": problems}


def row_key(row: dict) -> str:
    """The row a stored result was scored on, so --resume never keeps an answer to a
    row that has since been edited."""
    text = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run_row(row: dict, candidate: Candidate) -> dict:
    out = {"id": row["id"], "lang": row["lang"], "kind": row["kind"], "type": row["type"],
           "row_key": row_key(row), "slots": slot_stage(row)}
    if row["type"] != "answer":
        return out
    out["ran_on"] = time.strftime("%Y-%m-%d")
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    started = time.perf_counter()
    candidate.last_tool_calls = None
    try:
        reply = candidate(row, facts)
        error = None
    except (agent.AgentError, OSError, ValueError) as exc:
        reply, error = "", f"{type(exc).__name__}: {exc}"
    out["latency_s"] = round(time.perf_counter() - started, 3)
    out["tool_calls"] = candidate.last_tool_calls
    out["reply"] = reply
    out["error"] = error
    out["model"] = score_reply(row, facts, reply)
    if error:
        out["model"]["problems"].insert(0, f"call failed: {error}")
    return out


def reusable(previous: dict | None, row: dict) -> bool:
    """Whether --resume keeps a stored answer instead of asking again. A rate limit
    is the free tier's daily quota, not the agent, so that row is asked again; a
    timeout or a 503 is a measurement (TFA-18 counts them) and is kept."""
    return (previous is not None and "model" in previous
            and previous.get("row_key") == row_key(row)
            and error_kind(previous.get("error")) != "rate_limited")


def run_rows(rows: list[dict], candidate: Candidate, *, pause: float = 0.0,
             sleep=time.sleep, previous: dict[str, dict] | None = None,
             progress=None) -> list[dict]:
    """Every row in order. `pause` spaces the model calls out: on a free tier a
    burst of 54 agent runs is mostly measuring the rate limiter (plan.md TFA-18).
    Ask-back rows make no call, so they never wait. `previous` holds an earlier
    run's results by id; its reusable answers are kept without a call (the slot
    stage, which costs nothing, is run again). `progress(result, kept)` is called
    after each answer row."""
    previous = previous or {}
    results = []
    called = False
    for row in rows:
        old = previous.get(row["id"])
        if row["type"] == "answer" and reusable(old, row):
            results.append({**old, "slots": slot_stage(row)})
            if progress:
                progress(results[-1], True)
            continue
        if pause and called and row["type"] == "answer":
            sleep(pause)
        results.append(run_row(row, candidate))
        called = called or row["type"] == "answer"
        if progress and row["type"] == "answer":
            progress(results[-1], False)
    return results


def print_progress(result: dict, kept: bool) -> None:
    """One line per answer row on stderr, so a long live run can be watched (and a
    run the quota refuses from the first row can be stopped)."""
    if kept:
        status = "kept"
    elif result["error"]:
        status = error_kind(result["error"])
    else:
        status = "pass" if result["model"]["passed"] else "fail"
    print(f"  {result['id']:<11}{status:<21}{result['latency_s']:.2f}s",
          file=sys.stderr, flush=True)


def load_previous(path: Path, model: str, timeout: float) -> dict[str, dict]:
    """An earlier --out file's rows by id. It must be the same model and budget,
    or the merged numbers would describe two different setups."""
    if not path.exists():
        print(f"--resume: {path} not found yet, so every row is asked\n")
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("model") != model or data.get("timeout_s") != timeout:
        raise SystemExit(f"--resume {path}: it was run as model={data.get('model')} "
                         f"timeout={data.get('timeout_s')}s, not {model} {timeout}s")
    return {r["id"]: r for r in data.get("rows", [])}


# --- report ------------------------------------------------------------------------


def _pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "-"


def error_kind(error: str | None) -> str | None:
    """A failed call, sorted by why: a free-tier rate limit is not the agent being
    wrong, and a timeout is the budget talking, so TFA-18 reads them apart."""
    if not error:
        return None
    text = error.lower()
    if any(s in text for s in ("throttl", "429", "resource_exhausted", "rate limit")):
        return "rate_limited"
    if "no reply within" in text or "timeout" in text or "timed out" in text:
        return "timeout"
    if any(s in text for s in ("503", "unavailable", "overloaded")):
        return "provider_unavailable"
    return "other"


def summarise(results: list[dict]) -> dict:
    scored = [r for r in results if "model" in r]
    summary: dict = {"answer_rows": len(scored)}
    kinds = [error_kind(r.get("error")) for r in scored]
    summary["call_errors"] = {k: kinds.count(k) for k in sorted({k for k in kinds if k})}
    for key in ("valid_json", "rubric", "guardrail", "passed"):
        summary[key] = sum(r["model"][key] for r in scored)
    # A rate-limited row is the free tier's quota, not the agent: it comes back in a
    # fraction of a second, so it is left out of the latency and counted apart.
    answered = [r for r, k in zip(scored, kinds) if k != "rate_limited"]
    summary["answered"] = len(answered)
    summary["answered_passed"] = sum(r["model"]["passed"] for r in answered)
    latencies = sorted(r["latency_s"] for r in answered)
    if latencies:
        summary["latency_p50_s"] = round(statistics.median(latencies), 3)
        summary["latency_p95_s"] = round(latencies[min(len(latencies) - 1,
                                                       int(0.95 * len(latencies)))], 3)
    # TFA-18: tool calls per row, for an agent candidate only (the oracle makes none
    # and reports None, which is left out rather than counted as zero).
    calls = [r["tool_calls"] for r in scored if r.get("tool_calls") is not None]
    if calls:
        summary["tool_calls_mean"] = round(statistics.mean(calls), 2)
        summary["tool_calls_max"] = max(calls)
        summary["tool_calls_per_row"] = {str(n): calls.count(n) for n in sorted(set(calls))}
    # A resumed run spans days; which rows ran when goes into the plan.md log.
    days = [r["ran_on"] for r in scored if r.get("ran_on")]
    summary["ran_on"] = {d: days.count(d) for d in sorted(set(days))}
    summary["slot_stage"] = {s: sum(r["slots"]["status"] == s for r in results)
                             for s in ("pass", "fail", "known_gap", "gap_closed")}
    return summary


def print_report(name: str, results: list[dict], summary: dict) -> None:
    scored = [r for r in results if "model" in r]
    n = summary["answer_rows"]
    print(f"model={name}  answer_rows={n}  ask_back_rows={len(results) - n}\n")
    if n:
        print(f"{'':<12}{'valid_json':<12}{'rubric':<10}{'guardrail':<11}{'all three'}")
        groups: dict[str, list[dict]] = {"ALL": scored}
        for r in scored:
            groups.setdefault(r["kind"], []).append(r)
            groups.setdefault(r["lang"], []).append(r)
        for label, rows in groups.items():
            cells = [_pct(sum(r["model"][k] for r in rows), len(rows))
                     for k in ("valid_json", "rubric", "guardrail", "passed")]
            print(f"{label:<12}{cells[0]:<12}{cells[1]:<10}{cells[2]:<11}{cells[3]}  "
                  f"({len(rows)} rows)")
        if summary["answered"] < n:
            print(f"\nanswered (not rate-limited)  {summary['answered']}/{n} rows, "
                  f"{_pct(summary['answered_passed'], summary['answered'])} of them pass "
                  "all three")
        if "latency_p50_s" in summary:
            print(f"\nlatency  p50={summary['latency_p50_s']}s  p95={summary['latency_p95_s']}s"
                  + ("  (answered rows)" if summary["answered"] < n else ""))
        if summary["call_errors"]:
            print("call errors  " + "  ".join(
                f"{k}={v}" for k, v in summary["call_errors"].items()))
        if len(summary["ran_on"]) > 1:
            print("answered on  " + "  ".join(
                f"{d}:{c}" for d, c in summary["ran_on"].items()))
        if "tool_calls_mean" in summary:
            spread = "  ".join(f"{n}:{c}" for n, c in summary["tool_calls_per_row"].items())
            print(f"tool calls per row  mean={summary['tool_calls_mean']}  "
                  f"max={summary['tool_calls_max']}  (calls:rows {spread})")
        failed = [r for r in scored if not r["model"]["passed"]]
        if failed:
            print(f"\n{'id':<11}problems")
            for r in failed:
                print(f"{r['id']:<11}{'; '.join(r['model']['problems'])[:300]}")

    slot = summary["slot_stage"]
    print(f"\nslot stage (TFA-3)  pass={slot['pass']}  known_gap={slot['known_gap']}  "
          f"fail={slot['fail']}  gap_closed={slot['gap_closed']}")
    for r in results:
        s = r["slots"]
        if s["status"] == "known_gap":
            print(f"  gap   {r['id']:<11}{s['known_gap']}")
        elif s["status"] in ("fail", "gap_closed"):
            note = "now passes: remove known_gap" if s["status"] == "gap_closed" else "; ".join(
                s["problems"])
            print(f"  {s['status']:<5} {r['id']:<11}{note}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--model", default="oracle",
                    help="oracle | strands:<gemini|groq|ollama>[:<model>]")
    ap.add_argument("--timeout", type=float, default=config.ADVISORY_AGENT_TIMEOUT_S,
                    help="seconds per row for an agent (default: ADVISORY_AGENT_TIMEOUT_S)")
    ap.add_argument("--kind", choices=KINDS)
    ap.add_argument("--lang")
    ap.add_argument("--min-pass", type=float, default=None,
                    help="exit 1 if the all-three pass rate is below this (0-1)")
    ap.add_argument("--out", default=None, help="write the full results as JSON here")
    ap.add_argument("--pause", type=float, default=0.0,
                    help="seconds to wait between answer rows (free-tier rate limits)")
    ap.add_argument("--resume", default=None,
                    help="an earlier --out file: keep its answers, ask only the rows that\n"
                         "were rate-limited or are missing (same model and --timeout)")
    args = ap.parse_args()
    if args.resume and (args.kind or args.lang):
        # The --out file is rewritten from this run's rows, so a subset would drop
        # the stored answers outside it.
        raise SystemExit("--resume runs the whole set: drop --kind/--lang")

    rows = load_rows()
    bad = [(r.get("id"), p) for r in rows for p in validate_row(r)]
    if bad:
        for row_id, problem in bad:
            print(f"eval set: {row_id}: {problem}")
        return 1
    rows = [r for r in rows if (not args.kind or r["kind"] == args.kind)
            and (not args.lang or r["lang"].split("-")[0] == args.lang)]

    candidate = make_candidate(args.model, timeout=args.timeout)
    previous = (load_previous(Path(args.resume), candidate.name, args.timeout)
                if args.resume else None)
    results = run_rows(rows, candidate, pause=args.pause, previous=previous,
                       progress=print_progress)
    summary = summarise(results)
    print_report(candidate.name, results, summary)
    limited = summary["call_errors"].get("rate_limited")
    if limited and args.out:
        print(f"\n{limited} rows were rate-limited: run the same command with "
              f"--resume {args.out} once the quota resets to ask only those")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "model": candidate.name, "timeout_s": args.timeout, "summary": summary,
            "rows": results,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    unexpected = summary["slot_stage"]["fail"] + summary["slot_stage"]["gap_closed"]
    below = (args.min_pass is not None and summary["answer_rows"]
             and summary["passed"] / summary["answer_rows"] < args.min_pass)
    return 1 if unexpected or below else 0


if __name__ == "__main__":
    sys.exit(main())
