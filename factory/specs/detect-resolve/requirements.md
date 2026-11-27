# Requirements: detect-resolve

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| IR-1 | When a DQ or contract check fails on an element, the system shall attach the upstream path, the ranked change events and the blast radius to the alert within 2 minutes. | Incident scenarios in the twin | WP-39, WP-40, WP-42 |  |
| IR-2 | The system shall walk upstream over the incident window: every edge valid at any time between the last passing check and the failure, including edges that closed in between. It shall not use the current graph. | Scenario where the offending edge closed before the alert (C4 inside an incident window); scenario where an edge changed after the incident | WP-13, WP-41, WP-42 | S-IR-01, S-IR-02 |
| IR-3 | The system shall identify the first failing element: the furthest upstream element with a failing check whose own inputs pass or have no check. | Multi-hop failure fixtures | WP-40, WP-42 | S-IR-03 |
| IR-4 | The system shall rank change events on the upstream path by a deterministic score, and shall show the terms of the score, the evidence path and any lineage gap on that path for each candidate. | Ranking fixtures; explanation snapshot; a scenario with an opaque hop | WP-41, WP-42 | S-IR-04 |
| IR-5 | On the incident replay corpus the true cause shall be ranked first on at least 70% of incidents and in the top three on at least 90%. | `lineage-eval replay incidents` | WP-02, WP-04, WP-42 |  |
| IR-6 | The system shall split the blast radius into assets already affected and assets not yet affected, using run events after the failure time. | Scheduled-run fixtures: the dbt job's runs after the failure time | WP-43 | S-IR-05 |
| IR-7 | The system shall emit a remediation plan in topological order with an action per node type and the owning team. | Plan snapshots for incident I1 and for change C1 deployed to the twin | WP-43 | S-IR-06 |
| IR-8 | Where a job has opted in to the circuit breaker, the system shall pause it when an upstream tier 1 element is failing, and shall resume it only on a person's instruction. | Circuit breaker scenario on the opted-in dbt job | WP-43 | S-IR-07 |
| IR-9 | The system shall record, per incident, when bad data landed, when the alert fired, when the cause was identified and when remediation completed. | MTTD and MTTR report against baseline replays run without lineage (D16) | WP-44 | S-IR-08 |
