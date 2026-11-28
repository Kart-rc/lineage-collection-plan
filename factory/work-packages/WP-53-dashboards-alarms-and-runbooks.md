# WP-53: Dashboards, alarms and runbooks

Wave 5 · family platform · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** XC-3, IA-6  
**Depends on:** WP-52

## Scope

Operating the platform - health, freshness, accuracy published weekly, fail-open paths.

## Inputs

- factory/parameters.yaml

## Outputs

- planned:ops/

## Must hold

- Every alarm links to a runbook step that a fault-injection scenario has exercised

## Done when

- Fault injection (evidence broker down, graph store down, a bad extractor release): each raises its alarm within 5 minutes and the runbook restores service
- Producers and merges keep working in 100% of fault scenarios
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- none

## Requirements

- **XC-3**: The system shall never block or slow a producer. All emission shall be asynchronous and droppable. Scenarios: S-BL-08, S-XC-03.
- **IA-6**: If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. Scenarios: S-IA-08.
