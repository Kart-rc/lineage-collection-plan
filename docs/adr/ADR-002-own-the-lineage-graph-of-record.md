# ADR-002: Own the lineage graph of record, adopt the rest

Nov 22, 2026 · @kart

We own a thin lineage core (identity scheme, evidence log, versioned and confidence-scored edges) and adopt everything else, with vendor catalogs fed as projections, because no catalog or product we checked covers services, streams and ML, takes static CI evidence and keeps history for RCA. This is the build-vs-buy ADR in your Distinguished Engineer plan, drafted from your lineage implementation plan; edit it into your own words before it counts.

## Header

- **Title:** ADR-002: Own the lineage graph of record; adopt commodity parts; vendor catalogs are projections
- **Status:** Proposed
- **Date:** (the day you finish)
- **Deciders:** platform architecture group, data governance lead, the lineage platform lead, and the owning teams of the first slice
- **Scope:** where lineage truth lives and which parts the platform builds versus adopts. Out of scope: which graph store (a reversible week-1 sub-decision, see section 4), contract formats, and catalog UI choice.
- **Related:** ADR-001 (open table format). The raw evidence lake in this ADR is an Iceberg table, so it inherits that decision.

## 1. Context and forces

A change in one system quietly breaks reports, features and models downstream, and teams usually learn it from the people affected. The lineage plan answers this top down: gateway logs first, then catalog and component overlay, then static code and runtime edges, proven on one vertical slice before widening.

The slice is card payment authorization through to the fraud model: payments-svc, the auth.events.v1 topic and txn-enrichment Flink job, fct\_card\_auth, and the mcc\_decline\_7d feature feeding fraud-score-v12. Names are illustrative. It crosses all four app types, which is exactly where vendor catalogs are thinnest.

The forces that pull against each other:

- **Coverage vs time to value:** a platform catalog gives warehouse lineage in weeks but stops at the platform edge; services and streams need evidence it never sees.
- **Prevention vs detection:** pre-merge impact needs static evidence from CI; most catalogs accept only runtime events.
- **Control vs run cost:** owning edge semantics needs a team; renting them needs a license and accepts someone else's model.
- **Reversibility vs convenience:** wiring every producer straight into one catalog is fastest now and costliest to undo later.

**What the vendor docs say today (read 2026-11-22):**

- SageMaker Unified Studio lists RunEvent, DatasetEvent and JobEvent, then says it "only supports RunEvents" ([AWS docs](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/datazone-data-lineage-what-is-openlineage.html)). Static CI lineage can't go there.
- Google's lineage page (Dataplex, now Knowledge Catalog) recommends OpenLineage for custom sources, but custom OpenLineage events carry no column-level lineage, and lineage is kept 30 days ([Google docs](https://docs.cloud.google.com/dataplex/docs/about-data-lineage)). The page was cut off when read, so the 30-day and column points are less certain; recheck.
- Unity Catalog keeps lineage in Catalog Explorer indefinitely and system tables for a rolling 395 days, and can link external assets as external metadata objects ([Databricks docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage.html)). This is the strongest vendor case, and it weakens the "history" argument for Databricks-centric estates. It still has no notion of gateway call edges or per-source confidence.

**Cost of inaction:** every schema change stays a manual consultation or a silent risk, every incident starts with a hunt for who consumes what, and the PR #482 rename in the plan surfaces the next day as a model metric anomaly. The cost grows with each new service, topic and model.

**Hidden assumptions:**

1. About six engineers can be funded for the 18-week first slice and a smaller team kept after it. If not, this ADR flips.
2. The differentiator is evidence semantics (identity, confidence, declared vs observed), not the UI. If consumers only need warehouse and BI lineage, buying wins.
3. Gateway and mesh logs carry caller identity, or can be made to. The plan's first risk.
4. Vendor limits are stable for about a year. They move fast, which is why trigger 1 exists.
5. Owners will work a reconciliation queue. Without that, an owned graph decays like any catalog.
6. The org can run a stateful platform (graph, bus, search) at tier 1 reliability, or the graph can fail open without blocking anyone.

**5 whys: why decide now?**

1. Why now? Phase 1 writes the first edges, and week 1 picks the store.
2. Why does that matter? The first writer defines the identity scheme and the edge model.
3. Why is that sticky? Every collector, PR bot and RCA query is written against them.
4. Why not let a catalog define them? Each catalog models only what reports to it, and none we checked models service calls, confidence or declared vs observed edges.
5. Root: whoever owns the identity table and edge semantics owns lineage. That part should be ours; everything else can be rented.

## 2. Decision drivers

Ranked. The top three decide; the rest break ties.

1. **One graph across all four app types, one identity scheme.** The five whys in the research point to a coverage gap at the operational edge, not a missing DQ check.
2. **Pre-merge impact from static CI evidence.** Prevention moves cost to the cheapest moment; detection alone only shortens the outage.
3. **Time-versioned history and replay.** RCA needs the graph as it was at 02:00 on the night it broke, and the ability to rescore when a collector misbehaves.
4. Evidence semantics we control: per-source confidence, edge states, reconciliation.
5. Exit cost if a catalog or store vendor changes.
6. Time to first value (week 5 for service blast radius in the plan).
7. Run cost and team load.
8. Metadata only, with PII-tagged names access-controlled.

## 3. Options considered

1. **Platform-native catalog as system of record** (Unity Catalog, SageMaker Catalog, Dataplex). Pros: weeks to value, low run cost, strong column lineage inside the platform; Unity Catalog keeps long history. Cons: stops at the platform edge; SageMaker accepts RunEvents only; Dataplex history and custom-event column lineage are limited; high lock-in. Wins if the estate is one platform and services and streams don't matter.
2. **Data observability product as system of record** (query-log field lineage plus anomaly detection). Pros: weeks to value, strong warehouse and BI field lineage, anomaly detection included. Cons: services and ML thin, no pre-merge impact, license scales with tables (price not looked up), graph in the vendor's format. Wins if the main pain is warehouse incidents and MTTR, not prevention.
3. **Open-source metadata platform as the record** (DataHub or Amundsen style, scheduled crawlers). Pros: open source, good UI and search, warehouse, BI and scheduler coverage. Cons: crawls after deploy, services weak, no native confidence or declared vs observed model; one to two quarters to value. Wins if crawler coverage is enough and the team wants a portal more than a control system.
4. **OpenLineage plus Marquez as the record.** Pros: reference backend for the standard, small footprint on Postgres, good fit for a first slice. Cons: built around jobs, runs and datasets, so gateway CALLS edges, per-source confidence and reconciliation would sit outside it; UI and search are basic (check against current Marquez docs). Wins for a proof of concept, or if the scope stays batch and streaming jobs.
5. **Build everything, including store, search and UI.** Pros: total control. Cons: rebuilds commodity parts, slowest to value, the team becomes a catalog vendor. Wins only if no store or UI can hold the edge model, which nothing in the plan suggests.
6. **Own the thin core, adopt the rest, catalogs as projections (chosen).** Pros: covers all four app types, takes static and runtime evidence, versioned and replayable, low exit cost. Cons: highest upfront cost of the non-build options, a platform to run, one more hop. Wins when the top three drivers matter, which they do for this slice.

### Comparison

Ratings are judgments from the lineage research and the vendor pages above, not measurements.

| Driver | 1. Platform catalog | 2. Observability product | 3. OSS metadata platform | 4. OpenLineage + Marquez | 5. Build everything | 6. Thin core, adopt rest |
| --- | --- | --- | --- | --- | --- | --- |
| Four app types in one graph | Low | Med | Med | Med | High | High |
| Pre-merge impact from CI | Low | Low | Low | Med | High | High |
| Versioned history and replay | Med (High on Unity) | Med | Med | Med | High | High |
| Evidence semantics we control | Low | Low | Med | Med | High | High |
| Exit cost | High | High | Low | Low | Low | Low |
| Time to first value | Weeks | Weeks | 1 to 2 quarters | Weeks for a slice | 3 to 4 quarters | 5 weeks for service edges |
| Run cost and team load | Low | Low team, license cost | Medium | Low | Highest | High |

## 4. The decision

We will own the lineage graph of record (the identity scheme, the raw evidence log and the versioned, confidence-scored edges) and build only that thin core, because no catalog or product we checked covers services, streams and ML, accepts static CI evidence and keeps replayable history; we adopt every commodity part and feed vendor catalogs as projections, accepting a six-person team for the first slice and a platform to run after it.

The trade-off we knowingly take: we pay engineers instead of a license, and we carry the risk of building a catalog by accident. The guard is the line below. We build what encodes our semantics and nothing that a store, parser or UI already does.

| Part | Build, adopt or buy | Why |
| --- | --- | --- |
| Identity scheme and resolver | Build | The join key for every collector; the part we must own |
| Confidence scorer and daily reconciler | Build, small | Our edge semantics: noisy-OR across sources, declared vs static vs observed |
| Versioned graph writer | Build, thin | Valid-from and valid-to on every edge for RCA |
| PR impact bot and contract gate | Build, thin, on the graph API | Prevention lives in the PR |
| Catalog projections | Build thin emitters | Catalogs stay governance front ends, rebuilt from the archive |
| Evidence bus | Adopt: Kafka (MSK), OpenLineage Kafka transport | Replayable, keyed by URN |
| Raw evidence | Adopt: Iceberg on S3 | Replay and rebuild source; inherits ADR-001 |
| Graph store, search, UI | Adopt: Neptune plus OpenSearch, or DataHub | Week-1 sub-decision, reversible because the graph can be rebuilt from the lake |
| Parsers and runtime collectors | Adopt: SQLGlot, Flink planner, datacontract-cli, OpenLineage integrations, OTel | Don't write a SQL parser |
| Anomaly detection | Keep or buy | Findings land as DQ facets on graph nodes |

**Store sub-decision, decided 27 November 2026: Neptune.** Each edge version is its own relationship with valid and recorded times; Aurora keeps the alias table and queues; Neo4j stands in locally over the same Bolt protocol and openCypher. See D12 and D23 in [doc 08](../08-build-decisions.md).

**Original wording, deferred to week 1:** Neptune if edge semantics and traversal depth need full control; DataHub if a UI and search on day one matter more. Either way the graph writer is the only component that changes, so this stays a two-way door.

## 5. Rejected options and why

- **Platform catalog as the record:** loses on driver 1 and 2. SageMaker rejects JobEvents, and none of the three models service calls. It would win if the estate collapsed onto one platform with no services in scope. Deferred, not closed: catalogs stay as projections, and trigger 1 re-tests this.
- **Observability product as the record:** loses on driver 2; it detects after the fact. It would win if the goal were MTTR on warehouse incidents only. Deferred: its detectors can feed DQ facets into our graph.
- **OSS metadata platform as the record:** loses on driver 1 and 4 when run as a crawler fleet. It would win if crawler coverage met the gates. Not closed at all: DataHub is a candidate store under the chosen option.
- **OpenLineage plus Marquez as the record:** loses on driver 4 at scale, since gateway edges and confidence don't fit its model. It would win for a batch-only scope. Deferred: usable as a first-slice store if week 1 wants the smallest footprint.
- **Build everything:** loses on drivers 6 and 7 and adds no differentiation. It would win only if no store could hold the edge model. Closed unless trigger 4 fires.

## 6. Consequences

- **What gets easier:** one answer to "who consumes this" across services, streams, tables and models; impact in the PR; RCA on the graph as it was; changing catalog vendor without rewiring producers.
- **What gets harder:** running a bus, graph and search at tier 1 reliability; keeping the identity table clean; staffing a platform team after the slice.
- **Rollout:** follows the plan's phases. Service edges by week 5, owners by week 7, PR impact in warn mode by week 11, runtime reconciliation by week 14, contracts and RCA by week 18. Catalog projections start once Phase 4 precision passes.
- **Main risk and guard:** a graph that looks complete but quietly misses paths, so teams stop trusting it. Guard: accuracy measured weekly against the golden graph, replay tests, fail-open PR bot, and blocking only for tier 1 contracts.
- **Who carries the cost:** the platform team (about six engineers for 18 weeks, roughly 108 engineer-weeks); slice owners (a few hours each for golden graph sessions and the queue); producer teams (one CI step and a log format fix).

**Cost of action vs inaction.** Action: about 108 engineer-weeks for the first slice, then a smaller run team, plus infrastructure whose main drivers are span volume, graph size, OpenSearch and MSK retention. No dollar figures were looked up for infrastructure or vendor licenses. Inaction: manual consultation on every schema change, incidents found by consumers, and a vendor-only path whose license grows with table count while still missing services and pre-merge impact.

## 7. Revisit triggers

Owner: the lineage platform lead. Reviews at the end of Phase 2 (week 7) and Phase 4 (week 14), then each quarter.

1. **A catalog in use closes the gap:** it accepts static OpenLineage JobEvents, models service or topic nodes, and keeps at least 13 months of queryable lineage. Then re-run option 1 as the record.
2. **Accuracy stalls:** Phase 4 misses its gate (edge precision at least 95%, freshness under 15 minutes) by more than two weeks. Then adopt a full platform (DataHub or Marquez) for the record and stop building the scorer.
3. **Cost crosses over:** platform run cost per tier 1 data product covered exceeds a written vendor quote at the same coverage for two consecutive quarters. Needs real quotes first.
4. **Building a catalog by accident:** more than 30% of platform engineering time goes to store, search or UI work instead of evidence for a full quarter. Then move that work onto an adopted store.
5. **Team shrinks:** fewer than four engineers for more than a quarter. Then stop after Phase 2 on an adopted platform and keep the owned identity table.

## 8. Facts to check before you finalize

- Vendor license models and prices for any observability or catalog product you name (not looked up).
- Google's lineage retention and custom-event column limits; the page was cut off when read.
- Unity Catalog's external lineage steps (its separate external lineage page was not read).
- DataHub's current OpenLineage ingestion and support for custom edge properties such as confidence and valid-from.
- Marquez's current graph API, column lineage support and UI.
- Neptune and OpenSearch pricing for the slice size, if you want a dollar line.

## 9. Public-safe scrub

- No employer name, internal system or team names, or vendor contract details. The slice names are illustrative; keep them that way.
- Volumes as ranges, money as relative change.
- Every number defensible from the plan, a public doc or your own experience.

## Done bar

- [ ] Every option has pros, cons and a "wins if" line
- [ ] Rejected options tie to the top three drivers
- [ ] At least two measurable revisit triggers with an owner
- [ ] Rewritten in your own voice; a peer can restate the decision in one minute

## Sources

Vendor pages opened 2026-11-22: [SageMaker Unified Studio lineage](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/datazone-data-lineage-what-is-openlineage.html), [Google data lineage](https://docs.cloud.google.com/dataplex/docs/about-data-lineage), [Unity Catalog lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage.html). Everything else comes from your [lineage plan](https://claude.ai/artifact/L3VYkPdpZ8VB5kgJWgw4gd), its research appendix and architecture tab. The ADR set: [ADR-001 outline](https://claude.ai/artifact/S1C5MBhcww94UkhQbAzZeW) and the [Distinguished Engineer prep plan](https://claude.ai/artifact/FU4j6Jn4tFrr6yeeepeCrL), which also lists a separate build-vs-buy memo that this ADR can feed.
