# Architecture and deployment

This tab answers three questions about the plan: what the lineage system is made of, how information moves through it, and what it runs on in AWS. Nothing here is extra scope. Every component is brought online by one of the phases in the plan tab, and the table near the end shows which phase brings which part.

## Architecture on a page

&#91;embedded content: the six layers: signals, collectors, evidence bus, lineage core, stores and uses\]

Click any of the 24 boxes to open it. Each one shows what the component does, why it matters, a worked example from the PR #482 slice, how it is built and what to watch out for. Eight of them have a small visual you can play with: the CI scanners, identity resolver, confidence scorer, daily reconciler, versioned graph writer, graph store, PR impact gate and RCA circuit breaker. The flow is also a loop: DQ results, contract checks, deploys and merged PRs are published back to the evidence topic, so changes and failures sit on one timeline.

Read the diagram top to bottom. Five kinds of signal come in, each collector turns its signal into the same OpenLineage-shaped evidence, and all of it lands on one topic. That single entry point is the most important design choice: adding a source later means adding a collector, never changing the core or the stores.

The lineage core does four jobs, in this order:

- **Identity resolver:** maps every name a signal uses (a gateway host, a topic, a table path, a model name) to one URN, so the gateway log's txn-enrichment and the Flink job's sink become the same node.
- **Confidence scorer:** combines the evidence for each edge with noisy-OR, so an edge seen by three independent sources scores higher than one seen by a single source.
- **Daily reconciler:** compares what code says with what actually ran, and turns each disagreement into a task for the owning team.
- **Versioned graph writer:** writes every edge with valid-from and valid-to, so the graph can be read as it was at any moment. RCA depends on this.

The stores are split by job. The graph answers traversals, search answers "find me this asset", Postgres holds the identity table and the owner queues, and the Iceberg lake keeps every raw event so the graph can be rebuilt or rescored at any time.

### Why this shape and not another

| Option | What it gets you | What it costs |
| --- | --- | --- |
| Each tool writes straight into a catalog | Fastest start; no platform to run | No replay point, scoring and reconciliation get bolted on later, and changing catalog means rewiring every producer |
| **Evidence bus plus a small lineage core (recommended)** | Sources and stores are decoupled, every event can be replayed, confidence and versioning are built in | One more hop to run and a small team to own it |
| Buy a lineage product | Quick coverage of warehouses and BI tools | Weak on service-to-service and streaming edges from logs, and the graph sits in someone else's format |

If the week-1 decision picks DataHub as the store, the shape stays the same: the graph writer becomes a DataHub emitter, and DataHub supplies the graph, search and UI. Neptune and OpenSearch then drop out of the deployment view below.

## Process flows

&#91;embedded content: the four process flows, each traced with the PR #482 example\]

The four flows run on the same components. What separates them is the trigger and how fast the answer is needed.

| Flow | Trigger | Needed by | Comes online in |
| --- | --- | --- | --- |
| Change (pull request) | A PR opens or updates | Before merge, in under 5 minutes | Phase 3, warn mode; Phase 5, block mode for tier 1 |
| Runtime collection | Requests, messages, jobs and queries run | Minutes for streams, hourly for logs | Phase 1 for gateway logs; Phase 4 for spans, OpenLineage and query history |
| Daily reconciliation | Nightly schedule | By the start of the working day | Phase 4 |
| Incident and RCA | A DQ or contract check fails | Minutes from alert to likely cause | Phase 5 |

The change flow and the incident flow are the two that leaders will feel. The first stops a breaking change before it ships. The second turns a 2 AM page into one alert with the cause, owners and fix order. The other two flows exist to keep the graph trustworthy enough for those two.

## Deployment on AWS

&#91;embedded content: deployment across producer accounts and the lineage platform account\]

The lineage platform lives in its own AWS account, and producer accounts only run small agents and log forwarders. That keeps the blast radius small in both directions: a fault in the platform never stops a producer, and producers never need access to the graph.

### Component choices

| Component | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Evidence bus | Amazon MSK (Kafka), topic lineage.evidence keyed by URN | OpenLineage has a Kafka transport, events can be replayed, and keying by URN keeps each edge in order | Kinesis Data Streams if the company does not run Kafka |
| Log transport | CloudWatch subscription, then Firehose into an Iceberg table | No change to gateways or the mesh; logs already flow to CloudWatch | Mesh sidecars publishing access logs straight to the bus |
| Core services | EKS, deployed with Helm and Argo CD | Several small services that scale on their own; same platform as most service teams | ECS on Fargate for a team without Kubernetes |
| Batch jobs | Step Functions running EMR Serverless | Hourly log edges and the nightly reconciler run on Spark without a cluster to keep up | Glue jobs or Athena queries |
| Graph | Neptune with openCypher, 1 writer and 2 readers | Fast multi-hop traversal for impact and RCA, Multi-AZ | DataHub, decided in week 1; Marquez on Postgres for a small first slice |
| Search | OpenSearch | Asset search and type-ahead in the UI | DataHub's own search if DataHub is the store |
| State | Aurora Postgres | Identity table, owner queues, PR overlays, all transactional | DynamoDB, at the cost of harder ad hoc queries |
| Raw evidence | Iceberg on S3 with the Glue catalog | Cheap, queryable with Athena or Spark, the replay source for every rebuild | Plain S3 Parquet |

### What comes online in each phase

| Phase | New components | Where they run |
| --- | --- | --- |
| Phase 0 · Baseline | Golden graph for the slice, accuracy report job | S3, one scheduled job |
| Phase 1 · Gateway logs | Log forwarding, hourly log edge builder, evidence topic, identity resolver, graph writer, graph store, first UI | Producer CloudWatch, Firehose, EMR Serverless, MSK, EKS, Neptune |
| Phase 2 · Catalog overlay | Registry and catalog crawlers, owners, search | EKS, OpenSearch, Aurora |
| Phase 3 · Static code | CI scanners, PR overlay, PR impact bot in warn mode | CI runners, EKS, Aurora |
| Phase 4 · Runtime edges | OTel lineage processor, OpenLineage listeners, query history puller, full confidence scorer, daily reconciler, owner queue | Producer clusters, EKS, EMR Serverless |
| Phase 5 · Prevention and RCA | Contract gate in block mode for tier 1, DQ events on the bus, RCA service, circuit breaker | CI, EKS, orchestrator hooks |
| Phase 6 · Scale out | Producer modules rolled out to more accounts, more graph readers | Terraform modules per account, Neptune |

### Environments and infrastructure as code

- **Three accounts:** dev, stage and prod for the platform, each a copy built from the same Terraform.
- **Producer side as a module:** the CloudWatch subscription, the OTel collector config and the OpenLineage settings ship as one Terraform module and one Helm values file, so a new team turns lineage on in a single pull request.
- **Services:** Helm charts synced by Argo CD; a release goes to stage first.
- **Safe releases:** stage replays a day of prod evidence from the lake before a new scorer or resolver goes to prod, and the accuracy report must not drop.
- **CI scanners:** one reusable CI workflow that repos include, so the scanner version is the same everywhere.

### Security

- **Metadata only:** no payload ever leaves a producer. The OTel processor keeps attribute names, never values, and gateway logs keep path templates, not query strings.
- **Access:** an IAM role per service, private connectivity from producer accounts to MSK, Lake Formation on the Iceberg tables, and SSO in front of the UI and API.
- **Encryption:** KMS keys for every store and TLS everywhere in transit.
- **Sensitive names:** column names can themselves be sensitive, so assets tagged PII are shown only to roles allowed to see them.

### Scale and cost drivers

- **Span volume:** the biggest lever. The collector sends one edge summary per minute instead of one event per span.
- **Graph size:** Neptune instance size and the number of readers grow with the number of assets and queries, not with traffic.
- **Search and bus:** the OpenSearch domain and MSK brokers and retention are the next largest lines.
- **Object-level logs:** CloudTrail data events on S3 are costly at volume, so prefer warehouse query history and turn on S3 data events only for the buckets in the slice.

### What happens when something fails

| Failure | Effect | Design response |
| --- | --- | --- |
| Lineage platform is down | Producers keep running; the graph goes stale | Every send is asynchronous and can be dropped; the UI shows "as of" times |
| Bus backlog | Graph lags behind runtime | Alarm on consumer lag; consumers scale out on EKS |
| A collector release writes wrong edges | Bad edges in the graph | Each edge records the collector version; exclude it and rescore from the lake |
| PR bot is down | No impact comment on a PR | Fails open with a "lineage check unavailable" comment and an alert, so merges never wait on the platform |
| Graph store fails | Impact and RCA queries stop | Multi-AZ readers take over; nightly snapshot; full rebuild from the lake |
| Two assets merged by mistake | Wrong impact results | The identity table is versioned; split the URN and replay its evidence |
