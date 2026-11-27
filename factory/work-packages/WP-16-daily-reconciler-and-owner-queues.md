# WP-16: Daily reconciler and owner queues

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-7  
**Depends on:** WP-12, WP-17

## Scope

Queue static-only, runtime-only, declared-never-seen and disagreeing edges to the owner in catalog.yaml.

## Inputs

- fixtures/otel-demo-3.1.0/catalog.yaml

## Outputs

- planned:core/reconcile/

## Must hold

- One queue item per edge per day, however often it is seen

## Done when

- From the first capture the queue holds exactly: frontend -> currency and frontend -> shipping (static only), and 6 services that read a flag with no flagd span
- 100% of queue items carry an owner
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`
- `fixtures/otel-demo-3.1.0/catalog.yaml`

## Requirements

- **IA-7**: The report shall offer a "this is wrong" action per row, and a disputed edge shall drop to candidate until reviewed. Scenarios: S-IA-09.
