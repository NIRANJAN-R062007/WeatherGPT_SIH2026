"""WIE-16: live check of persona and windowed answers against the guardrail (plan.md §15).

    python ml/intelligence/live_check.py --out ml/intelligence/live_check.json
    python ml/intelligence/live_check.py --kind window --pause 8

Needs real provider keys in .env (GEMINI_API_KEY and/or GROQ_API_KEY); the weather
is fixtures, so only the LLM is live. Every row goes through main._narrate_grounded,
the production loop /ask uses: narrate, guardrail.check against the full facts, one
regenerate with the unmatched figures as feedback, else the template. Two kinds:

  persona  a current-weather answer narrated for each persona — exactly what /ask
           does today when a persona is set
  window   the Weather Intelligence Engine's best window (persona_advisor.advise)
           worded by the LLM and grounded against the engine's own result. /ask
           does NOT do this yet (its window answer is i18n.py's template, WIE-8);
           this row kind measures whether it could

Each row records the outcome — `first_try` (grounded at once), `regenerated`
(grounded on the retry), `template` (both attempts failed the guardrail, /ask
would answer from the template) or `no_llm` (no provider answered) — with the
provider, the wall-clock latency of the whole loop, the text and any unmatched
figures. The summary gives the rates per kind and p50/p95 of the latency against
plan.md's 2 s p95 target. English only: Bhashini's translation step is not run.
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
os.environ.setdefault("WEATHER_MODE", "fixtures")  # before config is imported
sys.path.insert(0, str(HERE.parents[1] / "services" / "orchestrator"))

import cities  # noqa: E402
import guardrail  # noqa: E402
import main  # noqa: E402
import narrate  # noqa: E402
import persona as persona_module  # noqa: E402
import weather_data  # noqa: E402
from weather_intelligence.persona_advisor import advise, wants_window  # noqa: E402

KINDS = ("persona", "window")
PERSONAS = ("general", "farmer", "traveller", "fisherman", "aviation", "city_official")
_WINDOW_SUMMARY = ("start_local", "end_local", "avg_temp_c", "max_rain_probability_pct",
                   "max_wind_kmh")


def build_rows(kinds=KINDS) -> list[dict]:
    """(kind, city, persona, facts) rows from the fixture weather."""
    rows = []
    for key in sorted(cities.CITY_KEYS):
        name = cities.display_name(key, "en")
        if "persona" in kinds:
            facts = weather_data.get_weather(key, "current_weather", "today")
            if facts:
                for p in PERSONAS:
                    rows.append({"id": f"persona:{key}:{p}", "kind": "persona", "city": name,
                                 "persona": p, "intent": "current_weather",
                                 "data": facts, "prompt_facts": facts})
        if "window" in kinds:
            hourly = weather_data.hourly_facts(key, "today")
            if not hourly:
                continue
            for p in PERSONAS:
                if not wants_window(p):
                    continue
                window = advise(hourly["hours"], p)["window"]
                if window is None:
                    continue  # "no suitable window" has nothing to word
                summary = {k: window[k] for k in _WINDOW_SUMMARY}
                rows.append({"id": f"window:{key}:{p}", "kind": "window", "city": name,
                             "persona": p, "intent": "best_window",
                             # the guardrail sees the engine's whole result, hours included
                             "data": {"window": window},
                             "prompt_facts": {"day": hourly["day"], "best_window": summary}})
    return rows


def run_row(row: dict) -> dict:
    persona = None if row["persona"] == persona_module.DEFAULT else row["persona"]
    tries = []  # every narration the loop asked for, kept for the log

    def recording_narrate(*a, **k):
        t0 = time.perf_counter()
        text = narrate.narrate(*a, **k)
        report = guardrail.check(text, row["data"]) if text else None
        tries.append({"provider": narrate.last_provider if text else None,
                      "latency_s": round(time.perf_counter() - t0, 3), "text": text,
                      "unmatched": [f["reading"] for f in report.figures if not f["matched"]]
                      if report else None})
        return text

    main.narrate = recording_narrate
    try:
        start = time.perf_counter()
        text, _, attempted, attempts, provider = main._narrate_grounded(
            row["intent"], row["city"], row["data"], row["prompt_facts"], persona)
        latency = time.perf_counter() - start
    finally:
        main.narrate = narrate.narrate
    if text:
        outcome = "first_try" if attempts == 1 else "regenerated"
    else:
        outcome = "template" if attempted else "no_llm"
    return {"id": row["id"], "kind": row["kind"], "persona": row["persona"],
            "outcome": outcome, "provider": provider, "latency_s": round(latency, 3),
            "answer": text, "tries": tries}


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1]


def summarise(results: list[dict]) -> dict:
    out = {}
    for kind in KINDS:
        rs = [r for r in results if r["kind"] == kind]
        if not rs:
            continue
        counts = {o: sum(r["outcome"] == o for r in rs)
                  for o in ("first_try", "regenerated", "template", "no_llm")}
        answered = [r for r in rs if r["outcome"] != "no_llm"]
        lat = sorted(r["latency_s"] for r in answered)
        out[kind] = {
            "rows": len(rs), **counts,
            "tripped_guardrail": counts["regenerated"] + counts["template"],
            "providers": {p: sum((r["provider"] or "none") == p for r in rs)
                          for p in sorted({r["provider"] or "none" for r in rs})},
            "p50_s": _pct(lat, 50), "p95_s": _pct(lat, 95), "max_s": max(lat, default=None),
        }
    return out


def main_cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--kind", choices=KINDS, help="only this row kind")
    ap.add_argument("--limit", type=int, default=None, help="stop after this many rows")
    ap.add_argument("--pause", type=float, default=0.0,
                    help="seconds between rows (Groq's free tier allows 8,000 tokens a minute)")
    ap.add_argument("--out", default=None, help="write rows and summary as JSON here")
    args = ap.parse_args()

    if not narrate.is_configured():
        print("no LLM provider configured: set GEMINI_API_KEY / GROQ_API_KEY in .env",
              file=sys.stderr)
        return 2
    rows = build_rows((args.kind,) if args.kind else KINDS)[: args.limit]
    print(f"{len(rows)} rows, providers: {[n for n, _ in narrate.providers()]}")
    results = []
    for i, row in enumerate(rows):
        if i and args.pause:
            time.sleep(args.pause)
        r = run_row(row)
        results.append(r)
        print(f"{r['id']:<40} {r['outcome']:<12} {r['provider'] or '-':<7} {r['latency_s']:.2f}s")
    summary = summarise(results)
    print(json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": results},
                                             indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
