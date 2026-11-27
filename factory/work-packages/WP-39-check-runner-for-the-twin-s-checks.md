# WP-39: Check runner for the twin's checks

Wave 4 · family detect_resolve · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-1  
**Depends on:** WP-11

## Scope

Evaluate checks.yaml every minute and publish QUALITY_ASSERTION events (D26).

## Inputs

- fixtures/otel-demo-3.1.0/checks.yaml
- code/run_checks.py

## Outputs

- planned:collectors/checks/

## Must hold

- Thresholds are read from checks.yaml; never tuned on the incident being scored

## Done when

- 0 false alarms over the baseline periods of both runs
- For at least 90% of visible incidents, a check listed in catches fails within 3 minutes of the injection
- 100% of results validate as QUALITY_ASSERTION events
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/checks.yaml`
- `fixtures/otel-demo-3.1.0/capture-2026-11-27/checks-run.json`

## Requirements

- **IR-1**: When a DQ or contract check fails on an element, the system shall attach the upstream path, the ranked change events and the blast radius to the alert within 2 minutes.
