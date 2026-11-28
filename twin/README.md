# Local reference twin (WP-03)

The starter renders the pinned OpenTelemetry Demo 3.1.0 full profile, its capture
add-on, and a separate lineage Kafka, Neo4j Community and PostgreSQL. Full startup
also includes the existing runtime worker and capture bridge. The source
checkout is read only. The 26 demo/platform images are locked by digest in `images.lock.json`;
the three manifest-only resolutions for frontend, payment and load-generator
are Linux AMD64. The pinned source commit is
`dedc0178918e260823323b8d95005a8cb924b007`.

Use a Python environment with this project's dependencies and Docker Compose
2.40 or newer. Obtain the demo checkout at the pinned commit, build the current
worker image as `lineage-platform:local`, and build the static Linux probe from
`twin/probe` into ignored `twin/.state/bin/lineage-healthcheck`. Then run from the
repository root:

```sh
python3 twin/start.py up --demo /tmp/lineage-reference-otel-demo
```

Full startup has one monotonic 900-second deadline. `--timeout` may shorten it;
the CLI and Python entrypoint reject nonpositive, nonfinite or above-900 values.
The deadline covers preparation, image inspection/pulls, infrastructure startup,
topic setup, all remaining services, and final readiness inspection. It first
starts the three lineage infrastructure services, runs the topic initializer with
`compose run --rm`, then starts the demo, worker and bridge. All **28** expected
long-running services must be present exactly once, running and healthy before
the deadline. Their identities are fixed for the pinned reference slice, independent
of the rendered configuration; missing or additional definitions also fail startup.
The completed initializer is recorded separately as a successful
prerequisite; it is never counted as a healthy container. `--worker-image` can
select a different already-built local candidate. The starter records and uses
its immutable Docker image ID and never implicitly builds or pulls that image.

`startup.json` in the selected ignored state directory records success or failure,
the phase, elapsed time, expected service identities, health results, probe SHA-256
and worker image ID. Late, missing, duplicate, stopped or unhealthy services produce
a nonzero exit. Failures after state initialization are reported using controlled
categories; raw subprocess output and exceptions are not printed or stored. If
the filesystem cannot write the report, a metadata-only `report_unwritable` error
is emitted instead. An interrupted or timed-out Docker client can leave containers
running; the report does not claim automatic rollback.

Five previously absent readiness checks are added only to the generated Compose
configuration. Cart uses the pinned image's `/bin/grpc_health_probe` against its
gRPC health service. Flagd uses HTTP `8014/readyz`, which proves its initial flag
sync; it does not prove later sync freshness. The OTel collector enables its local
`health_check` extension on `127.0.0.1:13133`. Accounting and fraud detection use
read-only Kafka DescribeGroups requests: their group must be Stable, with an
`orders` assignment belonging to a member whose host matches that container's
local IP. Those checks neither consume messages nor join/modify consumer groups.
The helper is mounted read-only at `/lineage-healthcheck`.

The bridge starts against precreated empty mode-0600 capture files inside the
mode-0700 capture directory. Empty-input readiness proves startup only; the smoke
run must separately demonstrate fresh telemetry and graph/archive progress.
The demo load generator is explicitly configured for autostart, five HTTP users,
and its non-headless web/API mode regardless of inherited host settings. The pilot
must still observe its running state, user count and advancing request counters.
`prepare` continues to render the base 26-service configuration without requiring
the helper or worker image; `platform` starts and strictly checks only the three
lineage infrastructure services. Full `up` assembles its additional services in
ignored generated configuration without modifying the standalone Compose files.

This command includes the IPv4 and no-ulimit sandbox adaptations. It uses the
unique Compose project `lineage-twin`, removes upstream global container names,
binds published ports to loopback, and removes the collector's Docker socket and
host-root mounts. It never removes volumes. `python3 twin/start.py down` stops
only this project. No command prunes Docker resources.

The current 32 GiB managed host uses Docker's `vfs` driver. Pulling the full demo
exhausted its filesystem before three images finished. Full startup now stops
before pulling when `vfs` has less than 50 GiB free. This is a conservative guard,
not a measured full-stack capacity requirement. Use an overlay-backed Docker
host or more disk for the full reference run. A smaller platform-only run is:

```sh
python3 twin/start.py platform --demo /tmp/lineage-reference-otel-demo
python3 twin/start.py status
LINEAGE_TWIN_LIVE=1 python3 -m pytest tests/test_twin_faults.py tests/test_twin_infrastructure.py -q
```

| Service | Host endpoint | Container endpoint |
| --- | --- | --- |
| Lineage Kafka | `127.0.0.1:19092` | `lineage-kafka:9092` |
| Neo4j Bolt | `127.0.0.1:17687` | `lineage-neo4j:7687` |
| Neo4j browser | `http://127.0.0.1:17474` | `lineage-neo4j:7474` |
| Lineage PostgreSQL | `127.0.0.1:15432` | `lineage-postgres:5432` |
| Demo storefront | `http://127.0.0.1:18080` | `frontend-proxy:8080` |
| Demo flag UI | `http://127.0.0.1:14000` | `flagd-ui:4000` |
| Demo load generator | `http://127.0.0.1:18089` | `load-generator:8089` |
| Demo OFREP | `http://127.0.0.1:18016` | `flagd:8016` |

Local disposable credentials: Neo4j user `neo4j`; PostgreSQL database and user
`lineage`; both use `lineage-local-only`. These credentials are restricted to
loopback access and the isolated lineage network. Demo Kafka and `astronomy-db`
remain on the demo network and never carry lineage evidence.

`lineage-archive` is the named volume for the platform's metadata-only Parquet
archive. `worker.compose.yaml` mounts it into the runtime worker; start that worker
and its topic initializer with `sh twin/run-platform.sh`. See
[`docs/11-local-implementation.md`](../docs/11-local-implementation.md) for build
instructions and the delivery guarantees. PostgreSQL initializes aliases and
reconciliation queue tables. The platform currently has single-node local
durability; it is not an HA deployment.

`lineage-snapshot-archive` is the separate shared volume for durable static
reservations and immutable complete-unit objects. The worker mounts it at
`/snapshot-archive` and consumes completion manifests on `lineage.unit-snapshots`.
A CI publisher must mount this same volume read/write and use
`--snapshot-root /snapshot-archive --transport kafka --broker lineage-kafka:9092`
on the isolated lineage network. The image initializes the volume for UID 1000.
Proposed PR consumers require a separate archive and their explicit route/namespace;
the default worker accepts only merged completions. See the runner guide for
standalone commands. These local shared volumes do not implement remote storage
authorization or distributed coordination.

For exported-telemetry forwarding, build the current worker image and run
`sh twin/run-collector.sh` after raw `traces.jsonl` or `logs.jsonl` exists.
`collector.compose.yaml` is an optional profile with read-only capture/fault
mounts and separate durable metadata progress. The runtime guide documents
input bounds, health checks and source rotation handling. Default bounds fit
small local runs; they do not establish full reference-capture capacity.

Fault commands are:

```sh
python3 twin/flip.py flag paymentFailure '50%'
python3 twin/flip.py flag paymentFailure off
python3 twin/flip.py flag productCatalogFailure on
python3 twin/flip.py flag productCatalogFailure off
python3 twin/flip.py stop accounting
python3 twin/flip.py start accounting
```

The targeted flag updates `targeting.if[1]`, matching flagd-ui's branch selection.
Unsupported targeting structures fail before mutation. Changes append to
`twin/.state/changes.jsonl` only after a successful action, with strict schema and
format validation. A separate fsynced `change-intents.jsonl` records intent before
the side effect. After an interrupted process, compare intent refs against
committed event refs and inspect the flag/container state before replaying an
uncommitted intent. Concurrent invocations serialize through a local file lock.
The fault tool does not stop/start lineage infrastructure. Kafka forwarding of
the committed events is a worker responsibility.

Only the twin's authorized synthetic traffic belongs in this environment. Raw
demo OTLP capture stays in ignored, mode-0700 `twin/.state/capture`; never copy it
into source control, run records or a platform archive. Debug raw export is
disabled. Only projected metadata envelopes may enter lineage Kafka/Parquet.
Keep capture local even if a synthetic flag emits PII-shaped attributes.

Validation on 2026-11-28: 14 tests passed in 5.68 seconds, including actual
Neo4j write/read/delete, Kafka publish/consume, and PostgreSQL schema checks.
The pinned flagd service also evaluated the targeted rule through OFREP v1:
the matching branch became true and the other branch stayed false; the flag
was restored to off. Real stop/start operations produced schema-valid events.
The upstream checkout remained clean. Details are in
`validation-2026-11-28.json`.

The assembled runtime worker also passed a separate synthetic metadata check:
two identical Kafka deliveries produced one accepted Parquet receipt, one graph
assertion and one logical change. Those counts survived a worker restart with
the named volume retained. Evidence is in
`factory/runs/wave-0-1/checks/container-worker-smoke.json`. This establishes local
runtime plumbing, not full reference-workload collection or latency acceptance.

WP-03 is **incomplete**. The full-demo cold start gate (3/3 within 15 minutes),
ten-minute live service-edge precision score and traced visible timing scenarios
are not proven by these infrastructure and synthetic plumbing checks. The
new readiness probes and strict starter still require a fresh full-workload run;
source and mocked failure tests do not establish the cold-start or load gates.
No holdout results were accessed or inferred.

## Hosted feasibility pilot

`full-reference-pilot.yml` runs one fresh standard GitHub-hosted Ubuntu job.
It checks out the pinned demo, builds the static probe with Go 1.27.4 and the
candidate worker image, then invokes `twin/pilot.py`. Image/probe preparation
is reported separately from the measured container start; reference image
pulls stay inside the 900-second startup window.

For the same measurement on a fresh disposable Linux AMD64 Docker host:

```sh
sh twin/build-probe.sh
docker build -f twin/worker.Dockerfile -t lineage-platform:pilot .
python twin/pilot.py --demo /path/to/pinned-demo --state twin/.state \
  --output pilot-results --worker-image lineage-platform:pilot
```

The pilot refuses an existing `lineage-twin` project, its retained volumes,
or prior capture/startup state. It does not clean a shared local environment
to make that check pass. The static binary and its build cache can already
exist in the ignored state directory. Only a project acquired by this
invocation is stopped; the workflow's final Compose cleanup also requires
the current invocation token. Neither cleanup deletes named volumes.

During at least 600 measured seconds, the pilot checks the exact 28 healthy
services, active Locust users and increasing aggregate request counts,
resource headroom, accepted metadata receipts, and persisted graph/outbox
counts. It stops its containers before the offline scorer, whose parser is
capped at 8 GiB and 180 seconds. These checks establish only their stated
scope; they do not measure the full IN-10 or IA-1 p95 requirements.

Only `pilot.json`, `startup.json`, and `smoke.json` under `pilot-results` are
uploaded. Raw OTLP and unrestricted process diagnostics remain in ignored
state. The pilot retains failures and does not automatically retry. A
successful pilot still requires three separately recorded fresh cold-start
trials and the remaining work-package and human acceptance gates.
