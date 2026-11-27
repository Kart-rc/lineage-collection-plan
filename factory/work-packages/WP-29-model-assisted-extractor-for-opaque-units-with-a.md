# WP-29: Model-assisted extractor for opaque units, with a verifier

Wave 2 · family extractors · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-4, XC-6  
**Depends on:** WP-11, WP-23

## Scope

Candidate evidence for units no rule can read (the Ruby email service, templates); a verifier checks every edge against real schemas.

## Inputs

- opaque units listed by WP-23

## Outputs

- planned:extractors/model_assisted/

## Must hold

- Its edges stay candidate unless another source confirms them
- Only source code and schemas leave through the approved endpoint (D19)

## Done when

- The verifier rejects 100% of proposed edges whose fields do not exist in the schemas
- Precision >= 0.80 on accepted edges against the golden graph
- 100% of events record model, prompt version and output hash; the egress allow-list test passes
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/golden-graph.json`

## Requirements

- **BL-4**: If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. Scenarios: S-BL-04.
- **XC-6**: Where a model is used to read code, the system shall send only source code and schemas through the approved endpoint, and shall record the model, prompt version and output hash with the evidence. Scenarios: S-XC-06.
