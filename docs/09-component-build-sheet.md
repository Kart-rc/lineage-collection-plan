# Component build sheet

Nov 27, 2026 · Takes each component of the breakdown in [`site/lineage-components.html`](../site/lineage-components.html) and states, for the reference slice in [doc 07](07-reference-slice-otel-demo.md), what it reads, what it produces, which work package builds it and what tests it. Decisions are in [doc 08](08-build-decisions.md); work packages in [doc 06](06-element-lineage-factory-spec.md).

## On a page

The review on 27 November found 11 of 26 components ready, 7 still describing the old design and 8 with a missing piece. After the decisions in doc 08 and the fixtures added with it, every component has an input on the real flow, a work package and a test. Two are deferred on purpose, not missing: the search index and the catalog UI.

**What "ready" means here.** A second review the same day found that "ready" meant scoped, not buildable. Each component had a work package and a named test, but no pass/fail threshold a builder could run against, and several tests still named the old slice. That gap is now closed in the spec pack ([`factory/`](../factory/README.md), decisions D33 to D37):

- every work package has measurable done-when lines ([`factory/work-packages/`](../factory/work-packages/README.md));
- every requirement is traced to visible scenarios;
- the interfaces are fixed as schemas;
- `code/spec_pack.py --check` keeps them consistent.

So "Ready" below means: an input on the real flow, a work package, and acceptance criteria a harness can check. It does not mean built. Two packages remain partly blocked on inputs from later stages:

- WP-28, the BI extractor, at field level until slice 2 names a BI tool;
- WP-22 and WP-25, the stream and feature extractors, until WP-01 writes the complement's golden edges.

| Status | Count | Components |
| --- | --- | --- |
| Ready | 25 | Everything below not marked deferred, including one new component, the check runner |
| Deferred to wave 5 | 2 | Search index, lineage UI and catalog projections |

What changed to get there:

- **Re-specified to the decisions:** gateway logs now cover traffic entering the estate only; a service edge builder reads traces; access history reads Postgres statistics first; the graph is Neptune, with Neo4j standing in locally.
- **Added work packages:** WP-16 reconciler, WP-17 owner and tier overlay, WP-19 service edge builder, WP-39 check runner.
- **Re-scoped work packages:** WP-13 to Neptune over Bolt, WP-22 to PyFlink code, WP-24 to the ORM writer, WP-26 to Postgres first.
- **Added fixtures:** owners and tiers, two contracts, checks for the incidents, resolver aliases taken from a real capture run, and the thin dbt model with its golden edges, schedule and circuit-breaker opt-in.
- **Ran the twin:** half an hour of the demo with two flags flipped, scored by two prototypes. The run confirmed the design, found one golden edge missing, and produced four more decisions (D29 to D32 in doc 08).

## The flow the components serve

```text
 SIGNALS                COLLECTORS                  BUS                 CORE                     STORES             USES
 demo + complement code  ─▶ code extractors ──┐
 demo.proto, init.sql,                         │
 catalog.yaml            ─▶ registry crawlers ─┤
 OTel spans, Envoy logs  ─▶ service edge builder├─▶ lineage.evidence ─▶ resolver ─▶ merger ─▶ scorer ─▶ writer ─▶ Neptune (Neo4j locally) ─▶ impact API, PR bot, gate
 OpenLineage (Feast)     ─▶ runtime normalizer ─┤   (envelope v2)        ▲                  │                     Postgres: aliases, queues ─▶ RCA, remediation
 pg_stat_statements      ─▶ access history ─────┤        │               │                  └─▶ reconciler          raw archive (files; S3 in AWS)
 checks.yaml             ─▶ check runner ───────┘        └─▶ raw archive  alias table
 flag flips, deploys     ─▶ change events ──────────────────────────────────────────────────────────────────────────▶ RCA timeline
```

## Components

**Signals**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| Gateway and mesh logs | Envoy's OTLP access log (`event.name = proxy.access`). Covers only traffic entering the shop: load generator to frontend-proxy to frontend. Internal calls bypass it (D7) | WP-19 | Golden edges `load-generator → frontend-proxy → frontend` | Ready |
| Registries | Compiled `pb/demo.proto`; `src/postgresql/init.sql` and Postgres `information_schema`; `fixtures/.../catalog.yaml` for owners and tiers; `src/flagd/demo.flagd.json` for flag nodes (D29); the complement's Feast registry | WP-17, WP-21 | Every golden node has a schema, an owner and a tier | Ready |
| Source code and PRs | The demo at tag 3.1.0 and the complement at commit `d1692f9`; real history for change replay | WP-20 to WP-25, WP-30 | 36 golden field edges; changes C1 to C6 | Ready |
| Running jobs and services | OpenTelemetry spans from every demo service; OpenLineage from Feast in the complement | WP-19, WP-27 | The capture run (see the evidence section) | Ready |
| Warehouse query history | Postgres `pg_stat_statements` in the twin. Snowflake `ACCESS_HISTORY` and Databricks lineage system tables for slice 2 (D22) | WP-26 | Writes to the three accounting tables; reads of `catalog.products` | Ready |
| Change and quality events | Flag flips in `flagd`, logged as change events (`capture-2026-11-27/change-events.jsonl` shows the format); container restarts and image tags as deploys; merged commits; check results from the check runner | WP-39, WP-41 | Incidents I1 to I4; change C7 | Ready |

**Collectors**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| Service edge builder (was: gateway log edge builder) | Trace walk for `CALLS`; producer and consumer spans joined on topic name for `PRODUCES` and `CONSUMES` (D7, D8); Envoy logs for ingress, by upstream cluster. Calls to flagd are scored as configuration reads (D29). Prototype: `code/observed_edges.py` | WP-19 | 13 upstream-asserted edges at 100% recall; golden service edges. First run: precision 1.00, recall 0.90 | Ready |
| Registry crawlers | Protobuf descriptors to topic and call fields; DDL to columns; `catalog.yaml` to `OWNS` at weight 0.50 and tiers; also writes resolver aliases | WP-17, WP-21 | Node completeness; alias coverage of every name in the capture | Ready |
| CI scanners | Run by one `lineage-ci` step per onboarded repository, through the extractor plugin contract (D39). Extractors: Go assembly in checkout (18 edges), C# ORM writes in accounting (17), PyFlink code and the declared feature registry in the complement, Feast and MLflow configs, dbt on jaffle-shop plus the thin model (D10) | WP-18, WP-20, WP-22, WP-23, WP-24, WP-25 | Golden field edges per unit; metamorphic tests | Ready |
| Runtime normalizer | Rolls spans up to one evidence event per edge per minute; maps Feast OpenLineage events, keeping the column facet | WP-19, WP-27 | Round trip of OpenLineage; evidence counts per edge | Ready |
| Access history puller | Database client spans first: they carry the service and the full statement. Then `pg_stat_statements` for clients without spans. SQLGlot's Postgres dialect splits batched statements and emits `READS` and `WRITES` with columns. Never attributes by login, because accounting and product-catalog share one (D27). Adapters for Snowflake and Databricks follow for slice 2 | WP-26 | Accounting writes three tables and the 17 golden columns; product-catalog reads one table. First run: all confirmed | Ready |
| Evidence library | Envelope v2 JSON Schema and emit function, shared by every collector | WP-11 | Schema tests; v1 compatibility | Ready |

**Bus**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| `lineage.evidence` topic | A separate single-node Kafka in the twin, never the demo's own broker, so lineage traffic does not change what is being measured (D23). Amazon MSK in AWS | WP-03, WP-11 | Replay determinism | Ready |
| Raw archive | Parquet files by source and day in the twin; Iceberg on S3 in AWS | WP-12 | Rebuild from the archive gives the same graph hash | Ready |

**Core**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| Identity resolver | Maps span service names, gRPC service names, configured host:port addresses, Envoy clusters, user agents, consumer groups, topic and table names to URNs, using `fixtures/.../aliases.json`. Never aliases an IP (D31) | WP-15 | Every name in the capture resolves; no duplicate nodes. First run: 55 of 55; 3,103 IP references left unresolved by rule | Ready |
| Edge merger | One row per edge per source; static evidence owned by its unit | WP-12 | Removal and idempotency scenarios | Ready |
| Confidence scorer | Noisy-OR over the plan's weights; states | WP-12 | Property tests; golden states | Ready |
| Daily reconciler | Queues static-only, runtime-only, declared-never-seen and disagreeing edges to the owner in `catalog.yaml` | WP-16 | Known cases from the first run: `frontend → shipping` and `frontend → currency` in code, not seen at runtime; six services that read a flag in code but emit no flagd span | Ready |
| Versioned graph writer | Writes each edge version as its own relationship with `valid_from`, `valid_to` and `recorded_at`, plus any `condition` and its latent or active state (D30), in the openCypher subset Neptune supports, over Bolt (D12) | WP-13 | Bitemporal property tests against Neo4j locally and a Neptune instance in stage | Ready |

**Stores**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| Lineage graph | Neptune in AWS; Neo4j Community in the twin, both reached over Bolt with openCypher (D12, D23) | WP-13 | As above | Ready |
| Alias table and queues | Postgres in the twin, Aurora in AWS | WP-15, WP-16 | Resolver and reconciler tests | Ready |
| Search index | Deferred. Lookups go through the alias table until wave 5; then OpenSearch with Neptune's full-text integration | WP-50 | Not in waves 0 to 2 | Deferred |

**Uses**

| Component | On the reference slice | Work package | Tested by | Status |
| --- | --- | --- | --- | --- |
| Lineage UI and catalog | Deferred. Neo4j Browser is enough to inspect the twin; projections to Snowflake Horizon and Unity Catalog come in wave 5 for slice 2 | WP-50 | Not in waves 0 to 2 | Deferred |
| Impact API and PR bot | Element diff and downstream walk on pull requests against the demo fork | WP-31, WP-32, WP-33, WP-51 | Changes C1 to C6 plus held-out authored changes | Ready |
| Contract gate | Enforces `contracts/orders.contract.yaml` and `contracts/accounting.contract.yaml`, and the five must-not-flow rules over active and latent edges (D30) | WP-34 | C1 must block; a field added with a new number must pass; C7 must report the latent card path before the flag is switched on | Ready |
| DQ alerts and RCA | Starts from the first failing check, walks what its node depends on, keeps the callee where failing calls stop, ranks the change events that touch it (D32), then plans remediation | WP-40 to WP-44 | Incidents I1 to I4 in the twin. First run: I1's flag ranked first | Ready |
| Check runner (new) | Evaluates `fixtures/.../checks.yaml` every minute over a two-minute window, widening rate windows until the baseline expects 20 events, and publishes results as quality assertions on the evidence topic. Prototype: `code/run_checks.py` | WP-39 | Each check fails on its incidents and passes on the baseline. First run: I1 caught in 2 minutes, no false alarms | Ready |

## Evidence from the first capture run

The twin ran on 27 November 2026 from 14:06 to 14:39 UTC: demo 3.1.0, 23 containers, the load generator's HTTP users, the capture add-on and the sandbox override. Two flags were flipped (UTC):

- `emitRawPii` on from 14:22:19 to 14:24:10 (change C7);
- `paymentFailure` at 50% from 14:24:55 to 14:30:09 (incident I1).

By the end, 104 orders had passed through the topic into `accounting."order"`. The summaries are in [`fixtures/otel-demo-3.1.0/capture-2026-11-27/`](../fixtures/otel-demo-3.1.0/capture-2026-11-27/); the raw capture, 96 MB of OTLP JSON, is not kept.

| Component | What the run showed |
| --- | --- |
| Service edge builder | 18 service and topic edges observed, all of them golden: precision 1.00, recall 0.90, and 1.00 on the 13 upstream-asserted edges. The two misses, `frontend → currency` and `frontend → shipping`, are reached only from browser pages the load generator does not open |
| Kafka join (D8) | Checkout's producer spans and the consumer spans of accounting and fraud-detection all name `orders`. The broker metrics list both consumer groups, with lag between 0 and 1. At 14:17 the topic offset, 30, matched the 30 rows in `accounting."order"` |
| Access history | Six database edges, all golden. SQLGlot splits accounting's batched insert into three tables and 17 columns, and all 17 are the golden ones. Product-catalog reads 8 columns of `catalog.products`. Connection spans with no statement are skipped |
| Identity resolver | 55 distinct names across traces, logs and metrics resolve or are declared non-entities; none is missing. 3,103 references by IP address are left unresolved, by rule (D31) |
| Daily reconciler | First queue entries: the two calls seen only in code, and six services that read a flag in code but emit no flagd span. Three of those six (checkout, product-catalog, email) are behind I2 to I4 |
| Flag-gated lineage (D30) | 13 seconds after `emitRawPii` went on, checkout spans arrived with `user.hash` and a masked card number, and payment spans with a masked card number. No CVV or raw email ever reached the export. None of the 56 order spans after the flag went off carried any of these attributes |
| Check runner | Ten minutes of baseline and six of recovery with no false alarm. In I1, checkout errors failed 2.0 minutes after the flip and passed again 47 seconds after the flag went off. The order-rate and accounting insert-rate checks failed after 3.0 minutes and recovered after 2.8. Lag and latency stayed green, as they should for I1 |
| Root-cause narrowing (D32) | From the first failing check (checkout errors), the walk covered 9 dependencies and found failing calls stopping at payment. `paymentFailure` ranked first. `emitRawPii` ranked second: payment reads it too, and only time separated the two |

### Second run: the incident corpus

From 16:54 to 18:43 UTC the twin ran again, with 15 simulated shoppers and two more checks fixed in advance (checkout latency, accounting consumer lag). After a 12-minute baseline, a script injected nine incidents, each on for 4 minutes. Scores come from `code/run_checks.py --replay` with the D35 score; data in [`capture-2026-11-27/incident-replay.json`](../fixtures/otel-demo-3.1.0/capture-2026-11-27/incident-replay.json).

| Incident | Family | First check to fail | Minutes after injection | True cause ranked |
| --- | --- | --- | --- | --- |
| I1 (first run) | dependency failure | checkout errors | 2.0 | 1st |
| I2 | consumer lag | order rate, fraud-detection lag and accounting lag together | 0.8 | 1st |
| I3 | storage contention | checkout errors, then catalog latency | 1.8 | 1st |
| I4 | unreachable address | checkout errors | 0.8 | 1st |
| I5 | silent failure | none | – | not detected |
| I6 | dependency failure | checkout errors | 1.6 | 1st |
| I7 | consumer outage | accounting insert rate | 1.8 | 1st |
| I8 | latency only | checkout latency | 1.8 | 1st |
| I9 | decoy outside the lineage | checkout errors | 1.8 | 1st; the decoy scored a lineage term of 0 |
| I10 | volume surge | none | – | not detected |

Over the ten incidents:

- 8 were detected, every one within 2 minutes.
- In all 8, the true cause ranked first.

Against IR-5 that is 80% first (the bar is 70%) and 80% in the top three (the bar is 90%), because the two undetected incidents count as misses.

**What the corpus taught (D38):**

- **Ranking leaned on time.** Only I1, I3 and I9 had failing calls that led to the cause. Elsewhere lineage narrowed the field to "a dependency", and time decided. The incidents were nine minutes apart, which flatters this. The holdout needs near-simultaneous changes on different dependencies.
- **A silent failure fires nothing.** `cartFailure` breaks `EmptyCart`, and checkout ignores the error, so orders keep flowing while carts keep old items. Lineage cannot start without a failing check. Items per order moved, but within baseline noise, so a check for it must be designed and then validated on a fresh run.
- **A cause from callers is out of reach.** The traffic flood fired no check. Had one failed, the dependency walk would still not have reached the load generator.
- **The injection tool needs the targeting rule.** The first attempt at I6 changed `productCatalogFailure`'s default variant, which its targeting rule overrides, so nothing happened. WP-03 now flips targeted flags through the rule, as flagd-ui does.
- **One pre-registered threshold was too high.** Accounting consumer lag stayed under 100 during a 4-minute outage, about 36 unread messages at this load. It is kept unchanged; the insert-rate check caught the outage instead.
- **The cause of I3 is in access history.** Product-catalog's database spans contain the `LOCK TABLE catalog.products IN ACCESS EXCLUSIVE MODE` statement. That is a candidate source of change events for the timeline (WP-41).
- **The second capture scored the same as the first.** Service and topic edges: precision 1.00 and recall 0.90, all 13 upstream-asserted edges. All 55 names resolved.
- **The thin dbt model built in the twin.** 4 of 4 models; `fct_order_value` holds 1,098 rows, one per order. Its reads are attributed to `analytics_dbt`, apart from accounting's `astronomy_user`.

Found and fixed during the run:

- **A missing golden edge.** The golden graph lacked `frontend → currency`, though doc 07 named it. It is now added, with a citation, and waits for G3 sign-off.
- **The table parser.** It broke on `accounting."order"` and on batched statements, and now uses SQLGlot.
- **A YAML key.** PyYAML reads the key `on:` as `true`, so the checks now name their node with `node:`.
- **False alarms in rate checks.** At six events per window they raised one, so they now widen their window to 20 expected events.
- **The error-share check.** It read "no data" until the first error series existed; a missing counter now counts as zero.
- **Two signals the plan had not used.** The collector's own per-table insert counter replaces polling `count(*)`, and database spans give column-level writes at runtime.

## Build order

Unchanged from doc 06, with the new work packages slotted in:

| Wave | Work packages |
| --- | --- |
| 0 Oracle and twin | WP-00 to WP-04, with the twin now runnable here and the fixtures in place |
| 1 Core | WP-10 to WP-19 (WP-18: the `lineage-ci` runner and repository onboarding) |
| 2 Extractors | WP-20 to WP-29 |
| 3 Incremental and impact | WP-30 to WP-34 |
| 4 Detect and resolve | WP-39 to WP-44 |
| 5 Projections and operations | WP-50 to WP-53, search index, catalog UI |
