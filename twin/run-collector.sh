#!/bin/sh
set -eu
LINEAGE_PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$LINEAGE_PROJECT_ROOT"
LINEAGE_CAPTURE_DIR=${LINEAGE_CAPTURE_DIR:-$LINEAGE_PROJECT_ROOT/twin/.state/capture}
LINEAGE_CHANGES_FILE=${LINEAGE_CHANGES_FILE:-$LINEAGE_PROJECT_ROOT/twin/.state/changes.jsonl}
LINEAGE_COLLECTOR_STATE_DIR=${LINEAGE_COLLECTOR_STATE_DIR:-$LINEAGE_PROJECT_ROOT/twin/.state/collector}
LINEAGE_COLLECTOR_UID=$(id -u)
LINEAGE_COLLECTOR_GID=$(id -g)
export LINEAGE_PROJECT_ROOT LINEAGE_CAPTURE_DIR LINEAGE_CHANGES_FILE
export LINEAGE_COLLECTOR_STATE_DIR LINEAGE_COLLECTOR_UID LINEAGE_COLLECTOR_GID
if [ ! -f twin/.state/compose.yaml ] || [ ! -d "$LINEAGE_CAPTURE_DIR" ]; then
    echo 'Start the platform and configure an exported-telemetry directory first.' >&2
    exit 1
fi
if [ ! -f "$LINEAGE_CAPTURE_DIR/traces.jsonl" ] && [ ! -f "$LINEAGE_CAPTURE_DIR/logs.jsonl" ]; then
    echo 'No exported traces.jsonl or logs.jsonl is available; summaries cannot replace raw telemetry.' >&2
    exit 1
fi
umask 077
mkdir -p "$LINEAGE_COLLECTOR_STATE_DIR"
if [ ! -e "$LINEAGE_CHANGES_FILE" ]; then
    mkdir -p "$(dirname -- "$LINEAGE_CHANGES_FILE")"
    : > "$LINEAGE_CHANGES_FILE"
fi
docker compose -p lineage-twin -f twin/.state/compose.yaml \
    -f twin/worker.compose.yaml -f twin/collector.compose.yaml \
    up -d --no-build --wait lineage-collector
