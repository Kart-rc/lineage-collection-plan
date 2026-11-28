# Constitution

Every agent run in the factory loads this file first. It restates the operating principles of [doc 06](../docs/06-element-lineage-factory-spec.md#operating-principles) as rules an agent can follow, and adds the protected paths and the definition of done. Status: approved at gate G1, 28 November 2026 ([record](gates/G1-2026-11-28.md)).

## Rules

1. **The spec is the source of truth.** Work only from `factory/specs/`, your work package in `factory/work-packages/` and `factory/parameters.yaml`. If the code and the spec disagree, stop and propose a spec change; do not fix it in code alone.
2. **Every task traces to a requirement and an oracle.** If you cannot name the requirement ID and the check that proves it, stop and report it.
3. **You never see the holdout.** It is not in this repository. You get back a pass rate and failure categories. Do not try to infer or reconstruct holdout cases.
4. **You never change the oracle.** You may propose changes to protected paths in a separate pull request with the reason. Only people merge them.
5. **You never tune a threshold on the case being scored.** Thresholds come from `parameters.yaml` and `checks.yaml`, set before the run.
6. **Everything runs in the twin.** No production credentials, no production data, no network beyond the twin and the package registries.
7. **Metadata only.** No payload value is stored, logged or sent anywhere: names, schemas, expressions, counts and times only (XC-1).
8. **Fail open.** Nothing you build may block or slow a producer, a request path or a merge when the platform is down (XC-3, IA-6).
9. **Limits stop the line.** 6 build attempts or 1 working day, whichever comes first; then stop and hand over to a person with what you tried. Record tokens used; there is no token cap (D21).
10. **An escaped defect becomes a scenario.** If a defect is found after a gate, add a visible scenario that would have caught it and tell a person, who adds a holdout sibling.

## Protected paths

Only a person merges a change to these. Agents propose.

| Path | What it is |
| --- | --- |
| `factory/constitution.md`, `factory/parameters.yaml` | These rules and every number the build is judged by |
| `factory/specs/requirements.yaml`, `factory/specs/*/interfaces/` | Requirements and interface contracts (change through G1) |
| `factory/oracle/` | Harness, policies and the pointer to the holdout store |
| `fixtures/otel-demo-3.1.0/golden-graph.json`, `fixtures/otel-demo-3.1.0/dbt/golden-dbt.json` | The golden graph (G3) |
| `fixtures/otel-demo-3.1.0/change-replay.json`, `incident-scenarios.json`, `checks.yaml`, `contracts/` | Replay corpora, checks and contracts (G3) |
| `code/reference_slice.py` | The source of the golden graph and its citation checker |
| `factory/gates/` | One record per gate decision: who approved what, at which commit |

## Definition of done

A change to a work package is done when all of these hold:

- Every line under "Done when" in its work package file is true, measured by the harness.
- Every visible scenario traced to the package passes.
- The holdout pass rate is at or above the family's rate in `parameters.yaml`.
- `python3 code/spec_pack.py --check` reports 0 errors.
- The reviewer agent reports no open conformance finding.
- A run record is written to `factory/runs/` (spec version, work package, commit, scores, tokens, attempts).
- At level 2 a person has read the change (gate G2). At level 3 a person approves the batch.

## Autonomy in practice (D18)

Waves 0 and 1 run at level 2: a person reads every change. Extractors start at level 2 too, and move to level 3 only once wave 1 holds its holdout pass rate. A family moves up one level after five consecutive changes at or above its holdout rate with no escaped defect and no finding in the weekly sample, and moves down on any escaped defect that reached stage.

## Gates and who approves

You approve all four gates until domain teams join for slice 2 (D20): G1 spec, G2 change, G3 oracle, G4 release.

## Release gate (G4)

**Proposed in G1 amendment 2 (D40), not yet approved.** The numbers are in `parameters.yaml` under `release_gate`; each record follows [`gates/templates/G4-release.md`](gates/templates/G4-release.md).

1. **Every release is gated.** A wave is available to teams once the release that holds its last work package passes.
2. **Floor.** Every metric the release carries meets its bar in `parameters.yaml` and in its work package's done-when.
3. **No lost case.** On the recorded replays, which are deterministic, the release fails no case that the last approved release passed. Both are scored against the oracle pinned by the latest G3 record. A case is a golden edge, a change or an incident. The approver may waive a lost case only by naming it and the reason in the record, and never below the floor.
4. **Hard zeros, with no waiver:** must-not-flow violations, payload values stored, and fault scenarios in which a producer or a merge was blocked.
5. **Timings are measured, not compared.** On a fresh twin run, each p95 the release carries (IA-1, IN-10, IR-1, XC-7) meets its bar.
6. **Holdout or say so.** IA-8 and IR-5 are declared held only with holdout evidence. Until the holdout exists (WP-02), the record says "visible only" and those two bars are not declared held.
7. **Replay source.** Until slice 2: the recorded twin captures and corpora, plus one fresh twin run of the release. The record states that this cannot catch a difference between the twin and production. From slice 2, one day of production evidence is added.
8. **First release.** With no approved release to compare against, rule 3 is skipped and the release becomes the baseline.
9. **A held release changes nothing for teams.** The platform stays on the last approved release. Failing categories go back to the builder (station 4), and a difference between the twin and production adds a twin fixture.
10. **The record pins what was approved:** the release commit, the SHA-256 of the accuracy report and of every G3-pinned oracle file, and the approver (D20).
