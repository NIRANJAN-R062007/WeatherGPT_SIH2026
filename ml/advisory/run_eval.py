"""Score candidate models on the travel/farming eval set (plan.md §8 TFA-1, §11.5).

    python ml/advisory/run_eval.py --model oracle
    python ml/advisory/run_eval.py --model ollama:qwen3:8b --no-think --out qwen3-8b.json
    python ml/advisory/run_eval.py --model openai:qwen3-8b --base-url http://gpu-host:8000/v1

For each `answer` row it builds the facts (real fixture collectors plus one named
weather scenario, scenarios.py), asks the candidate, and scores three things per
plan §11.5:

  valid JSON   the reply is one JSON object in the advisory/schema.py shape
  rubric       the verdict is one the row allows (and carries the window when asked)
  guardrail    guardrail.check_advisory() passes: every number, clock time, window
               and cited path in the reply traces to the facts

A row passes only if all three do. Each row also reports latency. `ask_back` rows
have no model call: they check the TFA-3 slot parser, as does the first stage of
every `answer` row. The model scores are results, not a pass/fail gate, unless
`--min-pass` is given; the exit code is 1 for a broken eval set or an unexpected
slot-stage failure.

`oracle` answers from the rubric in code, so it must score 100%: it proves the
set, the scenarios and the harness agree with each other, and is the baseline a
real model is read against. Real candidates need a server (TFA-2); nothing here
starts one.

Row fields: id, lang, kind (travel|farming), type (answer|ask_back), text, slots
(the slots a correct parse yields), then for answers `scenario` and `expected`
{verdict: [allowed...], window: bool}, for ask-backs `missing` (and optionally
`unsupported`). `known_gap` marks a row whose slot stage fails today because of a
TFA-3 gap: it reports as a gap, and flags itself once the gap is fixed.
"""

from __future__ import annotations

import argparse
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

import guardrail  # noqa: E402
import httpx  # noqa: E402
import prompt as prompt_module  # noqa: E402
import rubric  # noqa: E402
import scenarios  # noqa: E402
from advisory import schema, slots  # noqa: E402

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


# --- the reference answer (the `oracle` candidate) -------------------------------


def reference_answer(row: dict, facts) -> str:
    verdict = rubric.reference_verdict(facts)
    pros: list[str] = []
    cons: list[str] = []
    cites: list[str] = []
    raw = facts.raw()

    if facts.kind == "travel":
        for role in ("origin", "destination"):
            if "forecast" not in raw.get(role, {}):
                cons.append(f"The forecast for the {role} is not available.")
                continue
            pct = raw[role]["forecast"]["rain_probability_pct"]
            (cons if pct >= rubric.RAIN_CAUTION_PCT else pros).append(
                f"Rain chance at the {role} is {pct}%.")
            cites.append(f"{role}.forecast.rain_probability_pct")
            wind = (raw[role].get("current") or {}).get("wind_kmh")
            if wind is not None:
                (cons if wind >= rubric.WIND_CAUTION_KMH else pros).append(
                    f"Wind at the {role} is {wind} km/h.")
                cites.append(f"{role}.current.wind_kmh")
            warning = raw[role].get("warnings")
            if warning is None:
                cons.append(f"The IMD warning for the {role} is not available.")
            elif warning["colour"] == "green":
                pros.append(f"No IMD warning is in force at the {role}.")
            else:
                cons.append(f"An {warning['colour']} IMD warning is in force at the {role}.")
            aviation = raw[role].get("aviation")
            if aviation and "thunderstorm" in aviation["metar"]["briefing"]:
                cons.append(f"The {role} airport report shows a thunderstorm.")
    else:
        crop = raw.get("crop", {}).get("entry")
        days = (raw.get("location", {}).get("forecast") or {}).get("days")
        if crop is None:
            cons.append("The crop file has no entry for this crop.")
        if not days:
            cons.append("The forecast is not available.")
        if crop and days:
            day = days[0]
            ok = verdict == "suitable"
            (pros if ok else cons).append(
                f"Rain chance is {day['rain_probability_pct']}% with a high of {day['high_c']}°C.")
            cites += ["location.forecast.days[0].rain_probability_pct",
                      "location.forecast.days[0].high_c"]

    window = None
    section = facts.section("destination", "window")
    if row["expected"]["window"] and section is not None and section.available:
        window = {k: section.data[k] for k in ("start_local", "end_local")}
    return json.dumps({"verdict": verdict, "pros": pros, "cons": cons, "window": window,
                       "cites": cites}, ensure_ascii=False)


# --- candidates ------------------------------------------------------------------


class Candidate:
    name = "?"

    def __call__(self, text: str, row: dict, facts) -> str:
        raise NotImplementedError


class Oracle(Candidate):
    name = "oracle"

    def __call__(self, text, row, facts):
        return reference_answer(row, facts)


class Ollama(Candidate):
    """Native /api/generate. Temperature 0, so a re-run is comparable."""

    def __init__(self, model: str, base: str, constrain: bool, no_think: bool, timeout: float):
        self.name = f"ollama:{model}"
        self.model, self.base = model, base.rstrip("/")
        self.constrain, self.no_think, self.timeout = constrain, no_think, timeout

    def __call__(self, text, row, facts):
        body = {"model": self.model, "prompt": text, "stream": False, "keep_alive": "30m",
                "options": {"temperature": 0, "num_predict": 700}}
        if self.constrain:
            body["format"] = prompt_module.json_schema(row["kind"])
        if self.no_think:
            body["think"] = False
        resp = httpx.post(f"{self.base}/api/generate", json=body,
                          timeout=httpx.Timeout(self.timeout, connect=5.0))
        resp.raise_for_status()
        return resp.json().get("response") or ""


class OpenAICompatible(Candidate):
    """/chat/completions: vLLM, Groq, or any hosted open-weight endpoint. The key
    is read from LLM_API_KEY, never from the command line."""

    def __init__(self, model: str, base: str, constrain: bool, no_think: bool, timeout: float):
        self.name = f"openai:{model}"
        self.model, self.base = model, base.rstrip("/")
        self.constrain, self.no_think, self.timeout = constrain, no_think, timeout

    def __call__(self, text, row, facts):
        body = {"model": self.model, "messages": [{"role": "user", "content": text}],
                "temperature": 0, "max_tokens": 700}
        if self.constrain:
            body["response_format"] = {"type": "json_object"}
        if self.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Content-Type": "application/json"}
        if os.getenv("LLM_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['LLM_API_KEY']}"
        resp = httpx.post(f"{self.base}/chat/completions", json=body, headers=headers,
                          timeout=httpx.Timeout(self.timeout, connect=5.0))
        resp.raise_for_status()
        choices = resp.json().get("choices") or []
        return ((choices[0].get("message") or {}).get("content") or "") if choices else ""


def make_candidate(spec: str, *, base_url: str | None, constrain: bool, no_think: bool,
                   timeout: float) -> Candidate:
    kind, _, model = spec.partition(":")
    if kind == "oracle" and not model:
        return Oracle()
    if kind == "ollama" and model:
        base = base_url or os.getenv("OLLAMA_BASE") or "http://localhost:11434"
        return Ollama(model, base, constrain, no_think, timeout)
    if kind == "openai" and model:
        base = base_url or os.getenv("LLM_BASE_URL")
        if not base:
            raise SystemExit("openai:<model> needs --base-url (or LLM_BASE_URL)")
        return OpenAICompatible(model, base, constrain, no_think, timeout)
    raise SystemExit(f"unknown --model {spec!r}: use oracle, ollama:<model> or openai:<model>")


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


def run_row(row: dict, candidate: Candidate) -> dict:
    out = {"id": row["id"], "lang": row["lang"], "kind": row["kind"], "type": row["type"],
           "slots": slot_stage(row)}
    if row["type"] != "answer":
        return out
    facts = scenarios.build(row["kind"], row["slots"], row["scenario"])
    text = prompt_module.build(row, facts)
    started = time.perf_counter()
    try:
        reply = candidate(text, row, facts)
        error = None
    except (httpx.HTTPError, OSError, ValueError) as exc:
        reply, error = "", f"{type(exc).__name__}: {exc}"
    out["latency_s"] = round(time.perf_counter() - started, 3)
    out["reply"] = reply
    out["error"] = error
    out["model"] = score_reply(row, facts, reply)
    if error:
        out["model"]["problems"].insert(0, f"call failed: {error}")
    return out


# --- report ------------------------------------------------------------------------


def _pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "-"


def summarise(results: list[dict]) -> dict:
    scored = [r for r in results if "model" in r]
    summary: dict = {"answer_rows": len(scored)}
    for key in ("valid_json", "rubric", "guardrail", "passed"):
        summary[key] = sum(r["model"][key] for r in scored)
    latencies = sorted(r["latency_s"] for r in scored)
    if latencies:
        summary["latency_p50_s"] = round(statistics.median(latencies), 3)
        summary["latency_p95_s"] = round(latencies[min(len(latencies) - 1,
                                                       int(0.95 * len(latencies)))], 3)
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
        if "latency_p50_s" in summary:
            print(f"\nlatency  p50={summary['latency_p50_s']}s  p95={summary['latency_p95_s']}s")
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
    ap.add_argument("--model", default="oracle", help="oracle | ollama:<model> | openai:<model>")
    ap.add_argument("--base-url", default=None, help="server base URL (ollama or openai)")
    ap.add_argument("--schema", action="store_true",
                    help="constrain decoding to the answer schema (default: free generation)")
    ap.add_argument("--no-think", action="store_true", help="turn a thinking model's reasoning off")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--kind", choices=KINDS)
    ap.add_argument("--lang")
    ap.add_argument("--min-pass", type=float, default=None,
                    help="exit 1 if the all-three pass rate is below this (0-1)")
    ap.add_argument("--out", default=None, help="write the full results as JSON here")
    args = ap.parse_args()

    rows = load_rows()
    bad = [(r.get("id"), p) for r in rows for p in validate_row(r)]
    if bad:
        for row_id, problem in bad:
            print(f"eval set: {row_id}: {problem}")
        return 1
    rows = [r for r in rows if (not args.kind or r["kind"] == args.kind)
            and (not args.lang or r["lang"].split("-")[0] == args.lang)]

    candidate = make_candidate(args.model, base_url=args.base_url, constrain=args.schema,
                               no_think=args.no_think, timeout=args.timeout)
    results = [run_row(row, candidate) for row in rows]
    summary = summarise(results)
    print_report(candidate.name, results, summary)

    if args.out:
        Path(args.out).write_text(json.dumps({
            "model": candidate.name, "schema_constrained": args.schema,
            "no_think": args.no_think, "summary": summary, "rows": results,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    unexpected = summary["slot_stage"]["fail"] + summary["slot_stage"]["gap_closed"]
    below = (args.min_pass is not None and summary["answer_rows"]
             and summary["passed"] / summary["answer_rows"] < args.min_pass)
    return 1 if unexpected or below else 0


if __name__ == "__main__":
    sys.exit(main())
