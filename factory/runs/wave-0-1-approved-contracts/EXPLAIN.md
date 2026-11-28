# Why the approved changes fit together

A static extractor describes a complete unit of code. An individual evidence
message cannot tell the consumer whether the extractor finished, found no edges,
or lost some messages. The new completion message references immutable metadata,
its count and hash, and a generation reserved before extraction. Only a validated
complete set may replace the prior unit. Deletion is explicit, and failed work
cannot masquerade as a complete empty set.

Runtime evidence remains additive. Both kinds of receipt enter one ordered
acceptance journal, so recovery rebuilds their combined meaning. Receipt
acceptance and the change outbox commit before graph projection. If projection
fails, the durable journal repairs it; if acceptance fails, no unaccepted graph
revision is published. Delivery is at least once, with stable deduplication keys.

Expression hashes are sets of independently supported alternatives. Replacing
one unit removes only its contribution. A changed set is represented in changes
schema v2, with the previous and current sets explicitly present, including the
empty set when the last expression disappears. Legacy hashless events remain v1.

Mass-close safeguards continue to hold suspicious replacements. A hold survives
restart, and a reviewed release binds its receipt to an actor and unique action.
That audit record commits with acceptance and the outbox. Approval supplies the
new recorded time; the original valid time is preserved. Later runtime evidence
may remove the original reason for the hold without making it impossible to
release. Caller attribution does not implement authentication.

The CI runner keeps real timing measurements in the full manifest. It compares
only normalized content across wrappers, excluding the three specified timing
fields. Companion fixture entry points make plugin checks discoverable, while
approved family accuracy floors cannot be weakened by the fixture itself.

These are local single-writer implementations using a shared archive and free
Docker Neo4j. Their tests do not manufacture private holdout results, original
capture inputs, full-reference load measurements or a human release decision.
The precise protected contracts are in draft PR #8. Implementation remains a
local candidate, with its source identity preserved in this run's artifacts.
