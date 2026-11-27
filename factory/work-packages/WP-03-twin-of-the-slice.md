# WP-03: Twin of the slice

Wave 0 · family platform · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IN-10, IA-1  
**Depends on:** WP-00

## Scope

One command starts the demo with the capture add-on and the separate lineage platform (Kafka for evidence, Neo4j, Postgres for aliases and queues, a Parquet archive), and flips flags with logged change events.

## Inputs

- fixtures/otel-demo-3.1.0/run/
- fixtures/otel-demo-3.1.0/dbt/

## Outputs

- planned:twin/compose.yaml
- planned:twin/flip.py

## Must hold

- Lineage traffic never uses the demo's own Kafka (D23)
- Works in a sandbox without IPv6 or ulimit (sandbox.override.yaml)

## Done when

- Cold start to all containers healthy in 15 minutes or less, 3 of 3 attempts
- Smoke run: observed service edges score precision >= 0.95 against the golden graph after 10 minutes of load
- Every flag flip and service stop or start is logged as a CHANGE_EVENT that validates against envelope-v2.schema.json
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/run/sandbox.override.yaml`
- `fixtures/otel-demo-3.1.0/run/otelcol-capture.yml`

## Requirements

- **IN-10**: The system shall make an edge visible within 15 minutes of the merge or run that produced it, at the 95th percentile. Scenarios: S-IN-11.
- **IA-1**: When a pull request opens or updates in an onboarded repository, the system shall post an impact report within 5 minutes at the 95th percentile. Scenarios: S-IA-07.
