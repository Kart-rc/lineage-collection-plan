# WP-13: Bitemporal graph writer and as-of reads, on Neptune over Bolt with Neo4j standing in locally

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-7, IN-4, IN-5, IN-10, IR-2  
**Depends on:** WP-12

## Scope

Write each edge version as its own relationship with valid and recorded times, condition and state; read as of any valid or recorded time.

## Inputs

- factory/specs/changes/interfaces/lineage-changes.schema.json

## Outputs

- planned:core/graph/

## Must hold

- No edge version is ever updated in place
- Only the openCypher subset Neptune supports

## Done when

- Bitemporal property tests: 0 failures on Neo4j and on a stage Neptune, and 100% agreement between the two on the as-of suite
- Rebuild from the raw archive gives the live graph's hash, 3 of 3 times
- Merge or run to visible edge in 15 minutes or less at p95 in the twin
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **BL-7**: When the graph is rebuilt from the evidence lake, the system shall produce the same graph hash as the live graph at the same as-of time. Scenarios: S-BL-07.
- **IN-4**: The system shall write every edge version with valid-from, valid-to and recorded-at times, and shall never overwrite an edge in place. Scenarios: S-IN-05.
- **IN-5**: The system shall return the graph as of any valid time, and the graph as it was recorded at any transaction time. Scenarios: S-IN-05, S-IN-06.
- **IN-10**: The system shall make an edge visible within 15 minutes of the merge or run that produced it, at the 95th percentile. Scenarios: S-IN-11.
- **IR-2**: The system shall walk upstream over the incident window: every edge valid at any time between the last passing check and the failure, including edges that closed in between. It shall not use the current graph. Scenarios: S-IR-01, S-IR-02.
