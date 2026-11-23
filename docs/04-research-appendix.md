# Appendix: Lineage Research, Industry Survey and Options

Nov 21, 2026 · @kart

## Executive summary

**Recommendation: build lineage as an OpenLineage event stream fed by both CI (static) and runtime collectors, stored in a time-versioned graph you own, with data contracts and DQ results as attributes on that graph.** This is the only option that reaches services, streams and ML, and that shows impact on the pull request rather than after the incident.

- **What the industry learned.** Meta, LinkedIn, Uber, Slack and Yelp all converged on hybrid collection (static analysis plus runtime capture), push over pull, and collectors built into shared libraries rather than per-team crawlers. Meta is the clearest public example of lineage reaching into service code and AI training.
- **Where the gaps are.** Warehouse lineage is mature through query logs and SQL parsing. Services, streams and ML are not: Flink 2, Confluent and OpenTelemetry give topic or service level only, so field detail on those hops must come from schemas and contracts.
- **Why own the graph.** SageMaker Unified Studio and Dataplex accept only runtime events, not the static events CI produces, and Dataplex keeps 30 days of history. They work well as projections, not as the record.
- **How it pays back.** Three loops: prevent (PR impact and contract gates), detect (contract rules at the producer, DQ alerts enriched with upstream paths) and resolve (graph-walk RCA and a topologically ordered remediation plan).
- **Rollout.** Five phases over about a year, starting with three tier 1 data products end to end, then widening by app type. Success is measured by coverage, pre-merge catch rate, and halving MTTD and MTTR against a baseline quarter.

## Problem framing

Most data incidents are not caused by bad data at rest. They are caused by an upstream change that nobody downstream knew about: a renamed column in a service's event payload, a widened enum in a Kafka topic, a changed join in a dbt model, a feature whose definition drifted. Lineage is the map that turns "something broke" into "this commit, in this repo, broke these 14 assets owned by these 5 teams".

**The system we are designing has two flows.**

- Inflow: change signals (pull requests, schema registry versions, deploys, job runs, query logs) and observed data movement (runtime events, traces, access logs).
- Outflow: decisions (block or warn a PR, notify owners, open an incident, scope a backfill) and knowledge (impact reports, RCA paths, coverage and trust scores).

The graph is only valuable if both flows are continuous. A lineage graph refreshed weekly is a museum; a graph that updates on every merge and every run is a control system.

**Goals**

1. Show, before merge, which downstream assets and owners a code or schema change affects, at column level where it matters.
2. Stop breaking changes at the producer boundary through data contracts enforced in CI and at runtime.
3. When an issue does escape, cut time to detect (MTTD) and time to resolve (MTTR) by walking the graph upstream to the first failing node and downstream to everything that needs a fix or backfill.
4. Cover all four app types (microservices, streaming, analytics, ML features and models) in one graph with one identity scheme.

**Five whys on a typical incident**

1. Why did the fraud model's precision drop? A key feature went mostly null.
2. Why was it null? The upstream Flink job stopped populating a field.
3. Why? The payments service renamed a JSON field in its event.
4. Why didn't anyone catch it? The topic had no enforced schema contract, and the service team didn't know the model consumed the field.
5. Why didn't they know? Lineage stopped at the warehouse; service code and streaming jobs were invisible to it.

The root cause is a coverage gap at the operational edge, not a missing DQ check. That is why this proposal starts lineage at source code and topics, not at the warehouse.

**Hidden assumptions worth stating**

- Assets have stable, unique identifiers across systems. Usually false today; a naming scheme is a prerequisite (see the recommendation).
- Code is the source of truth for intended flows. True for SQL and pipelines; weaker for services where dynamic payloads and config drive behavior.
- Runtime events reflect what actually happened. True, but only for jobs that ran; dormant or rare paths are invisible until they execute.
- Owners exist and will act on alerts. Lineage without ownership metadata produces noise, not action.
- Column-level lineage is needed everywhere. It is not: it is worth the cost on contract-bearing and tier-1 assets, while table-level is enough for the long tail.

**Cost of inaction vs action.** Without lineage, every schema change is either a slow, manual consultation or a silent risk, and every incident starts with a hunt across Slack for who consumes what. With lineage, the cost moves to instrumentation, a metadata platform team and governance discipline; the payback comes from fewer breaking changes, smaller blast radius and faster RCA.

## Collection options by app type

No single collection technique covers all four app types: warehouse lineage is a solved problem through query logs and SQL parsing, while services, streams and ML need code analysis and framework hooks. The design question is which mix of six techniques to use where.

**The six collection techniques**

| Technique | What it sees | Pros | Cons |
| --- | --- | --- | --- |
| 1. Declared lineage (contracts, YAML, catalog entry) | Intended producer, consumer and field mapping, e.g. [ODCS](https://bitol-io.github.io/open-data-contract-standard/latest/schema/) transformSourceObjects and transformLogic | Works for any system, owner-authored, reviewable in PRs | Drifts from reality unless diffed against observed lineage; relies on discipline |
| 2. Static analysis in CI | Flows implied by code before it runs: SQL parsed with [SQLGlot](https://sqlglot.com/sqlglot/lineage.html), [dbt column lineage](https://docs.getdbt.com/docs/explore/column-level-lineage), service code analysis as at [Meta](https://engineering.fb.com/2025/01/22/security/how-meta-discovers-data-flows-via-lineage-at-scale/); emitted as OpenLineage JobEvents, which the [spec](https://openlineage.io/docs/spec/object-model) calls static lineage | The only way to show impact before merge; covers dormant code paths | Over-approximates (dead code, feature flags); dynamic SQL, UDFs and Python models break chains |
| 3. Runtime framework hooks | What actually ran: OpenLineage for [Spark](https://openlineage.io/docs/integrations/spark/spark_column_lineage), [Flink 2](https://openlineage.io/docs/integrations/flink/flink2), [dbt](https://openlineage.io/docs/integrations/dbt), Airflow, [Feast](https://docs.feast.dev/reference/openlineage); or a shared I/O library like Meta's PrivacyLib | Accurate, near zero effort per team once in the shared framework, carries run status and DQ facets | Only sees paths that executed; needs framework ownership; Flink 2 has no column lineage |
| 4. Query and access log mining | Warehouse reads and writes: [Snowflake ACCESS\_HISTORY](https://docs.snowflake.com/en/user-guide/access-history) (column level, up to 3 hours latency, 365 days), BigQuery jobs, Redshift system tables | Complete for SQL engines, no producer changes | Post-hoc only; writes that bypass SQL are invisible ([Uber](https://www.uber.com/blog/queryparser)) |
| 5. Tracing and stream telemetry | Who talks to whom: OTel [messaging](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans) and [database](https://opentelemetry.io/docs/specs/semconv/database/database-spans/) spans, [Confluent Stream Lineage](https://docs.confluent.io/cloud/current/stream-governance/stream-lineage.html), Netflix-style message tracing | Covers microservices and topics with existing instrumentation; gives latency and volume | Service and topic level, not field level; sampling; not a lineage model by itself |
| 6. Platform-native catalogs | Automatic lineage inside one platform: [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage.html), [Dataplex](https://docs.cloud.google.com/dataplex/docs/about-data-lineage), [SageMaker Unified Studio](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/datazone-data-lineage-what-is-openlineage.html) | Fastest time to value inside that platform | Stops at the platform edge; retention limits (Dataplex 30 days); SageMaker and Dataplex accept runtime RunEvents only, not static JobEvents |

**Recommended mix per app type**

| App type | Primary signal | Complement | Granularity to aim for | Watch-outs |
| --- | --- | --- | --- | --- |
| Microservices | Shared I/O and serialization library that stamps producer, schema and correlation ID on every read, write and publish (the Meta pattern) | Static analysis of payload models in CI; OTel spans for the service topology | Field level for contract-bearing events; service level elsewhere | Dynamic payloads and config-driven routing; a correlation key must survive every hop |
| Streaming | Schema Registry subjects as the contract plus OpenLineage from Flink and Kafka Streams | Producer and consumer telemetry for live topology and volume | Topic and field level via the schema; job level from Flink | Confluent contract rules run in client serializers only, not in Kafka Connect, Flink SQL or ksqlDB ([docs](https://docs.confluent.io/cloud/current/sr/fundamentals/data-contracts.html)) |
| Analytics (batch, SQL, BI) | OpenLineage from Spark, Airflow and dbt; query log mining for ad hoc and BI | SQL parsing in CI for pre-merge column diffs | Column level, separating value edges from filter and join edges | MERGE, UDFs and multi-statement SQL often lose column lineage ([DataHub parser notes](https://docs.datahub.com/docs/lineage/sql_parsing.md)) |
| ML features and models | Feature store hooks (Feast apply and materialize emit OpenLineage) and model registry links from features to model versions | Training-config parsing; inference request logging for model to service edges | Feature to model version to serving endpoint | Lineage is lost if models are logged outside the feature client ([Databricks](https://docs.databricks.com/aws/en/machine-learning/feature-store/lineage)); MLflow dataset logging records only what the user supplies ([MLflow](https://mlflow.org/docs/latest/ml/dataset/)) |

One implication matters most for the design: column detail on the service and streaming hops has to come from schemas and contracts, because neither Flink 2, Confluent nor OpenTelemetry provides it at runtime.

## How leading tech companies solve it

Every company that reached broad coverage ended up hybrid: static analysis of code, SQL and configs to see intended flows, plus runtime capture to confirm what actually ran, joined in a central graph. Meta is the only one that publicly extends this all the way into service code and AI training; most others stop at the warehouse and scheduler.

| Company | How lineage is collected | Granularity | Store | Main uses |
| --- | --- | --- | --- | --- |
| [Meta](https://engineering.fb.com/2025/01/22/security/how-meta-discovers-data-flows-via-lineage-at-scale/) | Services: static code analysis plus runtime "Privacy Probes" in shared frameworks (logger, RPC) that sample source and sink payloads per request. Warehouse: executed SQL logged at runtime, then parsed. AI: training configs parsed, hooks in data loaders and PyTorch | Asset level with a confidence score per edge; column level for SQL | Central lineage graph keyed by asset IDs | Placing privacy Policy Zones, compliance monitoring, gating training jobs on permitted inputs |
| [Meta, GenAI](https://engineering.fb.com/2025/10/23/security/scaling-privacy-infrastructure-for-genai-product-innovation/) | One shared library (PrivacyLib) wraps every read, write and remote call; each write is logged with the same correlation key as the read that fed it | Asset level across web, logger, warehouse, inference and checkpoints | Same graph | A training job starts only if every input is permitted |
| [LinkedIn](https://engineering.linkedin.com/blog/2019/data-hub) | Moved from WhereHows crawlers parsing scheduler logs to DataHub push: producers emit Kafka Metadata Change Events keyed by entity URN | Job and dataset | Document store, search index and graph DB, built from change events | Impact analysis, search, access control and privacy |
| [Uber](https://www.uber.com/blog/queryparser) | Queryparser statically parses the live warehouse query stream; Databook moved lineage and freshness to Kafka push events | Table lineage, column access and join statistics | Cassandra plus Elasticsearch ([Databook](https://www.uber.com/blog/databook)) | Scoping bad-table impact, notifying recent users, auto-generating upstream and downstream tests in [UDQ](https://www.uber.com/in/en/blog/operational-excellence-data-quality/) |
| [Airbnb](https://medium.com/airbnb-engineering/metis-building-airbnbs-next-generation-data-management-platform-d2c5219edf19) | Central Lineage Service on Apache Atlas hooks, mostly from Hive | Table | JanusGraph, read through GraphQL; 100M+ nodes, 300M+ edges | SLA debugging of upstream delays, compliance, quality |
| [Slack](https://slack.engineering/data-lineage-at-slack/) | Airflow success callbacks send task metadata; SQL parsed with ANTLR; dashboards from Presto audit tables | Table and column, plus hop count | MySQL, flattened daily by a Spark GraphX job | Backfill impact, PII discovery, deprecation notices |
| [Spotify](https://backstage.spotify.com/docs/portal/core-features-and-plugins/data-experience/data-lineage) | Pull from warehouse query-history metadata every 6 hours (no SQL text parsing) plus OpenLineage push from Airflow and dbt | Workflow to dataset | Normalized to OpenLineage events; unknown datasets kept as "unlinked" nodes | Catalog lineage in Backstage |
| [Shopify](https://shopify.engineering/solving-data-discovery-challenges-shopify) | Pull jobs extract metadata from each store, chosen for speed to market | Asset | Graph DB, Elasticsearch, GraphQL | Discovery and change impact; teams that understood the impact of their changes rose from 16% to 46% |
| [Yelp](https://engineeringblog.yelp.com/2022/08/spark-data-lineage.html) | Instrumented inside the shared Spark ETL wrapper from each job's DAG | Job, source to target table | Kafka then Redshift | Explaining ML features, incident freeze and backfill |
| [Netflix, Inca](https://netflixtechblog.medium.com/inca-message-tracing-and-loss-detection-for-streaming-data-netflix-de4836fc38c9) | Runtime tracing: Kafka producer callbacks and consumer interceptors, message ID in a header, about 2B traces a day | Message level on streams | Dedicated Kafka cluster joined by a Flink job | Detecting loss and duplicates in streams |
| [Lyft, Amundsen](https://github.com/amundsen-io/amundsen/blob/master/docs/architecture.md) | Daily Airflow crawl ("data builder") of databases, dashboards and HR systems | Table and dashboard | Neo4j plus Elasticsearch | Discovery, trust, tagging personal data |
| [Google, Goods](https://research.google/pubs/goods-organizing-googles-datasets/) | Post-hoc and non-intrusive: provenance inferred from production job logs | Job to dataset | Catalog at the scale of billions of datasets | Discovery and provenance as a ranking signal |

**Lessons that recur across these sources**

- **Push beats pull at scale.** LinkedIn found a central fleet of crawlers "quickly becomes a nightmare"; Uber moved lineage and freshness to push events for near-real-time outage detection. Pull is still the fastest start (Shopify, Spotify, Amundsen).
- **Put collection in shared libraries, not in every team's backlog.** Meta's biggest lesson was that asking each system to build its own collector did not scale; Yelp and Slack hook the shared ETL wrapper and the scheduler.
- **SQL parsing is necessary but leaky.** Uber notes that any write that bypasses SQL "opts out" of lineage; Slack says manual lineage for non-SQL Spark jobs does not scale.
- **A shared correlation key is the bridge across systems.** Meta joins read-only and write-only jobs into flows by job or trace IDs; this is the pattern that links microservices to data assets.
- **Edges need confidence, and consumers need tooling.** Meta attaches confidence to each edge and found raw signals "overwhelmingly complex" for owners until it built traversal tools on top.
- **Lineage pays for itself through quality and privacy, not discovery alone.** Uber generates tests from lineage; Meta gates training on it; Airbnb and Netflix use it for SLA forecasting.

Two gaps in the public record: no company I read derives warehouse lineage from OpenTelemetry traces alone, and published ML feature lineage is thin (Netflix's Model Lifecycle Graph is known only from a [secondary summary](https://infoq.com/news/2026/05/netflix-ml-graph); Uber's [Michelangelo](https://www.uber.com/blog/michelangelo-machine-learning-platform/) records features and dataset references per model version, but no explicit graph).

## Comparing the strategic options

Option C, an OpenLineage-first event backbone feeding a graph you own, is the only option that covers all four app types, supports pre-merge impact and survives a change of catalog vendor. The others are good components but poor systems of record.

| Option | Coverage across the four app types | Pre-merge impact from code | Column level | Lock-in | Time to first value | Run cost and effort |
| --- | --- | --- | --- | --- | --- | --- |
| A. Platform-native catalog only (Unity Catalog, SageMaker Catalog, Dataplex) | Low: stops at the platform edge; services and streams mostly missing | None: runtime RunEvents only | Strong inside the platform | High | Weeks | Low |
| B. Metadata platform with pull crawlers (DataHub or Amundsen style, scheduled ingestion) | Medium: warehouse, BI and scheduler strong; services weak | Weak: crawls after deploy | Medium, depends on the SQL parser | Low (open source) | 1 to 2 quarters | Medium; crawler fleet grows with sources |
| C. OpenLineage event backbone plus owned graph, static and runtime events, contracts diffed against observed | High: shared libraries and framework hooks reach services, streams and ML | Strong: CI emits JobEvents and impact reports on every PR | Strong where contracts and SQL exist; schema level on streams | Low: open standard, catalogs become projections | 1 quarter for tier 1, 3 to 4 quarters broad | Highest upfront; a platform team owns libraries and the graph |
| D. Data observability vendor (query-log based field lineage plus anomaly detection) | Medium: warehouse and BI strong; services and ML thin | None | Strong in the warehouse | High | Weeks | License cost scales with tables |

**Why not the cheaper options alone.** Option A answers "what feeds this table" inside one platform but cannot tell a service owner that their field rename breaks a model. Options B and D detect after the fact, which helps MTTR but not prevention. Option C costs the most upfront, but it is the only one that moves detection to the pull request, which is where the five whys above point.

**What C reuses rather than rebuilds.** C is not a reason to discard A, B or D. The platform catalogs stay as governance front ends fed from the graph, a metadata platform can serve as the graph's UI and search, and an observability tool can keep running anomaly detection, writing its findings back as DQ facets on graph nodes.

## Recommended architecture

Every producer of lineage, whether a CI job, a runtime framework or a contract, emits OpenLineage events onto one Kafka topic; a normalizer resolves identities and writes a time-versioned graph that you own; impact analysis, contract drift and RCA run as services on that graph, and vendor catalogs receive projections.

**Design decisions that make it work**

1. **One identity scheme first.** Every dataset, topic, field, feature and model gets a stable name following OpenLineage's namespace plus name convention, with fields as a suffix. Meta keys its whole graph on asset IDs; without this, edges from different collectors never join.
2. **Three edge kinds, kept apart.** Declared (from contracts), static (from CI) and observed (from runtime). Each edge carries its source, a confidence score as at Meta, the git SHA or run ID that produced it, and valid-from and valid-to times. Keeping them apart is what lets you detect drift: a declared edge with no observed traffic, or an observed edge nobody declared.
3. **Time-versioned, not overwritten.** Incident RCA needs the graph as it was at 02:00 on the night it broke, not as it is now. SageMaker's ListLineageNodeHistory and Snowflake's 365-day retention help, but Dataplex keeps only 30 days, so the system of record has to be yours. Raw events also land in an Iceberg table on S3 for replay.
4. **Collection lives in shared code.** A thin internal library wraps the serializer and I/O clients used by services and stream processors, stamping producer, schema version and a correlation ID; OpenLineage integrations are switched on centrally in the Spark, Flink, Airflow, dbt and Feast platforms. No team writes a collector.
5. **CI is a first-class producer.** On every pull request, the pipeline parses changed SQL, dbt models and payload schemas, runs a contract breaking-change check (for example datacontract-cli's breaking command), and emits static JobEvents tagged with the PR. Because SageMaker and Dataplex reject JobEvents, these go only to your graph.
6. **Contracts and DQ are graph attributes.** A contract (ODCS or Schema Registry subject with rules) attaches to the producing node; DQ results arrive as OpenLineage dataQualityAssertions facets on the dataset. Lineage then answers both "who consumes this" and "where did the first failing check appear".

**Store choice.** A property graph is the natural fit; on AWS, Amazon Neptune has a published reference pattern for lineage ([AWS blog](https://aws.amazon.com/blogs/big-data/build-data-lineage-for-data-lakes-using-aws-glue-amazon-neptune-and-spline)). If you want a UI and search on day one, DataHub (LinkedIn's push-based design) can serve as the graph and front end, with Neptune added later if traversal depth or custom edge semantics outgrow it. Either way, pair the graph with a search index, as every company in the survey did.

**The three loops it enables**

- **Prevent (pre-merge).** The PR bot computes the downstream subgraph of every changed field up to N hops, lists affected assets with tier and owner, and fails the check when a tier 1 contract breaks without a version bump or consumer sign-off.
- **Detect (runtime).** Contract rules in serializers stop bad events at the producer (with a DLQ where supported); DQ checks on observed edges fire alerts enriched with the upstream path, and drift between declared and observed edges raises a governance ticket.
- **Resolve (incident).** From a failing node, walk upstream to the earliest node with a failing check or a change in the incident window, correlating with deploy and commit events to rank likely causes. Walk downstream to produce the remediation plan: affected assets in topological order for backfill, owners to notify, and downstream jobs to pause as circuit breakers.

&#91;embedded content: lineage architecture · 4 signal types, 1 event stream, 1 graph, 4 uses\]

All four signal types land on the same event stream, so static, runtime and declared edges share one identity scheme; catalogs are fed from the graph and can be rebuilt from the archive.

## Rollout phases

Start narrow and end to end: three tier 1 data products, one crossing each app type, prove the whole loop before coverage is widened. Durations below are a proposal for a platform team of about six engineers and should be set against your own baseline.

1. **Phase 0, foundations (6 weeks).** Publish the identity scheme, stand up the Kafka lineage topic, normalizer and graph, and switch on OpenLineage in Airflow, Spark and dbt. Pick the three pilot products, including one that ends in an ML model.
   - Exit gate: each pilot product has an unbroken graph from source event to final consumer, reviewed by its owners.
2. **Phase 1, analytics and pre-merge (next quarter).** Add query log mining for the warehouse and BI, SQL and dbt parsing in CI, and the PR impact bot in warn-only mode.
   - Exit gate: the PR bot runs on every SQL and dbt repo, and owners rate most impact reports as accurate.
3. **Phase 2, streaming and contracts.** Put Schema Registry contracts with rules on tier 1 topics, enable the Flink integration, ship the serializer library that stamps correlation IDs, and write ODCS contracts for tier 1 data products. Turn the PR gate to blocking for tier 1 contracts.
   - Exit gate: no breaking change reaches a tier 1 topic or product without a version bump or consumer sign-off.
4. **Phase 3, services and ML.** Roll the shared I/O library into the service framework, link feature store, model registry and serving endpoints, and log model to endpoint edges from inference.
   - Exit gate: every tier 1 model shows lineage from source event through feature to serving endpoint.
5. **Phase 4, automated RCA.** Ingest DQ results as facets, run the RCA service on incidents, add circuit breakers that pause downstream jobs, project the graph into the vendor catalogs, and turn on declared versus observed drift alerts.
   - Exit gate: MTTD and MTTR targets below are met for two consecutive quarters.

## Risks and metrics

The biggest risk is not technical: it is a graph that looks complete but quietly misses paths, which teaches teams to distrust it. Coverage has to be measured, not assumed, and every risk below has a counter-measure built into the design.

| Risk | Mitigation |
| --- | --- |
| Identities don't join across collectors, so the graph fragments | Identity scheme in Phase 0; normalizer rejects or quarantines unresolved names; keep unknown datasets as "unlinked" nodes rather than dropping them, as Spotify does |
| Static analysis over-reports and floods teams with false impact | Confidence per edge; warn-only mode first; filter reports by asset tier; show observed edges first |
| Paths that bypass instrumented code stay invisible (Uber's lesson) | Coverage metric per platform; query log mining as a safety net; treat unexplained writes as a finding |
| Collection adds latency or load to services | Asynchronous emission from the shared library; record schema, IDs and counts, never payloads |
| Lineage captures sensitive data | Metadata only; no payload sampling (unlike Meta's privacy probes); access control on the graph like any other dataset |
| Vendor catalogs reject static events or expire history | Own the graph of record; catalogs are projections, rebuilt from the event archive |
| Owners ignore impact reports | Ownership is a required field in contracts; reports land in the PR, not a separate portal; blocking only for tier 1 |
| Platform team becomes a bottleneck | Self-serve contracts and SDKs; the graph exposes an API and events so other teams build on it |

**Cost of action vs inaction.** Action costs a dedicated platform team, framework changes in services and streams, and governance discipline on contracts. Inaction keeps every schema change a manual consultation and every incident a search across chat for who consumes what, and that cost grows with each new service, topic and model.

**Metrics** (targets are proposals; set them after a baseline quarter)

| Metric | Definition | Proposed target |
| --- | --- | --- |
| Tier 1 lineage coverage | Share of tier 1 assets with an unbroken graph to source and to final consumers | 95% |
| Column coverage on contracts | Share of contract-bearing assets with field-level edges | 90% |
| Graph freshness | Time from merge or run completion to the edge appearing | Under 15 minutes |
| Declared vs observed agreement | Share of declared edges confirmed by runtime, and observed edges that are declared | Above 90% both ways |
| Breaking changes caught pre-merge | Breaking changes stopped in PR divided by all breaking changes, including those found in production | Above 80% |
| MTTD | Time from bad data landing to an alert with the upstream path | Halve the baseline |
| MTTR | Time from alert to downstream remediation complete | Halve the baseline |
| Blast radius | Median downstream assets affected per incident | Falling quarter over quarter |
| Impact report precision | Share of PR impact reports owners rate as accurate | Above 80% |

## Sources

All pages below were opened and read on 2026-11-21. Netflix's main lineage post and its Model Lifecycle Graph post would not load, so Netflix rests on the Inca post and a secondary InfoQ summary.

**Company engineering posts**

- [Meta: How Meta discovers data flows via lineage at scale](https://engineering.fb.com/2025/01/22/security/how-meta-discovers-data-flows-via-lineage-at-scale/)
- [Meta: Scaling privacy infrastructure for GenAI](https://engineering.fb.com/2025/10/23/security/scaling-privacy-infrastructure-for-genai-product-innovation/)
- [Meta: How Meta understands data at scale](https://engineering.fb.com/2025/04/28/security/how-meta-understands-data-at-scale/)
- [Meta: Static analysis for SQL queries](https://engineering.fb.com/2022/11/30/data-infrastructure/static-analysis-sql-queries/)
- [LinkedIn: Open sourcing WhereHows](https://engineering.linkedin.com/blog/2016/03/open-sourcing-wherehows--a-data-discovery-and-lineage-portal)
- [LinkedIn: DataHub](https://engineering.linkedin.com/blog/2019/data-hub)
- [LinkedIn: Shifting left on governance with schema annotations](https://engineering.linkedin.com/blog/2022/shifting-left-on-governance--datahub-and-schema-annotations)
- [Uber: Databook](https://www.uber.com/blog/databook)
- [Uber: Queryparser](https://www.uber.com/blog/queryparser)
- [Uber: Operational excellence in data quality](https://www.uber.com/in/en/blog/operational-excellence-data-quality/)
- [Uber: Michelangelo](https://www.uber.com/blog/michelangelo-machine-learning-platform/)
- [Airbnb: Metis](https://medium.com/airbnb-engineering/metis-building-airbnbs-next-generation-data-management-platform-d2c5219edf19)
- [Airbnb: Data quality at Airbnb](https://medium.com/airbnb-engineering/data-quality-at-airbnb-870d03080469)
- [Slack: Data lineage at Slack](https://slack.engineering/data-lineage-at-slack/)
- [Spotify: Portal data lineage](https://backstage.spotify.com/docs/portal/core-features-and-plugins/data-experience/data-lineage)
- [Shopify: Solving data discovery challenges](https://shopify.engineering/solving-data-discovery-challenges-shopify)
- [Yelp: Spark data lineage](https://engineeringblog.yelp.com/2022/08/spark-data-lineage.html)
- [Netflix: Inca message tracing](https://netflixtechblog.medium.com/inca-message-tracing-and-loss-detection-for-streaming-data-netflix-de4836fc38c9)
- [InfoQ: Netflix ML Model Lifecycle Graph](https://infoq.com/news/2026/05/netflix-ml-graph) (secondary)
- [Lyft: Amundsen architecture](https://github.com/amundsen-io/amundsen/blob/master/docs/architecture.md)
- [Google: Goods, organizing Google's datasets](https://research.google/pubs/goods-organizing-googles-datasets/)

**Standards, tools and platforms**

- [OpenLineage object model](https://openlineage.io/docs/spec/object-model), [column lineage facet](https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet), [static lineage](https://openlineage.io/blog/static-lineage/), [data quality assertions facet](https://openlineage.io/docs/spec/facets/dataset-facets/data_quality_assertions)
- OpenLineage integrations: [Spark column lineage](https://openlineage.io/docs/integrations/spark/spark_column_lineage), [Flink 2](https://openlineage.io/docs/integrations/flink/flink2), [dbt](https://openlineage.io/docs/integrations/dbt), [Feast](https://docs.feast.dev/reference/openlineage)
- [OpenLineage takes inspiration from OpenTelemetry](https://openlineage.io/blog/openlineage-takes-inspiration-from-opentelemetry/)
- [Confluent Stream Lineage](https://docs.confluent.io/cloud/current/stream-governance/stream-lineage.html), [data contracts](https://docs.confluent.io/cloud/current/sr/fundamentals/data-contracts.html), [schema evolution](https://docs.confluent.io/cloud/current/sr/fundamentals/schema-evolution.html)
- [SQLGlot lineage](https://sqlglot.com/sqlglot/lineage.html), [DataHub SQL parsing](https://docs.datahub.com/docs/lineage/sql_parsing.md), [dbt column-level lineage](https://docs.getdbt.com/docs/explore/column-level-lineage)
- [Snowflake access history](https://docs.snowflake.com/en/user-guide/access-history), [Google Dataplex lineage](https://docs.cloud.google.com/dataplex/docs/about-data-lineage)
- [SageMaker Unified Studio lineage](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/datazone-data-lineage-what-is-openlineage.html), [AWS lineage with Glue, Neptune and Spline](https://aws.amazon.com/blogs/big-data/build-data-lineage-for-data-lakes-using-aws-glue-amazon-neptune-and-spline)
- [Unity Catalog lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage.html), [Databricks feature lineage](https://docs.databricks.com/aws/en/machine-learning/feature-store/lineage), [MLflow datasets](https://mlflow.org/docs/latest/ml/dataset/)
- [Open Data Contract Standard schema](https://bitol-io.github.io/open-data-contract-standard/latest/schema/), [ODCS data quality](https://bitol-io.github.io/open-data-contract-standard/latest/data-quality/), [datacontract-cli](https://pypi.org/project/datacontract-cli)
- OpenTelemetry semantic conventions: [messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans), [database spans](https://opentelemetry.io/docs/specs/semconv/database/database-spans/)
- [Monte Carlo field-level lineage (InfoQ)](https://www.infoq.com/articles/field-level-lineage-modern-data-systems)
