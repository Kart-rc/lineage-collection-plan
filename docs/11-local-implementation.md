# Local Wave 0 and Wave 1 candidate

The graph target for this build is free Neo4j Community in Docker, following the
user's explicit substitution for stage Neptune. The approved source documents
still describe the future AWS option; no AWS compatibility is claimed here.

## What can be exercised

| Area | Implementation |
| --- | --- |
| WP-03 | Pinned Docker twin/platform, isolated networks, fault events and targeted flag handling |
| WP-04 | `lineage-eval`: semantic graph scoring, change/incident replay, release comparison, oracle hashes, private-job interface |
| WP-10–14 | URNs, durable complete unit snapshots, evidence merge, confidence, conditions, bitemporal graph, material diffs |
| WP-15–17 | Alias resolver, owner/tier and personal-field overlay, persistent daily reconciliation |
| WP-18 | `lineage-ci`: exact Git views, incremental hashes, isolated plugins, durable snapshot publication and PR routing |
| WP-19 | Exported-telemetry collection, topic-based Kafka joins, control-edge separation |
| Runtime integration | Validated v2 metadata through Kafka, Parquet receipts, Neo4j projection and durable change outbox |

The initial acceptance record is in `factory/runs/wave-0-1/`; the later runtime
bridge work is recorded separately in `factory/runs/wave-0-1-runtime-bridge/`.
The approved-contract implementation is recorded in
`factory/runs/wave-0-1-approved-contracts/`.
Existing G1/G3 records are not replacements for approval of this implementation.

## Database and runtime worker

With the pinned demo checkout available as described in `twin/README.md`, run:

```sh
LINEAGE_PYTHON=.venv/bin/python sh twin/run-platform.sh
```

The worker mounts the `lineage-archive` and `lineage-snapshot-archive` volumes and uses a read-only root filesystem,
no elevated capabilities, and the isolated lineage network. It consumes
`lineage.evidence` and `lineage.unit-snapshots`, and publishes `lineage.changes`. It does not read raw demo
payloads. Its default namespace is `lineage-runtime`. Local disposable credentials
are documented in the twin guide and are never intended for a shared deployment.

If a registry proxy requires a public CA bundle, build once with a temporary
BuildKit mount, keeping TLS verification enabled:

```sh
docker build --secret id=registry_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f twin/worker.Dockerfile -t lineage-platform:local .
LINEAGE_PROJECT_ROOT="$PWD" docker compose -p lineage-twin \
  -f twin/.state/compose.yaml -f twin/worker.compose.yaml up -d --no-build --wait lineage-worker
```

The certificate bundle is not copied into the image. On a host without such a
proxy, the normal build needs no secret mount.

For a local v2 metadata JSONL replay, with a fresh archive directory:

```sh
python -m lineage.pipeline --archive /tmp/lineage-replay \
  --events /path/to/metadata-only-events.jsonl --bolt-url bolt://127.0.0.1:17687
```

The archive is the durable source of truth. Receipt acceptance and the change
outbox commit together before Neo4j projection. A graph failure keeps the receipt
and leaves the Kafka offset unacknowledged; restart/redelivery restores the graph.
An archive failure cannot publish an unaccepted graph revision. Each receipt has a
content hash and an immutable Parquet object; unknown fields and corrupt objects
are rejected. Queries can resolve original metadata rawRefs through the archive
index. This does not claim that historical raw captures omitted from the repository
are available.

Change delivery is **at least once**. A crash after Kafka delivery but before the
outbox acknowledgement can repeat delivery with the same stable content-hash key.
Downstream projections must deduplicate by that key. Logical source redelivery
produces no new material change; cross-system exactly-once delivery is not claimed.
The current worker is single-writer per namespace and archive. A held material
change is retained pending review and is not acknowledged as a successful source
event. An unsupported or invalid source event stops the worker with its offset
unacknowledged; automatic dead-letter handling is not yet implemented.

A mass-close hold persists its receipt and alert across restarts. With the worker
stopped to preserve the single-writer boundary, inspect
`RuntimePipeline.pending_snapshot_holds()` and release a reviewed receipt using:

```sh
python -m lineage.pipeline --archive /path/to/archive \
  --snapshot-root /path/to/snapshots --bolt-url bolt://127.0.0.1:17687 \
  --release-snapshot RECEIPT_DIGEST --owner-action-id REVIEW_ID \
  --actor OWNER --recorded-at ACTUAL_APPROVAL_TIME_UTC
```

The action and actor are audited with acceptance and the outbox. Restart the same
worker afterward; redelivery repairs projection and acknowledges the source.
The approval time cannot precede the held receipt or newer accepted evidence.
Caller-supplied actor text is attribution; deployment access controls must
authorize the operator. No existing hold is released merely by running tests.

## Exported telemetry and fault forwarding

`python -m lineage.collector` bridges append-only exported `traces.jsonl` and
`logs.jsonl`, plus committed fault events, into approved v2 runtime evidence. It
uses the same service-edge collector, including topic-based joins and SQL-name
projection. It runs outside producer/request paths. Raw inputs are read-only;
the progress directory contains metadata and acknowledged content digests.

Build the current `lineage-platform:local` image using the worker Dockerfile above.
Once the platform and actual exported-telemetry files exist, start the optional
collector:

```sh
LINEAGE_CAPTURE_DIR=/absolute/path/to/exported-telemetry \
LINEAGE_CHANGES_FILE="$PWD/twin/.state/changes.jsonl" \
sh twin/run-collector.sh
```

The script uses the current host UID/GID so raw files need not be made readable
by other users. State defaults to the ignored `twin/.state/collector` directory.
The Compose service has read-only source mounts and root filesystem, dropped
capabilities, a 512 MiB memory limit, and a separate writable progress mount.
It polls every five seconds. A standalone health probe is:

```sh
python -m lineage.collector --state /path/to/progress --health
```

This is a **bounded whole-capture reread implementation**. Defaults cap combined
input at 16 MiB, each line at 1 MiB, events at 4,096 and projected metadata at
8 MiB. Parsing and Kafka acknowledgement have deadlines. The CLI exposes the
limits through `--help`; Compose exposes input/event caps through
`LINEAGE_COLLECTOR_MAX_INPUT_BYTES` and `LINEAGE_COLLECTOR_MAX_EVENTS`. These
defaults do not fit the missing historical 96/650 MiB captures. Raising a byte
cap alone does not establish memory or throughput capacity; measure those before
using larger inputs. This is not a general-purpose streaming collector.
Limits must be positive finite numbers of the documented type; timer settings
cannot exceed one day. Parser failures always terminate and reap the isolated
process before removing its metadata output.

Only complete newline-terminated records are eligible. A trailing partial record
is deferred until completed. Validated source fingerprints are recorded before
delivery to detect replacement even during a first-delivery outage. Only a
successful Kafka acknowledgement permits durable delivery-digest progress; a
failure retains the source for retry. A crash between broker
acknowledgement and progress commit may redeliver the same key. The runtime archive
deduplicates identical envelopes; physical delivery is at least once. Late spans
may revise a minute's rollup, creating a new digest without implying a new material
graph edge.

Rotation, truncation or rewriting of accepted source content requires operator
attention and does not silently reset progress. Keep the old source and state
together, then deliberately start a new state directory for a new source. Retain
the downstream archive and its deduplication state. Do not delete progress to
hide a parse or delivery failure. A controlled error category and unhealthy status
make that failure visible without printing raw input or exception text.

Container integration uses labeled synthetic exports and disposable topics and
graph namespaces. Full reference-workload forwarding, live latency and the two
historical captures remain separate acceptance requirements.

## Approved contract directions

The user approved all four directions: complete-unit transport, expression-change
sets, normalized manifest parity, and companion conformance fixtures. Their exact
[contract amendment](../factory/gates/proposed/G1-amendment-3-2026-11-28.md) is
prepared for human merge. The candidate implements the amended contracts.

The CI publisher and worker share the snapshot archive root. For Kafka publication,
run `lineage-ci scan` with `--transport kafka --snapshot-root PATH --broker HOST`;
the default completion topic is `lineage.unit-snapshots`. A container publisher
mounts the same named volume at `/snapshot-archive`. Full manifests retain real
timings; parity uses normalized `scan-content.json`. See the
[runner guide](../lineage-ci/README.md) for exact invocation and routing.

Static completion and runtime evidence share one acceptance/recovery journal.
Expression-only rewrites emit schema v2 with explicit old/new hash sets; legacy
hashless changes remain v1. The [protocol](../factory/specs/evidence/interfaces/unit-snapshot-protocol.md)
defines validation and retry semantics. Changes outbox consumers must understand
v2 before expression-aware producers are enabled.

Impact reports and external comment/alert delivery remain later adapters. These
changes preserve the approved thresholds and oracle; their local checks do not
constitute G2/G4 acceptance.

## Validation boundaries

The private holdout must be authored and run independently under the custody
policy. The implemented runner interface cannot establish independence by testing
cases authored or visible to the builder. Evaluation reports explicitly withhold
holdout claims when that job is not connected.

The full demo exhausted the current 32 GiB Docker-vfs host. Unused task images were
removed; the smaller platform remains runnable. The full profile has a capacity
guard. Its three cold starts, ten-minute reference load run and checkout p99 fault
test require an overlay-backed or larger host. Component and synthetic plumbing
tests do not satisfy those checks. The original raw captures are absent, so their
summaries are treated as saved results, not independently replayed input.

The plugin worker uses `fork` and is supported as the dedicated CLI/container.
Embedding it after other libraries start threads can deadlock inherited locks;
deadlines fail open but do not establish safe embedding. See the runner proposal
for a future executable JSON worker boundary.
