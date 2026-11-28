# WP-43: Remediation planner and circuit breaker

Wave 4 · family detect_resolve · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-6, IR-7, IR-8  
**Depends on:** WP-42

## Scope

Blast radius split by run events after the failure; remediation plan in topological order with owners; pause opted-in jobs.

## Inputs

- fixtures/otel-demo-3.1.0/dbt/jobs.yml
- fixtures/otel-demo-3.1.0/dbt/runs-incident-I1.json

## Outputs

- planned:services/remediate/

## Must hold

- A paused job resumes only on a person's instruction

## Done when

- I1 blast radius equals the expected affected and not-yet-affected sets in runs-incident-I1.json
- Plan snapshots for I1 and C1 match, in topological order with an owner per step
- Breaker pauses orders_mart and not finance_dashboard_refresh (2 of 2); 100% of resumes without a person are refused
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/dbt/jobs.yml`
- `fixtures/otel-demo-3.1.0/dbt/runs-incident-I1.json`

## Requirements

- **IR-6**: The system shall split the blast radius into assets already affected and assets not yet affected, using run events after the failure time. Scenarios: S-IR-05.
- **IR-7**: The system shall emit a remediation plan in topological order with an action per node type and the owning team. Scenarios: S-IR-06.
- **IR-8**: Where a job has opted in to the circuit breaker, the system shall pause it when an upstream tier 1 element is failing, and shall resume it only on a person's instruction. Scenarios: S-IR-07.
