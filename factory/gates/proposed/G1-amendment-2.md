# Gate G1, amendment 2: the release gate (G4)

**Status: proposed on 28 November 2026, not yet approved.** The approver is the platform lead, who approves all four gates (D20). On approval this file moves to `factory/gates/G1-amendment-2-<date>.md`, the "proposed" markers come out of the files below, and `parameters.yaml` becomes version 1.1.0.

## Why

Doc 06 defines G4 in one row of the stations table: "Stage replay of a day of production evidence, accuracy report, change record. **G4 release gate:** accuracy does not drop; named approver." Three things in that row are undefined:

1. **"Does not drop" has nothing to compare against at first.** The first release has no earlier accuracy, so "no drop" passes by default. A floor is needed as well as a comparison.
2. **"A day of production evidence" does not exist on the reference slice.** The demo is the twin. Until slice 2, the only replay is the twin's own captures, and those cannot catch a difference between the twin and production. That difference is the risk G4 exists for (doc 06, risk table).
3. **G4 has no numbers or record format.** `parameters.yaml` has no G4 section: no metric list, no tolerance, and no rule for whether it applies per release or per wave. `factory/gates/` has no G4 template. No work package builds the comparison report.

This matters now because the onboarding guide (doc 10) defines a service level as available to teams once its release passes G4. Without this amendment, nobody can check that definition.

## What changes

| Part | Change |
| --- | --- |
| Parameters | **Adds `release_gate`** to `parameters.yaml`. It sets the unit (every release), the baseline (the last approved release, scored against the same G3 oracle), the first-release rule, the replay sources before and from slice 2, 0 lost cases, the waiver rule, 4 timed requirements, 3 hard zeros, the 2 requirements that need holdout evidence, and when each check applies. Version 1.0.0 becomes 1.1.0. |
| Constitution | **Adds "Release gate (G4)"**: 10 rules covering gating, floor, no lost case, hard zeros, timings, holdout, replay source, first release, held releases and the record. |
| Gate record | **Adds `factory/gates/templates/G4-release.md`** with 11 required sections: Decision, Release, Oracle, Replay, Floor, Lost cases, Hard zeros, Timings, Holdout, Accuracy report, Service levels declared held. |
| Work packages | **WP-04 builds `lineage-eval release`,** the comparison report behind G4, in wave 0. It adds 3 done-when lines: identical builds give 0 lost cases and carry the 8 oracle hashes; 3 seeded regressions are caught and named; the report fills 10 of the 11 sections. Done-when lines go from 104 to 107. |
| Checker | `code/spec_pack.py --check` now checks four things: `release_gate` has every key; its hard zeros are 0; its requirement IDs exist; the template and every `G4-*.md` record have the 11 sections. |
| Doc 06 | **Station 8** points to the rules and states the replay source before and after slice 2. |
| Doc 08 | **Adds D40**, marked proposed. Also fixes the status table, whose first two rows had their text swapped. |
| Doc 10 | **States when a service level holds:** when the release holding its work package passes G4. Notes that IA-8 and IR-5 need holdout evidence. |

## The rules in brief

- **Floor:** every metric meets its bar in `parameters.yaml` and in its work package's done-when.
- **No lost case.** On recorded replays, no golden edge, change or incident that the last approved release passed may fail. The approver may waive one named case, with a reason, and never below the floor.
- **Hard zeros, with no waiver:**
  - must-not-flow violations;
  - stored payload values;
  - producers or merges blocked in fault scenarios.
- **Timings** are checked on a fresh twin run against their bars: IA-1, IN-10, IR-1 and XC-7. They are not compared between releases, because timings vary from run to run.
- **Holdout:** IA-8 and IR-5 are not declared held on visible cases alone.
- **Replay source:**
  - until slice 2: twin captures, the corpora and a fresh twin run, and the record states the twin-only limit;
  - from slice 2: one day of production evidence as well.

### Why 0 lost cases, not "no metric down more than 1 point"

The first proposal was a drop of no more than 1 percentage point per metric. On this oracle one case is worth more than a point:

- one golden field edge is 2.8 points of 36;
- one visible change is 7.7 points of 13;
- one visible incident is 10 points of 10;
- one holdout case is about 14 points of 7.

So a 1-point rule already means no lost case. It would only hide that fact behind a percentage.

The recorded replays are deterministic: this is a WP-04 must-hold, and station 5 checks replay determinism. A lost case is therefore a real regression, not noise. A named waiver covers a deliberate trade-off, and the record shows it.

## What does not change

- No existing value in `parameters.yaml`; only the new section is added.
- No requirement; there are still 43. G4 is a factory control, not product behaviour.
- No interface: envelope v2, `lineage.changes`, the OpenAPI and the build-collection interfaces are unchanged.
- No oracle file pinned at G3.
- The approver for G4 stays the platform lead (D20).

## Check

`python3 code/spec_pack.py --check` reports 0 errors with the amendment applied:

- 43 requirements;
- 40 work packages with 107 measurable done-when lines;
- the release gate with 3 hard zeros, 4 timed requirements and the 11-section template.

In a scratch copy, four planted faults were each rejected with a message that names it:

- a hard zero set to 2;
- an unknown requirement ID;
- a template with a renamed section;
- a G4 record with only its Decision section.

## What it leaves open

- **The `lineage-eval release` command itself.** WP-04 builds it in wave 0; until then no release can pass G4.
- **The production replay.** It starts with slice 2, which is not yet chosen (D22). The drop rule should be reviewed then against a real day's variation.
- **Who signs G4 after slice 2.** D20 runs until domain teams join.
