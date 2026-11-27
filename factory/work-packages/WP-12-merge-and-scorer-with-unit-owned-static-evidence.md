# WP-12: Merge and scorer with unit-owned static evidence; conditional edges with a latent state

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-5, IN-2, IN-8, IN-9, IA-7, XC-2  
**Depends on:** WP-11

## Scope

One row per edge per source; noisy-OR confidence and states from parameters.yaml; unit replacement; mass-close hold; dormancy; disputes; conditions and latent state (D30).

## Inputs

- factory/parameters.yaml

## Outputs

- planned:core/merge/

## Must hold

- Static evidence is replaced per unit as one atomic set; runtime evidence only adds
- An indirect dependency is stored once per (source element, subtype, target dataset)

## Done when

- Property tests: noisy-OR monotonic, merge idempotent and order-independent, 0 failures over 1,000 generated event sequences
- Mass-close hold triggers at more than 20% of an extractor's edges and at least 10 edges, and not below
- Change C7: 5 latent edges become active on the flag event and latent again when it is reverted
- BL-5 size check on fct_order_value: exactly 5 indirect edges stored, not 35
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/dbt/golden-dbt.json`
- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **BL-5**: The system shall store an indirect dependency once, from the source element to the target dataset, and shall not fan it out to every target column. Scenarios: S-BL-05.
- **IN-2**: When a unit is re-extracted, the system shall replace that unit's prior static evidence as one atomic set, closing any element edge the new extraction no longer supports. If one extraction would close more than a set share of an extractor's edges, then the system shall hold the write and raise an alert. Scenarios: S-IN-02, S-IN-03, S-IN-12.
- **IN-8**: When runtime evidence for an edge has not been seen for 30 days, the system shall mark the edge dormant and keep it. Scenarios: S-IN-09.
- **IN-9**: When the same evidence is delivered more than once, the system shall leave the graph unchanged. Scenarios: S-IN-10.
- **IA-7**: The report shall offer a "this is wrong" action per row, and a disputed edge shall drop to candidate until reviewed. Scenarios: S-IA-09.
- **XC-2**: Every edge shall be traceable to its evidence records, and every evidence record to the raw input and the tool version that produced it. Scenarios: S-XC-02.
