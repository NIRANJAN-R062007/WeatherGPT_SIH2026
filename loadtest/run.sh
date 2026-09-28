#!/usr/bin/env bash
# Run a k6 load test against a locally started gateway + orchestrator, with
# WEATHER_MODE=fixtures. spike/abuse run with no LLM/Bhashini keys so they
# make zero paid API calls; llm keeps the keys from .env on purpose and needs
# LLM_LOADTEST_CONFIRM=1. See loadtest/README.md.
#
# Usage: loadtest/run.sh <spike|abuse|llm>
#   ORCH_PORT / GW_PORT      override 8001 / 8000
#   RATE_PER_MIN / DURATION  llm only: request rate and length (default 10, 6m)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TEST_NAME="${1:-}"
if [[ "$TEST_NAME" != "spike" && "$TEST_NAME" != "abuse" && "$TEST_NAME" != "llm" ]]; then
  echo "usage: $0 <spike|abuse|llm>" >&2
  exit 1
fi

if [[ "$TEST_NAME" == "llm" && "${LLM_LOADTEST_CONFIRM:-}" != "1" ]]; then
  echo "error: the llm test makes real Gemini/Groq/Bhashini calls (~RATE_PER_MIN × DURATION of them)." >&2
  echo "       Re-run with LLM_LOADTEST_CONFIRM=1 to accept that." >&2
  exit 1
fi

ORCH_PORT="${ORCH_PORT:-8001}"
GW_PORT="${GW_PORT:-8000}"

# Default to the per-service venv; fall back to the repo-root one.
if [[ -z "${VENV:-}" ]]; then
  VENV="services/orchestrator/.venv/bin"
  [[ -x "$ROOT/$VENV/uvicorn" ]] || VENV=".venv/bin"
fi
if [[ ! -x "$ROOT/$VENV/uvicorn" ]]; then
  echo "error: uvicorn not found at $ROOT/$VENV — is the orchestrator venv set up?" >&2
  exit 1
fi

RESULTS_DIR="$ROOT/loadtest/results"
mkdir -p "$RESULTS_DIR"

port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$1 )" | grep -q ":$1"
  else  # macOS has no ss
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  fi
}

for port in "$GW_PORT" "$ORCH_PORT"; do
  if port_in_use "$port"; then
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
#
# llm keeps GEMINI/GROQ/Bhashini from .env (config.py load_dotenv) and RAG as
# configured (it's local BM25, no API call), but still pins weather to
# fixtures (the narration path is what's measured, not Google Weather) and
# still points Ollama at a dead port, so the chain is gemini -> groq ->
# template, as on the deployed targets.
export WEATHER_MODE=fixtures
export OLLAMA_MODEL=
export OLLAMA_BASE=http://127.0.0.1:1
export OLLAMA_TIMEOUT=1
if [[ "$TEST_NAME" != "llm" ]]; then
  export GEMINI_API_KEY=
  export GROQ_API_KEY=
  export BHASHINI_ULCA_API_KEY=
  export BHASHINI_INFERENCE_KEY=
  export RAG_ENABLED=0
fi

if [[ "$TEST_NAME" == "abuse" ]]; then
  export RATE_LIMIT_PER_MINUTE=30
else
  export RATE_LIMIT_PER_MINUTE=0
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

echo "starting orchestrator on :$ORCH_PORT..."
# `exec` so $! is uvicorn itself, not a wrapper subshell — otherwise the EXIT
# trap kills the wrapper and leaves the server holding the port.
#
# --no-proxy-headers on both servers: uvicorn's default is to trust
# X-Forwarded-For from 127.0.0.1 and rewrite `request.client` from it. k6
# connects from 127.0.0.1, so without this the gateway would "append" whatever
# abuse.js put in the header instead of the real peer, and the limiter
# (TRUSTED_PROXY_HOPS=1, the gateway being the one proxy here) would key on
# the spoof. The containers don't hit this — their peers are never 127.0.0.1.
(cd "$ROOT/services/orchestrator" && exec "$ROOT/$VENV/uvicorn" main:app --no-proxy-headers --port "$ORCH_PORT" >> "$ORCH_LOG" 2>&1) &
ORCH_PID=$!

echo "starting gateway on :$GW_PORT..."
export ORCHESTRATOR_URL=http://localhost:$ORCH_PORT
export DATABASE_URL=postgresql://weathergpt:weathergpt_dev@localhost:5432/weathergpt
export REDIS_URL=redis://localhost:6379/0
(cd "$ROOT/services/gateway" && exec "$ROOT/$VENV/uvicorn" main:app --no-proxy-headers --port "$GW_PORT" >> "$GW_LOG" 2>&1) &
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

wait_for_ready "http://localhost:$ORCH_PORT" "orchestrator"
wait_for_ready "http://localhost:$GW_PORT" "gateway"

echo "orchestrator /health:"
HEALTH_JSON="$(curl -s "http://localhost:$ORCH_PORT/health")"
echo "$HEALTH_JSON"

if [[ "$TEST_NAME" == "llm" ]]; then
  # The inverse guard: an llm run with no cloud provider would just measure
  # the template again and look like a great LLM number.
  if ! echo "$HEALTH_JSON" | grep -qiE '"providers":\s*\[[^]]*"(gemini|groq)"'; then
    echo "error: no Gemini/Groq provider configured — the llm test would only measure the template" >&2
    exit 1
  fi
  if ! echo "$HEALTH_JSON" | grep -qi '"bhashini": *"configured"'; then
    echo "warning: Bhashini not configured — non-English answers will fall back to the template" >&2
  fi
# Guard rail: abort rather than run load against a server that might make
# paid calls.
elif echo "$HEALTH_JSON" | grep -qiE '"providers":\s*\[[^]]*"(gemini|groq)"'; then
  echo "error: an LLM provider is configured — aborting to avoid paid calls under load" >&2
  exit 1
elif echo "$HEALTH_JSON" | grep -qi '"bhashini": *"configured"'; then
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

# Docker Desktop (macOS) can't reach the host's localhost from a container
# over --network host; host.docker.internal is its route to the host.
if [[ "$(uname -s)" == "Darwin" ]]; then
  DOCKER_NET=()
  K6_BASE="http://host.docker.internal:$GW_PORT"
else
  DOCKER_NET=(--network host)
  K6_BASE="http://localhost:$GW_PORT"
fi

echo "running k6 $TEST_NAME..."
# --user matches the host UID/GID so the k6 image (which otherwise runs as
# its own non-root user) can write into loadtest/results, which is owned by
# whoever is running this script.
#
# A crossed threshold exits 99 but still writes the summary; keep it and
# report the status at the end instead of dropping the results.
K6_STATUS=0
docker run --rm -i ${DOCKER_NET[@]+"${DOCKER_NET[@]}"} \
  --user "$(id -u):$(id -g)" \
  -v "$ROOT/loadtest:/lt" \
  "$K6_IMAGE" run \
  --summary-export="$OUT_FILE" \
  -e BASE_URL="$K6_BASE" \
  -e RATE_PER_MIN="${RATE_PER_MIN:-10}" \
  -e DURATION="${DURATION:-6m}" \
  "/lt/${TEST_NAME}.js" || K6_STATUS=$?

# One canonical, committed file per test — overwritten on re-run rather than
# piling up (the timestamped file above stays local, gitignored).
cp "$RESULTS_DIR/${TEST_NAME}-${TIMESTAMP}.json" "$RESULTS_DIR/${TEST_NAME}.json"
echo "summary written to loadtest/results/${TEST_NAME}.json"
[[ "$K6_STATUS" == "0" ]] || echo "k6 exited $K6_STATUS (a threshold was crossed or the run failed)" >&2
exit "$K6_STATUS"
