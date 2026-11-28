# Wave 0/1 implementation review guide

This is a locally verified implementation candidate for human G2 review. It depends
on the four G1 contract directions approved by the user and proposed precisely in
[PR #8](https://github.com/Kart-rc/lineage-collection-plan/pull/8). The candidate is
not a completed-wave or release claim. Neo4j Community in Docker is the authorized
graph target; AWS Neptune is outside this acceptance scope.

## Review by component

The implementation draft groups its commits in dependency order:

1. Package/spec discovery, URNs and bounded metadata evidence emission.
2. Merge ownership, confidence, conditions, immutable history and expression diffs.
3. Identity, catalog, reconciliation and service-edge collection.
4. Immutable archives, complete-unit transport and combined acceptance/recovery.
5. Exported-telemetry bridge and the isolated Docker twin.
6. Incremental CI runner, plugin isolation and companion conformance fixtures.
7. Evaluation reports, oracle integrity and the aggregate-only private-job boundary.
8. CI coverage, operating documentation and review evidence.

The contract-only PR owns interface changes. This implementation draft adds no
oracle, threshold or gate-policy changes and records no human approval.

## What was measured

The final local candidate has **367 unique passing tests and no unresolved
failure or skip**: 45 runner tests and 322 platform tests. One of the platform
tests initially failed because its container restart cleanup raced startup. The
test was repaired to wait for committed Kafka offsets; its independent final
rerun passed on the unchanged worker image. The metrics preserve that initial
failure and deduplicate the repaired case instead of adding overlapping runs.

Spec checks report zero errors; all eight G3-pinned oracle hashes match.
Independent review reports PASS_WITH_RISK with zero open scoped findings.
Application code and tests remain at that reviewed source identity. The handoff
adds CI coverage for the actual static-snapshot worker container and separates
runner tests into a fresh interpreter before native networking libraries start
threads. Its specific workflow validation is recorded separately.

Selected machine-readable evidence and independent review are committed under
`factory/runs/wave-0-1-approved-contracts/`. The original complete local run packets,
source archives and earlier attempts remain in the shared workspace. Their local
archive references are provenance, not additional files required to run the code.
New workflow validation is under `factory/runs/wave-0-1-review-handoff/`.

## Acceptance that remains open

| Requirement | Remaining proof or action |
| --- | --- |
| Independent holdout | Independent owner/custody and signed aggregate family results tied to the candidate. Builders must never receive or author the private cases. |
| Original replay inputs | Original raw captures for checks explicitly tied to those runs, or a separately approved replacement baseline. Saved summaries cannot stand in for raw replay. |
| Full reference twin | Three cold starts, ten minutes of reference load, producer p99 overhead and required end-to-end timings. The current 32 GiB Docker-vfs host has insufficient capacity. |
| Traced end-to-end scenarios | Complete the later impact and authorized external feedback adapters where the existing scenarios require them. The WP-18 runner itself intentionally ships a stub; real technology extractors belong to later packages. |
| Human gates | Human merge of the exact G1 amendment, G2 review of implementation, and G4 only once its existing acceptance rules are met. |

No existing hard zero, holdout rule or original-specific acceptance requirement is
waived. Local single-writer archives and synthetic integration tests do not prove
production scale, remote storage authorization or the reference workload's timing.
See [operating instructions](11-local-implementation.md) and the
[twin guide](../twin/README.md).
