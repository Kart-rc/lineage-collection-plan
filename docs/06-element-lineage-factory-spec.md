# Element-level lineage: build spec for AI-factory delivery

Nov 26, 2026 · @kart

## Spec on a page

Extend the owned lineage core to element level, end to end, on the card-authorization slice, and build it with an AI factory. People write the specification, the golden graph and the scenarios. Agents write and check the code. People approve at four named gates.

"Element" means a field, column or attribute: a payload field in a service, a field in a Kafka topic, a column in a table, a feature, a model input. The target is one unbroken element path from `payments-svc` to `fraud-svc`, kept current as code and schemas change, and used in the pull request and in the incident.

**Why build at all.** The [vendor assessment](05-vendor-assessment-element-level-lineage.md) found no product that delivers element lineage across all eight hops of the slice. Products are strong where SQL runs: scanner suites on stored procedures and legacy ETL, query-log tools and platform catalogs on cloud warehouses, and CI tools inside a dbt or SQLMesh project. None documents field-level lineage for the service, Kafka, Flink or feature-store hops. No cloud catalog accepts lineage from code that has not yet run. Pull-request impact exists only inside SQL projects. So ADR-002 stands: own the thin core, adopt the extractors and collectors the market already does well, and build the hops nobody covers.

**Four objectives, four capabilities**

| Objective | Capability | What ships | Measure and gate |
| --- | --- | --- | --- |
| O1. Baseline lineage | Element harvest | One extractor per hop of the slice, each emitting field-to-field evidence with a transform class | Field-edge precision and recall at least 90% against the golden graph (the plan's Phase 4 gate) |
| O2. Incremental lineage | Change-driven refresh | Change detectors, unit-level re-extraction, bitemporal edges, lineage diff | Merge or run to edge visible in under 15 minutes; replay is deterministic; a diff exists between any two times or commits |
| O3. Change impact | PR impact and gate | Semantic diff, change classes, PR overlay, PR report, tier 1 block | Report within 5 minutes; change replay finds at least 8 of 10 consumers that broke; at least 80% of breaking changes caught before merge |
| O4. Detect and resolve | Lineage-led RCA | DQ and contract results on elements, as-of upstream walk, ranked causes, remediation order | Cause attached to the alert within 2 minutes; true cause in the top 3 on at least 90% of replayed incidents; MTTD and MTTR at most half the Phase 0 baseline |

The 2-minute and top-3 targets are new proposals in this spec. Every other number is a gate the plan already set.

**How it is built**

1. **Oracle first.** The golden graph, a corpus of replayed changes and incidents, and a twin of the slice that runs on a laptop come before any feature code. They are what lets a machine say whether a change is right.
2. **Spec pack, not tickets.** Each capability has requirements, interface schemas, visible scenarios and holdout scenarios in the repo. The spec is the source of truth and the code is a build product of it.
3. **Agents build in isolation.** Each work package is built by an agent in its own sandbox against the twin, scored by a harness the agent cannot edit, and reviewed by a second agent that did not write it.
4. **Autonomy is earned per work package.** Core semantics start with a person reviewing every change. Extractors, which have the strongest oracle, move to review by exception once they hold their pass rate.
5. **People keep four gates:** the spec, the oracle, protected changes, and the production release.

**What does not change.** The architecture, URN scheme, evidence weights, edge states, phases and exit gates in the [plan](01-implementation-plan.md), the [architecture](02-architecture-and-deployment.md), the [build guide](03-collection-and-build-guide.md) and [ADR-002](adr/ADR-002-own-the-lineage-graph-of-record.md) all stand. This spec adds element-level detail to them and changes how the code gets written.

## How this document fits

| Document | What it settles | What this spec adds |
| --- | --- | --- |
| [01 Implementation plan](01-implementation-plan.md) | Phases, gates, the slice, the graph model | Element edges as first-class records; requirements with IDs |
| [02 Architecture and deployment](02-architecture-and-deployment.md) | Components, four flows, AWS deployment | The incremental engine and lineage diff inside the core |
| [03 Collection and build guide](03-collection-and-build-guide.md) | Collectors, the evidence envelope, seven build steps | Envelope v2 with element detail; one extractor per hop |
| [04 Research appendix](04-research-appendix.md) | Techniques and how large tech companies do it | Nothing; it is the background |
| [05 Vendor assessment](05-vendor-assessment-element-level-lineage.md) | How each vendor gets element lineage and where it stops | The adopt, buy and build line per hop |
| [ADR-002](adr/ADR-002-own-the-lineage-graph-of-record.md) | Own the thin core, adopt the rest | Evidence that the decision still holds, and what would flip it |

## System view

### Things and connections

Three loops run at once, and they share one object.

- **The lineage loop.** Signals become evidence, evidence becomes edges, edges become decisions: warn or block a PR, rank a root cause, order a backfill.
- **The factory loop.** Intent becomes a spec, the spec becomes work packages, agents build them, a harness scores them, people gate them, and every escaped defect returns as a new scenario.
- **The trust loop.** Owners confirm edges, accuracy is published weekly, and a gate is only ever as strict as the measured precision allows.

The shared object is the golden graph with its scenario corpus. It is the test oracle for the factory, the accuracy yardstick for the product, and the thing owners sign. Whoever keeps it current controls the quality of all three loops, which is why it is authored by people and protected from agents.

### Inflow and outflow

| Loop | Inflow | Outflow |
| --- | --- | --- |
| Lineage | Code and pull requests, schema versions, table DDL, job runs, query history, DQ and contract results, deploy events | Impact reports and gate decisions, lineage diffs, ranked root causes, remediation order, coverage and accuracy numbers, catalog projections |
| Factory | Intent, specs, scenarios, golden fixtures, model capacity in tokens, reviewer and approver time | Merged changes with their evidence, scenario pass rates, new scenarios from escaped defects, cost per merged change |

Two stocks decide whether the flows are healthy. The evidence lake must only grow, because it is the replay source. The reconciliation queue and the gate queue must not grow, because a queue of unreviewed findings or unapproved changes is where trust and speed are lost.

**Where the constraint moves.** In a conventional build the constraint is engineering hours spent writing collectors. In the factory it moves to four places: how fast people can author the oracle, how much owner time the golden graph gets, how fast real evidence accrues, and how many changes the human gates can clear. The third cannot be compressed. A 30-day decay window takes 30 days, and runtime reconciliation needs jobs to actually run. The factory shortens the parts of the plan that are bound by building, not the parts bound by evidence.

### Cost of action and inaction

| Decision | Cost of acting | Cost of not acting |
| --- | --- | --- |
| Take lineage to element level | An extractor per technology with a long tail of constructs; a golden graph of about 40 field edges that owners must keep current; more nodes and edges to store | Impact stops at "this table is affected", so every report still needs a person to read SQL; a field rename such as PR #482 passes the registry check and breaks seven assets unseen |
| Keep it incremental, not rescanned | A change detector per signal, unit hashing, bitemporal writes | The graph is a snapshot that is wrong between scans; RCA reads today's graph for last night's incident |
| Build with a factory | About three weeks of oracle, twin and harness before feature code; token spend; a new operating discipline; the risk that agents satisfy tests without satisfying intent | Extractor breadth arrives serially at the speed of six engineers; each new technology or slice needs more of them; the oracle is still needed for Phase 0 but is used only as a report |
| Keep people at the gates | Gate latency; approver time | In a card-payments estate, unreviewed changes to gate policy, IAM or the scorer are an audit finding and a real risk |

### Hidden assumptions

1. Element means field, column or attribute. Row-level and record-level provenance are out of scope.
2. The estate is the plan's: AWS, MSK with a schema registry, Flink, a SQL warehouse with dbt, a feature store, a model registry. Names are illustrative.
3. "AI factory" means spec-driven software delivery in which agents write and verify the code and people own intent and gates. It does not mean a GPU data center.
4. Owners will author and maintain the golden graph. Without it there is no oracle, and the factory degrades to people reviewing every line.
5. Policy allows AI-written code in this estate when a named person approves protected changes and releases. If policy requires a person to review every change, the autonomy ladder stops at level 2 and the gain is smaller.
6. Source code and schemas may be sent to a model through an approved endpoint inside the organization's cloud boundary. Production data, payloads and secrets never are.
7. Agents never hold production credentials. Everything they need exists in the twin.
8. Element lineage is needed on tier 1 and contract-bearing assets. Dataset level is enough for the long tail.
9. The token budget is funded and tracked per merged change, and a budget overrun stops the line like a failing test does.
10. Vendor facts are as read in November 2026. They move fast, which is why the revisit triggers in ADR-002 stay live.

### Five whys: why a factory for this system

1. **Why not staff it conventionally?** The plan needs about 108 engineer-weeks for the first slice, and the long pole is the breadth of extractors, not any single hard algorithm.
2. **Why is breadth the long pole?** Element lineage needs an extractor per language and framework, and each one has a long tail of constructs. It is the reason scanner vendors maintain large connector catalogs.
3. **Why does that suit agents?** Each extractor is a bounded unit with a crisp contract: given this code and these schemas, emit these element edges.
4. **Why does a crisp contract matter?** Factory throughput is limited by verification, not generation. Without a machine-checkable oracle a person must read every line, and the gain disappears.
5. **Root.** Lineage has an objective, replayable ground truth. An edge exists or it does not, and a past change either broke a consumer or did not. That is rare, and it is what makes this system a good factory candidate. So the first investment is the oracle, not the code.

### Alternatives considered

**Where element lineage comes from.** The assessment in [doc 05](05-vendor-assessment-element-level-lineage.md) compares the options. The short form:

| Source of element lineage | Strong at | Stops at | Role in this build |
| --- | --- | --- | --- |
| Scanner suite (IBM Manta, Informatica, Collibra, Octopai, Rocket) | Stored procedures, legacy ETL, BI reports, mainframe code; the deepest baseline | Dynamic SQL; scheduled scans; no pull-request check; no services, streams or ML | Buy only if the estate has legacy ETL, and feed its output in as evidence |
| Catalog or observability product on query logs (Atlan, Alation, Monte Carlo, Datadog, Bigeye) | What actually ran in the warehouse and BI; incident triage | Code that has not run; anything outside the warehouse; retention windows | Keep or buy for detection; findings land as DQ results on elements |
| Platform-native catalog (Unity Catalog, Snowflake Horizon, Knowledge Catalog, SageMaker Catalog) | Column lineage inside the platform, with long history on Databricks and Snowflake | The platform edge; runtime only; none takes static lineage from CI | A source of runtime evidence and a projection target |
| CI tool inside a SQL project (dbt, SQLMesh, Recce, Datafold) or code-based vendor (Foundational, Gable) | Impact before merge, where it exists | The project boundary; Flink, features and models are not evidenced | Borrow the classification patterns; trial one code-based vendor on the service hop |
| Open standard and open platforms (OpenLineage, Marquez, DataHub, OpenMetadata) | One event model; column lineage from Spark, Trino, dbt and Airflow SQL | No column lineage from Flink or Kafka; no lineage history in DataHub; no shipped CI tool | Adopt the event model and collectors; a candidate store |
| **Thin owned core with adopted extractors (chosen)** | All eight hops, static and runtime evidence, history and diff | A platform to run; the service and Flink hops stay probable until an owner verifies them | ADR-002, extended to element level |

**How the code gets written**

| Delivery model | What it gets you | What it costs | Verdict |
| --- | --- | --- | --- |
| Conventional team, six engineers | Known process, known controls | Extractors arrive one at a time; breadth limited by headcount | The baseline the factory is measured against |
| AI-assisted, people write and review everything | Faster typing, same process | The review queue becomes the constraint; little change in lead time | Fallback if the factory misses its checks at the wave 1 decision point |
| **AI factory with human gates (chosen)** | Extractors built in parallel against one oracle; people spend their time on specs, scenarios and gates | Oracle and harness up front; token spend; discipline about what agents may touch | Chosen, with autonomy earned per work package |
| Dark factory, no human review at all | Maximum throughput | No named approver for gate policy, IAM or release in a regulated estate; test-gaming goes unseen | Rejected for now; revisit when escaped-defect data exists |

## What the vendor assessment changes

The full assessment, with sources and evidence grades, is in [doc 05](05-vendor-assessment-element-level-lineage.md). This section records what it changes in the design.

### What the market does, by objective

| Objective | What exists | What is missing |
| --- | --- | --- |
| O1. Baseline | Mature column lineage wherever SQL runs: scanners for stored procedures and ETL tools, query-log mining for cloud warehouses, engine capture inside Databricks and Snowflake, OpenLineage for Spark, Trino, dbt and Airflow SQL | Field-level lineage for service code, Kafka topics, Flink jobs, sink connectors, feature stores and model inputs. OpenLineage's Flink integration states that Flink 2.x lineage interfaces "do not provide column level lineage information" |
| O2. Incremental | Three styles: scheduled rescans (scanner suites), continuous log ingestion (catalogs and observability), and per-commit recompute inside a project (dbt, SQLMesh) | Lineage history and diff are rare. IBM Manta keeps revision snapshots, Marquez serves point-in-time column lineage, and SageMaker Catalog versions lineage with each event. Collibra replaces a source's lineage at every synchronisation and documents no history. DataHub's incremental mode never removes an edge. No product publishes lineage changes as a stream |
| O3. Change impact | Pull-request checks inside SQL projects: Recce, the SQLMesh bot and Paradime at column level; an asset-level comment from Atlan; a risk comment and optional merge gate from Monte Carlo; a dbt check from Datadog; and Datafold, which documents pull-request testing only for its Classic product. Two young vendors read application code. Foundational posts native pull-request checks and documents field-level lineage through Kafka, resolved from schema registry definitions. Gable scans Java and TypeScript in the customer's CI and flags how complete each field mapping is; its pull-request reports are not yet generally available. Both are vendor statements, untested | A check that crosses every hop. Nothing found covers a Flink job, a feature definition or a model input before merge. Scanner suites and cloud catalogs offer interactive impact analysis, APIs and, in 2026, tool servers for agents, but no pre-merge check. No cloud catalog derives lineage from code before it runs |
| O4. Detect and resolve | Observability products walk warehouse lineage from an anomaly and correlate it with query and code changes | Independent evidence of the effect. Every MTTD and MTTR figure found is vendor-claimed or from a vendor-funded survey. On the one academic benchmark found, AI agents named the right root cause about half the time, and less often as the lineage path grew |

### What it confirms and what it updates in ADR-002

| ADR-002 said | The assessment found | Consequence |
| --- | --- | --- |
| No catalog covers services, streams and ML | Confirmed. No vendor documents field-level lineage on those hops; Amazon MSK and Managed Flink have no lineage capture at all | The decision stands |
| SageMaker Unified Studio accepts run events only | Confirmed on the AWS page: "Currently, Amazon SageMaker Unified Studio only supports RunEvents." A column lineage facet inside a run event is honoured. It versions lineage with each event and can show it at a point in time; no retention period is stated. Its support matrix lists no Athena, Airflow or dbt | Static CI evidence still cannot be projected to it; runtime column edges can |
| Google keeps lineage 30 days and drops columns on custom events | Both confirmed on Google's own pages: "All lineage information is retained in the system for only 30 days", and custom OpenLineage events produce table-level edges only | A view of recent lineage, not a record |
| Unity Catalog keeps long history | Confirmed with limits: 395 days rolling in system tables; indefinite in Catalog Explorer for lineage captured after September 2024; external lineage is declarative, capped at 10,000 objects and 100,000 relationships per metastore, and kept out of the system tables | Strongest platform case, unchanged |
| Marquez is a candidate first-slice store | It accepts static job and dataset events and serves point-in-time column lineage, but its README still lists a release from October 2024 as the recommended one | A data model worth copying; a release cadence that argues against depending on it |
| DataHub is a candidate store | Its OpenLineage endpoint treats every event as a run event, it has no lineage history, and stale edges persist in incremental mode | If DataHub is the store, history and removal must live in the owned writer and the lake |
| New since the ADR: Snowflake | OpenLineage ingestion for external lineage has been generally available since 3 September 2026 and keeps column detail. Snowflake's own page sets the limits: Enterprise Edition, `COMPLETE` events only, at most 15,000 edges per event and 20,000 external lineage edges per account | A projection target for one slice. The account cap rules it out for an estate-wide field graph |
| New since the ADR: OpenLineage | An explicit lineage facet in which run events accumulate and job and dataset events replace. Its guide is marked experimental and says the idea may still change or be dropped | The standard now points at the same replace-or-accumulate rule this spec uses, but assume no consumer reads the facet yet |
| New since the ADR: Flink on AWS | Amazon Managed Service for Apache Flink now lists Flink 2.3.0 and 2.2.1 as supported. AWS documents no lineage capture for it or for MSK, and does not say whether the OpenLineage listener can be loaded | Dataset-level runtime evidence on the Flink hop is plausible but untested; WP-27 has to try it in a real account |

### Adopt, buy or build, by need

| Need | Decision | Why |
| --- | --- | --- |
| SQL and dbt element extraction | Adopt SQLGlot with the dbt manifest | The same parser underlies DataHub, SQLMesh and Recce; do not write one |
| Runtime column lineage | Adopt the OpenLineage integrations for Spark, dbt, Airflow and Trino | Centrally enabled; no work per team |
| Warehouse truth | Adopt the platform's own lineage and access history | Complete for what ran, including ad hoc and BI |
| Pull-request impact inside the dbt project | Adopt the open change classification from Recce or SQLMesh | It is documented, open and able to block. Build only the check that crosses hops |
| Anomaly and DQ detection | Keep or buy an observability product | Detection is a commodity; its findings arrive as results on elements |
| Legacy ETL and stored procedures, if the wider estate has them | Buy a scanner suite and treat it as a collector | Thousands of constructs already handled; not worth rebuilding |
| Service code to topic fields | Build with code rules, and trial one code-based vendor on `payments-svc` | No open tool emits lineage from code analysis. Two vendors cover this hop. Foundational documents field-level lineage through Kafka from producer and consumer code and does not say where code is processed. Gable runs in your own CI and sends code-level metadata to its platform. Either way, security decides what may leave the environment before any trial |
| Flink field mapping | Build on the Flink planner in CI | Nothing in the market provides it |
| Feature and model hops | Build small extractors over the feature repository and registry | Platform ML lineage is artifact-level and separate from the catalog |
| Identity, evidence merge, history, diff, cross-system PR impact, RCA ranking | Build: the thin core | This is where no product fits, and it is what ADR-002 chose to own |

### Patterns borrowed from the market

| Pattern | Seen in | Where it lands here |
| --- | --- | --- |
| Direct and indirect dependencies with subtypes; indirect stored at dataset scope | OpenLineage column lineage facet; IBM Manta | Element model; BL-5 |
| Static statements replace, observed runs accumulate | OpenLineage explicit lineage facet | Envelope v2 merge rules; IN-2 |
| Content fingerprint per model with parent hashes | SQLMesh snapshots; dbt state | The three hashes; IN-1 |
| Breaking and non-breaking change classes, conservative by default, with an explicit unknown | SQLMesh; Recce | Change classifier; IA-3 |
| Point-in-time lineage from versioned rows and a replayable log | Marquez; DataHub | Bitemporal writer and the evidence lake; IN-4, IN-5 |
| Anomaly correlated with query and code changes on the lineage path | Monte Carlo; Datadog; SYNQ | RCA ranker; IR-4 |
| Lineage served to coding agents as tools | Tool servers from most vendors in 2026 | Agent tool server; IA-9 |

**How far to trust this.** The first draft was researched with most vendor documentation hosts blocked. A verification pass then re-read 50 load-bearing claims at their sources: 26 were confirmed, 17 were corrected, and this section carries the corrections. Seven could not be checked, because IBM's and Informatica's documentation refuses automated requests or the documentation is silent. Prices, analyst rankings and acquisition dates still rest on search summaries. A claim read at source shows what the vendor states, not that it works: every capability on the service, stream and feature hops still needs a hands-on test.

## Scope and definitions

**In scope**

- Element-level edges for every hop of the slice, from `payments-svc` to `fraud-svc`, including the BI dashboard.
- The four capabilities in the table above, on the plan's architecture.
- The factory: spec pack, oracle, twin, harness, stations, gates and metrics.

**Out of scope**

- Row-level provenance and payload sampling. The platform stays metadata only.
- A new catalog UI. Catalogs remain projections, as ADR-002 decided.
- Technologies not in the slice. They are added as later work packages using the same template.

**Terms**

| Term | Meaning |
| --- | --- |
| Element | A field, column, attribute, feature or model input, named `<dataset URN>#<field path>` |
| Element edge | A `DERIVES` edge from one element to another element, or to a dataset when the dependency is indirect |
| Direct dependency | The source value flows into the target value: identity, transformation or aggregation |
| Indirect dependency | The source decides which rows or which value appears, without being the value: join, filter, group by, sort, window or conditional |
| Extraction unit | The smallest thing an extractor can re-read alone: a dbt model, one SQL statement, a schema subject version, a feature view, a producer mapping in a service |
| Opaque unit | A unit whose element mapping cannot be resolved: dynamic SQL, an untyped UDF, reflection |
| Oracle | The golden graph, the scenario corpus and the harness that scores against them |
| Twin | A local copy of the slice's systems, seeded with toy repos and schemas, where agents build and test |
| Work package | One unit of factory work with its own requirements, interfaces, scenarios and oracle |

## Requirements

Requirements use EARS phrasing so that agents and the harness can read them the same way. Each has an ID that work packages and scenarios trace to.

### O1. Baseline lineage

| ID | Requirement | Verified by |
| --- | --- | --- |
| BL-1 | The system shall represent every field of every tier 1 asset in the slice as a node with the URN `<dataset URN>#<field path>`, using a dotted path for nested fields and `[]` for array items. | URN property tests; golden graph node check |
| BL-2 | When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. | Envelope schema validation; fixture tests per extractor |
| BL-3 | The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". | Golden graph recall per hop |
| BL-4 | If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. | Opaque fixtures; gap count on the coverage report |
| BL-5 | The system shall store an indirect dependency once, from the source element to the target dataset, and shall not fan it out to every target column. | Graph size check on the join-heavy fixture |
| BL-6 | The baseline shall reach field-edge precision of at least 90% and recall of at least 90% against the golden graph once runtime evidence is on. | `lineage-eval score` on the slice |
| BL-7 | When the graph is rebuilt from the evidence lake, the system shall produce the same graph hash as the live graph at the same as-of time. | Replay determinism test |

### O2. Incremental lineage

| ID | Requirement | Verified by |
| --- | --- | --- |
| IN-1 | When a commit lands on a default branch, the system shall re-extract only the units whose content hash, input schema hash or extractor version changed. | Unit-invalidation scenarios; extractor call count |
| IN-2 | When a unit is re-extracted, the system shall replace that unit's prior static evidence as one atomic set, closing any element edge the new extraction no longer supports. If one extraction would close more than a set share of an extractor's edges, then the system shall hold the write and raise an alert. | Removal scenarios: delete a column, delete a model; a broken-extractor scenario |
| IN-3 | When a schema version is registered or a tier 1 table's DDL changes, the system shall publish a schema-change event and re-extract every unit that reads the changed dataset. | `SELECT *` scenario: upstream column added |
| IN-4 | The system shall write every edge version with valid-from, valid-to and recorded-at times, and shall never overwrite an edge in place. | Bitemporal property tests |
| IN-5 | The system shall return the graph as of any valid time, and the graph as it was recorded at any transaction time. | As-of scenarios, including late-arriving access history |
| IN-6 | The system shall produce a lineage diff between any two times or commits: elements and edges added, removed and changed, with the evidence that caused each change. | Diff scenarios against hand-written expected diffs |
| IN-7 | While a pull request is open, the system shall hold its static evidence in an overlay keyed by repository and PR number, invisible to production impact and RCA queries. | Overlay isolation scenario |
| IN-8 | When runtime evidence for an edge has not been seen for 30 days, the system shall mark the edge dormant and keep it. | Clock-advance scenario |
| IN-9 | When the same evidence is delivered more than once, the system shall leave the graph unchanged. | Idempotency property test |
| IN-10 | The system shall make an edge visible within 15 minutes of the merge or run that produced it, at the 95th percentile. | Freshness probe on stage replay |

### O3. Change impact

| ID | Requirement | Verified by |
| --- | --- | --- |
| IA-1 | When a pull request opens or updates in an onboarded repository, the system shall post an impact report within 5 minutes at the 95th percentile. | Timing in the twin; production probe |
| IA-2 | The report shall list each changed element with its change kind: added, removed, renamed, retyped, nullability changed, logic changed, or row set changed. | Change-kind fixtures per extractor |
| IA-3 | The system shall classify each change as breaking, potentially breaking, non-breaking or unknown. It shall classify a change that leaves the normalized expression unchanged as non-breaking, and a change in a unit it cannot parse as unknown, which is reported and treated as potentially breaking. | Classification fixtures, including formatting-only diffs and an opaque unit |
| IA-4 | The report shall list downstream elements and assets by hop with owner, tier, edge state and confidence, following direct dependencies for value impact and reporting indirect dependencies separately as row-set impact. | PR #482 scenario; direct and indirect fixtures |
| IA-5 | While the gate is in block mode, the system shall fail the check only when a tier 1 contract element with confirmed downstream readers is removed, renamed or retyped without a version bump or sign-off from those readers' owners. | Gate policy scenarios |
| IA-6 | If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. | Fail-open scenario |
| IA-7 | The report shall offer a "this is wrong" action per row, and a disputed edge shall drop to candidate until reviewed. | Feedback scenario |
| IA-8 | On the change replay corpus the report shall list at least 8 of every 10 consumers that actually broke. | `lineage-eval replay changes` |
| IA-9 | The system shall expose the same impact query through an API that coding agents can call before a pull request exists. | API contract test |

### O4. Detect and resolve

| ID | Requirement | Verified by |
| --- | --- | --- |
| IR-1 | When a DQ or contract check fails on an element, the system shall attach the upstream path, the ranked change events and the blast radius to the alert within 2 minutes. | Incident scenarios in the twin |
| IR-2 | The system shall walk upstream over the incident window: every edge valid at any time between the last passing check and the failure, including edges that closed in between. It shall not use the current graph. | Scenario where the offending edge closed before the alert; scenario where an edge changed after the incident |
| IR-3 | The system shall identify the first failing element: the furthest upstream element with a failing check whose own inputs pass or have no check. | Multi-hop failure fixtures |
| IR-4 | The system shall rank change events on the upstream path by a deterministic score, and shall show the terms of the score, the evidence path and any lineage gap on that path for each candidate. | Ranking fixtures; explanation snapshot; a scenario with an opaque hop |
| IR-5 | On the incident replay corpus the true cause shall be ranked first on at least 70% of incidents and in the top three on at least 90%. | `lineage-eval replay incidents` |
| IR-6 | The system shall split the blast radius into assets already affected and assets not yet affected, using run events after the failure time. | Scheduled-run fixtures |
| IR-7 | The system shall emit a remediation plan in topological order with an action per node type and the owning team. | Plan snapshot for the PR #482 hotfix scenario |
| IR-8 | Where a job has opted in to the circuit breaker, the system shall pause it when an upstream tier 1 element is failing, and shall resume it only on a person's instruction. | Circuit breaker scenario |
| IR-9 | The system shall record, per incident, when bad data landed, when the alert fired, when the cause was identified and when remediation completed. | MTTD and MTTR report against the Phase 0 baseline |

### Cross-cutting

| ID | Requirement | Verified by |
| --- | --- | --- |
| XC-1 | The system shall collect and store metadata only: names, schemas, expressions, counts and times. It shall not store payload values. | Schema allow-list; scan of the evidence lake fixture |
| XC-2 | Every edge shall be traceable to its evidence records, and every evidence record to the raw input and the tool version that produced it. | Trace test from edge to `rawRef` |
| XC-3 | The system shall never block or slow a producer. All emission shall be asynchronous and droppable. | Fault-injection scenario |
| XC-4 | The system shall accept and emit OpenLineage events, including the column lineage facet, without loss of dependency class and subtype. | Round-trip test |
| XC-5 | The system shall show elements tagged as personal data only to roles allowed to see them. | Access-control scenario |
| XC-6 | Where a model is used to read code, the system shall send only source code and schemas through the approved endpoint, and shall record the model, prompt version and output hash with the evidence. | Egress allow-list test; evidence field check |

## Design

### Element model

The plan's graph model already names fields with a `#` suffix and has a `DERIVES` edge. This spec makes three additions.

**1. Element edges are first-class.** The build guide's envelope carries columns as a list on a dataset edge. In v2 each element mapping becomes its own edge with its own key, evidence and confidence, because one column of a model can be confirmed at runtime while another is static only.

```text
edge key = <from URN>#<field> | DERIVES | <to URN>#<field>
```

**2. Dependency class and subtype.** The plan's four transforms (identity, rename, aggregate, filter) widen to the taxonomy in the OpenLineage column lineage facet, so runtime events map without translation.

| Class | Subtype | Example on the slice | How impact treats it |
| --- | --- | --- | --- |
| Direct | Identity | `raw.card_auth#mcc` to `fct_card_auth#mcc`; a rename is identity with two names | Value impact: a removed or retyped source breaks the target |
| Direct | Transformation | `auth_ts` to `auth_date` through a cast | Value impact, and a changed expression is a logic change |
| Direct | Aggregation | `fct_card_auth#declined` to `mcc_decline_7d` through a 7-day sum | Value impact, and a changed window is a logic change |
| Indirect | Join, filter, group by, sort, window, conditional | `status = 'AUTH'` filters `fct_card_auth`; `mcc` is the group-by key of the feature | Row-set impact: reported separately and never blocks alone |

**3. Gaps are stated.** An opaque unit produces a dataset-level edge with `opaque: true` and a reason code. The affected target elements are flagged `lineage_gap`. Impact reports then say "field-level unknown through `txn-enrichment` (DataStream API)" instead of ending the path quietly. The gap count per hop is a coverage metric.

**An element edge record**

```json
{
  "from": "warehouse://prod/analytics.fct_card_auth#declined",
  "to": "feast://fraud/mcc_decline_7d#value",
  "type": "DERIVES",
  "class": "DIRECT",
  "subtype": "AGGREGATION",
  "expr_hash": "sha256:7c0e…",
  "evidence": [
    {"source": "ci_static", "tool": "feature-repo-extractor@1.2.0",
     "unit": "unit://git/fraud-features/feature_views/mcc_decline.py#mcc_decline_7d",
     "commit": "b81d09a", "seen": "2026-11-24T10:12:00Z"},
    {"source": "openlineage", "tool": "feast-materialize", "seen": "2026-11-26T04:00:41Z"}
  ],
  "confidence": 0.98,
  "state": "confirmed",
  "valid_from": "2026-10-02T00:00:00Z",
  "valid_to": null,
  "recorded_at": "2026-11-26T04:03:10Z"
}
```

### Evidence envelope v2

The envelope keeps its shape and gains a `unit` block and an `elements` list. Collectors that only know datasets keep sending v1; the core accepts both.

```json
{
  "eventType": "EVIDENCE",
  "eventTime": "2026-11-26T14:02:11Z",
  "producer": "lineage-extractors/dbt-sql@2.0.0",
  "unit": {
    "urn": "unit://git/analytics-dbt/models/marts/fct_card_auth.sql",
    "contentHash": "sha256:5d1c…",
    "inputSchemaHash": "sha256:a07e…",
    "commit": "9f3c2e1",
    "pr": 482
  },
  "edge": {
    "type": "DERIVES",
    "from": {"namespace": "iceberg://s3-prod", "name": "raw.card_auth"},
    "to": {"namespace": "warehouse://prod", "name": "analytics.fct_card_auth"},
    "elements": [
      {"from": "mcc", "to": "mcc", "class": "DIRECT", "subtype": "IDENTITY", "exprHash": "sha256:11aa…"},
      {"from": "auth_ts", "to": "auth_date", "class": "DIRECT", "subtype": "TRANSFORMATION", "exprHash": "sha256:77c0…"},
      {"from": "status", "to": null, "class": "INDIRECT", "subtype": "FILTER", "exprHash": "sha256:be42…"}
    ],
    "opaque": []
  },
  "evidence": {
    "source": "ci_static", "weight": 0.60, "runtime": false,
    "observedAt": "2026-11-26T14:02:09Z", "replaces": "unit",
    "rawRef": "evidence_raw/ci_static/dt=2026-11-26/part-0031.parquet"
  }
}
```

Two rules change in the core's merge step.

- **Static evidence is owned by its unit.** `replaces: "unit"` tells the core that this event set is the complete truth for that unit and extractor. Any element edge the unit supported before and does not support now loses that support. This is what makes a deleted column disappear from the graph on the next merge instead of the next full rescan.
- **Runtime evidence is additive.** It only ever adds support and refreshes last-seen. It leaves the graph by decay, not by replacement.

### Baseline: one extractor per hop

The baseline is not one scan. It is one extractor per hop, each chosen for the best source of element truth at that hop, plus a runtime source that confirms it where one exists.

| Hop on the slice | Static source of element truth | Runtime confirmation | Expected state after both |
| --- | --- | --- | --- |
| `payments-svc` to `auth.events.v1` | Avro schema plus code rules for which fields the producer sets | OTel producer span (dataset level) | Probable; verified by the owner for tier 1 fields |
| `auth.events.v1` to `auth.enrich.v1` through `txn-enrichment` | Flink SQL through the planner in a CI harness; a declared mapping for DataStream code | OpenLineage Flink event (dataset level) | Probable; verified by the owner |
| `auth.enrich.v1` to `raw.card_auth` | Sink connector configuration and its field mapping | OpenLineage or connector status | Probable to confirmed |
| `raw.card_auth` to `fct_card_auth` | dbt manifest and compiled SQL through a column-lineage parser | OpenLineage dbt column facet; warehouse access history | Confirmed |
| `fct_card_auth` to the Approval rate dashboard | BI metadata API for the fields a dashboard uses | Warehouse access history by service account | Confirmed |
| `fct_card_auth` to `mcc_decline_7d` | Feature repository: source columns, entity keys, aggregation | Materialization run event | Confirmed |
| `mcc_decline_7d` to `fraud-score-v12` | Training configuration and the model signature in the registry | Training run event | Confirmed |
| `fraud-score-v12` to `fraud-svc` | Registry deployment record and the serving request schema | Inference call edge from gateway logs | Confirmed |

**What the research says about these choices**

- **Flink.** The OpenLineage integration reports datasets only, and its docs call column lineage for Flink SQL a proposed extension. Field edges on that hop come from the planner in CI or a declared mapping, as the plan already assumed.
- **dbt and SQL.** dbt's own column lineage covers select lists and, by its docs, "doesn't reflect other usage like joins and filters", and it cannot parse Python models. The OpenLineage dbt integration says its column lineage was "tested with simple projections only". So the extractor parses compiled SQL itself to get indirect dependencies, and treats both of those as confirmation.
- **Known hard constructs.** DataHub's parser, built on the same SQLGlot, documents no column lineage for `MERGE INTO`, multi-statement scripts, table-valued functions and the inside of UDFs. These are the first entries in the opaque reason codes, and the fixtures for BL-4.
- **Service code.** No open-source project was found that turns code analysis (Semgrep, CodeQL, Joern) into lineage. WP-23 is a real build, which is why a vendor trial on that hop is worth a week.
- **Model-assisted extraction.** No published precision or recall at column level was found. WP-29 therefore emits candidate evidence only, each edge checked by a verifier against real schemas, and it can never lift an edge above probable alone.
- **Accuracy numbers.** The only parser figure found is vendor-stated and its method is unpublished. Targets in this spec are set against the local golden graph, not the literature.

### Incremental engine

A graph that is rescanned is wrong between scans. The incremental engine makes every change to the estate an event that touches only what it must.

**Change signals**

| Signal | Detected from | What it invalidates | Target latency |
| --- | --- | --- | --- |
| PR opened or updated | Git provider webhook, CI workflow | Units in the diff, into the PR overlay | Under 5 minutes |
| Merge to default branch | Webhook, CI workflow on the default branch | Units in the diff; their static evidence is replaced | Under 15 minutes |
| Schema version registered | Schema registry event | Units that read the subject, through the input schema hash | Under 5 minutes |
| Table DDL change | Warehouse schema history, hourly | Units that read the table | Bounded by the source's lag |
| Job run | OpenLineage run event | Nothing; adds runtime evidence and refreshes last-seen | Minutes |
| Query history | Hourly pull of access history | Nothing; adds runtime evidence | Bounded by the source's lag |
| Deploy, DQ result, contract check | CD and check events on the evidence topic | Nothing; lands on the change timeline for RCA | Minutes |
| No runtime evidence for 30 days | Daily decay job | Edge state moves to dormant | Daily |

**Three hashes decide whether a unit is re-read.** The content hash covers the unit's normalized source. The input schema hash covers the schema versions of everything the unit reads, which is what catches a `SELECT *` that changes meaning when an upstream column is added. The extractor version covers a parser upgrade. If none changed, the unit is skipped. This keeps a merge that touches three models from re-parsing three thousand.

**Bitemporal edges.** Valid time records when a flow was true in the world. Recorded time records when the graph learned it. RCA asks a valid-time question: what fed this column at 02:42? An audit asks a recorded-time question: what did the graph tell the PR bot when it approved the change? Late evidence, such as access history that lags by hours, is written with its true valid time and a later recorded time, so history is corrected without being silently rewritten. The public designs found stop short of this. Marquez reads versioned rows with a timestamp bound and DataHub replays its change log, and neither records what was believed at one time about another. The second clock is this spec's own addition, and WP-13 carries the risk of it.

**Lineage diff.** Every graph write that changes an edge's existence, class, subtype, expression hash or state is published to a `lineage.changes` topic. The diff between two times or commits is a fold over that stream. It has three consumers: the PR report (base graph against base plus overlay), catalog projections (send only what changed), and RCA (what changed in lineage inside the incident window).

### Change impact

The PR flow answers one question before merge: which elements does this change touch, and who reads them?

1. **Extract twice.** Run the extractors on the changed units at the base commit and at the head commit.
2. **Diff by element.** Compare the two extractions. Schema diffs give added, removed, retyped and nullability changes. A removed field and an added field of the same type in the same position is a probable rename and is reported as one. A changed expression hash on an unchanged column is a logic change. A changed filter or join is a row-set change.
3. **Classify.** Removed, renamed and narrowed elements are breaking. Logic and row-set changes are potentially breaking. Additions and changes that leave the normalized expression unchanged are non-breaking, so reformatting a model produces an empty report.
4. **Overlay.** Write the head extraction into the PR overlay. Nothing in the production graph changes.
5. **Walk.** From each changed element, follow direct edges downstream on the base graph plus the overlay, at confidence 0.6 and above, to ten hops. Collect indirect dependents separately.
6. **Rank and render.** Order by tier, then edge state, then hops, then recent read volume. Post one comment and one check status. Request sign-off from the owners of confirmed tier 1 readers.
7. **Gate.** Warn by default. Block only under IA-5. Fail open under IA-6.

The registry's own compatibility check is not enough, and PR #482 is the proof: removing `merchant_category_code` and adding `mcc` with a default passes BACKWARD compatibility while breaking seven assets. The element diff sees a rename with five tier 1 readers.

### Detect and resolve

The incident flow answers two questions when a check fails: what is the most likely cause, and what must be fixed in which order?

1. **Trigger.** A DQ or contract result arrives on the evidence topic as a failing assertion on an element at time *t*. The detector can be a contract rule, a DQ tool or an observability product; the platform does not need to own detection.
2. **Walk upstream over the incident window.** Use every edge valid between the last passing check and *t*, because the edge that explains the failure has often been closed by the change that caused it. Follow direct edges first, then indirect ones, collecting each ancestor's check state at *t*.
3. **Find the first failing element** (IR-3). That is where the investigation starts, usually several hops above where the alert fired.
4. **Collect change events** on the path between the last passing check and *t*: schema registrations, merged PRs with their lineage diff, deploys, failed or late runs.
5. **Score candidates** with a transparent sum: the change touches an element on the path, it falls between last pass and first fail, it sits near the first failing element, and its change class is breaking. Weights are calibrated on the incident replay corpus. A model may write the narrative from that bounded evidence set. It does not set the ranking, so the result is reproducible and explainable. The one benchmark found for this task, DataTrace, is the reason: seven frontier models averaged 48% top-1 root-cause accuracy, got worse as the lineage path grew, and gave a correct answer without supporting evidence in 15% to 23% of their correct cases. Showing the path is the control.
6. **Scope the blast radius** downstream as of *t*, split by run events into already affected and not yet affected.
7. **Plan remediation** in topological order with an action template per node type, and pause opted-in jobs through the circuit breaker.
8. **Record the four timestamps** in IR-9, which is what turns MTTD and MTTR from estimates into a series.

### Interfaces

| Interface | Consumers | Notes |
| --- | --- | --- |
| `lineage.evidence` topic, envelope v1 and v2 | Every collector and extractor | JSON Schema in the spec pack; the harness validates every event |
| `lineage.changes` topic | Catalog projections, notifications, RCA | One event per material edge change |
| `GET /impact`, `GET /upstream`, `GET /diff`, `GET /explain` | PR bot, RCA service, UI, coding agents | All take `as_of` and `min_confidence`; `/explain` returns evidence for an edge |
| OpenLineage in and out | Runtime integrations; catalogs | Column lineage facet preserved both ways (XC-4) |
| Agent tool server | Coding agents inside and outside the factory | The same four queries as tools, so an agent can ask what a rename breaks before it opens a PR (IA-9) |

### Non-functional requirements

| Area | Requirement |
| --- | --- |
| Freshness | PR report under 5 minutes and merge or run to edge under 15 minutes, both at the 95th percentile |
| Accuracy | The plan's targets by phase, measured weekly by `lineage-eval` and published |
| Determinism | The same evidence in the same order yields the same graph hash |
| Availability | Fail open everywhere a producer or a merge could otherwise wait on the platform |
| Security | Metadata only; KMS on every store; SSO on the API; least-privilege roles per service; no agent holds production credentials |
| Cost | Model calls inside the product are limited to opaque units and narrative text; every call is logged with tokens used |
| Operability | Every edge records the extractor version, so a bad release can be excluded and the graph rescored from the lake |

## The AI factory

### What the term means here

An AI factory is a way of delivering software in which the specification is the durable asset and code is produced from it by agents. People decide what should exist and how it will be judged. Agents plan, implement, test and review. A harness, not a person's reading of the diff, is the primary check on correctness. People stay accountable at a small number of gates.

**Where the term comes from.** The software sense of "factory" took shape in January and February 2026 in three public accounts: Dan Shapiro's five levels of AI-assisted programming, whose top level is the "dark factory"; StrongDM's Software Factory, with its two rules that code is neither written nor reviewed by people; and OpenAI's "harness engineering" account of a product built by agents under the motto "Humans steer. Agents execute." Spec-driven toolkits give the method its artefacts. GitHub Spec Kit runs constitution, specify, plan, tasks, implement and converge. The AWS AI-DLC workflows describe 5 phases and 33 stages with human approval gates and a 134-event audit trail, and run inside Claude Code, Kiro, Codex and Cursor. StrongDM publishes its orchestrator, Attractor, as specifications only, with human gates as first-class pipeline nodes.

**What this spec takes from them**

| Idea | Source | How it appears here |
| --- | --- | --- |
| Scenarios kept outside the builder's reach, like a holdout set | StrongDM | Principle 3 and the holdout corpus |
| A twin of external systems so agents can test at volume | StrongDM's Digital Twin Universe | The twin of the slice |
| A constitution, then spec, plan, tasks | GitHub Spec Kit | `factory/constitution.md` and the spec pack |
| Approval after each stage and an audit trail per change | AWS AI-DLC | The four gates and `factory/runs/` |
| Rules that must hold are enforced by the build, not by instructions | OpenAI harness engineering; Claude Code guidance | Protected paths, policy checks and sandbox limits at station 5 and 6 |
| A separate evaluator, because agents grade their own work leniently | Anthropic harness guidance | Principle 5; the harness and the reviewer are not the builder |
| The verifier must be nearly perfect or the agent solves the wrong problem | Anthropic's parallel-agents compiler write-up | "Oracle first"; G3 |

**What the evidence does and does not show.** It supports a factory with people at the gates. It does not support removing them.

- The no-review variant is advocated, not demonstrated. StrongDM's results are self-reported, and no independent audit or outcome data for a lights-off factory was found. A detailed practitioner critique reports a failed lights-off attempt and says agent-built codebases begin to struggle after three to six months.
- DORA's 2025 research finds that "AI improves throughput, but often at the cost of stability if your foundation isn't solid", and describes AI as an amplifier of an organization's existing strengths and weaknesses.
- Controlled results are mixed. METR's 2025 trial found experienced developers took 19% longer with early-2025 tools. Its February 2026 update estimates 18% less task time for the same developers, with an interval that still includes no change, and METR calls the data an unreliable signal.
- Telemetry studies report more merged pull requests alongside longer review times and more defects, which is the review constraint this spec plans for.
- Cost varies by two orders of magnitude: about $13 per developer-day for typical enterprise use of one coding agent, up to StrongDM's benchmark of $1,000 per engineer-day. A planner, builder and evaluator harness cost about twenty times a single unassisted run on the same brief in one published comparison.
- No regulator or card-scheme endorsement of development without human review was found. Secure-development requirements for card environments are written around accountable review and approval.

So this spec is what one commentator calls a light factory: agents execute, people approve, and autonomy widens only on measured results. The sources, and which of them were read in full, are in [doc 05](05-vendor-assessment-element-level-lineage.md).

### Operating principles

1. **The spec is the source of truth.** If code and spec disagree, fix the spec first, then regenerate or repair the code. A fix made only in code will be undone by the next agent.
2. **No work package without an oracle.** A requirement that cannot be checked by the harness is rewritten until it can, or it is assigned to a person.
3. **Builders never see the holdout.** Visible scenarios guide the build. Holdout scenarios are run by the harness in a separate job, and the builder gets back a pass rate and failure categories, never the scenario text.
4. **The oracle is protected.** The golden graph, the scenario corpus, the harness and the gate policies live under protected paths. Agents can propose changes to them. Only people merge them.
5. **Builder and reviewer are different agents.** The reviewer starts from the spec and the diff with a fresh context and checks conformance, not style.
6. **Everything runs in the twin.** No agent holds production credentials or reads production data.
7. **Escaped defects become scenarios.** Every defect found after a gate adds a holdout scenario and, if the spec was wrong or silent, a spec change.
8. **Autonomy is earned and can be lost.** It is set per work package from the strength of its oracle and its blast radius, and it moves on measured results.
9. **Budgets stop the line.** A work package that exceeds its token or retry budget stops and goes to a person, the same as a failing gate.

### Stations and gates

| Station | Who | Input | Output | Gate or stop rule |
| --- | --- | --- | --- | --- |
| 1. Intent | Person | Objective, constraints, measures | Intent brief | None |
| 2. Specify | Person owns, agent drafts | Intent brief, existing docs | Requirements, interface schemas, visible and holdout scenarios, fixtures | **G1 spec gate:** domain owner and platform lead approve |
| 3. Plan | Agent | Spec pack | Work packages and tasks, each traced to requirement IDs | Automated: every task has a requirement and an oracle |
| 4. Build | Agents, one sandbox each | Work package, twin | Code, tests, a change summary | Token and retry budget |
| 5. Verify | Harness | Branch | Scores: unit and property tests, visible scenarios, holdout pass rate, golden precision and recall, replay determinism, security scans | Automated: thresholds in the work package |
| 6. Review | Second agent, then policy checks | Spec, diff, scores | Conformance findings; protected-path and IaC diff report | Automated; findings return to station 4 |
| 7. Approve | Person | Evidence bundle | Merge decision | **G2 change gate:** every change at level 2; protected paths and exceptions at levels 3 and 4. **G3 oracle gate:** any change to the oracle |
| 8. Release | Pipeline, person approves | Merged build | Stage replay of a day of production evidence, accuracy report, change record | **G4 release gate:** accuracy does not drop; named approver |
| 9. Operate and learn | People and agents | Incidents, reconciliation findings, owner feedback | New scenarios, spec changes | Weekly factory review |

Three feedback paths close the loop. A failed verification returns to the builder with the failing category. A rejected change at G2 returns to the spec, because a change that passed the harness and still looks wrong means the spec or the oracle was incomplete. An escaped defect returns as a holdout scenario.

### The oracle

Four things make "correct" machine-checkable for this system.

- **The golden graph.** About 15 service and dataset edges and 40 element edges for the slice, written with the owners in Phase 0 and stored as fixtures. The harness reports precision and recall per edge type and per hop.
- **The change replay corpus.** The last ten schema and logic changes on the slice, each with the base commit, the head commit and the consumers that actually broke. It scores O3.
- **The incident replay corpus.** Six months of incidents on the slice, each with the failing check, the timeline of change events and the true cause. It scores O4.
- **The twin.** Kafka with a schema registry, a Flink mini cluster, a local SQL engine standing in for the warehouse with the dbt project, a local feature store and model registry, object storage, and a stub Git provider, all started by one command and seeded with toy versions of the slice's repositories. Every scenario runs here.

Around them sit property tests for the core (noisy-OR is monotonic, merge is idempotent, replay is deterministic, as-of reads are stable) and metamorphic tests for the extractors (renaming an alias, reordering a CTE or reformatting a query must not change the element edges).

The corpus is split. About two thirds of the scenarios are visible to builders. The rest are holdout. The split is by scenario family, so a builder cannot pass the holdout by memorizing the visible ones.

### Spec pack layout

```text
factory/
  constitution.md            rules every agent run loads: principles, protected paths, definition of done
  specs/
    <capability>/
      requirements.md        EARS requirements with IDs
      interfaces/            JSON Schema, OpenAPI
      design.md              decisions and constraints, not code
      scenarios/visible/     Given/When/Then with fixtures
  work-packages/
    WP-20-dbt-sql-extractor.md   scope, inputs, outputs, requirement IDs, thresholds, autonomy level, budget
  oracle/                    PROTECTED: people merge
    golden-graph/            nodes and edges as YAML
    replay/changes/          base, head, expected consumers
    replay/incidents/        timeline, failing check, true cause
    holdout/                 not readable from build sandboxes
    harness/                 lineage-eval
    policies/                gate rules as code
  twin/                      compose file, seed repos, seed schemas
  runs/                      one record per agent run: spec version, work package, transcript ID, commit, scores, tokens
```

### Work packages

Each work package is sized so that one agent can finish it in one sandbox against one oracle. The autonomy level is the starting level, defined under "Autonomy ladder".

| ID | Work package | Serves | Oracle | Start level |
| --- | --- | --- | --- | --- |
| **Wave 0: oracle and twin** | | | | |
| WP-00 | Constitution and spec pack skeleton | All | People review | People |
| WP-01 | Golden graph at element level, as fixtures | O1 | Owners sign | People, agent drafts candidates |
| WP-02 | Change and incident replay corpora, visible and holdout split | O3, O4 | Owners and platform lead sign | People |
| WP-03 | Twin of the slice | All | Smoke scenarios run end to end | 2 |
| WP-04 | Scoring harness `lineage-eval` | All | People review every line; it is the oracle | 2 |
| **Wave 1: core semantics** | | | | |
| WP-10 | URN library with nested field paths | O1 | Property tests | 2 |
| WP-11 | Envelope v2 schema and emit library | O1, O2 | Schema tests; v1 compatibility | 2 |
| WP-12 | Merge and scorer with unit-owned static evidence | O1, O2 | Property tests; removal scenarios | 2 |
| WP-13 | Bitemporal graph writer and as-of reads | O2 | Bitemporal property tests; replay determinism | 2 |
| WP-14 | Lineage diff and the `lineage.changes` stream | O2 | Diff scenarios | 2 |
| WP-15 | Identity resolver at element level | O1 | Alias fixtures; unresolved rate | 2 |
| **Wave 2: element extractors, built in parallel** | | | | |
| WP-20 | dbt and SQL extractor | O1 | Golden hop; metamorphic tests | 3 |
| WP-21 | Avro and Protobuf schema differ and registry watcher | O1, O2 | Schema-change fixtures | 3 |
| WP-22 | Flink SQL extractor on the planner harness | O1 | Golden hop | 3 |
| WP-23 | Service producer and consumer field scanner | O1 | Golden hop; rule fixtures per framework | 3 |
| WP-24 | Sink connector extractor | O1 | Golden hop | 3 |
| WP-25 | Feature repository and training config extractor | O1 | Golden hops | 3 |
| WP-26 | Warehouse access-history collector at column level | O1, O2 | Recorded query fixtures | 3 |
| WP-27 | OpenLineage ingestion with column facets | O1, O2 | Round-trip tests | 3 |
| WP-28 | BI metadata extractor | O1 | Golden hop | 3 |
| WP-29 | Model-assisted extractor for opaque units, with a verifier | O1 | Opaque fixtures; precision floor | 2 |
| **Wave 3: incremental and impact** | | | | |
| WP-30 | Change detectors and unit invalidation | O2 | Invalidation scenarios; call counts | 3 |
| WP-31 | PR overlay and impact query API | O3 | Overlay isolation; PR #482 scenario | 3 |
| WP-32 | Change classifier | O3 | Classification fixtures | 3 |
| WP-33 | PR bot in warn mode with feedback | O3 | Change replay, visible and holdout | 3 |
| WP-34 | Contract gate in block mode | O3 | Gate policy scenarios | 2 |
| **Wave 4: detect and resolve** | | | | |
| WP-40 | DQ and contract result ingestion on elements | O4 | Assertion fixtures | 3 |
| WP-41 | Change-event timeline | O4 | Timeline fixtures | 3 |
| WP-42 | RCA ranker | O4 | Incident replay, visible and holdout | 3 |
| WP-43 | Remediation planner and circuit breaker | O4 | Plan snapshots; breaker scenario | 2 |
| WP-44 | MTTD and MTTR recorder | O4 | Timestamp fixtures | 3 |
| **Wave 5: projections and operations** | | | | |
| WP-50 | Catalog projections from `lineage.changes` | All | Projection round trip | 3 |
| WP-51 | Read API and agent tool server | O3, O4 | Contract tests | 3 |
| WP-52 | Terraform modules and service roles | All | Policy checks; plan diff reviewed by a person | 2 |
| WP-53 | Dashboards, alarms and runbooks | All | Fault-injection scenarios | 3 |

### Autonomy ladder

| Level | Who writes | Who reviews | Who merges | Used for |
| --- | --- | --- | --- | --- |
| 1 | Person, agent assists | Person | Person | The golden graph, replay corpora, gate policy |
| 2 | Agent | Person reads every change | Person | Core semantics, the harness, IaC, anything that blocks or pauses a team |
| 3 | Agent | Second agent; person reviews exceptions and a weekly sample | Person approves a batch | Extractors and services with a strong oracle |
| 4 | Agent | Second agent | Automatic on green; person reviews scores weekly | Extractor rule additions and regression fixtures, once earned |
| 5 | Agent | None | Automatic | Not used |

**Promotion.** A work package family moves up one level after five consecutive changes with a holdout pass rate at or above its threshold, no escaped defect, and no finding in the weekly sample. **Demotion.** Any escaped defect that reached stage or production, or any attempt to edit a protected path, moves the family down one level and adds a scenario.

### People and accountability

The plan staffs six engineers. The factory keeps the six and changes what they do.

| Role | Count | Owns |
| --- | --- | --- |
| Platform lead | 1 | Intent, G1 and G4, the autonomy ladder, the weekly factory review |
| Factory engineers | 2 | The twin, the harness, the pipeline, sandboxes and budgets |
| Spec owners (streaming, analytics, ML) | 3 | Requirements, scenarios and G2 for their hops; the golden graph sessions with slice owners |
| Slice owners | About 6 teams | Signing the golden graph, working the reconciliation queue, G1 for their boundary |

What people stop doing is typing extractor code. What they start doing is writing scenarios precise enough that a wrong extractor fails them.

### Controls for a regulated estate

- **Named approver.** Every merge to a protected branch and every production release has a named person, recorded in the run record.
- **Segregation of duties.** The building agent, the reviewing agent and the approving person are distinct. The agent that built a change cannot approve it.
- **Traceability.** Each run record links spec version, work package, agent transcript, commit, harness scores and approval. That chain is the change record.
- **Least privilege.** Sandboxes have no route to production, no production secrets and an egress allow-list. Agents open pull requests; they do not push to protected branches.
- **Model boundary.** Code and schemas go to the model through the approved endpoint only. No production data, payloads or secrets enter a prompt.
- **Supply chain.** Dependencies come from an allow-list; licence, secret and vulnerability scans run at station 5 on every change.
- **Labelling.** Agent-authored commits are marked as such, so later audits can tell them apart.

### Factory metrics and budgets

| Metric | Definition | Use |
| --- | --- | --- |
| Lead time | Work package ready to merged | The main throughput number |
| First-pass rate | Share of builds that pass station 5 on the first attempt | Spec and context quality |
| Holdout pass rate | Share of holdout scenarios passed at merge | The trust number; drives promotion |
| Golden delta | Change in precision and recall per merged change | Catches regressions the scenarios miss |
| Escaped defects | Defects found after G2, per work package | Drives demotion and new scenarios |
| Person-minutes per change | Review and approval time | Shows whether the gates are the constraint |
| Cost per merged change | Model tokens and compute | Budget control |
| Rework rate | Work packages reopened after merge | Spec stability |

Budgets are set per work package before it starts: a token ceiling, a retry ceiling and a wall-clock ceiling. Hitting any one stops the run and raises it to a person.

### Failure modes of the factory

| Failure | How it shows | Response |
| --- | --- | --- |
| Agents satisfy the tests but not the intent | Visible pass rate high, holdout pass rate lower | Holdout by scenario family; metamorphic tests; G2 samples |
| The oracle is wrong | A correct extractor fails; owners dispute golden edges | G3; owner re-signs; the disputed edge is excluded until settled |
| Spec drift | Code fixed by hand; the next agent run reverts it | Principle 1; the harness checks that every changed file traces to a work package |
| Review becomes the constraint | Person-minutes per change rise; G2 queue grows | Promote families with strong oracles; shrink work packages |
| Cost runs away | Cost per merged change rises without quality | Budgets stop the line; tighten context; split the package |
| The twin diverges from production | Passes in the twin, fails on stage replay | Stage replay is G4; each divergence adds a twin fixture |
| An agent reaches for more access | Attempted write to a protected path or blocked egress | Denied by the sandbox; logged; demotion |

## Delivery plan

### Waves against the plan's phases

The plan's phases and exit gates stay. The factory changes what happens inside them.

| Plan phase | Factory wave | What people do | What agents do |
| --- | --- | --- | --- |
| 0. Baseline and golden graph | Wave 0 | Golden graph sessions, replay corpora, constitution, G3 on the harness | Draft candidate edges from code for owners to confirm; build the twin and the harness |
| 1 and 2. Gateway edges, components and catalog | Wave 1 | Review every core change (level 2) | Build the core with element-level semantics |
| 3. Static code edges and PR impact | Waves 2 and 3 | Write extractor scenarios; G2 by exception | Build the extractors in parallel; build the overlay, classifier and bot |
| 4. Runtime edges and reconciliation | Waves 2 and 3 | Work the reconciliation queue; turn findings into scenarios | Build runtime ingestion; add a regression fixture per finding |
| 5. Contracts, DQ and RCA | Wave 4 | Curate incident replays; approve gate policy | Build ingestion, timeline, ranker and planner |
| 6. Widen | Wave 5 and repeats | Pick slices; write per-slice golden samples | Build projections; extend extractors to new technologies using the same work package template |

No calendar compression is promised. The exit gates depend on owner sessions and on runtime evidence, and neither is faster with agents. The hypothesis to test is narrower: with the oracle in place, the wave 2 extractors can be built in parallel and limited by how fast scenarios are written rather than how fast code is typed.

### Decision points

| When | Question | If yes | If no |
| --- | --- | --- | --- |
| End of wave 0 | Do the harness and twin score the hand-built reference (`code/element_lineage_demo.py`) correctly? | Start wave 1 | Fix the oracle before any more code |
| End of wave 1 | Did the core work packages hold their holdout pass rate with no escaped defect? | Run wave 2 at level 3 | Run wave 2 at level 2 and re-test after three packages |
| After the first three wave 2 packages | Are lead time and person-minutes per change better than the plan's estimate for the same scope? | Continue; consider level 4 for rule additions | Fall back to AI-assisted delivery and keep the oracle |
| Each phase gate | Does the plan's exit gate pass? | Next phase | Same rule as the plan: the phase is not done |

## Traceability

| Objective | Requirements | Work packages | Scored by | Plan gate |
| --- | --- | --- | --- | --- |
| O1. Baseline | BL-1 to BL-7 | WP-01, WP-10 to WP-15, WP-20 to WP-29 | Golden graph precision and recall per hop; replay determinism | Phases 3 and 4 |
| O2. Incremental | IN-1 to IN-10 | WP-12 to WP-14, WP-21, WP-26, WP-27, WP-30 | Invalidation, removal, as-of and diff scenarios; freshness probe | Phase 4 |
| O3. Change impact | IA-1 to IA-9 | WP-31 to WP-34, WP-51 | Change replay; classification fixtures; gate scenarios | Phases 3 and 5 |
| O4. Detect and resolve | IR-1 to IR-9 | WP-40 to WP-44 | Incident replay; plan snapshots; MTTD and MTTR series | Phase 5 |
| Cross-cutting | XC-1 to XC-6 | WP-11, WP-27, WP-50 to WP-53 | Trace, round-trip, access and fault scenarios | All |

## Reference run

[`code/element_lineage_demo.py`](../code/element_lineage_demo.py) runs the four objectives end to end on toy versions of the slice's repositories. It parses the SQL with SQLGlot, keeps unit-owned evidence in a versioned graph, and asserts its own results with `--check`. It is one file a person can read in ten minutes. It is the hand-built reference that the wave 0 decision point asks for, and the first set of fixtures for the oracle.

```text
pip install sqlglot
python3 code/element_lineage_demo.py --check
```

| Objective | What the run does | Result on the slice |
| --- | --- | --- |
| O1. Baseline | Reads eight units and scores the element edges against a hand-written golden graph | 26 element edges with class and subtype. Precision 1.00, recall 0.93. The two missed edges are the service-to-topic hop, which has no extractor in the demo (WP-23) |
| O3. Change impact | Diffs PR #482 by element before merge, classifies it and walks downstream | One breaking change, "renamed to mcc". Seven assets, five teams, five tier 1, on a change the registry's BACKWARD check would pass |
| O2. Incremental | Registers schema v8 and re-reads only the units whose three hashes changed | Two units re-read, six skipped. One edge closed, one gap reported. The graph as of 02:00 still has the old edge, and a rebuild from the same evidence gives the same graph hash |
| O4. Detect and resolve | Starts from a null-rate check failing at 02:42 and walks the incident window | Six changes in the window across the estate, three on the lineage path, the true cause ranked first. Two assets already affected, five not yet, and a fix order that starts upstream |

**What it is and is not.** It demonstrates each mechanism and gives the harness its first assertions. It is a replay on illustrative data. It does not measure detection or resolution time in production. That takes the Phase 0 baseline and the four timestamps of IR-9 on real incidents, because no independent evidence of lineage shortening incidents was found in the market.

**What building it changed.** The first draft of IR-2 said to walk the graph as of the failure time. The run showed that this loses the cause: by 02:42 the offending edge had already been closed at 02:05, so a read at one instant no longer contains the path to it. The walk has to cover every edge valid between the last passing check and the failure. IR-2 and the detect-and-resolve design now say so. This is the factory's loop at small scale: a scenario exposed a hole in the spec, and the spec was fixed before the code.

## What people actually write

Two artefacts carry most of the human effort in the factory. One of each is written out here so the level of precision is clear.

### A work package

```markdown
# WP-20: dbt and SQL element extractor

Serves:       O1 (BL-2, BL-3, BL-4, BL-5), O2 (IN-1)
Start level:  3
Depends on:   WP-10 URN library, WP-11 envelope v2
Budget:       token ceiling, 6 build attempts, 1 working day

## Scope
Read a dbt project at a commit and emit envelope v2 evidence for every model:
direct and indirect element dependencies, expression hashes, opaque reasons.

## Inputs
- twin/repos/analytics-dbt at the given commit: manifest.json and compiled SQL
- Source schemas from the twin's schema store, as of that commit

## Outputs
- Evidence events that validate against specs/evidence/interfaces/envelope-v2.schema.json
- One event set per model, with replaces: "unit"

## Must hold
- Parsing uses SQLGlot. No hand-written SQL parsing.
- A reformatted or alias-renamed model yields identical element edges and expression hashes.
- A model that cannot be resolved emits an opaque edge with a reason code. It never raises.
- An indirect dependency is emitted once per target dataset.
- No network access. No writes outside extractors/dbt_sql/ and its tests.

## Done when
- lineage-eval score --hop dbt-sql: field precision and recall at or above 0.90
- Visible scenarios all pass; holdout pass rate at or above 0.90
- Metamorphic suite all pass
- The reviewer agent reports no open conformance finding
```

### A scenario

```gherkin
# Traces to IA-1, IA-2, IA-3, IA-4, IN-7
Feature: A rename in an event schema is reported as breaking, with its readers

  Scenario: PR #482 renames merchant_category_code to mcc
    Given the twin at the base commit of payments-svc, with auth.events.v1 at schema v7
    And the element graph built from the golden baseline
    When a pull request removes "merchant_category_code" from auth-event.avsc
      and adds "mcc" as a string with default ""
    Then the report lists one change of kind "renamed", from merchant_category_code to mcc
    And the change class is "breaking"
    And the report states that the registry's BACKWARD check passes
    And the downstream list contains auth.enrich.v1#mcc, raw.card_auth#mcc, fct_card_auth#mcc,
      mcc_decline_7d, fraud-score-v12, fraud-svc and the Approval rate dashboard
    And every row has an owner, a tier and an edge state
    And the production graph is unchanged
    And the report is posted within 5 minutes
```

The holdout corpus holds siblings of this scenario from the same family, such as a retype instead of a rename, or the same rename made in the dbt model. The builder never sees them. It only learns how many it passed.

## Risks

| Risk | Mitigation |
| --- | --- |
| The golden graph is too small to be a real oracle | Monthly sampled audits outside the slice, as the plan already requires; every reconciliation finding becomes a fixture |
| Element extraction on the service and Flink hops stays probable | Owner verification for tier 1 fields; declared mappings in contracts; gap count is reported, not hidden |
| Indirect dependencies flood impact reports | Stored once per dataset; reported separately; never block alone |
| The pull-request gate is expected to carry the whole outcome | It cannot. One vendor's analysis of 1,000 incident investigations put code changes at about a tenth of root causes, and an earlier statement from the same vendor said about a third. Most incidents start elsewhere, so O4 is scored as hard as O3 and the Phase 5 gate measures both |
| A model-assisted extractor invents edges | Its output is candidate evidence only; a verifier checks every edge against real schemas; it never raises an edge above probable alone |
| Policy does not allow level 3 | Run at level 2; the oracle and spec pack still pay for themselves in review speed |
| The factory hides weak understanding in the team | Spec owners write the scenarios; G2 at level 2 on core semantics; the weekly review reads failures, not only scores |
| Vendor capabilities overtake the build | ADR-002's revisit triggers; catalogs remain projections, so adopting a vendor component is a collector swap |

## Open questions and decisions needed

| # | Decision or question | Why it matters | Who |
| --- | --- | --- | --- |
| 1 | Does policy allow agent-written code to merge after agent review, with a person approving by exception (level 3)? | Sets the ceiling of the autonomy ladder and most of the expected gain | Engineering risk and security |
| 2 | Which model endpoint is approved for source code and schemas, and under what data classification? | Nothing in the factory starts without it | Security |
| 3 | Who are the named approvers for G1 to G4? | Accountability has to exist before the first merge | Platform lead |
| 4 | What is the token budget per work package and per month? | Published cost ranges span two orders of magnitude; a ceiling has to be chosen, not discovered | Platform lead and finance |
| 5 | Which warehouse is on the slice? | Decides the access-history collector and the projection target | Data platform |
| 6 | Does the wider estate have stored-procedure or legacy ETL lineage needs? | If yes, a scanner suite becomes a collector worth buying | Data governance |
| 7 | Graph store: Neptune, or DataHub with history kept in the owned writer and the lake? | DataHub has no lineage history and its OpenLineage endpoint takes run events only | Week-1 sub-decision from ADR-002 |
| 8 | Build the service-code scanner, or buy that hop? | Two vendors cover it, and one documents field-level lineage through Kafka. A one-week trial on `payments-svc` settles it against the golden graph. Both reach into source code, so security answers first | Developer productivity and security |
| 9 | Which tools make up the twin, and under what licences? | At least one common AWS emulator changed its licence terms; check before adopting | Factory engineers |
| 10 | Read IBM Manta's and Informatica's documentation by hand, if either becomes a candidate | Both sites refuse automated requests, so their claims are still unverified. The other claims that carry weight were re-read at source | Whoever updates ADR-002 |

## Sources

The vendor, technique and factory evidence behind this spec is in [doc 05](05-vendor-assessment-element-level-lineage.md), with its working notes under `research_notes/`. Everything else comes from this repository's plan, architecture, build guide, research appendix and ADR-002.

A verification pass on 2026-11-26 re-read 50 vendor and publisher claims at their own sites. The verbatim quotes and verdicts are in `research_notes/Element level lineage vendor assessment/source_verification_platforms_and_factory.md` and `source_verification_commercial_vendors.md`.

Also read in full at the source on 2026-11-26, from each project's public repository:

- OpenLineage: [column lineage facet](https://github.com/OpenLineage/OpenLineage/blob/main/spec/facets/ColumnLineageDatasetFacet.json), [facet documentation](https://github.com/OpenLineage/OpenLineage/blob/main/website/docs/spec/facets/dataset-facets/column_lineage_facet.md), [Flink 2 integration](https://github.com/OpenLineage/OpenLineage/blob/main/website/docs/integrations/flink/flink2.md)
- dbt: [column-level lineage](https://github.com/dbt-labs/docs.getdbt.com/blob/current/website/docs/docs/explore/column-level-lineage.md)
- SQLMesh: [plans and change categories](https://github.com/TobikoData/sqlmesh/blob/main/docs/concepts/plans.md)
- DataHub: [SQL parsing](https://github.com/datahub-project/datahub/blob/master/docs/lineage/sql_parsing.md), [OpenLineage](https://github.com/datahub-project/datahub/blob/master/docs/lineage/openlineage.md), [impact analysis](https://github.com/datahub-project/datahub/blob/master/docs/act-on-metadata/impact-analysis.md)
- Marquez: [README](https://github.com/MarquezProject/marquez/blob/main/README.md)
- StrongDM Attractor: [README](https://github.com/strongdm/attractor) and [specification](https://github.com/strongdm/attractor/blob/main/attractor-spec.md)
- GitHub Spec Kit: [README](https://github.com/github/spec-kit)
- AWS AI-DLC workflows: [README](https://github.com/awslabs/aidlc-workflows)
