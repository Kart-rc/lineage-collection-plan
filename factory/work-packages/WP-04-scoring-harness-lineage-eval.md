# WP-04: Scoring harness lineage-eval

Wave 0 · family platform · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-6, BL-7, IA-8, IR-5  
**Depends on:** WP-01, WP-02

## Scope

The oracle's executable part - score, replay changes, replay incidents, run holdout - built from code/observed_edges.py and code/run_checks.py; and the release comparison behind gate G4, lineage-eval release (G1 amendment 2, D40).

## Inputs

- code/observed_edges.py
- code/run_checks.py
- fixtures/otel-demo-3.1.0/
- factory/gates/templates/G4-release.md

## Outputs

- planned:factory/oracle/harness/lineage_eval/

## Must hold

- A person reads every line; it is the oracle
- Deterministic - the same inputs give the same scores

## Done when

- `lineage-eval score` on the 27 November capture reproduces precision 1.00 and recall 0.90 on service edges
- `lineage-eval replay incidents` on run 1 reproduces I1 detection at 2.0 minutes and paymentFailure ranked first
- 3 consecutive runs on the same inputs give identical output files (byte for byte)
- The holdout runner's output contains 0 case texts: only a pass rate and failure categories per family
- `lineage-eval release` on two identical builds reports 0 lost cases and 0 on every hard zero, and its report carries the SHA-256 of all 8 G3-pinned oracle files
- 3 seeded regressions are each caught and named - 1 golden field edge dropped (lost case), 1 credit_card edge to the orders topic added (hard zero), 1 incident whose true cause falls to second (lost case)
- the report fills 10 of the 11 required sections of the G4 template, all but Decision, and spec_pack.py accepts it
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`
- `fixtures/otel-demo-3.1.0/capture-2026-11-27/checks-run.json`

## Requirements

- **BL-6**: The baseline shall reach field-edge precision of at least 90% and recall of at least 90% against the golden graph once runtime evidence is on. Scenarios: S-BL-01, S-BL-06, S-BL-08.
- **BL-7**: When the graph is rebuilt from the evidence lake, the system shall produce the same graph hash as the live graph at the same as-of time. Scenarios: S-BL-07.
- **IA-8**: On the change replay corpus the report shall list at least 8 of every 10 consumers that actually broke. Scenarios: S-IA-01, S-IA-06.
- **IR-5**: On the incident replay corpus the true cause shall be ranked first on at least 70% of incidents and in the top three on at least 90%. Scenarios: S-IR-10, S-IR-11, S-IR-12, S-IR-13, S-IR-14, S-IR-15, S-IR-16, S-IR-17.
