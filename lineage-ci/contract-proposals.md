# WP-18 directions and remaining acceptance limits

The user approved manifest normalization, complete-unit transport, conformance
fixture packaging, and the associated G1 directions on 28 November 2026. This
records implementation consequences, not a human merge or release sign-off.
Protected interfaces and gate records are maintained separately.

## Truthful timing and normalized parity

`unit-manifest.json` retains real `started`, `finished`, and per-unit
`duration_ms`. Cross-wrapper equality compares `scan-content.json`, which omits
only those operational timings. No fabricated deterministic timestamps are
used. Total scan wall time is a conservative upper bound on runner overhead.

## Durable complete-unit publication

Before extraction, a persistent coordinator reserves a generation scoped by
route, unit and producer name. A request identity includes commit, source and
schema hashes, extractor version and deletion flag. Exact retries reuse their
reservation; later revisions receive higher generations. The publisher writes
and flushes an immutable metadata object before publishing its complete-set
manifest on the separate completion topic. Empty and deleted sets have explicit
unit revisions. Proposed routes retain their repository/PR identity and cannot
enter the merged graph namespace.

The runner advances the merged cache only after every intended complete set is
published and extraction is complete. An interrupted or failed extraction emits
only local opaque diagnostics with `replaces: none`; it cannot close earlier
lineage. A publication failure keeps the baseline and the immutable objects for
retry. Local durable publication and Kafka acknowledgment are both distinct
from downstream graph acceptance. The implemented archive adapter uses one
shared filesystem; no S3 or distributed-filesystem behavior is claimed.

## Fixture packaging and process boundary

Each `lineage_ci.extractors` entry point requires a matching callable in
`lineage_ci.conformance` returning `ConformanceFixture`. The suite executes
golden, three-run determinism, formatting/alias metamorphic, unreadable-input,
schema, deadline and isolation checks before registration. The extractor's
`detect`, `inputs` and `extract` methods remain unchanged.

Use the dedicated CLI: workers fork before Kafka starts native networking
threads. Existing multithreaded embedding is unsupported because inherited
runtime locks can deadlock a worker. Deadlines contain those failures but do
not establish thread safety. The integrated in-process suite reports Python's
fork warnings rather than suppressing them. A clean-interpreter JSON worker
is needed before embedded multithreaded use can be supported.

## Remaining acceptance limits

Local alert records are not external alert delivery, prepared comments are not
posted comments, and PR snapshot publication is not an impact report. Those
later adapters remain unavailable. The stub does not establish real dbt
extraction. Untracked build artifacts need a pinned artifact contract before
they can be consumed reproducibly. Holdout, required human review, and release
approval must still be recorded independently; approval of implementation
direction does not establish them.
