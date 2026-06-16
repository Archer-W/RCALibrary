#!/usr/bin/env bash
# Launch the framework with THIS repo's use-case extensions layered on top.
set -euo pipefail
cd "$(dirname "$0")"

export PYTHONPATH="framework/backend:.${PYTHONPATH:+:$PYTHONPATH}"
export RCA_TEMPLATES_DIR="./templates"
export RCA_SAMPLES_DIR="./data/samples"
export RCA_FRONTEND_DIR="./framework/frontend"
export RCA_FRONTEND_EXT_DIR="./frontend-ext"
export RCA_PLUGINS="usecase.plugins"
export RCA_DATASOURCE="${RCA_DATASOURCE:-sample}"   # set to "snowflake" once implemented

# Watch *.yaml too so template edits trigger a reload (default only watches *.py).
exec uvicorn rcalibrary.main:app --reload \
  --reload-include "*.py" --reload-include "*.yaml" \
  --host "${RCA_HOST:-0.0.0.0}" --port "${RCA_PORT:-8000}"
