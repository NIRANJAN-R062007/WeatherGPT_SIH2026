#!/usr/bin/env bash
# Do Postgres and Redis keep their data across a restart? (plan.md Phase 7, B4)
#
# Run this ON the server that runs the containers, from the repo checkout:
#
#   deploy/persistence_check.sh                      # docker restart of the two data containers
#   MODE=recreate COMPOSE_FILE=docker-compose.yml deploy/persistence_check.sh
#                                                    # compose down + up -d: containers are destroyed
#                                                    # and rebuilt, so only named volumes survive
#
# It writes a marker into each store, restarts, and reads the marker back. The
# marker is a throwaway table (deploy_persistence_check) and one Redis key
# (weathergpt:deploy-check); both are removed at the end. Nothing else is
# touched, and `down` is never run with -v (that would delete the volumes).
# It also compares the row counts of weather_facts and schema_migrations before
# and after: they must not go down.
#
# Exit 0 only if every check passes. Container names default to docker-compose.yml's.
set -uo pipefail

DOCKER="${DOCKER:-docker}"
PG="${PG_CONTAINER:-weathergpt-postgres}"
REDIS="${REDIS_CONTAINER:-weathergpt-redis}"
PGUSER_NAME="${PGUSER_NAME:-weathergpt}"
PGDB_NAME="${PGDB_NAME:-weathergpt}"
MODE="${MODE:-restart}"
WAIT_SECONDS="${WAIT_SECONDS:-90}"
KEY="weathergpt:deploy-check"
TOKEN="b4-$(date +%s)-$RANDOM"
FAILED=0

say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
fail() { say "  FAIL  $*"; FAILED=1; }

psql_q() {  # one SQL statement, bare value out
  "$DOCKER" exec "$PG" psql -U "$PGUSER_NAME" -d "$PGDB_NAME" -v ON_ERROR_STOP=1 -tA -c "$1"
}
redis_q() { "$DOCKER" exec "$REDIS" redis-cli "$@"; }

cleanup() {
  psql_q "DROP TABLE IF EXISTS deploy_persistence_check" >/dev/null 2>&1 || true
  redis_q DEL "$KEY" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_ready() {
  local waited=0
  until psql_q "SELECT 1" >/dev/null 2>&1 && [ "$(redis_q PING 2>/dev/null)" = "PONG" ]; do
    waited=$((waited + 1))
    if [ "$waited" -ge "$WAIT_SECONDS" ]; then
      fail "Postgres and Redis not answering ${WAIT_SECONDS}s after the restart"
      return 1
    fi
    sleep 1
  done
}

count_or_minus1() {  # a table's row count, or -1 when the table does not exist yet
  psql_q "SELECT count(*) FROM $1" 2>/dev/null || echo -1
}

say "Persistence check (mode=$MODE, marker=$TOKEN)"

say; say "[before]"
if ! psql_q "CREATE TABLE IF NOT EXISTS deploy_persistence_check (token text PRIMARY KEY, written_at timestamptz DEFAULT now()); INSERT INTO deploy_persistence_check (token) VALUES ('$TOKEN')" >/dev/null; then
  fail "could not write the marker to Postgres (container '$PG' reachable? user/db right?)"
  exit 1
fi
pass "marker written to Postgres"
if [ "$(redis_q SET "$KEY" "$TOKEN" 2>/dev/null)" != "OK" ]; then
  fail "could not write the marker to Redis (container '$REDIS' reachable?)"
  exit 1
fi
pass "marker written to Redis (no expiry)"
FACTS_BEFORE="$(count_or_minus1 weather_facts)"
MIGR_BEFORE="$(count_or_minus1 schema_migrations)"
say "  info  weather_facts rows=$FACTS_BEFORE, schema_migrations rows=$MIGR_BEFORE (-1 = table not created yet)"

say; say "[restart]"
case "$MODE" in
  restart)
    "$DOCKER" restart "$PG" "$REDIS" >/dev/null || { fail "docker restart failed"; exit 1; }
    pass "restarted $PG and $REDIS" ;;
  recreate)
    if [ -z "${COMPOSE_FILE:-}" ]; then fail "MODE=recreate needs COMPOSE_FILE"; exit 1; fi
    "$DOCKER" compose -f "$COMPOSE_FILE" down || { fail "compose down failed"; exit 1; }
    "$DOCKER" compose -f "$COMPOSE_FILE" up -d || { fail "compose up failed"; exit 1; }
    pass "compose down (no -v) then up -d: containers recreated" ;;
  *) fail "MODE must be restart or recreate"; exit 1 ;;
esac
wait_ready || exit 1
pass "both answer again"

say; say "[after]"
if [ "$(psql_q "SELECT token FROM deploy_persistence_check WHERE token='$TOKEN'" 2>/dev/null)" = "$TOKEN" ]; then
  pass "Postgres still has the marker"
else
  fail "Postgres lost the marker: the data directory is not on a persistent volume"
fi
if [ "$(redis_q GET "$KEY" 2>/dev/null)" = "$TOKEN" ]; then
  pass "Redis still has the marker"
else
  fail "Redis lost the marker: no persistent volume, or no save on shutdown (check redis.conf save/appendonly)"
fi
FACTS_AFTER="$(count_or_minus1 weather_facts)"
MIGR_AFTER="$(count_or_minus1 schema_migrations)"
if [ "$FACTS_BEFORE" -ge 0 ]; then
  if [ "$FACTS_AFTER" -ge "$FACTS_BEFORE" ]; then
    pass "weather_facts rows $FACTS_BEFORE -> $FACTS_AFTER (did not shrink)"
  else
    fail "weather_facts rows $FACTS_BEFORE -> $FACTS_AFTER: rows were lost"
  fi
fi
if [ "$MIGR_BEFORE" -ge 0 ]; then
  if [ "$MIGR_AFTER" -ge "$MIGR_BEFORE" ]; then
    pass "schema_migrations rows $MIGR_BEFORE -> $MIGR_AFTER (did not shrink)"
  else
    fail "schema_migrations rows $MIGR_BEFORE -> $MIGR_AFTER: the schema was lost"
  fi
fi

say
if [ "$FAILED" -eq 0 ]; then say "RESULT: OK"; else say "RESULT: FAILED"; fi
exit "$FAILED"
