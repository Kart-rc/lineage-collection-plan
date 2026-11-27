# Build decisions

Nov 27, 2026 · Turns the open questions in [doc 06](06-element-lineage-factory-spec.md) and the plan's week-1 list into decisions, grounded in the real reference slice in [doc 07](07-reference-slice-otel-demo.md).

## On a page

The readiness review on 26 November found the build blocked on thirteen open decisions, no oracle, untested assumptions and an illustrative slice nobody could run. With a real system to test against, most of those can now be decided on evidence.

| Status | Count | Meaning |
| --- | --- | --- |
| Decided | 15 | Settled on evidence from the reference slice or the research. Each is reversible, and the "revisit if" column says when |
| Needs sign-off | 1 | D12 changes the store choice ADR-002 deferred. The platform lead signs or overrides |
| Needs a person | 6 | D13 needs Docker allowed in the factory's sandbox. D18 to D22 are policy, people and money. A recommendation is given for each; only you can make the call |

**What this unblocks.** Wave 0 of the spec can start this week: the oracle exists as fixtures, the twin is defined, and the first work packages have real inputs. Two things still gate it: a person allowing Docker in the factory's sandbox (D13), and the five calls in the last section (D18 to D22).

**What changed in the plan.** Three decisions change the plan, not only fill it in:

- **D7.** Phase 1 builds service edges from traces, not gateway logs.
- **D8.** Kafka hops are joined on the topic, not on trace links.
- **D12.** The first graph store is Postgres, not Neptune or DataHub.

All three come from reading the demo's code and its maintainers' own notes.

## What the build is tested against

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D1 | **The reference slice is the OpenTelemetry Demo's order flow at release 3.1.0.** It replaces the illustrative card-authorization slice for every work package, scenario and gate in doc 06 | Doc 07: a runnable, maintained, Apache-2.0 system with a real service → Kafka → Postgres flow in twelve languages, its own asserted service edges, six replayable schema changes and four injectable failures | A slice of your own estate is ready for Phase 0; it then becomes slice 2, and the demo stays as the regression twin |
| D2 | **Pending.** The open-source complement for the hops the demo lacks (stream processor, warehouse with dbt, feature store, model) | A survey of candidates is running; this row is filled from its findings | Not yet decided |
| D3 | **Pin 3.1.0 and upgrade only through a work package.** An upgrade re-runs `code/reference_slice.py --check`, re-signs any edge whose evidence moved, and adds the upstream changes as replay cases | Against the demo's `main` today, 299 commits after 3.1.0, 33 of 60 citations no longer point at the right line | Never; this is the rule that keeps the oracle honest |

## Names and records

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D4 | **One naming scheme**, as written in the fixtures: `svc://<env>/<service>`; `api://<env>/<service>/<call>/<request or response>#<field path>`; `kafka://<cluster>/<topic>#<field path>`; `postgres://<host>/<database>.<schema>.<table>#<column>`. Field paths are dotted, with `[]` for repeated fields | It names all 58 edges of the reference slice without a special case, including nested protobuf fields and repeated items. It is the plan's `scheme://namespace/name` shape with the call-message form added | A second technology needs a form this cannot express |
| D5 | **Evidence is anchored to a file, a text fragment and a line hint.** A checker looks for the text near the line, then anywhere in the file. A moved line is a warning; missing text is a failure that closes the static support for that edge | 33 of 60 line-anchored citations went stale in ten weeks while most of the edges still existed. Line numbers alone would have retired live edges | Never |
| D6 | **Envelope v2 is the only format for new collectors.** Its JSON Schema is the first deliverable of WP-11. Doc 03's envelope stays readable as v1 | Doc 06 already defines v2; the reference slice needs per-field edges and unit ownership, which v1 cannot carry | Never |

## Collection

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D7 | **Service-to-service edges come from traces.** The collector's `servicegraph` connector and a parent-child span walk produce `CALLS` edges at weight 0.90. Gateway and mesh logs are used only for traffic entering the estate, and as a mesh source where one exists. **This changes Phase 1 of the plan** | Envoy fronts only the web tier and identifies callers by remote address; checkout's calls to payment, cart and shipping never pass it. The 13 edges the demo's own tests assert are found by exactly this parent-child walk over live traces | A service mesh with workload identity is in place; then mesh logs join traces as a second source |
| D8 | **Kafka hops join on the topic.** The topic is a node. `PRODUCES` comes from producer spans' destination name; `CONSUMES` from consumer spans and the consumer group in broker metrics. Trace parent-child links are not relied on | The demo's maintainers exclude the two Kafka edges from their trace test because producer and consumer spans "live in separate traces" ([services.py:96](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/test/telemetry/services.py#L96)) | Consumers continue the trace context checkout already puts in message headers; then add trace links as extra evidence |
| D9 | **Each kind of field truth has one source.** Topic and call fields from compiled protobuf descriptors. Table columns from the ORM mappings and DDL. Field-to-field assembly inside a service from the code scanner. Runtime column use in Postgres from `pg_stat_statements`, parsed with SQLGlot | In the slice, these four are where the 36 field edges actually live. No registry or catalog holds the service-code mappings | A schema registry is adopted for the topics; then it replaces the descriptor source for topic fields |
| D10 | **Extractors are built in this order:** protobuf descriptors; the C# ORM mapping in accounting (17 edges); the Go assembly in checkout (18 edges, including the card pass-through); Postgres runtime evidence; then the remaining languages. Flink, dbt and feature extractors start with the complement in D2 | Ordered by how many golden field edges each unlocks and how mechanical the mapping is: the accounting mapping is one property per line | The vendor trial in D17 covers one of these hops well enough to buy it |
| D11 | **The telemetry pipeline is a destination, and must-not-flow checks cover it.** Exporters and backends are datasets; span and log attributes that carry data are fields | With `emitRawPii` on, checkout writes the card number and CVV into span attributes and the collector masks them. In a card estate that is a PCI-relevant flow | Never |

## Store and twin

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D12 | **Needs sign-off. The graph store for the first slices is Postgres** (Aurora in AWS): versioned edge rows with valid and recorded time, traversal by recursive SQL. Neptune and DataHub drop out of waves 0 to 2. This is the week-1 sub-decision ADR-002 deferred, with a third option | Marquez proves the pattern: version-keyed Postgres rows read with a time bound give point-in-time column lineage. The reference slice has 19 service and dataset nodes, 54 field elements and 58 edges. The twin must run on a laptop, which Neptune cannot. DataHub has no lineage history and its OpenLineage endpoint takes run events only. Aurora is already in the architecture for state | The 95th-percentile impact query passes 2 seconds, or the graph passes a million edges; then move the writer to Neptune and rebuild from the evidence lake |
| D13 | **Needs a person. The twin is the demo itself**, under Docker Compose at 3.1.0, with the capture add-on in `fixtures/otel-demo-3.1.0/run/` and the flags as fault injection. The factory's sandboxes need permission to run Docker | The demo is the system under test, so no separate simulator is needed. In the build session, starting the containers was refused by the session's permission check even with the host socket and filesystem removed | A lighter twin is needed for parallel agents; then a reduced profile with only checkout, Kafka, accounting and Postgres |

## Oracle

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D14 | **Golden graph v0 is `fixtures/otel-demo-3.1.0/golden-graph.json`:** 22 service edges and 36 field edges. The 13 edges upstream asserts in live traces count as owner-confirmed. The rest need the platform lead's sign-off, since the demo has no owners of yours | All 60 citations verified against the 3.1.0 source | The first runtime capture disagrees with an edge; then the disagreement goes to the reconciliation queue, and the golden graph changes only through G3 |
| D15 | **Change replay starts with C1 to C6** from the demo's history. The holdout set is changes authored against a fork that builders never see: renaming `shipping_tracking_id`, retyping `quantity`, removing a column from `accounting.shipping`, adding a field | Six real changes cover retype, rename, new consumer, identity move, retirement and a language rewrite | A slice of your estate replaces the demo; then its own history becomes the corpus |
| D16 | **Incident replay is I1 to I4, run in the twin.** The moment a flag flips is when bad data landed. Time to detect is from then to the first alert carrying an upstream path. Time to resolve is from then to the flag being flipped back by whoever followed the path. The baseline is the same runs without lineage | The flags are documented in the demo, are reversible, and two of them (I3, I4) put the cause one or two hops away from the symptom | Never for the twin; your estate's baseline still comes from Phase 0 |

## Build or buy

| Id | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| D17 | **Trial the two code-based vendors on the demo, not on your code.** Point Foundational and Gable at the demo's public repository for one week and score them against the 36 golden field edges, the three must-not-flow checks and changes C1 and C4 | The trial was blocked on what leaves your environment. The demo is public, so nothing confidential is shared. Its checkout (Go) and accounting (C#) are languages both vendors claim | Either scores above 90% field recall; then reconsider buying the service-code hop before WP-23 starts |

## Needs a person

| Id | Decision needed | Recommendation | Why it is yours |
| --- | --- | --- | --- |
| D18 | Can agent-written code merge after agent review, with a person approving by exception? | Level 2 (a person reads every change) for wave 0 and 1. Level 3 for extractors once wave 1 holds its holdout pass rate | It is an engineering risk and audit policy |
| D19 | Which model endpoint may read source code? | One inside your cloud boundary, for example Claude through Amazon Bedrock in the platform account. For the reference slice the code is public, so this only binds once the build reads your own repositories | It is a security and data-classification call |
| D20 | Who approves at the four gates? | G1 spec: platform lead plus one domain owner. G2 change: the spec owner for the hop. G3 oracle: platform lead. G4 release: platform lead or delegate | It needs names, not roles |
| D21 | What is the token budget? | A ceiling of $150 per work package and $3,000 a month for waves 0 and 1, reviewed at the wave 1 gate. Published costs range from about $13 per developer-day to $1,000 per engineer-day, so start low and let measured cost per merged change set the next figure | It is money |
| D22 | Which slice of your estate comes second, and on which warehouse? | Pick it during wave 1, ranked by incident count, so Phase 0 owner sessions can start while the factory builds against the demo | It needs your estate's owners |

## Changes to earlier documents

- **Plan (doc 01), Phase 1:** service edges come from traces where there is no mesh (D7). The illustrative slice stays as the explanation; the reference slice in doc 07 is what gets built and tested.
- **Architecture (doc 02):** Neptune and OpenSearch leave the first deployment; Aurora holds the graph (D12, pending sign-off).
- **Build guide (doc 03):** its envelope is v1; new collectors use v2 (D6).
- **ADR-002:** its store sub-decision is answered by D12 once signed.
- **Spec (doc 06):** open questions 2, 3, 4 and 8 have recommendations here; 5, 6 and 7 are decided or reshaped by D1, D12 and D17; 9 is D13.
