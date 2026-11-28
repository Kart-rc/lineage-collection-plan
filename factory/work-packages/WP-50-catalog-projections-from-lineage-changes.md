# WP-50: Catalog projections from lineage.changes

Wave 5 · family platform · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** XC-4  
**Depends on:** WP-14, WP-27

## Scope

Project confirmed and verified element edges to Snowflake Horizon and Unity Catalog (slice 2), via OpenLineage.

## Inputs

- lineage.changes

## Outputs

- planned:projections/

## Must hold

- Projections are copies; the graph of record stays authoritative

## Done when

- Round trip: 0 confirmed or verified element edges lost on the fixture
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `factory/specs/changes/interfaces/lineage-changes.schema.json`

## Requirements

- **XC-4**: The system shall accept and emit OpenLineage events, including the column lineage facet, without loss of dependency class and subtype. Scenarios: S-XC-04.
