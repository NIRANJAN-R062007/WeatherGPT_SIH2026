#!/usr/bin/env python3
"""End-to-end smoke test for a deployed WeatherGPT backend (plan.md Phase 7, B4).

    python deploy/smoke.py https://3-108-52-61.sslip.io
    python deploy/smoke.py http://localhost:8000 --json

Standard library only, so it runs from any machine with no install. It sends
read-only GETs and five /ask questions; nothing is written on the target.

Three groups of checks:

  health    /health answers 200. Through the gateway it also reports Postgres,
            PostGIS, Redis and the orchestrator; every one must be "ok".
  ask       One /ask per app language (en, hi, ta, te, mr): HTTP 200, a reply
            that is not empty, grounding ok with every figure matched, and (for
            the four Indic languages) a reply written in that script, so an
            English fallback does not pass as a translation.
  current   Routes and data that only a build of `main` has: all 8 demo cities,
            /warnings with a `status`, /aviation, /intelligence/best-window,
            /glossary, /forecast/daily with sunrise, /forecast/hourly, /facts'
            `rain_so_far` and /hotlines. A backend that passes `health` and
            `ask` but fails here is a stale deploy.

Exit code 0 only when every check passes. A template answer in place of an LLM
answer is reported as INFO, not a failure: the template path is a valid,
grounded answer (plan.md section 2).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LANGS = ("en", "hi", "ta", "te", "mr")

# Unicode block each Indic language's reply must contain (an English fallback
# or an untranslated reply has none of these).
SCRIPT = {
    "hi": (0x0900, 0x097F),
    "mr": (0x0900, 0x097F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
}

EXPECTED_CITIES = {
    "chennai", "madurai", "coimbatore", "bengaluru",
    "hyderabad", "mumbai", "delhi", "thiruvananthapuram",
}

ASK_TIMEOUT = 45  # /ask is the slow one: narration plus translation
GET_TIMEOUT = 20

PASS, FAIL, INFO = "PASS", "FAIL", "INFO"


def fetch(base: str, path: str, params: dict | None = None, timeout: int = GET_TIMEOUT):
    """(status, parsed JSON or None, seconds). status 0 means no HTTP answer."""
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read()
    except Exception as err:  # DNS, TLS, refused, timeout
        return 0, f"{type(err).__name__}: {err}", time.monotonic() - started
    elapsed = time.monotonic() - started
    try:
        return status, json.loads(body.decode("utf-8")), elapsed
    except ValueError:
        return status, None, elapsed


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, group: str, name: str, status: str, detail: str = "") -> None:
        self.rows.append({"group": group, "name": name, "status": status, "detail": detail})

    @property
    def failed(self) -> bool:
        return any(r["status"] == FAIL for r in self.rows)

    def print_table(self) -> None:
        width = max((len(r["name"]) for r in self.rows), default=10)
        group = None
        for r in self.rows:
            if r["group"] != group:
                group = r["group"]
                print(f"\n[{group}]")
            print(f"  {r['status']:<4}  {r['name']:<{width}}  {r['detail']}")
        counts = {s: sum(r["status"] == s for r in self.rows) for s in (PASS, FAIL, INFO)}
        print(f"\n{counts[PASS]} passed, {counts[FAIL]} failed, {counts[INFO]} info")
        print("RESULT:", "FAILED" if self.failed else "OK")


def check_health(base: str, rep: Report) -> None:
    status, body, secs = fetch(base, "/health")
    if status != 200 or not isinstance(body, dict):
        rep.add("health", "/health", FAIL, f"HTTP {status} {body if status == 0 else ''}".strip())
        return
    if "components" in body:  # the gateway's shape: every dependency named
        comps = body["components"]
        bad = {k: v for k, v in comps.items() if v != "ok"}
        detail = f"not ok: {bad}" if bad else "postgres, postgis, redis, orchestrator ok"
        rep.add("health", "/health (gateway)", FAIL if bad else PASS, f"{secs:.1f}s {detail}")
        return
    ok = body.get("status") == "ok"
    rep.add("health", "/health (orchestrator)", PASS if ok else FAIL,
            f"{secs:.1f}s status={body.get('status')}")
    rep.add("health", "Redis and Postgres reported", INFO,
            "not in the orchestrator's /health; put the gateway in front, "
            "or use deploy/persistence_check.sh")


def in_script(text: str, lang: str) -> bool:
    if lang == "en":
        return any("a" <= c.lower() <= "z" for c in text)
    low, high = SCRIPT[lang]
    return any(low <= ord(c) <= high for c in text)


def check_ask(base: str, rep: Report) -> None:
    for lang in LANGS:
        name = f"/ask lang={lang}"
        status, body, secs = fetch(
            base, "/ask",
            {"text": "will it rain today in Chennai", "lang": lang, "city": "chennai"},
            timeout=ASK_TIMEOUT)
        if status != 200 or not isinstance(body, dict):
            rep.add("ask", name, FAIL, f"HTTP {status} {body if status == 0 else ''}".strip())
            continue
        text = body.get("response")
        grounding = body.get("grounding") or {}
        problems = []
        if not text:
            problems.append("no `response` (got intent=%s)" % body.get("intent"))
        elif not in_script(text, lang):
            problems.append(f"reply is not written in {lang}")
        if grounding.get("ok") is not True:
            problems.append("grounding not ok")
        elif grounding.get("matched") != grounding.get("total"):
            problems.append(f"figures matched {grounding.get('matched')}/{grounding.get('total')}")
        narration = grounding.get("narration", "?")
        if problems:
            rep.add("ask", name, FAIL, "; ".join(problems))
        else:
            matched = f"{grounding['matched']}/{grounding['total']}"
            rep.add("ask", name, PASS, f"{secs:.1f}s grounded {matched}, narration={narration}")
        if not problems and narration == "template":
            rep.add("ask", f"/ask lang={lang} used the template", INFO,
                    "valid and grounded, but no LLM answered; check provider keys and quota")


def check_current(base: str, rep: Report) -> None:
    status, body, _ = fetch(base, "/cities")
    if status != 200 or not isinstance(body, dict):
        rep.add("current", "/cities", FAIL, f"HTTP {status}")
    else:
        keys = {c.get("key") for c in body.get("cities", [])}
        missing = sorted(EXPECTED_CITIES - keys)
        rep.add("current", "/cities lists all 8 demo cities", FAIL if missing else PASS,
                f"missing {missing}" if missing else f"{len(keys)} cities")

    # A city only the newer build serves: a stale one answers "I can only answer for ...".
    status, body, _ = fetch(base, "/facts", {"city": "mumbai"})
    has = status == 200 and isinstance(body, dict) and isinstance(body.get("facts"), dict)
    message = body.get("message", "") if isinstance(body, dict) else ""
    rep.add("current", "/facts?city=mumbai has facts", PASS if has else FAIL,
            "" if has else f"HTTP {status} {message}".strip())

    status, body, _ = fetch(base, "/warnings", {"city": "mumbai"})
    ok = status == 200 and isinstance(body, dict) and "status" in body
    why = f"HTTP {status}" if status != 200 else "no `status` field (old shape)"
    rep.add("current", "/warnings has `status`", PASS if ok else FAIL, "" if ok else why)

    status, body, _ = fetch(base, "/aviation", {"city": "chennai"})
    ok = status == 200 and isinstance(body, dict) and "status" in body
    rep.add("current", "/aviation answers", PASS if ok else FAIL, "" if ok else f"HTTP {status}")

    status, body, _ = fetch(base, "/intelligence/best-window", {"city": "chennai", "day": "today"})
    ok = status == 200 and isinstance(body, dict) and body.get("status") in (
        "ok", "no_suitable_window", "unavailable")
    rep.add("current", "/intelligence/best-window answers", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}")

    status, body, _ = fetch(base, "/glossary", {"lang": "hi"})
    ok = status == 200 and isinstance(body, dict) and bool(body.get("entries"))
    rep.add("current", "/glossary?lang=hi has entries", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}")

    status, body, _ = fetch(base, "/forecast/daily", {"city": "chennai"})
    days = body.get("days") if isinstance(body, dict) else None
    ok = status == 200 and bool(days) and "sunrise" in days[0]
    rep.add("current", "/forecast/daily has days with sunrise", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}")

    status, body, _ = fetch(base, "/forecast/hourly", {"city": "chennai"})
    ok = status == 200 and isinstance(body, dict) and bool(body.get("hours"))
    rep.add("current", "/forecast/hourly has hours", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}")

    status, body, _ = fetch(base, "/facts", {"city": "chennai"})
    ok = status == 200 and isinstance(body, dict) and "rain_so_far" in body
    rep.add("current", "/facts has `rain_so_far`", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}" if status != 200 else "no `rain_so_far` (old shape)")

    status, body, _ = fetch(base, "/hotlines", {"city": "chennai"})
    lines = body.get("hotlines") if isinstance(body, dict) else None
    ok = status == 200 and bool(lines) and lines[0].get("dial") == "112"
    rep.add("current", "/hotlines starts with 112", PASS if ok else FAIL,
            "" if ok else f"HTTP {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", help="e.g. https://3-108-52-61.sslip.io")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    parser.add_argument("--skip-ask", action="store_true",
                        help="skip the five /ask calls (they spend LLM and Bhashini quota)")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rep = Report()
    check_health(args.base_url, rep)
    if not args.skip_ask:
        check_ask(args.base_url, rep)
    check_current(args.base_url, rep)

    if args.json:
        print(json.dumps({"base_url": args.base_url, "failed": rep.failed, "checks": rep.rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"Smoke test: {args.base_url}")
        rep.print_table()
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
