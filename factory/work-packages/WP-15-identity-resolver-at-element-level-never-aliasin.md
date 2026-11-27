# WP-15: Identity resolver at element level, never aliasing an IP

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-1  
**Depends on:** WP-10

## Scope

Map every name a collector sees to one URN through the alias table and its rules (D31).

## Inputs

- fixtures/otel-demo-3.1.0/aliases.json

## Outputs

- planned:core/resolve/

## Must hold

- An IP address is never an alias
- A shared database login is never used for attribution (D27)

## Done when

- 55 of 55 distinct names in the first capture resolve or are declared non-entities; 0 IP addresses aliased
- 0 duplicate nodes after resolving both captures into the golden graph
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/aliases.json`
- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`

## Requirements

- **BL-1**: The system shall represent every field of every tier 1 asset in the slice as a node with the URN `<dataset URN>#<field path>`, using a dotted path for nested fields and `[]` for array items. Scenarios: S-BL-01, S-BL-03, S-BL-09.
