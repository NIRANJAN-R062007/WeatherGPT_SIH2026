#!/usr/bin/env bash
# Run a k6 load test (spike or abuse) against a locally started gateway +
# orchestrator, with WEATHER_MODE=fixtures and no LLM/Bhashini keys so the
# run makes zero paid API calls. See loadtest/README.md.
#
# Usage: loadtest/run.sh <spike|abuse>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TEST_NAME="${1:-}"
if [[ "$TEST_NAME" != "spike" && "$TEST_NAME" != "abuse" ]]; then
  echo "usage: $0 <spike|abuse>" >&2
  exit 1
fi

VENV="${VENV:-services/orchestrator/.venv/bin}"
if [[ ! -x "$ROOT/$VENV/uvicorn" ]]; then
  echo "error: uvicorn not found at $ROOT/$VENV — is the orchestrator venv set up?" >&2
  exit 1
fi

RESULTS_DIR="$ROOT/loadtest/results"
mkdir -p "$RESULTS_DIR"

for port in 8000 8001; do
  if ss -ltn "( sport = :$port )" | grep -q ":$port"; then
    echo "error: port $port is already in use — stop whatever is listening on it first" >&2
    exit 1
  fi
done

# Empty on purpose for GEMINI/GROQ/Bhashini: config.py gates those providers
# with `if config.GEMINI_API_KEY:` / `if config.GROQ_API_KEY:` (falsy checks),
# so an empty string correctly disables them.
#
# OLLAMA_MODEL is different and NOT safe to just blank out: config.py reads
# it as `os.getenv("OLLAMA_MODEL") or "llama3.2:3b"` — an `or default`
# pattern, not a falsy-gate — so an empty OLLAMA_MODEL silently falls back to
# the default model name and Ollama stays in the provider chain. Confirmed on
# this machine: a real Ollama server happens to be listening on :11434, so
# leaving this unguarded made every single /ask call attempt real local LLM
# inference and blocked on OLLAMA_TIMEOUT (30s default) — that's what turned
# a "template-only, no LLM calls" run into one with p95 latencies over 30s.
# Point OLLAMA_BASE at a port nothing listens on so the connection fails
# instantly (ECONNREFUSED) instead of timing out or, worse, actually running
# inference, and belt-and-suspenders it with a short OLLAMA_TIMEOUT too.
export WEATHER_MODE=fixtures
export GEMINI_API_KEY=
export GROQ_API_KEY=
export OLLAMA_MODEL=
export OLLAMA_BASE=http://127.0.0.1:1
export OLLAMA_TIMEOUT=1
export BHASHINI_ULCA_API_KEY=
export BHASHINI_INFERENCE_KEY=
export RAG_ENABLED=0

if [[ "$TEST_NAME" == "spike" ]]; then
  export RATE_LIMIT_PER_MINUTE=0
else
  export RATE_LIMIT_PER_MINUTE=30
fi

ORCH_LOG="$RESULTS_DIR/orchestrator.log"
GW_LOG="$RESULTS_DIR/gateway.log"
: > "$ORCH_LOG"
: > "$GW_LOG"

ORCH_PID=""
GW_PID=""

cleanup() {
  echo "stopping servers..."
  [[ -n "$GW_PID" ]] && kill "$GW_PID" 2>/dev/null || true
  [[ -n "$ORCH_PID" ]] && kill "$ORCH_PID" 2>/dev/null || true
  wait "$GW_PID" 2>/dev/null || true
  wait "$ORCH_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "starting orchestrator on :8001..."
# `exec` so $! is uvicorn itself, not a wrapper subshell — otherwise the EXIT
# trap kills the wrapper and leaves the server holding the port.
#
# --no-proxy-headers on both servers: uvicorn's default is to trust
# X-Forwarded-For from 127.0.0.1 and rewrite `request.client` from it. k6
# connects from 127.0.0.1, so without this the gateway would "append" whatever
# abuse.js put in the header instead of the real peer, and the limiter
# (TRUSTED_PROXY_HOPS=1, the gateway being the one proxy here) would key on
# the spoof. The containers don't hit this — their peers are never 127.0.0.1.
(cd "$ROOT/services/orchestrator" && exec "$ROOT/$VENV/uvicorn" main:app --no-proxy-headers --port 8001 >> "$ORCH_LOG" 2>&1) &
ORCH_PID=$!

echo "starting gateway on :8000..."
export ORCHESTRATOR_URL=http://localhost:8001
export DATABASE_URL=postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt
export REDIS_URL=redis://localhost:6379/0
(cd "$ROOT/services/gateway" && exec "$ROOT/$VENV/uvicorn" main:app --no-proxy-headers --port 8000 >> "$GW_LOG" 2>&1) &
GW_PID=$!

# Prefer /livez (no I/O, added alongside /metrics by a parallel workstream —
# see loadtest/README.md); fall back to /health if it 404s, i.e. that work
# hasn't landed in this checkout yet.
wait_for_ready() {
  local base="$1" name="$2"
  local path="/livez"
  for _ in $(seq 1 60); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$base$path" || true)"
    if [[ "$code" == "200" ]]; then
      echo "$name ready on $path"
      return 0
    fi
    if [[ "$code" == "404" && "$path" == "/livez" ]]; then
      echo "$name: /livez not found (404) — falling back to /health"
      path="/health"
      continue
    fi
    sleep 1
  done
  echo "error: $name never became ready on $path" >&2
  return 1
}

wait_for_ready "http://localhost:8001" "orchestrator"
wait_for_ready "http://localhost:8000" "gateway"

echo "orchestrator /health:"
HEALTH_JSON="$(curl -s http://localhost:8001/health)"
echo "$HEALTH_JSON"

# Guard rail: abort rather than run load against a server that might make
# paid calls.
if echo "$HEALTH_JSON" | grep -qiE '"providers":\s*\[[^]]*"(gemini|groq)"'; then
  echo "error: an LLM provider is configured — aborting to avoid paid calls under load" >&2
  exit 1
fi
if echo "$HEALTH_JSON" | grep -qi '"bhashini": *"configured"'; then
  echo "error: bhashini is configured — aborting to avoid paid calls under load" >&2
  exit 1
fi

# Ollama can't actually be removed from the provider chain this way: config.py
# resolves OLLAMA_MODEL as `os.getenv("OLLAMA_MODEL") or "llama3.2:3b"`, so it
# always ends up truthy and `ollama` always appears in `providers` regardless
# of what OLLAMA_MODEL is set to. What matters is that OLLAMA_BASE (set above
# to a port nothing listens on) makes every attempt fail in milliseconds
# instead of running real inference or waiting out a 30s timeout — confirm
# that here rather than trying to assert it's absent from the chain.
if echo "$HEALTH_JSON" | grep -qi '"reachable": *true'; then
  echo "error: ollama.reachable is true — a real Ollama server answered; aborting to avoid real LLM inference under load" >&2
  exit 1
fi

K6_IMAGE="grafana/k6:0.54.0"
TIMESTAMP="$(date +%Y%m%d-%H%M)"
OUT_FILE="/lt/results/${TEST_NAME}-${TIMESTAMP}.json"

echo "running k6 $TEST_NAME..."
# --user matches the host UID/GID so the k6 image (which otherwise runs as
# its own non-root user) can write into loadtest/results, which is owned by
# whoever is running this script.
docker run --rm -i --network host \
  --user "$(id -u):$(id -g)" \
  -v "$ROOT/loadtest:/lt" \
  "$K6_IMAGE" run \
  --summary-export="$OUT_FILE" \
  -e BASE_URL=http://localhost:8000 \
  "/lt/${TEST_NAME}.js"

# One canonical, committed file per test — overwritten on re-run rather than
# piling up (the timestamped file above stays local, gitignored).
cp "$RESULTS_DIR/${TEST_NAME}-${TIMESTAMP}.json" "$RESULTS_DIR/${TEST_NAME}.json"
echo "summary written to loadtest/results/${TEST_NAME}.json"
