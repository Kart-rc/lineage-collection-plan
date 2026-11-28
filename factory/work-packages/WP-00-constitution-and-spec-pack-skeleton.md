# WP-00: Constitution and spec pack skeleton

Wave 0 · family platform · start level people · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** the factory itself  
**Depends on:** nothing

## Scope

The factory folder itself - constitution, parameters, requirements, interfaces, work packages, visible scenarios - and the checker that keeps them consistent.

## Inputs

- docs/06-element-lineage-factory-spec.md
- docs/08-build-decisions.md

## Outputs

- factory/
- code/spec_pack.py

## Must hold

- Protected paths (factory/oracle, factory/parameters.yaml, policies) change only through a person's merge
- Every requirement ID in requirements.yaml is served by at least one package and traced by at least one visible scenario

## Done when

- `python3 code/spec_pack.py --check` reports 0 errors
- 41 of 41 requirements served by a work package and traced by a visible scenario
- Gate G1 signed by the approver (D20)
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `factory/specs/requirements.yaml`
- `factory/parameters.yaml`

## Requirements

