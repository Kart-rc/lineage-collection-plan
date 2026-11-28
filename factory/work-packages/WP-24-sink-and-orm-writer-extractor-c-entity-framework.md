# WP-24: Sink and ORM writer extractor, C# Entity Framework first

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-2, BL-3  
**Depends on:** WP-10, WP-11, WP-18

## Scope

Map ORM entity properties to table columns and the consumed message fields that fill them (accounting).

## Inputs

- demo src/accounting at 3.1.0

## Outputs

- planned:extractors/orm/

## Must hold

- Column names follow the ORM's naming convention (snake_case in accounting)

## Done when

- Precision and recall >= 0.95 on the 17 golden accounting edges
- The written columns agree 17 of 17 with the columns seen in accounting's database spans
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/golden-graph.json`
- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`

## Requirements

- **BL-2**: When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. Scenarios: S-BL-01, S-BL-02.
- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
