# End-to-End Lineage: Top-Down Implementation Plan

Nov 21, 2026 · @kart

## Plan on a page

Build lineage top down: start with gateway logs to see which services actually call each other, overlay components and catalog metadata so every node has an owner, then add static code and runtime edges to reach topics, tables, features and fields. Prove it on one vertical slice before widening. The first slice takes about 18 weeks, and every phase ships something a team can use that week.

The components, the four process flows and the AWS deployment behind this plan are in Architecture and deployment.

Where each collector gets its data, how their evidence merges into one graph, and the step-by-step build with code are in Collection and build guide.

**The four moves**

1. **Gateway first.** API gateway and service mesh access logs already record who called what, how often and how fast. Aggregated, they give a service dependency map in weeks with no code change and high confidence that each edge exists.
2. **Overlay components and catalog.** Map client IDs, hostnames and IAM roles to services, then attach owner, tier, on-call, repo, and the topics, tables, features and models each service owns. Edges become actionable: you know who to call.
3. **Augment with static and runtime edges.** Static code analysis in CI adds what the code says it reads and writes, down to fields. Runtime events (OpenLineage, OpenTelemetry, warehouse access logs) confirm what actually ran. Each source adds evidence to an edge rather than a separate graph.
4. **Raise accuracy on one vertical slice.** Measure every phase against an owner-reviewed golden graph, replay past schema changes and incidents, and reconcile sources daily until precision and recall pass the bar. Only then widen.

**The vertical slice:** card payment authorization through to the fraud model. It crosses a microservice (payments-svc), a stream (the auth.events.v1 topic and the txn-enrichment Flink job), an analytics table (fct\_card\_auth) and an ML feature (mcc\_decline\_7d feeding the fraud-score-v12 model). Names are illustrative; pick the equivalent in your estate.

**Phases, value and gates**

| Phase | Weeks | What you get | Measurable value | Exit gate |
| --- | --- | --- | --- | --- |
| 0. Baseline and golden graph | 1 to 2 | Owner-reviewed ground truth for the slice, baseline incident and change metrics, graph store running | A yardstick: every later claim of accuracy is measured against it | Golden graph signed off by all slice owners |
| 1. Gateway edges | 2 to 5 | Service dependency map from gateway and mesh logs; "who calls X" in seconds | Service-level blast radius on day one; recall of golden service edges | At least 90% of golden service-to-service edges found |
| 2. Components and catalog | 4 to 7 | Every node has owner, tier and on-call; topics, tables, features and models added as nodes | Incidents route to the right team in minutes; orphan services surface | 95% of nodes owned; under 5% unresolved callers |
| 3. Static code edges | 6 to 11 | Field-level edges from code, schemas, SQL and feature definitions; PR impact report in warn mode | Impact of a change shown before merge | Change replay finds at least 8 of 10 consumers that actually broke |
| 4. Runtime edges | 9 to 14 | OpenLineage, OTel and access-log edges; daily reconciliation queue | Static guesses confirmed or retired; hidden consumers found | Edge precision at least 95%; freshness under 15 minutes |
| 5. Contracts, DQ and RCA | 13 to 18 | Contracts on the slice's topic and table, DQ results on the graph, RCA from any failing check | Breaking changes blocked; alerts arrive with the upstream path and a remediation plan | MTTD and MTTR halved against baseline on replay and live incidents |
| 6. Widen | 19 onward | Same playbook on the next slices | Each new slice in about half the time of the first | Coverage targets per tier |

&#91;embedded content: roadmap · 7 phases by week, first slice proven at week 18\]

Phases overlap because each one starts as soon as the data it needs exists; none is declared done until its exit gate is measured.

**The value of each phase, on one real change.** Pick an outcome to replay PR #482, the column rename worked through in Phases 3 and 5.

&#91;embedded content: simulator · one schema change replayed at each phase\]

## How the phases build on each other

Think of it as mapping a city. You survey first so you can tell a good map from a bad one, then draw the roads, then add addresses and owners, then read the blueprints of what is about to be built, then put up traffic cameras to check the map against real traffic, and only then write traffic laws and alarms. Each phase is useful on its own, and each one hands the next exactly what it is missing.

&#91;embedded content: the seven phases as one chain: analogy, hand-off and value\]

### Why top down, and why in this order

The bottom-up alternative is to instrument every application with OpenLineage first. That gives precise edges for the few systems done early and nothing for the rest for months, so leaders see no value and teams see only asks. Top down starts broad and cheap, with estate-wide coverage at coarse grain in weeks, then adds precision only on the slice where it pays. Each source covers the previous one's blind spot, and where two sources disagree, the disagreement is itself a finding.

| Source | What it sees | What it is blind to | Who covers the gap |
| --- | --- | --- | --- |
| Gateway and mesh logs (Phase 1) | Every synchronous call, with no code changes | Kafka, data stores and fields | Phases 2 to 4 |
| Catalog and registries (Phase 2) | Owners, tiers, schemas and data assets | Can be stale or incomplete | Phase 4 checks it against runtime |
| Static code in CI (Phase 3) | Intent before merge, down to the field | Dead code, feature flags, notebooks, runtime config | Phase 4 |
| Runtime telemetry (Phase 4) | What actually ran | Rare paths, and only after the fact | Phase 3 covers before merge |
| Contracts and DQ (Phase 5) | Breaking changes at boundaries and bad data | Need a trusted list of consumers to be useful | Phases 1 to 4 supply it |

### The two-minute version

**For an executive audience:**

1. **The problem:** a change in one system quietly breaks reports, features and models downstream, and we usually find out from the people affected. Phase 0 measures how often and how long it takes to fix.
2. **The approach:** build a dependency map from data we already collect, sharpen it on one critical flow, then put guardrails on that flow.
3. **The value at each step:** blast radius in weeks, named owners next, impact shown before a change merges, and then detection and resolution time halved on the slice.
4. **The decision needed:** agree the first slice and name an owner in each team on it.

**For an engineering audience:**

1. **The model:** nodes are services, topics, tables, features and models, and each edge carries evidence from several sources combined into one confidence score.
2. **The collectors:** gateway and mesh logs, catalog crawlers, static scanners in CI that emit OpenLineage, and runtime OpenTelemetry and OpenLineage events.
3. **The lifecycle:** edges move from candidate to probable to confirmed as evidence agrees. Static-only edges go dormant, and runtime-only edges surface as undeclared consumers.
4. **The guardrails:** the PR bot warns first and blocks only tier 1 changes, and only once precision on the golden graph reaches 95%.
5. **What we ask of teams:** nothing in Phase 1, a catalog file in Phase 2, and one CI step in Phase 3.

### Questions you will get

- **How do we know it is accurate?** Every collector is scored against the golden graph from Phase 0, by precision and recall per edge type, and the number is published.
- **Does this read our data?** No. Every source is metadata: who called whom, which job read which table and which field. Payloads are never collected.
- **What if we stop after Phase 2?** We keep a live, owned dependency map with blast-radius queries. Each phase pays for itself, and the later ones add prevention.
- **Why not just turn on a catalog's lineage?** A catalog stores and shows lineage well, but it only sees the systems that report to it. The value here is combining gateway, code and runtime evidence so the gaps between them are covered.

## The vertical slice

The slice is card authorization to fraud scoring: eleven nodes, four app types, and a feedback loop where the service that produces the events also calls the model trained on them. It is small enough to review by hand and has enough hops to make a schema change hurt.

&#91;embedded content: vertical slice · 11 nodes, edges coloured by the phase that first finds them\]

Step through the phase buttons to watch the graph fill in, then click a box to trace everything downstream of it and the teams to warn. By the end of Phase 3 the whole path from payments-svc to fraud-svc is visible, and Phase 4 confirms it and adds the two hops code can't see: the lake sink and the dashboard.

| Node | Type | Owner (example) | What makes it a good test |
| --- | --- | --- | --- |
| mobile-bff | Client service | Mobile platform | Calls through the API gateway, so Phase 1 sees it |
| payments-svc | Microservice | Payments | Produces auth.events.v1 and calls fraud-svc on every authorization |
| auth.events.v1 | Kafka topic (Avro, Schema Registry) | Payments | The contract boundary where most breaking changes start |
| txn-enrichment | Flink job | Streaming platform | Reads and renames fields; no column lineage at runtime, so static analysis must cover it |
| auth.enrich.v1 | Kafka topic | Streaming platform | Intermediate hop that is easy to forget |
| raw.card\_auth | Iceberg table on S3 | Data platform | Landed by a sink; a write path that bypasses SQL |
| fct\_card\_auth | dbt model in the warehouse | Analytics engineering | Column lineage from SQL; feeds BI and features |
| Approval rate | BI dashboard | Payments analytics | Consumer seen only in query logs |
| mcc\_decline\_7d | Feature view | Fraud ML | Aggregates by merchant category code, so a field rename breaks it silently |
| fraud-score-v12 | Model version | Fraud ML | Links training data to the serving endpoint |
| fraud-svc | Model-serving microservice | Fraud ML | Closes the loop back to payments-svc |

## Graph model

One graph, one naming scheme, and edges that carry their evidence. Every phase below adds evidence to the same edges instead of building a separate map, which is how accuracy can rise phase by phase.

**Names.** Every node gets a URN of the form `scheme://namespace/name`, with fields after a `#`:

| Node | URN |
| --- | --- |
| Service | `svc://prod/payments-svc` |
| Endpoint | `svc://prod/fraud-svc#POST /v1/score` |
| Topic and field | `kafka://msk-prod/auth.events.v1#merchant_category_code` |
| Table and column | `warehouse://prod/analytics.fct_card_auth#mcc` |
| Feature | `feast://fraud/mcc_decline_7d` |
| Model version | `mlreg://fraud-score/12` |

**Edge types.** CALLS (service to endpoint), PRODUCES and CONSUMES (service or job to topic), READS and WRITES (job to table), DERIVES (field to field, with a transform: identity, rename, aggregate, filter), FEEDS (feature to model), SERVES (model to service), OWNS (team to node). Every lineage edge points downstream, in the direction data flows, so one traversal direction answers impact and the other answers root cause.

**A node record**

```json
{
  "urn": "kafka://msk-prod/auth.events.v1#merchant_category_code",
  "type": "field",
  "parent": "kafka://msk-prod/auth.events.v1",
  "data_type": "string",
  "schema_version": 7,
  "owner": "team:payments",
  "tier": 1,
  "contract": "payments/auth-events v2.1.0"
}
```

**An edge record with its evidence**

```json
{
  "from": "kafka://msk-prod/auth.events.v1#merchant_category_code",
  "to": "kafka://msk-prod/auth.enrich.v1#mcc",
  "type": "DERIVES",
  "transform": "rename",
  "evidence": [
    {"source": "static", "tool": "flink-sql-parser", "repo": "txn-enrichment",
     "commit": "9b1e44d", "seen": "2026-11-20T14:02:00Z"},
    {"source": "runtime_dataset", "tool": "openlineage-flink", "job": "txn-enrichment",
     "seen": "2026-11-21T09:15:00Z"}
  ],
  "confidence": 0.80,
  "state": "probable",
  "valid_from": "2026-10-02T00:00:00Z",
  "valid_to": null
}
```

The Flink integration confirms only that the job reads and writes the two topics, not the field mapping, so this field edge stays "probable" until an owner verifies it or a runtime source sees the field itself.

**Confidence by evidence source** (starting weights; Phase 4 recalibrates them against the golden graph)

| Evidence source | Weight | What it proves | Typical false signal |
| --- | --- | --- | --- |
| Warehouse access history | 0.95 | A query read or wrote these columns | Temporary tables, renamed objects |
| OpenLineage runtime event | 0.95 | A job run read or wrote this dataset (columns for Spark and dbt) | Wrong namespace configuration |
| Gateway or mesh access log | 0.90 | A call happened between two services | Unresolved caller, health checks |
| OTel messaging or database span | 0.90 | A service produced to, consumed from or queried a resource | Sampling misses rare paths |
| Runtime, dataset level only | 0.50 | Applied to a field edge when only its parent datasets were observed | Field may not actually be used |
| Static code analysis | 0.60 | The code can produce this flow | Dead code, feature flags, unreleased branches |
| Declared (contract or catalog entry) | 0.50 | The owner says the flow exists | Stale documentation |
| IAM or Kafka ACL permission | 0.20 | The flow is possible | Over-broad permissions |

Confidence combines independent sources as 1 minus the product of (1 minus weight). For example, payments-svc PRODUCES auth.events.v1 with static code (0.6), an OTel span (0.9) and an IAM grant (0.2) scores 1 − 0.4 × 0.1 × 0.8 = 0.97.

**Edge states.** Candidate (below 0.6), probable (0.6 to 0.9), confirmed (0.9 or above with at least one runtime source), verified (owner confirmed), dormant (no runtime evidence for 30 days; kept and flagged), retired (code removed and no traffic). Impact queries default to probable and above; RCA walks confirmed and above first.

&#91;embedded content: calculator · edge confidence from the evidence behind it\]

Try static code plus declared: it reaches 0.80 and stays probable; adding any runtime source tips it into confirmed.

## Phase 0: baseline and golden graph (weeks 1 to 2)

Before collecting anything, write down what the right answer is for the slice and how bad things are today. Without this, no later phase can prove it improved anything.

&#91;embedded content: phase 0 · golden graph and baseline\]

**Why this phase.** Without ground truth, every later claim that lineage is "90% accurate" is an opinion, and the first wrong edge someone finds becomes the story. Hand-verifying about 55 edges with the owning teams costs a few hours each, and it nearly always surfaces a consumer nobody knew about, which is the business case in one example. It comes first because every later phase is scored against this graph, and the MTTD and MTTR baseline is what Phase 5 has to beat.

- **To executives:** two weeks to measure today's cost of breaking changes and agree what "correct" looks like, so we can prove progress rather than assert it.
- **To engineers:** a signed-off golden set of service, dataset and field edges becomes the test suite for every collector, scored by precision and recall.

**Steps**

1. Confirm the slice and name one owner per node (eleven nodes, about six teams).
2. Build the golden graph: a one-hour session per team walking their code and config, recording each edge with its URN, type and field mapping. Expect roughly 15 service and dataset edges and 40 field edges for this slice.
3. Record the baseline from the incident tracker and repos for the last six months: incidents touching the slice, MTTD, MTTR, how root cause was found, schema changes to auth.events.v1 and fct\_card\_auth, and which consumers broke.
4. Stand up the plumbing: graph store (Neptune with openCypher, or DataHub if you want its UI on day one), a lineage.evidence Kafka topic, an Iceberg table on S3 for raw evidence, and the URN library.
5. Agree the exit gates in the plan summary with the slice owners and your leadership.

**Example golden graph rows**

| From | To | Type | Transform | Confirmed by |
| --- | --- | --- | --- | --- |
| `svc://prod/payments-svc` | `svc://prod/fraud-svc#POST /v1/score` | CALLS | none | Payments |
| `kafka://msk-prod/auth.events.v1#merchant_category_code` | `kafka://msk-prod/auth.enrich.v1#mcc` | DERIVES | rename | Streaming platform |
| `warehouse://prod/analytics.fct_card_auth#mcc` | `feast://fraud/mcc_decline_7d` | DERIVES | group by | Fraud ML |

**Delivered:** golden graph v0, baseline sheet, running but empty pipeline.

**Value:** accuracy becomes measurable. The workshops usually surface at least one consumer nobody on the producing team knew about, which is the first concrete proof of the problem.

**Exit gate:** every slice owner has signed off their part of the golden graph, and the baseline numbers are recorded.

## Phase 1: gateway logs to service edges (weeks 2 to 5)

Turn access logs you already have into a service dependency map. No application code changes; the work is log format, identity and aggregation.

&#91;embedded content: phase 1 · gateway and mesh logs to service edges\]

**Why this phase.** During an incident, "who calls this service?" is usually answered by a chain of messages. Every synchronous call already passes through a gateway or mesh that logs it, so reading those logs covers the whole estate's call traffic in about three weeks with no team changing code. Instrumenting each service first would take quarters and depend on every team's roadmap. It comes first because it builds the skeleton of service nodes that everything else hangs on, and its blind spots (Kafka, data stores, fields) define exactly what Phases 2 to 4 must add.

- **To executives:** we get a live map of which services depend on which, from logs we already pay for, so the blast radius of an outage or deploy is known in seconds.
- **To engineers:** access logs land in Iceberg, an hourly job keys them by caller identity, callee and route template, and the result is CALLS edges with volume, error rate and latency.

**Steps**

1. Make sure every gateway and mesh log line carries four things: caller identity, callee, route template and request ID. For API Gateway this is a custom access log format; for an Envoy-based mesh it is the downstream peer's certificate identity in the access log.
2. Ship logs to S3 through a CloudWatch Logs subscription and Firehose, landing in an Iceberg table such as gw\_access\_raw.
3. Run an hourly Spark or Athena job that aggregates to one row per caller, callee and route: call count, error rate, p50 and p99 latency, first seen, last seen.
4. Normalize raw paths to route templates (`/v1/authorizations/8812/capture` becomes `/v1/authorizations/{id}/capture`), preferring the gateway's own route field and falling back to a regex normalizer.
5. Resolve caller identities to service URNs. In this phase use a hand-built mapping for the slice; Phase 2 replaces it. Unresolved callers go to a queue.
6. Drop noise: health checks, synthetic monitors, scanners.
7. Publish edges as evidence events and ship three queries: who calls X, what does X call, and two-hop blast radius.

**Worked example: one mesh log line becomes an edge**

A single access log line from the sidecar in front of fraud-svc:

```json
{
  "start_time": "2026-11-21T14:02:11.482Z",
  "method": "POST",
  "path": "/v1/score",
  "route_name": "fraud-svc-score",
  "response_code": 200,
  "duration_ms": 38,
  "downstream_peer_identity": "spiffe://prod.example/ns/payments/sa/payments-svc",
  "upstream_cluster": "fraud-svc.fraud.svc.cluster.local",
  "request_id": "7f3a9c2e-51b0-4d6e-9a1f-0c2b7d8e4a11"
}
```

After an hour of aggregation and identity resolution:

```json
{
  "from": "svc://prod/payments-svc",
  "to": "svc://prod/fraud-svc#POST /v1/score",
  "type": "CALLS",
  "window": "2026-11-21T14:00Z/2026-11-21T15:00Z",
  "calls": 412880,
  "error_rate": 0.0011,
  "p99_ms": 91,
  "first_seen": "2026-08-03T10:12:00Z",
  "last_seen": "2026-11-21T14:59:58Z",
  "evidence": [{"source": "mesh_log", "weight": 0.9}],
  "confidence": 0.90,
  "state": "confirmed"
}
```

Now "if fraud-svc slows down, who is affected?" returns payments-svc (about 413,000 calls an hour) and, one hop further, mobile-bff, in seconds rather than a thread of messages.

**Delivered:** service dependency map for the slice and, at almost no extra cost, for everything behind the same gateways; the three queries; an unresolved-caller queue.

**Value:** service-level blast radius for incidents and deploys from week 5. Measured as recall of golden service edges, share of call volume with a resolved caller, and time to answer "who calls X".

**What it cannot see yet:** Kafka traffic, data stores, fields, and anything asynchronous. That is the point of Phases 2 to 4.

**Exit gate:** at least 90% of golden service-to-service edges found, with under 5% of call volume from unresolved callers.

## Phase 2: overlay components, ownership and catalog (weeks 4 to 7)

Turn anonymous callers and hostnames into owned services, and add the data assets each service owns as nodes. After this phase every node on the map has someone to page, and the topics, tables, features and models exist in the graph for Phases 3 and 4 to connect.

&#91;embedded content: phase 2 · identity, ownership and data assets\]

**Why this phase.** A box called 10.4.7.12 can't be paged, and a map of services alone can't say which Kafka topic or table a change touches. Instead of asking teams to write documentation, we join systems that are already the source of record: deploy manifests and IAM give identity, the catalog gives owner and tier, and the registries give topics, tables, features and models. It comes here because it resolves Phase 1's unresolved callers, and Phases 3 and 4 need data-asset nodes to attach their edges to.

- **To executives:** every dependency now has a named owner and a criticality tier, so an alert goes to a person rather than a channel.
- **To engineers:** an identity table maps caller credentials to service URNs, and registry crawlers add dataset, feature and model nodes with permission edges at low weight 0.2.

**Steps**

1. Build the identity table that maps every caller identity (mesh certificate identity, IAM role, Kubernetes service account, API client ID) to a service URN, generated from deployment manifests and IAM role tags rather than by hand. It replaces the Phase 1 mapping.
2. Import component metadata from the service catalog (Backstage catalog-info.yaml or your CMDB application record): owner, tier, system, on-call, repo, lifecycle.
3. Import data assets as nodes with their schemas: Schema Registry subjects (topic fields), Glue Data Catalog and warehouse information schema (tables and columns), the feature store registry (features), the model registry (model versions), and the BI tool's API (dashboards).
4. Add ownership edges: team OWNS topic, table, feature and model, from catalog tags or naming conventions.
5. Add low-confidence permission edges from IAM policies and Kafka ACLs (weight 0.2): payments-svc may write auth.events.v1. Optionally add CloudTrail S3 data events for the slice's buckets as runtime evidence, scoped tightly because data events cost money at volume.
6. Link model versions to the services that serve them (SERVES), from the model registry or serving deployment config.
7. Publish a hygiene report: services with no owner, identities with no service, topics with no schema, declared dependencies never observed.

**Worked example: a catalog entry becomes an overlay**

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payments-svc
  annotations:
    lineage/identities: spiffe://prod.example/ns/payments/sa/payments-svc
spec:
  type: service
  lifecycle: production
  owner: team-payments
  system: card-authorization
  providesApis: [payments-api]
  consumesApis: [fraud-scoring-api]
```

The identity annotation resolves the Phase 1 caller to payments-svc. Owner, system and tier attach to the node. The consumesApis line becomes declared evidence (weight 0.5) on the CALLS edge to fraud-svc, which raises it from 0.90 to 0.95, and gives Phase 4's reconciliation its first comparison of declared against observed.

**Delivered:** owned nodes for every service in the map; topic, table, feature, model and dashboard nodes for the slice with their schemas; permission edges; the hygiene report.

**Value:** incidents route to the right on-call in minutes, with the impacted teams listed. Orphan services and ownerless topics surface for the first time. Measured as share of nodes with an owner and on-call, and time from alert to the right team engaged.

**Exit gate:** at least 95% of slice nodes owned, under 5% of call volume from unresolved identities, and every slice data asset present with its schema.

## Phase 3: static code edges and PR impact (weeks 6 to 11)

Go below the service into topics, tables, features and fields by reading the code, and show the impact on every pull request. This is the phase that moves detection before the merge.

&#91;embedded content: phase 3 · static scanners and the PR impact bot\]

**Why this phase.** Breakage happens at field level, and logs and runtime telemetry only report what already shipped. Code is the one place that shows intent before merge, so this is where "updates when the source code changes" actually happens. We reuse parsers that exist (SQLGlot, Flink plans, Avro and OpenAPI diffs) rather than build one, and the bot starts in warn mode so teams see it be right before it can block them. It comes after Phase 2 because a PR comment that names assets but no owners is noise.

- **To executives:** before a change merges, its author sees which teams and tier 1 systems it will hit, the moment a fix is cheapest.
- **To engineers:** per-language scanners emit static OpenLineage events in CI, and the bot diffs fields and walks the graph downstream to list assets and owners in the PR.

**Steps: one scanner per app type, run in CI on every PR and nightly on the default branch**

1. **Services.** Read producer and consumer topic names from config, the Avro or Protobuf classes the code builds (which fields it sets and reads), OpenAPI specs for endpoints and request fields, and ORM mappings for tables. Config parsing plus code rules (for example Semgrep or a tree-sitter based scanner) is enough for the common frameworks.
2. **Streaming.** For Flink SQL, run the statements through Flink's own planner in a CI harness and read the column mapping from the plan. For DataStream jobs, use code rules plus the job's declared field mapping, since there is no runtime column lineage to fall back on.
3. **Analytics.** Parse dbt's manifest and compiled SQL with a column-lineage parser such as SQLGlot. For Spark jobs, run a CI dry run against empty tables with the OpenLineage listener on; the column lineage comes from the logical plan before the code ships.
4. **ML.** Parse the feature repository (each feature view's source columns and aggregation) and training configs (which features feed which model).
5. Emit every result as a static OpenLineage JobEvent tagged with repo, commit and PR number, so a change is visible in the graph before merge and replaced cleanly after.
6. Ship the PR impact bot in warn mode: compute the field-level diff, walk the graph downstream and post the result as a PR comment.

**Worked example: a field rename in payments-svc**

PR #482 renames `merchant_category_code` to `mcc` in the auth event schema (v7 to v8), adding `mcc` with a default. Under the registry's default BACKWARD compatibility, deleting a field and adding one with a default both pass, so the registry accepts it. Every consumer that reads the old name still breaks. The impact query:

```cypher
MATCH p = (f {urn: 'kafka://msk-prod/auth.events.v1#merchant_category_code'})
          -[:DERIVES|FEEDS|SERVES*1..10]->(n)
WHERE all(r IN relationships(p) WHERE r.confidence >= 0.6 AND r.valid_to IS NULL)
RETURN n.urn, n.type, n.owner, n.tier, length(p) AS hops
ORDER BY hops
```

The result, as the bot would show it:

| Hops | Asset | Owner | Tier | What breaks |
| --- | --- | --- | --- | --- |
| 1 | auth.enrich.v1#mcc (via txn-enrichment) | Streaming platform | 1 | Job reads the old name; field goes null |
| 2 | raw.card\_auth#mcc | Data platform | 2 | Nulls land in the lake |
| 3 | fct\_card\_auth#mcc | Analytics engineering | 1 | Nulls; group-bys collapse into one bucket |
| 4 | Approval rate dashboard | Payments analytics | 2 | Merchant category breakdown shows only "unknown" |
| 4 | mcc\_decline\_7d | Fraud ML | 1 | Feature flattens across all merchants |
| 5 | fraud-score-v12 | Fraud ML | 1 | Score drift: false declines or missed fraud |
| 6 | fraud-svc | Fraud ML | 1 | Serves degraded scores back to payments-svc |

The PR comment:

```text
Lineage impact for PR #482 (payments-svc)
auth.events.v1 v7 -> v8
  - removed merchant_category_code (string)
  + added   mcc (string, default "")
Registry compatibility (BACKWARD): PASS
Downstream readers of merchant_category_code: 7 assets, 5 teams, 5 tier 1
Suggested: keep merchant_category_code as an alias for one release,
or get sign-off from streaming-platform, analytics-eng and fraud-ml.
Mode: warn. Blocking for tier 1 contracts from Phase 5.
```

**Delivered:** scanners for the four app types in the slice's repos; static field-level edges; the PR bot in warn mode.

**Value:** the producing engineer sees the seven downstream assets and their owners before merging, instead of the fraud team finding out from model metrics. Measured by change replay: run the last ten schema changes in the slice through the bot and count how many of the consumers that actually broke it would have listed.

**Exit gate:** the bot runs on every PR in the slice's repos; field-level recall against the golden graph is at least 80%; change replay finds at least 8 of 10 consumers that broke.

## Phase 4: runtime edges and reconciliation (weeks 9 to 14)

Confirm or retire every static guess with what actually ran, and catch the consumers that code never mentioned. This is where precision climbs and where hidden dependencies, each a future incident, come to light.

&#91;embedded content: phase 4 · runtime evidence and reconciliation\]

**Why this phase.** Static analysis overclaims (dead code, paths behind feature flags) and misses consumers that are never in a repo, like notebooks, ad hoc SQL and sink connectors. Runtime telemetry shows what actually ran, but alone it misses rare paths and only reports after the fact. So we reconcile the two rather than replace one with the other, and we collect metadata only, never payloads. It comes before Phase 5 because a blocking gate needs about 95% precision, or people disable it after the first false alarm.

- **To executives:** the map is now checked every day against real traffic, which is what makes it safe to enforce rules on.
- **To engineers:** OTel spans, OpenLineage run events and warehouse access history become evidence on each edge, a daily job flags static-only and runtime-only edges, and weights are recalibrated against the golden graph.

**Steps**

1. Turn on OpenLineage centrally in the platforms the slice uses: Flink (job status listener, dataset level only), Spark (column lineage from the plan), Airflow, dbt and Feast materialization, all sending to the evidence topic.
2. Use the OpenTelemetry instrumentation services already have. A collector processor turns producer, consumer and database spans into PRODUCES, CONSUMES and READS evidence with counts, keeping only metadata attributes such as `messaging.destination.name` and `db.collection.name`, never payloads.
3. Pull warehouse access history every hour (Snowflake ACCESS\_HISTORY or Redshift system tables) for column-level reads and writes, including BI dashboard queries identified by service account or query tag.
4. Capture sink connectors (Kafka Connect or Flink sinks into Iceberg) from OpenLineage or connector config, which covers the write path that bypasses SQL.
5. Run reconciliation daily: compare evidence per edge across sources and queue every disagreement to the owning team.
6. Recalibrate source weights against the golden graph (see How accuracy is measured).

**Worked example: two runtime records**

An OTel producer span from payments-svc (abridged) confirms the PRODUCES edge to the topic:

```json
{
  "name": "send auth.events.v1",
  "kind": "PRODUCER",
  "resource": {"service.name": "payments-svc"},
  "attributes": {
    "messaging.operation.type": "send",
    "messaging.destination.name": "auth.events.v1"
  }
}
```

An OpenLineage COMPLETE event from the nightly dbt run (abridged) confirms the column edge into the fact table:

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2026-11-21T03:05:44Z",
  "job": {"namespace": "dbt://analytics", "name": "analytics.fct_card_auth"},
  "inputs": [{"namespace": "iceberg://s3-prod", "name": "raw.card_auth"}],
  "outputs": [{
    "namespace": "warehouse://prod",
    "name": "analytics.fct_card_auth",
    "facets": {"columnLineage": {"fields": {"mcc": {"inputFields": [{
      "namespace": "iceberg://s3-prod", "name": "raw.card_auth", "field": "mcc",
      "transformations": [{"type": "DIRECT", "subtype": "IDENTITY"}]
    }]}}}}
  }]
}
```

**The reconciliation queue, with examples from the slice**

| Finding | Example | Likely meaning | Action |
| --- | --- | --- | --- |
| Static only, no runtime for 30 days | payments-svc code still produces to auth.events.v0 | Dead path or feature flag off | Owner confirms; mark dormant or delete the code |
| Runtime only, not in code or catalog | A notebook service account reads fct\_card\_auth#card\_bin | Undeclared consumer | Register the consumer and its owner, or revoke access |
| Declared, never observed | Catalog says mobile-bff consumes fraud-scoring-api | Stale declaration | Fix the catalog entry |
| Unresolved identity | Gateway caller with an unknown client ID | Missing mapping | Add it to the identity table |
| Static and runtime disagree | Parser says mcc comes from merchant\_category\_code; runtime column lineage says from mcc\_raw | Scanner bug or code drift | Fix the scanner rule and add the case to its tests |

**Delivered:** runtime evidence for every app type in the slice; the reconciliation queue with owners and a weekly burn-down; recalibrated weights.

**Value:** the graph stops guessing. Measured as precision against the golden graph, number of undeclared consumers found (each one a breaking change that would have surprised someone), and edge freshness.

**Exit gate:** precision at least 95% on service and dataset edges and 90% on field edges, with field-level recall at least 90%; new runtime edges visible within 15 minutes; reconciliation queue under 10 open items for the slice.

## Phase 5: contracts, data quality and RCA (weeks 13 to 18)

Use the now-trusted graph to block breaking changes, attach the upstream path to every data quality alert, and produce a remediation plan when something still escapes. This is the phase where MTTD and MTTR move.

&#91;embedded content: phase 5 · contracts, quality checks, RCA and remediation\]

**Why this phase.** Knowing the impact of a change doesn't prevent it. Prevention needs guardrails at the boundaries: contracts that block a breaking change before merge, quality checks at every hop, and an RCA path that walks upstream to the first failing node and ranks the changes that landed in that window. The graph is what makes these cheap, because each contract's consumer list and each alert's audience is generated rather than kept by hand. It comes last because a blocking gate built on an untrusted graph is the fastest way to lose engineers' trust, and this is the phase where MTTD and MTTR halve.

- **To executives:** this is where the measurable payoff lands: fewer breaking changes reach production, and the ones that do are explained and contained in minutes.
- **To engineers:** contract checks run in CI against graph-generated consumer lists, DQ failures trigger an upstream walk plus change-event ranking, and a circuit breaker pauses downstream jobs in dependency order.

**Steps**

1. Write contracts for the slice's two boundaries, auth.events.v1 and fct\_card\_auth: schema, owner, quality rules and SLA, with the consumer list generated from the graph rather than typed by hand.
2. Put producer-side rules in the Schema Registry so bad events are stopped or sent to a dead letter queue at the source.
3. Turn the PR gate to blocking for tier 1: a change that removes or retypes a contract field with confirmed downstream readers needs a version bump and approval from those readers' owners, requested automatically from the graph.
4. Add a DQ check at each hop of the slice (null rate and value range on the merchant category field at the topic, lake table, fact table and feature), with results written to the graph as data quality facets.
5. Build the RCA service: from a failing check, walk upstream to the first failing node and rank change events in the window (schema registrations, deploys, merged PRs, failed runs).
6. Build the remediation planner: walk downstream in topological order and emit actions per node type, plus circuit breakers that pause downstream jobs.
7. Replay the last six months of slice incidents through RCA and record detection and resolution times.

**Contract excerpts**

```yaml
# ODCS-style contract for auth.events.v1 (abridged)
kind: DataContract
name: auth-events
version: 2.1.0
owner: team-payments
schema:
  - name: auth_event
    properties:
      - name: merchant_category_code
        logicalType: string
        required: true
        quality:
          - rule: nullRate
            mustBeLessThan: 0.01
consumers:   # generated from the lineage graph
  - txn-enrichment
  - fct_card_auth
  - mcc_decline_7d
```

```json
{"ruleSet": {"domainRules": [{
  "name": "mccFormat", "kind": "CONDITION", "type": "CEL", "mode": "WRITE",
  "expr": "message.merchant_category_code.matches('^[0-9]{4}$')",
  "onFailure": "DLQ"
}]}}
```

**Worked example: the same rename, escaping as an emergency hotfix**

Suppose PR #482 had shipped at 02:03 as a hotfix that skipped the gate. With the slice instrumented, this is what the on-call sees at 02:42:

```text
ALERT raw.card_auth.mcc null_rate 41% (threshold 1%) at 02:42

Upstream walk (confirmed edges)
  raw.card_auth#mcc   <- auth.enrich.v1#mcc                      null 43%  FAIL
  auth.enrich.v1#mcc  <- auth.events.v1#merchant_category_code   absent in v8
Change events 01:40-02:42, ranked
  1. 02:05 schema auth.events.v1 v8 registered (field removed)
  2. 02:03 deploy payments-svc 4f3c2a1 (PR #482, same change)
  3. 01:55 deploy txn-enrichment (config only)
Likely cause: PR #482 renamed merchant_category_code to mcc

Blast radius: 7 assets, 5 teams
  already affected: auth.enrich.v1, raw.card_auth
  not yet affected: fct_card_auth (dbt 03:00), mcc_decline_7d (04:00),
                    fraud-score-v12, fraud-svc, Approval rate dashboard

Remediation plan (topological)
  0. Circuit breaker: pause dbt fct_card_auth and feature job mcc_decline_7d
  1. payments-svc: re-add merchant_category_code as alias       (payments)
  2. txn-enrichment: replay auth.events.v1 from 02:05 offsets    (streaming-platform)
  3. raw.card_auth: rewrite partitions 2026-11-21 hours 02-03   (data-platform)
  4. Resume dbt; rerun fct_card_auth for 2026-11-21             (analytics-eng)
  5. Re-materialize mcc_decline_7d                              (fraud-ml)
  6. fraud-svc: no action if step 5 completes before 04:00
  7. Notify Approval rate dashboard owners                      (payments-analytics)
```

The circuit breaker is the quiet win: the bad data stops at two assets instead of reaching the fact table, the feature and the model. Without lineage, the same incident would likely surface the next day as a model metric anomaly, after the feature had been served for hours.

**Delivered:** contracts and registry rules on the slice's boundaries; a blocking PR gate for tier 1; DQ checks at every hop; the RCA and remediation services; an incident replay report.

**Value:** fewer breaking changes reach production, and those that do are detected at the first hop with the cause and plan attached. Measured as pre-merge catch rate, MTTD, MTTR and blast radius against the Phase 0 baseline.

**Exit gate:** MTTD and MTTR at most half the baseline on replayed incidents and on any live incident in the slice; at least 80% of breaking changes caught before merge.

## Phase 6: widen to the next slices (week 19 onward)

The first slice builds the platform; every later slice reuses it, so each one should take about half as long. Widening is a repeatable playbook, not a new project.

&#91;embedded content: phase 6 · the per-slice playbook\]

**Why this phase.** Rolling out lineage everywhere at once stalls, because no team sees value until every team has done the work. A slice proves the value end to end, and the platform pieces it built (gateway edges, catalog overlay, scanners, PR bot) are reused, so each new slice costs less than the last. Slices are picked by risk, meaning tier 1 data products with the most incidents, and after two or three the platform team hands the playbook to domain teams to run themselves.

- **To executives:** each new slice is roughly half the effort of the one before, and coverage of tier 1 data products is a dashboard you can track.
- **To engineers:** slice two needs no new collector work, only a light golden graph, switching on scanners and runtime collection, and contracts and DQ on its boundaries.

1. **Pick slices by risk.** Rank tier 1 data products by incident count and number of downstream teams from the Phase 0 baseline; take the top five.
2. **Reuse the estate-wide layers.** Gateway edges and the component overlay already cover everything behind the same gateways and catalog after Phases 1 and 2; only new gateways need onboarding.
3. **Per slice:** a lighter golden graph (a sample of about 30 edges), switch on the scanners and runtime integrations (mostly configuration by now), contracts on the boundary topics and tables, DQ checks at each hop.
4. **Productize what the first slice built by hand:** the serializer library that stamps identity, the scanner rule library with its tests, the PR bot as an organization-wide check, and a coverage dashboard by tier.
5. **Federate.** After two or three slices, domain teams run their own slices with the platform team as reviewers.

**Value:** coverage of tier 1 assets grows by one slice every six to eight weeks at first, then in parallel. Measured as tier 1 coverage, cost per slice, and the same MTTD and MTTR gates per slice.

## How accuracy is measured and improved

Accuracy is measured three ways, at three levels, every week: against the golden graph, by replaying real changes and incidents, and by sampling edges outside the slice. Each measurement feeds a specific fix, so accuracy rises by design rather than by hope.

**Three measurements**

1. **Against the golden graph.** Precision is the share of graph edges that are in the golden graph; recall is the share of golden edges the graph has. Both are reported separately for service, dataset and field edges, because a graph can be excellent at one level and poor at another.
2. **Replay tests.** Change replay runs past schema changes through the impact query and checks the result against the consumers that actually broke. Incident replay runs past incidents through RCA and checks whether the top-ranked cause was the real one. These measure usefulness, not just correctness.
3. **Sampled audits beyond the slice.** Each month, owners review 50 random edges from outside the slice, so the golden graph doesn't become the only thing the graph is good at.

**Five ways accuracy improves**

- **Reconciliation queue.** Every disagreement between sources goes to an owner with a weekly burn-down (Phase 4).
- **Weight calibration.** Each quarter, set each evidence source's weight to its measured precision against the golden graph, so confidence scores mean what they say.
- **Scanner regression tests.** Every scanner bug found in reconciliation becomes a test case, with golden graph edges as fixtures in the scanner's CI.
- **Owner feedback in the PR.** The impact comment has a "this is wrong" link per row; a disputed edge drops to candidate until reviewed.
- **Decay.** Runtime evidence expires after 30 days without being seen again; static evidence lasts while the code exists on the default branch. Stale edges turn dormant instead of lingering as false impact.

**Accuracy targets by phase** (precision / recall, proposed)

| After phase | Service edges | Dataset edges | Field edges |
| --- | --- | --- | --- |
| 1. Gateway | 95% / 90% | none yet | none yet |
| 2. Components and catalog | 97% / 95% | 50% / 60% (permission edges only) | none yet |
| 3. Static code | 97% / 95% | 80% / 85% | 75% / 80% |
| 4. Runtime | 98% / 98% | 95% / 95% | 90% / 90% |
| 5. Contracts and RCA | 98% / 98% | 97% / 95% | 95% / 90%, tier 1 owner-verified |

## Team, effort and risks

The first slice needs about six engineers for 18 weeks plus a few hours from each slice owner; after that the work shifts to productizing and federating.

| Role | Count | Owns |
| --- | --- | --- |
| Platform backend | 2 | Evidence pipeline, identity resolution, graph store, query API, RCA service |
| Streaming engineer | 1 | Gateway and mesh log ingestion, Kafka and Flink integration, serializer library |
| Analytics engineer | 1 | dbt and SQL scanners, warehouse access history, DQ checks |
| ML platform engineer | 1 | Feature store and model registry integration, training config scanner |
| Developer productivity | 1 | CI scanners harness, PR impact bot, the gate |
| Slice owners | about 6 teams | Golden graph sessions, reconciliation queue, contract review |

**Decisions for week 1:** graph store (Neptune for control over edge semantics, or DataHub for a UI on day one); which gateways and meshes are in scope; final choice of slice.

**Main risks**

| Risk | Mitigation |
| --- | --- |
| Gateway logs lack caller identity | Fix the log format first; mesh certificate identity is the strongest source; unresolved share is an exit metric |
| Route templates missing, so every ID becomes a new endpoint | Use the gateway's route field; fall back to a normalizer with tests |
| Flink gives no column lineage at runtime | Field edges on that hop come from the Flink planner in CI and from contracts; owner verification for tier 1 |
| Impact reports are noisy and get ignored | Warn mode first; show confirmed edges first; block only tier 1 contracts |
| Lineage captures sensitive data | Metadata only: names, schemas, counts; no payloads or sampled values |
| Owners don't work the reconciliation queue | Queue items count toward the team's operational review; exit gates depend on it |
| CloudTrail data events get expensive | Optional, and scoped to the slice's buckets |

The research behind this plan (industry survey, collection options, comparison, sources) is in Research appendix.
