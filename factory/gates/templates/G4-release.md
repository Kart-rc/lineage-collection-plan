# Gate G4: release `<name>`, `<YYYY-MM-DD>`

Template, proposed in G1 amendment 2 (D40). To record a release, copy this file to `factory/gates/G4-<YYYY-MM-DD>-<name>.md` and replace every placeholder. The rules are in the [constitution](../../constitution.md), "Release gate (G4)"; the numbers are in [`parameters.yaml`](../../parameters.yaml) under `release_gate`. Every `##` section below is required: `code/spec_pack.py --check` fails a record that lacks one. Sections 2 to 10 come from `lineage-eval release` (WP-04); a person writes Decision.

## Decision

Approved or held, by whom (D20), on which date. If held: which rule failed, and what goes back to the builder.

## Release

- Commit: `<sha>`
- Baseline: the last approved release and its commit, or "first release" (rule 8)
- Change record: the work packages and merged changes since the baseline
- Waves this release completes: `<none | wave n>`

## Oracle

The SHA-256 of each file pinned by the latest G3 record. Each must equal that record; a mismatch holds the release.

| File | SHA-256 (first 16 hex) | Equals the G3 record |
| --- | --- | --- |

## Replay

Sources, time span and event counts for each. Until slice 2, state: "Twin only. This replay cannot catch a difference between the twin and production."

## Floor

Every metric this release carries, against its bar in `parameters.yaml` and in its work package's done-when (rule 2).

| Metric | Work package | Bar | Value | Holds |
| --- | --- | --- | --- | --- |

## Lost cases

Cases the baseline passed and this release fails, on the recorded replays (rule 3). Write "None", or name each case with its reason and the approver's waiver. A waiver never takes a metric below its floor. For a first release write "Not applicable: first release".

| Case | Metric | Reason | Waived by |
| --- | --- | --- | --- |

## Hard zeros

Any value above 0 holds the release, with no waiver (rule 4). Write "not yet carried" for a count whose work package is not in the release.

| Count | Value |
| --- | --- |
| Must-not-flow violations | |
| Payload values stored | |
| Blocked producers or merges in fault scenarios | |

## Timings

On the fresh twin run, each p95 this release carries, against its bar (rule 5).

| Requirement | Bar (p95) | Measured | Holds |
| --- | --- | --- | --- |
| IA-1 | 5 minutes | | |
| IN-10 | 15 minutes | | |
| IR-1 | 2 minutes | | |
| XC-7 | 60 minutes (first scan) | | |

## Holdout

The pass rate per family from the holdout runner, or "Visible only: WP-02 has not delivered the holdout". Without holdout evidence, IA-8 and IR-5 are not declared held (rule 6).

## Accuracy report

Path and SHA-256 of the report `lineage-eval release` wrote for this release.

## Service levels declared held

The rows of doc 10's "Service levels by wave" that this release makes available to teams. Only bars that passed above, in a release that holds their work package, are listed.
