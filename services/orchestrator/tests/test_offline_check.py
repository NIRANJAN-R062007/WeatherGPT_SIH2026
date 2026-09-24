"""offline_check.run(): the demo-morning preflight must pass cleanly with
fixtures + no live Ollama (this suite's normal, network-blocked state) and
must distinguish "a needs_llm query failed but Ollama is down anyway" (WARN)
from a real failure (FAIL, exit 1).
"""

import config
import google_weather
import offline_check


def test_run_passes_offline_with_no_live_ollama(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    lines = []
    assert offline_check.run(max_age_hours=100000, out=lines.append) == 0

    ollama_line = next(line for line in lines if line.startswith("base="))
    assert "WARN" in ollama_line

    fixture_lines = [line for line in lines if "STALE" in line or " MISSING" in line]
    assert fixture_lines == []

    # Rain-keyword detection in intent.py's rules pass is still EN/TA-only, so
    # this Hindi query's *intent* comes back as the current_weather default
    # rather than will_it_rain — a pre-existing gap, unrelated to city
    # resolution. But cities.resolve() now matches hi/te/mr names too (it
    # used to check only en/ta), so the city itself resolves via
    # rules_fallback and the answer grounds cleanly offline: no WARN/FAIL.
    hindi_line = next(line for line in lines if "चेन्नई" in line)
    assert "WARN" not in hindi_line and "FAIL" not in hindi_line


def test_run_fails_on_missing_fixture(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setitem(google_weather.ENDPOINTS, "bogus_kind", "bogus:lookup")
    lines = []
    assert offline_check.run(max_age_hours=100000, out=lines.append) == 1
    assert any("MISSING" in line for line in lines)


def test_run_without_queries_skips_ask_checks(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2:3b")
    lines = []
    assert offline_check.run(max_age_hours=100000, queries=False, out=lines.append) == 0
    assert not any(line.startswith("query |") for line in lines)
