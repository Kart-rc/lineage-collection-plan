# WP-22: Stream job extractor: PyFlink code and the declared feature registry first

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-3, BL-4  
**Depends on:** WP-11, WP-18

## Scope

Field edges for the complement's PyFlink job from its declared feature registry and code; opaque edges for what neither declares.

## Inputs

- satyazm/Fraud-Detection-using-MLOps at d1692f9

## Outputs

- planned:extractors/stream/

## Must hold

- A transform neither declared nor parsed is opaque, never guessed

## Done when

- Precision and recall >= 0.90 against the golden edges a person writes from src/fraud_detection/features/registry.py in WP-01
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `planned:fixtures/complement/golden.json (WP-01)`

## Requirements

- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
- **BL-4**: If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. Scenarios: S-BL-04, S-BC-06.
