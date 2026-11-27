# WP-40: DQ and contract result ingestion on elements

Wave 4 · family detect_resolve · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-1, IR-3  
**Depends on:** WP-39, WP-34

## Scope

Attach check and contract results to the node or element they are about.

## Inputs

- QUALITY_ASSERTION events

## Outputs

- planned:core/assertions/

## Must hold

- An assertion on an unknown node is queued, never dropped

## Done when

- 100% of fixture assertions attach to the right node or element
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/checks-run.json`

## Requirements

- **IR-1**: When a DQ or contract check fails on an element, the system shall attach the upstream path, the ranked change events and the blast radius to the alert within 2 minutes. Scenarios: S-IR-10, S-IR-11, S-IR-12, S-IR-13, S-IR-14, S-IR-15, S-IR-16, S-IR-18.
- **IR-3**: The system shall identify the first failing element: the furthest upstream element with a failing check whose own inputs pass or have no check. Scenarios: S-IR-10, S-IR-12, S-IR-15, S-IR-03.
