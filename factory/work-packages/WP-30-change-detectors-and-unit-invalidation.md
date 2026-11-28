# WP-30: Change detectors and unit invalidation

Wave 3 · family impact · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IN-1, IN-3, IN-10  
**Depends on:** WP-12, WP-20, WP-21

## Scope

Re-extract only the units whose content, input schema or extractor version changed; on a schema change, every reader.

## Inputs

- git history of the demo and the dbt model

## Outputs

- planned:core/invalidate/

## Must hold

- A unit whose hashes are unchanged is never re-extracted

## Done when

- C1 replay: extractor calls equal exactly the units whose hashes changed
- A column added to accounting.shipping re-extracts stg_shipping and reaches it with 1 new edge
- Merge to visible edge in 15 minutes or less at p95 in the twin
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/dbt/models/staging/stg_shipping.sql`
- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **IN-1**: When a commit lands on a default branch, the system shall re-extract only the units whose content hash, input schema hash or extractor version changed. Scenarios: S-IN-01.
- **IN-3**: When a schema version is registered or a tier 1 table's DDL changes, the system shall publish a schema-change event and re-extract every unit that reads the changed dataset. Scenarios: S-IN-04.
- **IN-10**: The system shall make an edge visible within 15 minutes of the merge or run that produced it, at the 95th percentile. Scenarios: S-IN-11.
