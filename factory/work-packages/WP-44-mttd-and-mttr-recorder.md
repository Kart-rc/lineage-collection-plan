# WP-44: MTTD and MTTR recorder

Wave 4 · family detect_resolve · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-9  
**Depends on:** WP-42

## Scope

Record when bad data landed, when the alert fired, when the cause was identified and when remediation completed, and compare with the same replays without lineage (D16).

## Inputs

- incident replays with and without lineage

## Outputs

- planned:services/mttx/

## Must hold

- The landing time is the injection time from the change event, not an estimate

## Done when

- 4 timestamps recorded for 100% of replayed incidents
- A report compares 100% of incidents with their baseline run without lineage
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/incident-scenarios.json`

## Requirements

- **IR-9**: The system shall record, per incident, when bad data landed, when the alert fired, when the cause was identified and when remediation completed. Scenarios: S-IR-18, S-IR-19, S-IR-08.
