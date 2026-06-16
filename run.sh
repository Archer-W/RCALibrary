#!/usr/bin/env bash
# Launch the RCALibrary backend (serves the API + the static frontend).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="backend:${PYTHONPATH:-}"
HOST="${RCA_HOST:-0.0.0.0}"
PORT="${RCA_PORT:-8000}"
# --reload watches *.py by default; also watch *.yaml so template edits (which are
# read at startup by the template registry) trigger a reload.
exec uvicorn rcalibrary.main:app --reload \
  --reload-include "*.py" --reload-include "*.yaml" \
  --host "$HOST" --port "$PORT"
