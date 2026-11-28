# Build collection: the lineage-ci runner and the extractor plugin contract

Build-time collectors read code and schemas on every pull request and every merge, and emit static evidence (weight 0.60) before anything runs. This file fixes the two interfaces that let them reach any application flow without a change per flow:

- the **runner**, `lineage-ci`, which every onboarded repository calls once;
- the **plugin contract**, which every extractor implements.

Requirements: XC-7, XC-8, IN-1, IN-2, IN-7, IA-1, IA-6. Decision D39. Built by WP-18; extractors WP-20 to WP-25, WP-28 and WP-29 implement the contract.

## The runner

The runner is a CLI first. The GitHub Action is a thin wrapper, so the same command runs in any CI system and in the twin.

```text
lineage-ci validate [--config .lineage.yaml]
lineage-ci scan --stage proposed|merged --commit <sha> [--base <sha>] [--pr <n>] [--config .lineage.yaml] [--out <dir>]
lineage-ci impact --pr <n> --comment
```

What `scan` does, in order:

1. **Read and validate** `.lineage.yaml` against [`lineage-repo.schema.json`](lineage-repo.schema.json). If it is invalid, say which field and why, then exit 0. A wrong config never fails a build.
2. **Detect.** Ask every registered extractor for its units in the paths the config names, honouring `exclude`. Listed extractors run even when detection would not pick them; a path no extractor claims is reported.
3. **Hash.** For each unit, compute the content hash of its files and the input schema hash of everything `inputs()` names, as of the commit. Together with the extractor version these form the unit's key.
4. **Skip what has not changed.** A unit whose key matches the last merged scan is marked `unchanged` and not re-extracted (IN-1).
5. **Extract** the rest, each in its own time slice. A unit that overruns is marked `over_budget` and emitted as an opaque edge with a reason, never retried inside the scan.
6. **Emit.**
   - Reserve a durable generation before extracting each changed unit, keyed by route, unit and extractor name without its version. A stable request ID makes retries reuse that reservation.
   - Stage one complete immutable event object, then publish its [completion manifest](../../evidence/interfaces/unit-snapshot.schema.json) on `lineage.unit-snapshots`. Individual envelopes retain `replaces: "unit"`; none is itself a completion boundary (IN-2).
   - On `merged`, the completion route has `stage: merged` and `pr: null`.
   - On `proposed`, events carry `unit.pr` and the completion route names that same PR; the consumer uses an isolated overlay, never the merged graph (IN-7).
   - A successful empty extraction or deleted unit has an explicit complete zero-event manifest. A timeout, failure or incomplete extraction preserves the last accepted unit and publishes no replacing completion.
7. **Write the unit manifest** ([`unit-manifest.schema.json`](unit-manifest.schema.json)) and a run record, then exit 0.

Failing open (IA-6). If the evidence topic or the graph cannot be reached, `scan` writes the manifest with `outcome: unavailable` and exits 0. `impact` then posts "lineage check unavailable" and an alert is raised. Only the contract gate (WP-34) may fail a build, and only under IA-5.

Budget (IA-1). A PR scan, including any build step, finishes within 5 minutes at the 95th percentile. Build outputs the repository already produces are reused when `build.reuse_artifacts` is true: compiled descriptors, a dbt manifest, restored packages.

## The plugin contract

Every extractor is a Python package that exposes one object implementing this protocol and registers it under the entry point group `lineage_ci.extractors`.

The same package supplies a companion entry point with the same name in
`lineage_ci.conformance`. That entry point loads a zero-argument callable returning
`ConformanceFixture`: `repo`, `unit`, `expected_edges`, `reformatted`, `renamed`,
`unreadable`, `minimum_precision`, `minimum_recall`, and `deadline_seconds`.
`repo`, `reformatted` and `renamed` are immutable `RepoView` inputs; `unit` and
`unreadable` are `UnitRef` values. Thresholds must meet or exceed the applicable
approved family floor. Missing, invalid or failing fixtures prevent plugin load.
The fixture and plugin load under the same isolation/deadline controls as the
conformance checks. The three extractor methods below are unchanged.

```toml
[project.entry-points."lineage_ci.extractors"]
"example-sql" = "example_sql:extractor"
[project.entry-points."lineage_ci.conformance"]
"example-sql" = "example_sql.fixtures:conformance_fixture"
```

```python
from typing import Iterable, Iterator, Protocol

class Extractor(Protocol):
    name: str                    # unique, e.g. "dbt-sql"; listed in lineage-repo.schema.json
    version: str                 # semver; part of every unit's key, so a new version re-extracts its units
    technologies: frozenset[str] # what it reads, e.g. {"dbt"}, {"protobuf"}, {"go"}

    def detect(self, repo: "RepoView", paths: list[str]) -> list["UnitRef"]:
        """The units this extractor owns under the given paths. Reads files only; no network."""

    def inputs(self, unit: "UnitRef") -> list["InputRef"]:
        """Schemas and other inputs the unit depends on, for the input schema hash (SELECT * needs this)."""

    def extract(self, unit: "UnitRef", ctx: "ExtractContext") -> Iterator[dict]:
        """Envelope v2 EVIDENCE events for one unit. Schemas come only through ctx.schema_at(ref, commit)."""
```

Rules every extractor follows:

| Rule | Why |
| --- | --- |
| Deterministic: the same unit, inputs and version give byte-identical events | Replay and rebuild must give the same graph hash (BL-7) |
| No network except `ctx.schema_at`, which the runner serves from the repository or the registry as of the commit | Scans are reproducible and run in locked-down CI |
| Never raises on bad input: an unresolved mapping becomes an opaque edge with a reason code | BL-4: a gap is stated, never silent |
| Metadata only: names, types, expressions and their hashes, never literal values | XC-1 |
| Respects `ctx.deadline` and returns what it has | IA-1 budget |
| Events validate against `envelope-v2.schema.json`; weight is set by the runner, not the extractor | One evidence format; weights from `parameters.yaml` |

## The conformance suite

The runner loads an extractor only if it passes the conformance suite (XC-8). The suite runs against the extractor's own golden fixture:

| Check | Pass when |
| --- | --- |
| Golden | Precision and recall at or above the extractor's done-when on its golden fixture |
| Determinism | 3 runs give byte-identical events |
| Metamorphic | Reformatting or renaming aliases changes no edge and no expression hash |
| Opaque | A deliberately unreadable unit yields an opaque edge with a reason, and no exception |
| Schema | 100% of events validate against envelope v2 |
| Budget | Every fixture unit finishes inside its deadline |
| Isolation | No network call other than `ctx.schema_at` (enforced by the test sandbox) |

A stub extractor that passes the suite ships with the runner, so WP-18 can be built and tested before any real extractor exists.

## Deterministic content and measured time

The complete `unit-manifest.json` retains actual `started`, `finished` and each
unit's `duration_ms`. For Action/container parity, `scan-content.json` removes
exactly those three fields and uses deterministic JSON serialization. All other
fields remain in the comparison. A runtime duration is never fabricated to obtain
byte equality. Source commit, input schemas, extractor versions, configuration and
prior cache state must match for the comparison.

The completion protocol and recovery rules are specified in
[unit-snapshot-protocol.md](../../evidence/interfaces/unit-snapshot-protocol.md).

## Onboarding a repository

A repository is onboarded in one change:

1. Add `.lineage.yaml` (examples in [`fixtures/otel-demo-3.1.0/onboarding/`](../../../../fixtures/otel-demo-3.1.0/onboarding/)).
2. Add the `lineage-ci` step to CI: the Action, or the same command in any other CI.
3. Give the step read access to the repository and a write token for the evidence topic, nothing else.

The first merged scan of the default branch completes within 1 hour of onboarding (XC-7). Every later pull request and merge is scanned. A flow that spans several repositories is covered when each of them is onboarded.
