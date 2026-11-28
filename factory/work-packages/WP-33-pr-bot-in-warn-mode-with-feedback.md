# WP-33: PR bot in warn mode with feedback

Wave 3 · family impact · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-1, IA-6, IA-7, IA-8  
**Depends on:** WP-31, WP-32

## Scope

Post the impact report on pull requests against the demo fork; "this is wrong" per row; fail open.

## Inputs

- the demo fork's pull requests

## Outputs

- planned:services/pr_bot/

## Must hold

- If the platform is down the check passes with a comment and an alert

## Done when

- Report posted in 5 minutes or less at p95 in the twin
- Change replay: at least 80% of consumers that actually broke are listed, on visible and on holdout
- Fail-open and dispute scenarios: 100% pass
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **IA-1**: When a pull request opens or updates in an onboarded repository, the system shall post an impact report within 5 minutes at the 95th percentile. Scenarios: S-BC-03, S-IA-07.
- **IA-6**: If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. Scenarios: S-BC-04, S-IA-08.
- **IA-7**: The report shall offer a "this is wrong" action per row, and a disputed edge shall drop to candidate until reviewed. Scenarios: S-IA-09.
- **IA-8**: On the change replay corpus the report shall list at least 8 of every 10 consumers that actually broke. Scenarios: S-IA-01, S-IA-06.
