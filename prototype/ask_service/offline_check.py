"""Demo-morning preflight for OFFLINE_MODE (plan.md §8 Phase 6): confirms the
committed weather fixtures are present and fresh, Ollama is reachable and
warmed up, and a representative spread of /ask queries still ground —
without touching any real network.

    OFFLINE_MODE=1 python offline_check.py
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import cities
import config
import google_weather
import httpx
import narrate
from fastapi.testclient import TestClient
from main import app  # imported by name, not `main`, to leave main() free below

# EN current, TA rain tomorrow, EN 3-day, EN rain-so-far, HI rain tomorrow.
# Only the Hindi query needs an LLM to parse intent at all — EN/TA resolve via
# the rules fast-path even with Gemini/Groq/Ollama all down.
QUERIES = [
    ("what's the weather in Chennai", "en", False),
    ("நாளை சென்னையில் மழை பெய்யுமா?", "ta", False),
    ("3 day forecast for Chennai", "en", False),
    ("how much rain has Chennai had so far today?", "en", False),
    ("कल चेन्नई में बारिश होगी क्या?", "hi", True),
]

_REFRESH_CMD = "python snapshot_google_weather.py --city all --force"


def apply_offline() -> None:
    config.OFFLINE_MODE = True
    config.WEATHER_MODE = "fixtures"
    google_weather.cache_clear()


def check_fixtures(max_age_hours: float = 36.0) -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc)
    fixture_dir = config.FIXTURES_DIR / "google_weather"
    for kind in google_weather.ENDPOINTS:
        for city_key in sorted(cities.CITY_KEYS):
            path = fixture_dir / f"{kind}.{city_key}.json"
            row = {"kind": kind, "city": city_key, "status": "MISSING", "age_hours": None}
            if path.exists():
                try:
                    env = json.loads(path.read_text(encoding="utf-8"))
                    retrieved_at = env["_meta"]["retrieved_at"]
                    age = (now - datetime.fromisoformat(retrieved_at)).total_seconds() / 3600
                    row["age_hours"] = round(age, 1)
                    row["status"] = "STALE" if age > max_age_hours else "OK"
                except (OSError, KeyError, ValueError):
                    pass  # stays MISSING — unreadable is as unusable as absent
            rows.append(row)
    return rows


def check_ollama() -> dict:
    status = narrate.ollama_status()
    status["warmup_ms"] = None
    status["warmup_ok"] = False
    if status["reachable"]:
        start = time.monotonic()
        try:
            text = narrate.generate_ollama(
                "Reply OK", model=config.OLLAMA_MODEL, base=config.OLLAMA_BASE,
                timeout=config.OLLAMA_TIMEOUT,
            )
        except (httpx.HTTPError, KeyError, ValueError):
            text = None
        status["warmup_ms"] = round((time.monotonic() - start) * 1000)
        status["warmup_ok"] = bool(text)
    return status


def run_queries(client: TestClient) -> list[dict]:
    rows = []
    for text, lang, needs_llm in QUERIES:
        start = time.monotonic()
        body = client.get("/ask", params={"text": text, "lang": lang}).json()
        elapsed_ms = round((time.monotonic() - start) * 1000)
        grounding = body.get("grounding") or {}
        rows.append({
            "query": text, "lang": lang, "needs_llm": needs_llm,
            "intent": body.get("intent"),
            "nlu_source": (body.get("nlu") or {}).get("source"),
            "provider": grounding.get("provider"),
            "ok": bool(body.get("response")) and grounding.get("ok") is True,
            "attempts": grounding.get("attempts"),
            "narration": grounding.get("narration"),
            "fallback_used": grounding.get("fallback_used"),
            "text": body.get("response") or body.get("message") or "",
            "elapsed_ms": elapsed_ms,
        })
    return rows


def run(*, max_age_hours: float = 36.0, queries: bool = True, out=print) -> int:
    apply_offline()
    exit_code = 0

    out("=== fixtures ===")
    for row in check_fixtures(max_age_hours):
        if row["status"] == "MISSING":
            exit_code = 1
        line = f"{row['kind']:<20} {row['city']:<12} {row['status']}"
        if row["status"] == "STALE":
            line += f" (age {row['age_hours']}h) — refresh: {_REFRESH_CMD}"
        out(line)

    out("=== ollama ===")
    ollama = check_ollama()
    ollama_reachable = bool(ollama["reachable"])
    ollama_flag = "" if ollama["warmup_ok"] else " WARN"
    out(f"base={ollama['base']} model={ollama['model']} reachable={ollama['reachable']} "
        f"model_present={ollama['model_present']} warmup_ms={ollama['warmup_ms']}{ollama_flag}")

    if not queries:
        return exit_code

    out("=== queries ===")
    out("query | lang | intent | nlu.source | provider | ok | attempts | ms | text[:70]")
    client = TestClient(app)
    for row in run_queries(client):
        flag = ""
        if not row["ok"]:
            if row["needs_llm"] and not ollama_reachable:
                flag = " WARN"  # LLM-only query, offline fallback has no LLM to try
            else:
                flag = " FAIL"
                exit_code = 1
        out(f"{row['query']} | {row['lang']} | {row['intent']} | {row['nlu_source']} | "
            f"{row['provider']} | {row['ok']} | {row['attempts']} | {row['elapsed_ms']} | "
            f"{row['text'][:70]}{flag}")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-queries", action="store_true", help="skip the /ask spot checks")
    parser.add_argument("--max-age-hours", type=float, default=36.0,
                         help="fixture age before it's flagged STALE (default: 36)")
    args = parser.parse_args(argv)
    return run(max_age_hours=args.max_age_hours, queries=not args.no_queries)


if __name__ == "__main__":
    sys.exit(main())
