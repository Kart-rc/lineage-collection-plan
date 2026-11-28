#!/usr/bin/env bash
# A thin argv adapter. Values are never evaluated as shell source.
set -u
args=(scan --stage "${LINEAGE_STAGE:-merged}" --commit "${LINEAGE_COMMIT:-}"
      --config "${LINEAGE_CONFIG:-.lineage.yaml}" --out "${LINEAGE_OUT:-.lineage-out}"
      --state-dir "${LINEAGE_STATE_DIR:-.lineage-state}" --transport "${LINEAGE_TRANSPORT:-local}")
if [[ -n "${LINEAGE_BASE:-}" ]]; then args+=(--base "$LINEAGE_BASE"); fi
if [[ -n "${LINEAGE_PR:-}" ]]; then args+=(--pr "$LINEAGE_PR"); fi
if [[ -n "${LINEAGE_SNAPSHOT_ROOT:-}" ]]; then args+=(--snapshot-root "$LINEAGE_SNAPSHOT_ROOT"); fi
if [[ -n "${LINEAGE_BROKER:-}" ]]; then args+=(--broker "$LINEAGE_BROKER"); fi
if [[ -n "${LINEAGE_SNAPSHOT_TOPIC:-}" ]]; then args+=(--snapshot-topic "$LINEAGE_SNAPSHOT_TOPIC"); fi
if [[ "${LINEAGE_STUB:-false}" == true ]]; then args+=(--stub); fi
if ! lineage-ci "${args[@]}"; then
  printf '%s\n' 'lineage check unavailable: CLI could not run' >&2
fi
exit 0
