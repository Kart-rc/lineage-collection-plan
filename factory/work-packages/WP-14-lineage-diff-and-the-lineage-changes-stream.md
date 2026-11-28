# WP-14: Lineage diff and the lineage.changes stream

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IN-6  
**Depends on:** WP-13

## Scope

Diff between two times or commits with causes; one lineage.changes event per material change.

## Inputs

- factory/specs/changes/interfaces/lineage-changes.schema.json
- factory/specs/query-api/interfaces/openapi.yaml

## Outputs

- planned:core/diff/

## Must hold

- Redelivered evidence produces no new change event

## Done when

- Diffs for C3, C4, C5 and C7 equal the hand-written expected diffs exactly
- 100% of emitted events validate against lineage-changes.schema.json
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **IN-6**: The system shall produce a lineage diff between any two times or commits: elements and edges added, removed and changed, with the evidence that caused each change. Scenarios: S-IN-07, S-IN-12, S-IN-13.
