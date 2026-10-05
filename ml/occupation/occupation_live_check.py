"""Live check of answers narrated for a free-text occupation (plan.md §8 Phase 4
"any occupation" item, R12).

    python ml/occupation/occupation_live_check.py --provider groq --pause 8 \
        --out ml/occupation/live_check_groq.json

Needs a real key in .env; the weather is fixtures, so only the LLM is live.
Every row goes through main._narrate_grounded, the loop /ask uses: narrate,
guardrail.check against the full facts plus persona.makes_unsafe_claim, one
regenerate, else the template. Three kinds of row, a current-weather answer
for one demo city each:

  custom    every eval-set occupation the classifier should call "other", in
            all five languages, narrated as the unvetted `custom` persona
            (persona.Custom), which is what /ask does with one
  stress    the injection-shaped eval rows that pass the input filter, forced
            into a Custom persona as if the classifier had missed them: what
            the prompt quoting, the shared rules, the guardrail and the
            unsafe-claim check do on their own
  baseline  the same cities with no persona, for comparison

Each row records the outcome — `first_try`, `regenerated`, `template` (both
tries failed; /ask would answer from the template) or `no_llm` (no provider
gave any text) — with why each try failed (`ungrounded`, `no_figures`,
`unsafe_claim`), the provider, the latency of the whole loop and the text.
English only: Bhashini's translation step is not run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("WEATHER_MODE", "fixtures")  # before config is imported
sys.path.insert(0, str(HERE.parents[1] / "services" / "orchestrator"))
sys.path.insert(0, str(HERE))

import cities  # noqa: E402
import guardrail  # noqa: E402
import main  # noqa: E402
import narrate  # noqa: E402
import occupation  # noqa: E402
import occupation_eval  # noqa: E402
import persona as persona_module  # noqa: E402
import weather_data  # noqa: E402

KINDS = ("custom", "stress", "baseline")
OUTCOMES = ("first_try", "regenerated", "template", "no_llm")


def build_rows(kinds=KINDS) -> list[dict]:
    keys = sorted(cities.CITY_KEYS)
    eval_rows = occupation_eval.load_rows(("llm",))
    picks = {
        "custom": [r for r in eval_rows if r["expected"] == occupation.OTHER],
        "stress": [r for r in eval_rows if r["injection"]],
    }
    rows = []
    for kind in ("custom", "stress"):
        if kind not in kinds:
            continue
        for n, r in enumerate(picks[kind]):
            key = keys[n % len(keys)]
            rows.append({"id": f"{kind}:{r['id']}", "kind": kind, "city_key": key,
                         "occupation": occupation.clean(r["text"])})
    if "baseline" in kinds:
        rows += [{"id": f"baseline:{key}", "kind": "baseline", "city_key": key,
                  "occupation": None} for key in keys]
    return rows


def _why(text: str, report, persona) -> str | None:
    """Why the loop would reject this try, or None if it would take it."""
    if persona_module.makes_unsafe_claim(persona, text):
        return "unsafe_claim"
    if not report.ok:
        return "ungrounded"
    if report.total == 0:
        return "no_figures"
    return None


def run_row(row: dict) -> dict:
    persona = persona_module.Custom(row["occupation"]) if row["occupation"] else None
    facts = weather_data.get_weather(row["city_key"], "current_weather", "today")
    city = cities.display_name(row["city_key"], "en")
    tries = []
    errors = occupation_eval._Errors()
    narrate._LOG.addHandler(errors)

    def recording_narrate(*a, **k):
        t0 = time.perf_counter()
        text = narrate.narrate(*a, **k)
        report = guardrail.check(text, facts) if text else None
        tries.append({
            "provider": narrate.last_provider if text else None,
            "latency_s": round(time.perf_counter() - t0, 3), "text": text,
            "rejected_because": _why(text, report, persona) if text else "no_text",
            "unmatched": [f["reading"] for f in report.figures if not f["matched"]]
            if report else None,
        })
        return text

    main.narrate = recording_narrate
    try:
        start = time.perf_counter()
        text, _, attempted, attempts, provider = main._narrate_grounded(
            "current_weather", city, facts, facts, persona)
        latency = time.perf_counter() - start
    finally:
        main.narrate = narrate.narrate
        narrate._LOG.removeHandler(errors)
    if text:
        outcome = "first_try" if attempts == 1 else "regenerated"
    else:
        outcome = "template" if attempted else "no_llm"
    return {"id": row["id"], "kind": row["kind"], "occupation": row["occupation"],
            "city": city, "outcome": outcome, "provider": provider if text else None,
            "latency_s": round(latency, 3), "answer": text, "tries": tries,
            "error": "; ".join(errors.messages) or None}


def summarise(results: list[dict]) -> dict:
    out = {}
    for kind in KINDS:
        rs = [r for r in results if r["kind"] == kind]
        if not rs:
            continue
        counts = {o: sum(r["outcome"] == o for r in rs) for o in OUTCOMES}
        reasons: dict[str, int] = {}
        for r in rs:
            for t in r["tries"]:
                if t["rejected_because"]:
                    reasons[t["rejected_because"]] = reasons.get(t["rejected_because"], 0) + 1
        lat = sorted(r["latency_s"] for r in rs if r["outcome"] != "no_llm")
        out[kind] = {
            "rows": len(rs), **counts,
            "tripped_guardrail": counts["regenerated"] + counts["template"],
            "rejected_tries": reasons,
            "providers": {p: sum(r["provider"] == p for r in rs)
                          for p in sorted({r["provider"] for r in rs if r["provider"]})},
            "p50_s": occupation_eval._pct(lat, 50), "p95_s": occupation_eval._pct(lat, 95),
            "max_s": max(lat, default=None),
        }
    return out


def main_cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--provider", default="chain", choices=["chain", "gemini", "groq"])
    ap.add_argument("--kind", choices=KINDS, help="only this row kind")
    ap.add_argument("--limit", type=int, help="stop after this many rows")
    ap.add_argument("--pause", type=float, default=0.0,
                    help="seconds between rows (Groq's free tier allows 8,000 tokens a minute)")
    ap.add_argument("--resume", help="a previous --out file: run only its no_llm or missing rows")
    ap.add_argument("--out", help="write the rows and the summary here as JSON")
    args = ap.parse_args()

    occupation_eval._configure(args.provider, offline=False)
    if not narrate.is_configured():
        print(f"no key for {args.provider}: set GEMINI_API_KEY / GROQ_API_KEY in .env",
              file=sys.stderr)
        return 2
    rows = build_rows((args.kind,) if args.kind else KINDS)[: args.limit]
    results: list[dict] = []
    if args.resume and Path(args.resume).exists():
        previous = json.loads(Path(args.resume).read_text(encoding="utf-8"))["rows"]
        done = {r["id"]: r for r in previous if r["outcome"] != "no_llm"}
        results = [done[r["id"]] for r in rows if r["id"] in done]
        rows = [r for r in rows if r["id"] not in done]
        print(f"resuming: {len(results)} rows kept, {len(rows)} to run")
    print(f"{len(rows)} rows, providers: {[n for n, _ in narrate.providers()]}")
    for i, row in enumerate(rows):
        if i and args.pause:
            time.sleep(args.pause)
        r = run_row(row)
        results.append(r)
        print(f"{r['id']:<16} {r['outcome']:<12} {r['provider'] or '-':<7} {r['latency_s']:.2f}s"
              f"  {r['error'] or ''}", flush=True)
    summary = summarise(results)
    print(json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": results},
                                             indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
