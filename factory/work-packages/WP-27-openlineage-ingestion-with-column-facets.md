# WP-27: OpenLineage ingestion with column facets

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** XC-4  
**Depends on:** WP-11

## Scope

Accept and emit OpenLineage run events with the column lineage facet, from Feast and dbt.

## Inputs

- OpenLineage events from the complement's Feast and from dbt-ol

## Outputs

- planned:collectors/openlineage/

## Must hold

- Class and subtype survive the round trip

## Done when

- Round trip in and out: 100% of fixture events equal after normalization, class and subtype included
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `planned:fixtures/openlineage/ (WP-27)`

## Requirements

- **XC-4**: The system shall accept and emit OpenLineage events, including the column lineage facet, without loss of dependency class and subtype. Scenarios: S-XC-04.
