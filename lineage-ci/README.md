# lineage-ci candidate runner (WP-18)

The CLI validates the approved onboarding schema, reads tracked regular files
from the exact Git commit, discovers conforming extractors, hashes unit files
and input schema bytes, and publishes durable complete-unit snapshots. It never
checks out files or reads mutable worktree contents during a scan. Proposed
scans require a PR number; their candidate files live under
`overlays/<repository>/<pr>/<commit>/`. They cannot advance merged cache state.

Install the project with `pip install .`. The entry point is `lineage-ci`:

```sh
lineage-ci validate --config .lineage.yaml
lineage-ci scan --stage merged --commit "$COMMIT" --transport local --out /tmp/lineage-result
lineage-ci scan --stage proposed --commit "$COMMIT" --base "$BASE" --pr 42 --transport local
lineage-ci scan --stage merged --commit "$COMMIT" --transport kafka \
  --snapshot-root /shared/lineage-snapshots --broker redpanda:9092 \
  --snapshot-topic lineage.unit-snapshots
```

`--stub` explicitly enables the shipped fixture extractor. It produces one
metadata-only opaque unit boundary for each configured service, schema, or
project, and does not claim to extract the technology's actual dependencies.
The OpenTelemetry configuration therefore yields 16 units. Real technology
extractors belong to later work packages; unclaimed paths are reported with
`UNPARSED_LANGUAGE`. Artifact paths are visible in the exact commit view;
this version does not execute builds or acquire mutable CI build outputs.

The runner reserves a persistent per-route/unit/producer generation before
calling `extract()`. The request identity includes the commit, content hash,
input schema hash, extractor version, and deletion flag. Retrying the same
request reuses its generation and immutable content; a new revision receives
a later generation. The shared snapshot root stores reservations, immutable
evidence objects, and completion manifests. The object is flushed before its
completion is published. Complete empty sets and deletions carry explicit
unit revisions; incomplete extraction never publishes a replacement.

`--transport local` accepts a durable completion into that shared filesystem.
`--transport kafka` additionally requires acknowledgment on the separate
`lineage.unit-snapshots` topic. Individual static replacement envelopes never
enter the additive `lineage.evidence` topic. Consumers must mount the same
snapshot archive; no S3 adapter or distributed filesystem guarantee is claimed.
Publication is distinct from downstream graph acceptance: run records report
both and do not claim a graph update. `candidate: true` continues to describe
this unmerged/unreleased implementation, not a new requirement for approval of
the already accepted protocol direction.

`--transport unavailable` exercises an unreachable topic: the manifest reports
`unavailable`, the CLI exits 0, `alerts.json` records an alert and `comment.json`
prepares `lineage check unavailable`. No external alert or comment is sent.
`impact --pr 42 --comment` also prepares an unavailable response, because the
impact engine and external comment adapter belong to later work packages.

Artifacts:

* `unit-manifest.json`: schema-valid manifest with real start/end timestamps and
  per-unit duration measurements.
* `scan-content.json`: deterministic manifest content without operational
  timestamps or durations, for comparing identical scans and wrappers.
* `candidate-snapshots.json`: isolated route plus complete candidate sets.
* `completion-manifests.json`: acknowledged/staged complete-unit manifests.
* `diagnostic-events.json`: opaque diagnostics for failed extraction, marked
  `replaces: none` and never published as complete replacements.
* `run-record.json`: measured timings, errors, conformance refusals and explicit
  local candidate status.
* `alerts.json`: local alerts; delivery to an operational sink is not claimed.

The overhead check conservatively uses total scan wall time as an upper bound,
including extraction; `unit_processing_ms` also includes hashing and worker
orchestration and is not claimed as pure extractor CPU time. Passing this
stricter upper bound proves overhead is below the approved 60-second limit.

The local candidate merged cache is keyed by repository and checked against
Git ancestry and an explicit proposed base. It advances only after a complete,
available merged scan. Unavailable/partial runs retain the previous baseline;
PR state is separate. A PR refreshes unchanged units from its merged baseline
without re-extracting them, preventing stale overlays after a revert; removed
units receive empty deletion completions. Deletions are suppressed if detection
or extraction is incomplete. A separate publication-intent journal retains
possibly delivered units across ambiguous acknowledgments; it never makes a
failed run eligible for cache reuse. The cache and outputs should be outside tracked paths or
ignored by Git. Concurrent scans fail open immediately instead of waiting on
a cache lock. Missing schemas, extractor crashes and exceeded deadlines become
visible failures or opaque boundaries, with failed units retried on later runs.

## Plugin conformance and isolation

The published `detect`, `inputs`, and `extract` protocol is implemented in
`lineage.plugins`. `PluginRegistry.register(plugin, fixture)` runs golden,
three-run determinism, formatting/alias metamorphic, unreadable-input opaque,
envelope validation, deadline and isolation checks. An extractor cannot assign
the authoritative weight. The runner applies the approved `ci_static` weight.
Packages register their extractor in `lineage_ci.extractors`, with a matching
`lineage_ci.conformance` entry point whose callable returns a
`ConformanceFixture`. The companion convention leaves the three extraction
methods unchanged. Missing
or failed fixtures refuse the plugin with named checks; unknown extractors in
configuration are rejected by the approved schema.

Fixture thresholds cannot weaken the applicable approved floor. Descriptor and
ORM plugins use `baseline_accuracy.deterministic_hops`; ordinary plugins use
`per_hop_default`. Model-assisted precision follows WP-29's explicit accepted
edge threshold, with no additional platform recall bar where WP-29 defines
none. Fixtures may demand stronger precision or recall. Missing policy inputs
refuse registration rather than silently falling back to a weaker floor.

All package imports and calls run in disposable Linux workers. Linux seccomp
denies network syscalls, process creation/execution, namespace changes, ptrace,
and io_uring; inherited file descriptors are closed. Results cross the worker
boundary as JSON, never pickle. The runner kills a worker on deadline or crash.
Only `ctx.schema_at(ref, scanned_commit)` reads input schemas from the pinned
repository view. No registry networking or source-value logging is added.
Unsupported kernels/architectures fail closed for the plugin and open for CI.
This is not a sandbox against malicious filesystem access: install only trusted
extractor packages and run the container with a read-only repository mount.

Use the standalone CLI process. The current worker implementation uses Linux
`fork`; Kafka networking starts only after every extractor worker exits.
Embedding it in an application that has already started Python or
native background threads is unsupported. A child can inherit locked runtime
state and time out. Deadlines bound those failures, but do not make forking a
multithreaded application safe. The combined in-process test suite exposes
Python's fork deprecation warnings; they are not suppressed. A future worker
should start a clean interpreter and receive importable plugin requests as JSON
before embedded, multithreaded use is supported.

## Wrapper and container

The composite GitHub Action is a thin call to the installed CLI. It grants no
permissions and sends no comments. Install the same CLI version before using
`uses: ./lineage-ci`, then provide `stage`, `commit`, and `pr` for proposed scans.
The wrapper passes values as arguments through environment variables; it never
evaluates input strings. Cache restoration belongs to the host CI workflow.

```sh
docker build -f lineage-ci/Dockerfile -t lineage-ci:local .
docker run --rm --network none --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  -v "$PWD:/repo:ro" -v /tmp/lineage-result:/out \
  lineage-ci:local scan --stage merged --commit "$COMMIT" \
  --state-dir /out/state --out /out/result --transport local --stub
```

The container and Action run the same entry point. Compare `scan-content.json`
from fresh, identical baseline states. Actual wall-clock manifest timestamps
will differ; normalized parity follows the approved direction recorded in
`contract-proposals.md`. Holdout, full external comment/alert delivery, real
technology extraction and a production release remain unverified or deferred.

If the build environment uses an enterprise registry CA, pass the CA bundle as
`docker build --secret id=registry_ca,src=/path/to/ca-bundle ...`; certificate
verification remains enabled and the CA is not copied into the image.
