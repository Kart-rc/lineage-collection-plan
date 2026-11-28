# WP-23: Service producer and consumer field scanner

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-2, BL-3, BL-4  
**Depends on:** WP-10, WP-11, WP-21, WP-18

## Scope

Field-to-field assembly inside services - the Go code in checkout first, then Kotlin and the other languages; rules per framework.

## Inputs

- demo src/checkout at 3.1.0

## Outputs

- planned:extractors/service_fields/

## Must hold

- A service in a language without rules emits opaque edges (UNPARSED_LANGUAGE), never nothing

## Done when

- Checkout: precision and recall >= 0.90 on its 18 golden field edges, including the card pass-through to payment
- 0 edges from any credit_card field to the orders topic (must-not-flow)
- The 5 flag-gated edges carry the condition flag://otel-demo/emitRawPii == on
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/golden-graph.json`

## Requirements

- **BL-2**: When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. Scenarios: S-BL-01, S-BL-02.
- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
- **BL-4**: If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. Scenarios: S-BL-04, S-BC-06.
