# WP-34: Contract gate in block mode

Wave 3 · family platform · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-5, IA-6  
**Depends on:** WP-31, WP-32, WP-17

## Scope

Enforce the contracts and the must-not-flow rules, over active and latent edges.

## Inputs

- fixtures/otel-demo-3.1.0/contracts/
- fixtures/otel-demo-3.1.0/golden-graph.json

## Outputs

- planned:services/gate/

## Must hold

- Block only for tier 1 elements with confirmed or verified readers, removed, renamed or retyped without a version bump or sign-off

## Done when

- C1 blocks; a field added with a new number passes; a formatting-only change passes
- 5 of 5 must-not-flow rules enforced; the latent card path of C7 is reported before the flag is switched on
- Gate policy scenarios 100% pass, read by a person
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/contracts/orders.contract.yaml`
- `fixtures/otel-demo-3.1.0/contracts/accounting.contract.yaml`

## Requirements

- **IA-5**: While the gate is in block mode, the system shall fail the check only when a tier 1 contract element with confirmed downstream readers is removed, renamed or retyped without a version bump or sign-off from those readers' owners. Scenarios: S-XC-07, S-XC-08, S-IA-01, S-IA-06.
- **IA-6**: If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. Scenarios: S-BC-04, S-IA-08.
