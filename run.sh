#!/usr/bin/env bash
# Launch the RCALibrary backend (serves the API + the static frontend).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="backend:${PYTHONPATH:-}"
HOST="${RCA_HOST:-0.0.0.0}"
PORT="${RCA_PORT:-8000}"
exec uvicorn rcalibrary.main:app --reload --host "$HOST" --port "$PORT"
