# WP-41: Change-event timeline; flag changes join through flag edges

Wave 4 · family detect_resolve · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-2, IR-4  
**Depends on:** WP-11, WP-12

## Scope

Ingest flag changes, deploys, stops, starts and merges as CHANGE_EVENTs and join them to services (D29).

## Inputs

- fixtures/otel-demo-3.1.0/capture-2026-11-27/change-events.jsonl

## Outputs

- planned:core/timeline/

## Must hold

- A flag change joins through every service that reads the flag in code, with or without a flagd span
- Statements such as LOCK TABLE ... ACCESS EXCLUSIVE seen in database spans enter the timeline as change events (D38)

## Done when

- 100% of change events from both runs ingested and joined (20 flag edges, service stop and start)
- A window query returns exactly the events inside the window for 100% of visible incidents
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/change-events.jsonl`
- `fixtures/otel-demo-3.1.0/golden-graph.json`

## Requirements

- **IR-2**: The system shall walk upstream over the incident window: every edge valid at any time between the last passing check and the failure, including edges that closed in between. It shall not use the current graph. Scenarios: S-IR-01, S-IR-02.
- **IR-4**: The system shall rank change events on the upstream path by a deterministic score, and shall show the terms of the score, the evidence path and any lineage gap on that path for each candidate. Scenarios: S-IR-10, S-IR-17, S-IR-19, S-IR-04.
