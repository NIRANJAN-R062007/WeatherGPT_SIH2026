"""Run the NLU eval set (plan.md §8/§14) against nlu.parse() and report accuracy.

    python ml/nlu/run_eval.py --path rules   # offline, no keys
    python ml/nlu/run_eval.py --path llm     # needs GEMINI_API_KEY/GROQ_API_KEY in .env
    python ml/nlu/run_eval.py --path all
"""

import argparse
import json
import sys
from pathlib import Path

EVAL_SET = Path(__file__).resolve().parent / "eval_set.jsonl"


def _load_rows(path_filter: str, lang_filter: str | None) -> list[dict]:
    rows = []
    for line in EVAL_SET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if path_filter != "all" and row["path"] != path_filter:
            continue
        if lang_filter and row["lang"] != lang_filter:
            continue
        rows.append(row)
    return rows


def _check_row(row: dict, nlu, cities) -> list[tuple]:
    """Return a list of (field, expected, got) mismatches for one row."""
    pq = nlu.parse(row["text"])
    expected = row["expected"]
    mismatches = []

    if cities.resolve(pq.city) != expected.get("city"):
        mismatches.append(("city", expected.get("city"), cities.resolve(pq.city)))
    if pq.intent != expected.get("intent"):
        mismatches.append(("intent", expected.get("intent"), pq.intent))
    if pq.time_window != expected.get("time_window"):
        mismatches.append(("time_window", expected.get("time_window"), pq.time_window))
    if "days" in expected and pq.days != expected["days"]:
        mismatches.append(("days", expected["days"], pq.days))
    if pq.parameter != expected.get("parameter"):
        mismatches.append(("parameter", expected.get("parameter"), pq.parameter))

    expected_lang = None if row["lang"] == "other" else row["lang"]
    if pq.language != expected_lang:
        mismatches.append(("language", expected_lang, pq.language))

    return mismatches, pq.source


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default="rules", choices=["rules", "llm", "all"])
    ap.add_argument("--lang", default=None)
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "prototype" / "ask_service"))
    import cities
    import config
    import nlu

    if args.path == "rules":  # same isolation as test_nlu_eval.py: rules rows never hit an LLM
        config.GEMINI_API_KEY = None
        config.GROQ_API_KEY = None

    rows = _load_rows(args.path, args.lang)
    if not rows:
        print("No matching eval rows.")
        return 0

    total = 0
    passed = 0
    per_lang: dict[str, list[int]] = {}
    mismatch_rows = []

    for row in rows:
        total += 1
        lang = row["lang"]
        per_lang.setdefault(lang, [0, 0])
        per_lang[lang][1] += 1

        mismatches, source = _check_row(row, nlu, cities)
        if not mismatches:
            passed += 1
            per_lang[lang][0] += 1
        else:
            for field, expected, got in mismatches:
                mismatch_rows.append((row["id"], lang, field, expected, got, source))

    print(f"path={args.path}  rows={total}  passed={passed}  accuracy={passed / total:.1%}\n")
    print(f"{'lang':<8}{'passed':<10}{'total':<8}accuracy")
    for lang, (ok, n) in sorted(per_lang.items()):
        print(f"{lang:<8}{ok:<10}{n:<8}{ok / n:.1%}")

    if mismatch_rows:
        print(f"\n{'id':<10}{'lang':<8}{'field':<14}{'expected':<20}{'got':<20}source")
        for row_id, lang, field, expected, got, source in mismatch_rows:
            print(f"{row_id:<10}{lang:<8}{field:<14}{str(expected):<20}{str(got):<20}{source}")
        return 1

    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
