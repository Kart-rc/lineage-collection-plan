# WP-31: PR overlay and impact query API

Wave 3 · family impact · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IN-7, IA-4, IA-9  
**Depends on:** WP-13, WP-14

## Scope

Hold a PR's static evidence in an overlay; answer /impact for a PR or for a change described before any PR exists.

## Inputs

- factory/specs/query-api/interfaces/openapi.yaml

## Outputs

- planned:services/impact/

## Must hold

- The production graph's hash does not change while a PR is open

## Done when

- Overlay isolation: production graph hash unchanged across 100% of overlay scenarios
- /impact for C1 lists accounting.shipping#zip_code, shipping, frontend and load-generator, each with owner, tier, state and confidence
- Contract tests against openapi.yaml: 100% pass
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `factory/specs/query-api/interfaces/openapi.yaml`
- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **IN-7**: While a pull request is open, the system shall hold its static evidence in an overlay keyed by repository and PR number, invisible to production impact and RCA queries. Scenarios: S-IN-08.
- **IA-4**: The report shall list downstream elements and assets by hop with owner, tier, edge state and confidence, following direct dependencies for value impact and reporting indirect dependencies separately as row-set impact. Scenarios: S-IA-01, S-IA-03.
- **IA-9**: The system shall expose the same impact query through an API that coding agents can call before a pull request exists. Scenarios: S-IA-10.
