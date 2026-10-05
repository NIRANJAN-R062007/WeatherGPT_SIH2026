"""Run the occupation eval set (plan.md §8 Phase 4 "any occupation" item, R12)
through occupation.resolve() and report accuracy.

    python ml/occupation/occupation_eval.py              # filter + rules rows, offline
    python ml/occupation/occupation_eval.py --path llm --provider groq --pause 5 \
        --out ml/occupation/eval_groq.json
    python ml/occupation/occupation_eval.py --path llm --provider gemini \
        --resume ml/occupation/eval_gemini.json --out ml/occupation/eval_gemini.json

Each row's text goes through the production path: clean() (the input filter),
the keyword rules, then the LLM classifier. A row passes when the outcome is
its `expected`: "rejected" (the filter refused it), a vetted persona, "other"
(answered as `custom`) or "not_an_occupation" (answered as `general`).

`--provider` pins one provider by blanking the other key; `chain` keeps the
production order (Gemini, then Groq). The local Ollama is always switched off:
this measures the cloud providers. A row the classifier didn't answer (a 429,
a 503, a timeout) is counted as unanswered, not as wrong, and `--resume` asks
only those rows again on a later run.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_SET = HERE / "eval_set.jsonl"
LANGS = ("en", "hi", "ta", "te", "mr")
PATHS = ("filter", "rules", "llm")
REJECTED = "rejected"


def load_rows(paths=PATHS, lang: str | None = None) -> list[dict]:
    rows = []
    for line in EVAL_SET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["path"] in paths and (lang is None or row["lang"] == lang):
            rows.append(row)
    return rows


class _Errors(logging.Handler):
    """Keeps the provider warnings logged while one row runs (run_chain and
    _classify_llm log a failure and carry on rather than raising)."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record):
        # httpx puts the URL in its message; drop it, keep the status
        self.messages.append(re.sub(r" for url '[^']*'", "", record.getMessage())[:200])


def rate_limited(error: str | None) -> bool:
    return bool(error) and any(s in error for s in ("429", "RESOURCE_EXHAUSTED", "rate limit"))


def outcome(resolved) -> tuple[str | None, str]:
    """(category, source) for an occupation.Resolved; category None when the
    classifier gave no answer."""
    if resolved.source == "unclassified":
        return None, "unclassified"
    if resolved.key == "custom":
        return "other", resolved.source
    if resolved.key == "general":
        return "not_an_occupation", resolved.source
    return resolved.key, resolved.source


def run_row(row: dict, occupation, narrate) -> dict:
    errors = _Errors()
    loggers = [logging.getLogger(n) for n in ("weathergpt.narrate", "weathergpt.occupation")]
    for lg in loggers:
        lg.addHandler(errors)
    narrate.last_provider = None
    start = time.perf_counter()
    try:
        got, source = outcome(occupation.resolve(row["text"]))
    except occupation.Rejected:
        got, source = REJECTED, "filter"
    finally:
        latency = time.perf_counter() - start
        for lg in loggers:
            lg.removeHandler(errors)
    return {
        "id": row["id"], "lang": row["lang"], "path": row["path"],
        "injection": row["injection"], "text": row["text"],
        "expected": row["expected"], "got": got, "source": source,
        "provider": narrate.last_provider if source == "llm" else None,
        "latency_s": round(latency, 3) if source == "llm" else None,
        "error": "; ".join(errors.messages) or None,
        "ok": got == row["expected"],
    }


def _pct(values: list[float], q: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return round(statistics.quantiles(values, n=100, method="inclusive")[q - 1], 3)


def summarise(results: list[dict]) -> dict:
    answered = [r for r in results if r["got"] is not None]
    unanswered = [r for r in results if r["got"] is None]

    def score(rs):
        return {"passed": sum(r["ok"] for r in rs), "answered": len(rs)}

    lat = sorted(r["latency_s"] for r in answered if r["latency_s"] is not None)
    return {
        "rows": len(results),
        **score(answered),
        "unanswered": len(unanswered),
        "rate_limited": sum(rate_limited(r["error"]) for r in unanswered),
        "by_path": {p: score([r for r in answered if r["path"] == p])
                    for p in PATHS if any(r["path"] == p for r in results)},
        "by_lang": {g: score([r for r in answered if r["lang"] == g])
                    for g in LANGS if any(r["lang"] == g for r in results)},
        "by_expected": {e: score([r for r in answered if r["expected"] == e])
                        for e in sorted({r["expected"] for r in results})},
        "injection": score([r for r in answered if r["injection"]]),
        "providers": {p: sum(r["provider"] == p for r in answered)
                      for p in sorted({r["provider"] for r in answered if r["provider"]})},
        "llm_p50_s": _pct(lat, 50), "llm_p95_s": _pct(lat, 95), "llm_max_s": max(lat, default=None),
        "misses": [{k: r[k] for k in ("id", "text", "expected", "got")}
                   for r in answered if not r["ok"]],
    }


def interleave(rows: list[dict]) -> list[dict]:
    """One row per language in turn, so a run the daily quota cuts short
    still has every language in it."""
    per_lang = [[r for r in rows if r["lang"] == g] for g in LANGS]
    width = max(map(len, per_lang), default=0)
    return [rs[i] for i in range(width) for rs in per_lang if i < len(rs)]


def merge_resume(previous: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept results, rows still to ask): a previous run's answered rows are
    kept as they are; unanswered or missing rows are asked again."""
    done = {r["id"]: r for r in previous if r["got"] is not None}
    kept = [done[row["id"]] for row in rows if row["id"] in done]
    todo = [row for row in rows if row["id"] not in done]
    return kept, todo


def _configure(provider: str, offline: bool) -> None:
    import config
    config.OLLAMA_MODEL = None  # defaults on; a local Ollama would otherwise answer
    if offline:
        config.GEMINI_API_KEY = None
        config.GROQ_API_KEY = None
    elif provider == "gemini":
        config.GROQ_API_KEY = None
    elif provider == "groq":
        config.GEMINI_API_KEY = None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--path", default="offline", choices=["offline", "llm", "all"],
                    help="offline = filter + rules rows (no keys); llm needs a key")
    ap.add_argument("--provider", default="chain", choices=["chain", "gemini", "groq"])
    ap.add_argument("--lang", choices=LANGS)
    ap.add_argument("--pause", type=float, default=0.0, help="seconds between LLM rows")
    ap.add_argument("--resume", help="a previous --out file: ask only its unanswered rows")
    ap.add_argument("--out", help="write the rows and the summary here as JSON")
    args = ap.parse_args()

    sys.path.insert(0, str(HERE.parents[1] / "services" / "orchestrator"))
    import narrate
    import occupation

    offline = args.path == "offline"
    _configure(args.provider, offline)
    if not offline and not narrate.is_configured():
        print(f"no key for {args.provider}: set GEMINI_API_KEY / GROQ_API_KEY in .env",
              file=sys.stderr)
        return 2
    paths = {"offline": ("filter", "rules"), "llm": ("llm",), "all": PATHS}[args.path]
    rows = load_rows(paths, args.lang)

    results: list[dict] = []
    if args.resume and Path(args.resume).exists():
        previous = json.loads(Path(args.resume).read_text(encoding="utf-8"))["rows"]
        results, rows = merge_resume(previous, rows)
        print(f"resuming: {len(results)} rows kept, {len(rows)} to ask")

    occupation.cache_clear()
    for i, row in enumerate(interleave(rows)):
        if i and args.pause and row["path"] == "llm":
            time.sleep(args.pause)
        r = run_row(row, occupation, narrate)
        results.append(r)
        mark = "ok" if r["ok"] else ("--" if r["got"] is None else "XX")
        lat = f"{r['latency_s']:.2f}s" if r["latency_s"] is not None else ""
        print(f"{mark} {r['id']:<8} {str(r['got']):<18} {r['provider'] or '':<7} {lat:<7}"
              f"{r['error'] or ''}", flush=True)

    order = {row["id"]: n for n, row in enumerate(load_rows())}
    results.sort(key=lambda r: order.get(r["id"], len(order)))
    summary = summarise(results)
    print(f"\nrows={summary['rows']}  passed={summary['passed']}/{summary['answered']} answered"
          f"  unanswered={summary['unanswered']} (rate-limited {summary['rate_limited']})")
    for group in ("by_path", "by_lang", "by_expected"):
        print(f"{group[3:]:<9}" + "  ".join(f"{k} {v['passed']}/{v['answered']}"
                                         for k, v in summary[group].items()))
    print(f"injection {summary['injection']['passed']}/{summary['injection']['answered']}"
          f"  providers {summary['providers']}  llm p50 {summary['llm_p50_s']}s"
          f" p95 {summary['llm_p95_s']}s max {summary['llm_max_s']}s")
    for m in summary["misses"]:
        print(f"MISS {m['id']:<8} {m['text']!r}: expected {m['expected']}, got {m['got']}")
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": results},
                                             indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
    return 0 if not summary["misses"] and not summary["unanswered"] else 1


if __name__ == "__main__":
    sys.exit(main())
