# WP-32: Change classifier

Wave 3 · family impact · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-2, IA-3  
**Depends on:** WP-21, WP-20

## Scope

Change kind per element and change class per change.

## Inputs

- fixtures/otel-demo-3.1.0/change-replay.json

## Outputs

- planned:services/classify/

## Must hold

- An unchanged normalized expression is non-breaking; an unparsed unit is unknown and reported

## Done when

- Visible: kind and class correct for 100% of C1 to C7, the formatting-only change and the opaque unit
- Holdout pass rate >= 0.85
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **IA-2**: The report shall list each changed element with its change kind: added, removed, renamed, retyped, nullability changed, logic changed, or row set changed. Scenarios: S-IA-01, S-IA-06.
- **IA-3**: The system shall classify each change as breaking, potentially breaking, non-breaking or unknown. It shall classify a change that leaves the normalized expression unchanged as non-breaking, and a change in a unit it cannot parse as unknown, which is reported and treated as potentially breaking. Scenarios: S-IA-01, S-IA-02, S-IA-03, S-IA-04, S-IA-05, S-IA-06.
