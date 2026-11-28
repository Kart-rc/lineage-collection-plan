# Complete static unit transport

This candidate contract implements the four G1 directions approved by the user
on 28 November 2026. The exact amendment is prepared for human merge; this file
does not record a release approval.

The topic `lineage.unit-snapshots` carries
[`UNIT_SNAPSHOT_COMPLETE`](unit-snapshot.schema.json) manifests. The existing
`lineage.evidence` topic retains envelope v2 and must not receive these manifests.
The consumer uses a single ordered acceptance journal and merge engine for both
runtime evidence and static snapshots in each graph namespace.

## Identity, completion and immutable content

The manifest names the route, full unit revision, versioned producer, generation,
request ID, effective `validAt`, completion/deletion flags, count, event-set hash
and immutable object reference. `route` is `{repository, stage, pr}`. A merged
route has `pr: null`; a proposed route has a positive PR number matching `unit.pr`
and every enclosed event. Unit URNs must begin with that repository's canonical
`unit://git/<repository>/` prefix. Dot segments and foreign units are rejected.

The immutable object contains exactly `route`, `unit`, `producer`, `generation`,
`requestId`, `validAt`, `complete`, `deleted` and the complete `events` array. It
contains no claimed transaction time. Receipt acceptance supplies `recorded_at`.
Object bytes are UTF-8 JSON with sorted keys, compact separators, no NaN and no
ASCII escaping. `objectRef` is `snapshot://sha256/<SHA-256 of those exact bytes>`.
The local twin resolves only that content-addressed reference inside its configured
shared archive root; arbitrary paths, URLs, traversal and symlink escapes fail.

The event set is deduplicated and sorted by compact canonical JSON before staging.
`eventsHash` is `sha256:` followed by SHA-256 of the canonical JSON array of the
distinct canonical event strings in sorted order, matching `snapshot_digest`.
`eventCount` is the number of distinct events. Each event validates as envelope v2,
is static, replaces the same unit, and has the same unit revision and producer.
Unknown object fields and a count/hash/revision/route mismatch reject the whole
operation without accepting a generation or changing the graph.

A successful extraction with no edges is `complete: true`, `deleted: false`,
`eventCount: 0`. A removed unit is complete, deleted and empty. A failure, timeout
or partial result is neither; it cannot replace prior evidence. An extraction
explicitly declaring an opaque mapping may supply that complete mapping, subject
to the normal envelope and plugin rules.

## Generation and delivery

1. Before extraction, reserve a monotonically increasing generation durably,
   partitioned by route, unit and producer name without its release version.
   Retry of the same request ID returns the same reservation. Wall-clock order,
   Git SHA lexical order and extractor-version order do not allocate generations.
2. Write and durably synchronize the immutable metadata object before its
   completion manifest. Publish only the manifest to the completion topic after
   both exist. Retrying a completed request reuses the same object and manifest;
   conflicting content for its reserved generation fails visibly.
3. Verify the complete manifest, immutable bytes, event set and reservation before
   replacement. A partial upload changes no accepted evidence or graph state.
4. Equal-generation identical delivery is idempotent; conflicting content is an
   error. A delayed older generation may fill historical valid-time views, but
   cannot replace a newer effective generation or resurrect a deleted unit.
   Preserve a tombstone's generation. Maximum accepted generation remains
   monotonic while the ordered journal preserves historical receipts.
5. Apply mass-close checks using all evidence owners and the existing unchanged
   thresholds. A held operation stays pending and its source offset is not
   acknowledged. Preserve its receipt, operation identity and alert across
   restarts. Releasing a hold requires an attributable owner action bound to that
   pending receipt. Re-evaluate the unchanged threshold before release; unknown,
   never-held or conflicting releases fail. If later evidence removes the original
   mass-close reason, the same previously held receipt can still be accepted with
   its attributable release; it must not become permanently undrainable.
   Acceptance, the unique owner-action
   audit and changes outbox commit atomically. Historical reads before approval
   retain the prior graph; the approval time is the new transaction time, while
   the snapshot's original valid time remains intact. Retrying the same approved
   action is idempotent and can repair projection.
6. Accept the receipt, generation outcome and change outbox durably before graph
   projection. Projection failure leaves the source offset unacknowledged;
   restart or exact redelivery replays the same journal and repairs the graph.
   Failed receipt acceptance cannot leave a published graph revision.
7. Publish changes with stable content keys. A crash between broker acknowledgement
   and outbox checkpoint can repeat delivery; consumers deduplicate by key.
   Source offsets are acknowledged only after successful acceptance/projection.

## Routing and local deployment boundary

Merged ingestion may cover several repositories in one merged graph. Proposed
ingestion binds its state to one repository/PR route and a distinct graph namespace;
the default merged consumer rejects proposed manifests. The original object stays
intact for audit even if the merge adapter removes the PR marker inside that
already isolated overlay. PR state never advances a merged scan cache.

The reference implementation uses SQLite coordination and a shared local archive
volume. Publishers and the relevant consumer need access to that same root. Each
graph/archive has one writer. This contract does not claim distributed consensus,
multi-host shared-filesystem safety, S3 authorization or production rollout.
Deployment permissions must enforce the route boundary in a shared environment.
The local release command records an actor and action ID; those caller-supplied
values provide attribution, not authentication. A shared deployment must authorize
the caller before invoking it.
