# WP-19: Service edge builder: trace walk, topic joins, ingress logs

Wave 1 · family extractors · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-6, XC-3  
**Depends on:** WP-11, WP-15

## Scope

CALLS from the parent-child span walk, PRODUCES and CONSUMES joined on the topic, ingress from Envoy by upstream cluster, flagd calls as configuration reads (D7, D8, D29).

## Inputs

- code/observed_edges.py
- fixtures/otel-demo-3.1.0/aliases.json

## Outputs

- planned:collectors/service_edges/

## Must hold

- Reads exported telemetry only; never sits in a request path

## Done when

- On both captures: service and topic edges precision >= 0.95 and recall >= 0.90; 13 of 13 upstream-asserted edges
- 2 of 2 Kafka consumers found by topic join, with 0 trace links used
- 100% of calls to flagd scored as control edges; 0 as data edges
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`
- `fixtures/otel-demo-3.1.0/golden-graph.json`

## Requirements

- **BL-6**: The baseline shall reach field-edge precision of at least 90% and recall of at least 90% against the golden graph once runtime evidence is on. Scenarios: S-BL-01, S-BL-06, S-BL-08.
- **XC-3**: The system shall never block or slow a producer. All emission shall be asynchronous and droppable. Scenarios: S-BL-08, S-XC-03.
