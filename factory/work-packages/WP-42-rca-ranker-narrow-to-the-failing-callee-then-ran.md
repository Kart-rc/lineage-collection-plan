# WP-42: RCA ranker: narrow to the failing callee, then rank

Wave 4 · family detect_resolve · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IR-1, IR-2, IR-3, IR-4, IR-5  
**Depends on:** WP-13, WP-40, WP-41

## Scope

From the first failing check, walk the incident window upstream, find the first failing element, rank change events with the score in parameters.yaml and show its terms (D32).

## Inputs

- factory/parameters.yaml
- code/run_checks.py

## Outputs

- planned:services/rca/

## Must hold

- Walks every edge valid at any time in the window, including closed ones; never the current graph
- States when the cause may come from callers (traffic), which the dependency walk cannot reach (D38)
- Same inputs give the same ranking

## Done when

- Visible and holdout incident replay: true cause first on >= 70%, in the top three on >= 90%
- Path, ranked causes and blast radius attached to the alert in 2 minutes or less at p95
- 100% of candidates show all four score terms
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/incident-scenarios.json`

## Requirements

- **IR-1**: When a DQ or contract check fails on an element, the system shall attach the upstream path, the ranked change events and the blast radius to the alert within 2 minutes. Scenarios: S-IR-10, S-IR-11, S-IR-12, S-IR-13, S-IR-14, S-IR-15, S-IR-16, S-IR-18.
- **IR-2**: The system shall walk upstream over the incident window: every edge valid at any time between the last passing check and the failure, including edges that closed in between. It shall not use the current graph. Scenarios: S-IR-01, S-IR-02.
- **IR-3**: The system shall identify the first failing element: the furthest upstream element with a failing check whose own inputs pass or have no check. Scenarios: S-IR-10, S-IR-12, S-IR-15, S-IR-03.
- **IR-4**: The system shall rank change events on the upstream path by a deterministic score, and shall show the terms of the score, the evidence path and any lineage gap on that path for each candidate. Scenarios: S-IR-10, S-IR-17, S-IR-19, S-IR-04.
- **IR-5**: On the incident replay corpus the true cause shall be ranked first on at least 70% of incidents and in the top three on at least 90%. Scenarios: S-IR-10, S-IR-11, S-IR-12, S-IR-13, S-IR-14, S-IR-15, S-IR-16, S-IR-17.
