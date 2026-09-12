#!/usr/bin/env bash
# Stable public URL for the prototype (plan.md §14, Niranjan's host-pin task).
# Requires: `ngrok config add-authtoken <token>` once per machine (see
# https://dashboard.ngrok.com/get-started/your-authtoken), and the free
# static domain claimed at https://dashboard.ngrok.com/domains.
#
# Fixed hostname: https://plaza-syrup-appetizer.ngrok-free.dev
# Points at ask_service on :8001 — start that first (see prototype/README.md).
set -euo pipefail
exec ngrok http --url=plaza-syrup-appetizer.ngrok-free.dev 8001
