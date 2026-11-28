# Full reference readiness work

This increment supports WP-03, which serves IN-10 and IA-1. It prepares a
single hosted feasibility pilot of the pinned OpenTelemetry reference demo,
the capture bridge, and the separate Kafka / Neo4j Community / PostgreSQL
lineage platform. It does not accept WP-03 or the complete wave.

The four G1 design directions remain approved by the user. Their protected
contract changes are proposed in draft PR 8, and the implementation is in
draft PR 9. This increment changes no protected contract, oracle, threshold,
or gate decision.

The local Docker host uses vfs and has less than 4 GiB free. No full demo
pull, startup, or replacement of that shared infrastructure is attempted.
The pilot uses a fresh standard GitHub-hosted Ubuntu runner, without
production credentials or data. Raw synthetic captures and unrestricted
process diagnostics remain inside ignored state; only allowlisted metadata
reports are uploaded.

The starter checks all 28 long-running service identities and separates the
successful one-shot topic initializer. A static Go helper supplies the
readiness checks absent from five upstream service definitions. The pilot
independently enforces the 900-second startup limit, observes at least 600
seconds of load, checks fresh accepted receipts and persisted graph/outbox
counts, stops its own containers, and runs bounded offline smoke scoring.
The precision comparison uses the approved exact 0.95 floor.

Worker-image and probe preparation precede the measured container startup.
The reference image pulls remain inside that measurement. One feasibility
pilot does not establish the required three cold-start trials, original
capture replays, end-to-end p95 timings, holdout performance, or G2/G4.

Build accounting carries forward the initial candidate plus three prior
repair cycles as four. Readiness work is candidate 5. The single batched repair
candidate 6 addresses four independent review findings; a different host
does not reset the six-attempt limit. Successful measurement repetitions
are recorded as trials, not concealed source repair attempts. Token usage
is unavailable from the execution interface and is not invented.

See `checks/` for probe, test, and source evidence and `verification/` for
the independent review. Hosted results will be recorded separately from
local and mocked checks.
