#!/bin/sh
set -eu
LINEAGE_PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export LINEAGE_PROJECT_ROOT
cd "$LINEAGE_PROJECT_ROOT"
"${LINEAGE_PYTHON:-python3}" twin/start.py platform "$@"
docker compose -p lineage-twin -f twin/.state/compose.yaml -f twin/worker.compose.yaml up -d --build --wait lineage-worker
