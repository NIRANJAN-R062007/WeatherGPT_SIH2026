# WeatherGPT load & abuse tests (k6)

Two k6 scripts against the gateway + orchestrator (plan.md §14), run through
`loadtest/run.sh`, which starts both services locally with
`WEATHER_MODE=fixtures` and every LLM/Bhashini key exported empty — so
neither script ever makes a paid API call. `/ask` always answers from the
i18n template in this mode.

## What each script does

- **`spike.js`** — a synthetic traffic spike: `ramping-arrival-rate` from 0
  to 150 rps over 30 s, holds 150 rps for 60 s, ramps back to 0 over 15 s.
  Each iteration picks, weighted 60/25/15, one of: `GET /ask` (8 English
  query templates × 3 cities × 5 `lang` values — non-English `lang` keeps the
  query text English since there's no Bhashini in this mode, so it exercises
  template rendering per language, not real translation), `GET /facts`, or
  `GET /warnings`. Every request carries a distinct `X-Forwarded-For` per
  VU/iteration so the per-client rate limiter (disabled here via
  `RATE_LIMIT_PER_MINUTE=0`, but harmless either way) never collapses the
  spike. Thresholds: `p(95) < 2000ms`, error rate `< 1%`.
- **`abuse.js`** — run with `RATE_LIMIT_PER_MINUTE=30`, through the gateway
  so the whole `X-Forwarded-For` chain (`services/gateway/main.py`
  `_forward_headers` → `services/orchestrator/limits.py`) is proven end to
  end, not just the orchestrator in isolation:
  1. one client, 40 sequential `/ask` calls in under a minute — expects the
     first 30 to return 200 and the remaining 10 to return 429 with
     `Retry-After: 60`.
  2. a second, distinct client (`X-Forwarded-For: 203.0.113.9`) making 25
     calls concurrently with scenario 1 — comfortably under its own
     30/minute budget — expects all 200s, proving the first client's usage
     doesn't touch the second client's budget.
  3. one `POST /asr` with a ~3 MB JSON body (over the 2 MiB
     `MAX_BODY_BYTES` default) — expects 413, rejected by the body-size
     middleware before it would ever reach Bhashini.

## Running

```
bash loadtest/run.sh spike
bash loadtest/run.sh abuse
```

Each run: checks ports 8000/8001 are free, starts the orchestrator and
gateway in the background (logs under `loadtest/results/*.log`, gitignored),
waits for `/livez` (or `/health` if `/livez` 404s — see note below), prints
`orchestrator /health` and aborts before running k6 if it shows any LLM
provider configured or Bhashini configured, runs the k6 script via the
`grafana/k6` Docker image against `http://localhost:8000`, then stops both
servers on exit (including on error, via a `trap`).

The k6 JSON summary is written to
`loadtest/results/<name>-<timestamp>.json` and copied to the canonical,
committed `loadtest/results/spike.json` / `loadtest/results/abuse.json` (one
file each — re-runs overwrite the canonical copy; the timestamped file stays
local/gitignored).

**Note on `/livez`:** at the time this was written, a parallel workstream was
adding `GET /livez` (no I/O) and `GET /metrics` (Prometheus) to both
services in its own worktree — not yet present in this checkout. `run.sh`
tries `/livez` first and falls back to `/health` on a 404. This run used
**`/health`** for both services (the fallback path) — see
`loadtest/results/*.log` if re-running after that work has landed.

**Gotcha found and fixed while building this:** `config.py`'s `OLLAMA_MODEL`
is read as `os.getenv("OLLAMA_MODEL") or "llama3.2:3b"` — an `or default`
pattern, not the `if config.KEY:` falsy-gate that `GEMINI_API_KEY` and
`GROQ_API_KEY` use — so exporting `OLLAMA_MODEL=` empty does **not** drop
Ollama from the provider chain the way it does for Gemini/Groq; it silently
falls back to the default model name and Ollama stays configured. On the
machine this was built on, a real Ollama server happens to be listening on
`:11434`, so the first version of this script made every single `/ask` call
attempt real local LLM inference and block on `OLLAMA_TIMEOUT` — p95
latencies over 30s, nothing like a "template-only, zero LLM calls" run.
Fixed in `run.sh` by pointing `OLLAMA_BASE` at a port nothing listens on
(`http://127.0.0.1:1`, so the connection fails in milliseconds) and setting
`OLLAMA_TIMEOUT=1` as a second line of defense, plus an explicit abort in
`run.sh` if `orchestrator /health`'s `llm.ollama.reachable` is ever `true`.
The results below are from the corrected run.

## Results — this run

Machine: this laptop (Docker Engine, no external network), **template
narration mode** (`WEATHER_MODE=fixtures`, no Gemini/Groq/Ollama/Bhashini
keys) — no LLM calls in either run. This is the *floor* the LLM narration
path sits on top of: real Gemini/Groq/Bhashini calls add their own latency
and would need a separate run with keys present (and a much lower rps
target, given free-tier rate limits) to characterize.

### Spike (`loadtest/spike.js`)

| Metric | Value |
|---|---|
| Total requests | 12,375 over 1m45s |
| Achieved req/s (whole run, incl. ramp up/down) | 117.8 req/s |
| p50 (med) | 4.30 ms |
| p90 | 9.89 ms |
| p95 | 14.88 ms |
| p99 | not collected (k6 default trend stats stop at p95 — rerun with `--summary-trend-stats` for p99) |
| max | 85.30 ms |
| Error rate (`http_req_failed`) | 0.00% (0 / 12,375) |
| Checks passed | 100.00% (19,721 / 19,721) |
| Thresholds | `p(95)<2000` ✓ / `rate<0.01` ✓ (both passed — k6 exited 0) |

### Abuse (`loadtest/abuse.js`)

| Metric | Value |
|---|---|
| Rate-limited client: 200s | 30 / 30 expected |
| Rate-limited client: 429s | 10 / 10 expected |
| 429s with correct `Retry-After: 60` | 10 / 10 |
| Independent client (`X-Forwarded-For: 203.0.113.9`, 25 calls): 200s | 25 / 25 |
| Independent client: non-200s | 0 |
| Oversized `/asr` body (~3 MB): 413s | 1 / 1 |
| Checks passed | 100.00% (66 / 66) |
| All thresholds | passed — k6 exited 0 |

Raw k6 summaries: `loadtest/results/spike.json`, `loadtest/results/abuse.json`.

## Seeing this in Grafana

```
docker compose --profile monitoring up -d
```

then open the **"WeatherGPT — latency & grounding"** dashboard while a
`run.sh` run is in progress (point `BASE_URL` at the compose-networked
gateway instead of `localhost` if running k6 against the compose stack
rather than the bare `uvicorn` processes `run.sh` starts).
