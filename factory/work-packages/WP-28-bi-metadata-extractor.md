# WP-28: BI metadata extractor

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-3  
**Depends on:** WP-11, WP-18

## Scope

Fields a dashboard uses. The reference slice has no BI tool; the dbt exposure stands in until slice 2 names one.

## Inputs

- fixtures/otel-demo-3.1.0/dbt/models/marts/exposures.yml

## Outputs

- planned:extractors/bi/

## Must hold

- A dashboard whose fields cannot be read gets a dataset-level opaque edge

## Done when

- The exposure finance_orders_dashboard is linked to fct_order_value (1 of 1)
- Blocked for field level until slice 2 names a BI tool; then precision and recall >= 0.90 on recorded API fixtures
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/dbt/models/marts/exposures.yml`

## Requirements

- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
