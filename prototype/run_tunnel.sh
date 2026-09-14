#!/usr/bin/env bash
# Stable public URL for the prototype (plan.md §14, Niranjan's host-pin task).
# Requires: `ngrok config add-authtoken <token>` once per machine (see
# https://dashboard.ngrok.com/get-started/your-authtoken), and the free
# static domain claimed at https://dashboard.ngrok.com/domains.
#
# Fixed hostname: https://plaza-syrup-appetizer.ngrok-free.dev
# Points at the gateway on :8000, which proxies to the orchestrator on :8001 —
# start both first (see prototype/README.md). To bypass the gateway, use 8001.
set -euo pipefail
exec ngrok http --url=plaza-syrup-appetizer.ngrok-free.dev "${TUNNEL_PORT:-8000}"
