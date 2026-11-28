# WP-25: Feature repository and training config extractor

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-3  
**Depends on:** WP-11, WP-22

## Scope

Feast feature views to source columns, entity keys and aggregations; MLflow model signature to features.

## Inputs

- satyazm/Fraud-Detection-using-MLOps at d1692f9

## Outputs

- planned:extractors/features/

## Must hold

- Feature edges carry the aggregation window when there is one

## Done when

- Precision and recall >= 0.90 on the complement's golden feature and model edges
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `planned:fixtures/complement/golden.json (WP-01)`

## Requirements

- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
