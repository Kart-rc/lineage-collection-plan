# WP-02: Change and incident replay corpora, visible and holdout split

Wave 0 · family oracle · start level people · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-8, IR-5  
**Depends on:** WP-01

## Scope

At least 20 changes and 20 incidents, each with its expected outcome, split by family; the holdout third written and kept by people outside the build's reach.

## Inputs

- fixtures/otel-demo-3.1.0/change-replay.json
- fixtures/otel-demo-3.1.0/incident-scenarios.json
- factory/oracle/holdout/README.md

## Outputs

- fixtures/otel-demo-3.1.0/change-replay.json
- fixtures/otel-demo-3.1.0/incident-scenarios.json
- holdout store (outside this repository)

## Must hold

- Holdout cases are written by someone who does not build, and are not readable from build sandboxes
- The four examples named in D15 are public and count as visible; holdout cases must differ from them

## Done when

- At least 20 changes and 20 incidents across the families in parameters.yaml, at least 1/3 of each family in holdout
- 100% of cases have a base, a trigger and an expected outcome a script can compare
- Owners and the platform lead sign the corpora
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`
- `fixtures/otel-demo-3.1.0/incident-scenarios.json`
- `factory/oracle/holdout/README.md`

## Requirements

- **IA-8**: On the change replay corpus the report shall list at least 8 of every 10 consumers that actually broke. Scenarios: S-IA-01, S-IA-06.
- **IR-5**: On the incident replay corpus the true cause shall be ranked first on at least 70% of incidents and in the top three on at least 90%. Scenarios: S-IR-10, S-IR-11, S-IR-12, S-IR-13, S-IR-14, S-IR-15, S-IR-16, S-IR-17.
