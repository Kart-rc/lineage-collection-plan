# Wave 0/1 design directions approved

Status: the user approved all four directions with "approve all 4" on
28 November 2026. Precise amendments and implementation are prepared locally.
The [amendment record](../factory/gates/proposed/G1-amendment-3-2026-11-28.md)
remains subject to human merge and does not grant G2/G3/G4 approval.

## Approved directions

1. **Approve an explicit complete-unit snapshot boundary.** Adopt the fields,
   identity, completion digest, empty/deleted distinction, generation ordering,
   and atomic replacement rules in [unit-snapshot-protocol.md](unit-snapshot-protocol.md).
   Use a separate completion manifest, written after immutable evidence, rather
   than treating any individual v2 event as a whole unit. The candidate implements
   a durable coordinator, separate manifest schema and static transport.
2. **Represent expression changes truthfully.** Add explicit unique
   `expressionHashes` to old/new change-version objects and `expression_changed`
   to the change-kind enum, as proposed in the same document. Retain supporting
   hashes as a set when independent evidence supports alternatives; do not pick
   an arbitrary winner. Superseding evidence from the same unit replaces its
   hash contribution atomically. The candidate emits old/new sets and rawRefs in
   schema v2; legacy hashless events retain schema v1.
3. **Compare deterministic scan content while retaining measured timings.**
   Approve normalized content parity excluding only `started`, `finished` and
   per-unit `duration_ms`. Keep the complete schema-valid manifest for audit and
   latency measurement. See [the exact CI proposal](../lineage-ci/contract-proposals.md).
4. **Approve a companion conformance-fixture entry point.** Use
   `lineage_ci.conformance` and `ConformanceFixture` as documented in the CI
   proposal, leaving the extractor's three published methods unchanged. This
   makes the required plugin acceptance checks discoverable and executable.

The user has separately authorized Docker Neo4j Community instead of stage
Neptune for this build. That decision is recorded in the run ledger; AWS testing
is not an outstanding gate for the current scope.

## Approval boundary and subsequent work

The design directions are approved. Their implementation and exact protected
amendments are prepared for human review/merge, with conformance and recovery
checks. This approval does not approve implementation at G2, change an oracle at
G3, waive holdout or fresh-run evidence, or release a wave at G4.

The repository's `factory/constitution.md` rule 1 says: "If the code and the spec
disagree, stop and propose a spec change; do not fix it in code alone." Its
protected-path rule says: "Only a person merges a change to these. Agents propose."
The precise interface amendments are therefore prepared in a separate proposal;
their implemented behavior is covered by compatibility and recovery checks.

Rollback: retain the approved v2 interfaces, disable local static-snapshot
publication, and keep runtime ingestion available. No migration of approved
production data has occurred.
