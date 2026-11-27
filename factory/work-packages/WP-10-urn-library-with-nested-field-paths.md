# WP-10: URN library with nested field paths

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-1  
**Depends on:** WP-00

## Scope

Parse, format and normalize every URN kind in D4 plus flag:// and otel:// (D29, D30), with nested and repeated field paths.

## Inputs

- fixtures/otel-demo-3.1.0/golden-graph.json
- fixtures/otel-demo-3.1.0/aliases.json

## Outputs

- planned:core/urn/

## Must hold

- format(parse(x)) == x for every canonical URN
- Quoted identifiers normalize one way (accounting."order" and accounting.order resolve to the same node)

## Done when

- Property test: 10,000 generated URNs round-trip with 0 failures
- 100% of the URNs in golden-graph.json and golden-dbt.json parse
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/golden-graph.json`

## Requirements

- **BL-1**: The system shall represent every field of every tier 1 asset in the slice as a node with the URN `<dataset URN>#<field path>`, using a dotted path for nested fields and `[]` for array items. Scenarios: S-BL-01, S-BL-03, S-BL-09.
