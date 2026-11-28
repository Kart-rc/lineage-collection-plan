# Complete unit snapshots and expression changes

The user approved these directions with “approve all 4” on 28 November 2026.
The candidate implements them; exact protected amendments remain prepared for
human merge in the [G1 amendment](../factory/gates/proposed/G1-amendment-3-2026-11-28.md).

## Complete unit transport

The normative candidate [protocol](../factory/specs/evidence/interfaces/unit-snapshot-protocol.md)
and [manifest schema](../factory/specs/evidence/interfaces/unit-snapshot.schema.json)
define the boundary missing from individual `replaces: unit` envelopes.

`SnapshotCoordinator` durably reserves a generation before extraction, scoped by
repository/PR route, unit and producer name. `SnapshotPublisher` writes immutable
metadata first and publishes its completion manifest on `lineage.unit-snapshots`.
A successful empty extraction and a deleted unit are explicit complete sets;
a failed or partial extraction cannot replace accepted evidence. The local
implementation uses a shared archive volume and SQLite coordination.

`RuntimePipeline` validates the whole object, reservation, hash, count, revision
and route. It accepts runtime receipts and static snapshots into one ordered
journal before graph projection. Retries repair projection without duplicating
logical receipts. Delayed older snapshots may fill history but cannot resurrect
newer deleted units. Proposed routes use isolated archives and graph namespaces.
Mass-close safeguards and evidence ownership remain in force.

The in-process `UnitSnapshot` records `unit`, `producer`, `generation`, `valid_at`,
`recorded_at`, `events`, `digest`, `complete` and `deleted`. Wire objects omit
`recorded_at`; acceptance supplies the actual transaction time. The durable
coordinator allocates generations starting at one. `snapshot_digest(events)` hashes
an ordered, deduplicated set of canonical event strings. The wire protocol also
hashes exact immutable object bytes. Bare replacing envelopes remain invalid at
the runtime ingestion boundary.

## Expression changes

[Changes schema v2](../factory/specs/changes/interfaces/lineage-changes.schema.json)
adds `expression_changed` and explicit old/new `expressionHashes` sets. Replacing
one unit's evidence replaces its contribution; independent owners retain their
supported alternatives. Losing the final hash emits an explicit empty set.
Opened/closed transitions retain precedence; complete version objects also carry
state, confidence and condition changes. Hashless legacy events remain schema v1.
Consumers must accept v2 before producers enable these events.

Expression changes append immutable bitemporal history with evidence citations.
They no longer trigger an unsupported-expression hold. Existing mass-close holds
still require an attributable owner action. Real Neo4j tests cover correction,
rebuild and historical queries; no Neptune compatibility claim follows.

## Acceptance boundary

These implementations do not create holdout evidence or approve G2/G4. The twin
uses one writer per graph/archive; distributed coordination, remote archive
access controls and production rollout need separate validation. Approved
thresholds and the protected oracle remain unchanged.
