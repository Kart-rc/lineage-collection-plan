# Onboarding an application flow

Nov 28, 2026 · For application teams and their leads. It explains how a flow gets its lineage captured and managed by the platform: where to start, what each step asks of you, what you get back and when. The decisions behind it are in [doc 08](08-build-decisions.md), the components in [doc 09](09-component-build-sheet.md), and the contracts in [`factory/`](../factory/README.md).

## On a page

- **You do three things:**
  - onboard each repository with one change: a `.lineage.yaml` file and one `lineage-ci` step in CI;
  - name owners and tiers;
  - write checks, plus contracts for tier 1 data.
- **The platform does the rest:**
  - it reads your code on every pull request and merge;
  - it collects runtime evidence centrally;
  - it keeps a field-level, versioned lineage graph.
- **You get back:**
  - impact reports on your pull requests;
  - an API to ask "what breaks if I change this";
  - alerts that arrive with the path upstream and the likely causes ranked.
- **Two levels:**
  - **Covered:** current, scored lineage, with PR reports and incident analysis.
  - **Certified:** accuracy measured against a signed golden graph, and a PR gate that may block. Most flows only need covered.
- **Today:** the platform is being built in waves. The quick map (step 1) works now with the prototypes. None of the service levels is live yet: each is marked in this guide with the wave that brings it, and [Service levels by wave](#service-levels-by-wave) lists them together.

The interactive version of this guide, with a self-check of your flow, is [`site/lineage-onboarding-guide.html`](../site/lineage-onboarding-guide.html).

## Words used here

| Term | Meaning |
| --- | --- |
| Application flow | A business process that crosses several services and data stores, such as an order from checkout to the finance tables |
| Onboarded repository | A repository whose default branch holds a valid `.lineage.yaml` and whose CI runs the `lineage-ci` step (requirement XC-7) |
| Covered flow | Every repository of the flow is onboarded, its owners and tiers are in the catalog, and its runtime signals reach the platform |
| Certified flow | A covered flow with a golden graph signed at gate G3, and change and incident corpora that measure its accuracy |
| Tier | 1 for critical, 2 for high, 3 for the rest, following each service's criticality. Tier 1 elements are the ones the gate protects |
| Edge state | How sure the platform is that an edge exists:<br>**candidate:** below 0.60.<br>**probable:** at least 0.60, for example seen in code only.<br>**confirmed:** at least 0.90 and seen at runtime.<br>**verified:** an owner confirmed it.<br>**dormant:** no runtime evidence for 30 days. |

## The entry points

### Getting a flow in

| What your team does | What it gives the platform | Contract |
| --- | --- | --- |
| Add `.lineage.yaml` and the `lineage-ci` step to each repository, in one pull request | Static lineage, field to field, from code and schemas, on every pull request and merge | [`lineage-repo.schema.json`](../factory/specs/build-collection/interfaces/lineage-repo.schema.json), [`extractor-plugin.md`](../factory/specs/build-collection/interfaces/extractor-plugin.md) |
| Add owners and tiers to the catalog | Who gets questions and review requests; which elements are critical | [`catalog.yaml`](../fixtures/otel-demo-3.1.0/catalog.yaml) (reference example) |
| Write contracts for tier 1 data | What the PR gate enforces | [`orders.contract.yaml`](../fixtures/otel-demo-3.1.0/contracts/orders.contract.yaml) (example) |
| Write checks for what matters: rates, errors, lag, latency, data quality | Where incident analysis starts | [`checks.yaml`](../fixtures/otel-demo-3.1.0/checks.yaml) (example) |

### Signals the platform collects

Most of these are enabled centrally; your part is making sure the signal exists.

| Signal | What your flow needs | Used for | Collected from |
| --- | --- | --- | --- |
| OpenTelemetry traces | Every service emits spans with a `service.name` equal to its name in `.lineage.yaml` | Service-to-service edges at runtime (D7) | Wave 1 (WP-19) |
| Message spans | Producer and consumer spans name their topic (`messaging.destination.name`) | Kafka and queue hops, joined on the topic (D8) | Wave 1 (WP-19) |
| Database spans or warehouse query history | Statements in database client spans, or platform read access to Snowflake `ACCESS_HISTORY` or the Databricks lineage system tables | Column-level reads and writes at runtime (D27, D22) | Wave 2 (WP-26): Postgres first, then Snowflake and Databricks |
| OpenLineage | Spark, dbt, Flink and Feast integrations, switched on by the platform | Jobs and their column lineage | Wave 2 (WP-27) |
| Gateway logs | Nothing; the platform reads them | Traffic entering the estate only | Wave 1 (WP-19) |
| Change events | Deploys, flag changes and merges reach the timeline; flags are read from code | Ranking the causes of an incident (D29) | Wave 4 (WP-41) |

Everything arrives on one topic in one format (evidence envelope v2). It goes through name matching and scoring, and lands in the graph of record (Neptune, ADR-002).

### Using the lineage

| Where | What you see | Bar | From |
| --- | --- | --- | --- |
| Your pull requests | An impact report: changed fields, their kind (renamed, retyped, removed…), the readers downstream with owner and tier, and a gate result | Within 5 minutes at p95 (IA-1). Warns first; blocks only tier 1 contract breaks (IA-5) | Wave 3 (WP-33 reports, WP-34 blocking) |
| `/impact` API and agent tool | "What breaks if I change this field?", before a pull request exists | IA-9 | Wave 3 (WP-31) |
| Alerts | A failing check arrives with the path upstream, the ranked causes and the blast radius | Within 2 minutes at p95 (IR-1) | Wave 4 (WP-42) |
| `/upstream`, `/diff`, `/explain` | Lineage at any past time, what changed between two times or commits, and the evidence behind any edge | IN-5, IN-6, XC-2 | Wave 1 (WP-12, WP-13, WP-14) |
| Owner queue | Edges seen only in code, only at runtime, or in disagreement, for an owner to confirm or dispute | Daily (WP-16) | Wave 1 (WP-16) |

## Two levels: covered and certified

| | Covered | Certified |
| --- | --- | --- |
| For | Most flows | Flows that move money, personal data or regulatory reporting |
| Requires | Steps 0 to 4 | Steps 0 to 5 |
| Accuracy | Scored per edge; tracked by sampled audits and the owner queue | Measured weekly against a signed golden graph: field-edge precision and recall at least 90% (BL-6). Service and topic edges from wave 1, field edges from wave 2 |
| PR gate | Warns (wave 3) | May block tier 1 contract breaks, once the warn period shows at least 95% precision on the cases it would have blocked (wave 3) |
| Incidents | Ranked causes from the first failing check (wave 4) | The same, with accuracy measured on change and incident replays (wave 4) |

## Step by step

### Step 0. Intake

- **You:** name the flow, its repositories, services and data stores, its owners and its tier.
- **The platform:** checks what the flow already emits and which of its technologies have extractors.
- **You get:** a coverage list. It shows which hops will be field level from code, which are runtime only, and which are stated gaps. The self-check on the guide page gives a first answer in a minute.

### Step 1. Quick map

- **The platform:** adds its capture add-on to your OpenTelemetry collector in a stage environment and scores what it sees. This works today with the prototypes ([`code/observed_edges.py`](../code/observed_edges.py)); on the reference flow it found every expected service and topic edge, and every column written.
- **You get:** a map of services, topics and tables, with the columns written, in about a day.
- **Done when:** every service and data store of the flow is on the map, or on the gap list with a reason.

### Step 2. Onboard each repository

One pull request per repository. The [demo's monorepo of 14 services](../fixtures/otel-demo-3.1.0/onboarding/opentelemetry-demo.lineage.yaml) is onboarded by a 27-line file.

```yaml
# .lineage.yaml
version: 1
repository: payments-api          # becomes unit://git/payments-api/<path>
environment: prod                 # becomes svc://prod/<service>
owner: team-payments
services:
  - {name: checkout, path: src/checkout, language: go, extractors: [go-assembly]}
schemas:
  - {kind: protobuf, path: proto/orders.proto}
build: {reuse_artifacts: true, max_minutes: 5}
```

Then add the step to CI. The CLI is the product, so any CI system works; a GitHub Action wraps the same commands.

```text
lineage-ci validate
lineage-ci scan --stage proposed --commit $SHA --base $BASE_SHA --pr $PR_NUMBER    # on pull requests
lineage-ci impact --pr $PR_NUMBER --comment                                        # on pull requests
lineage-ci scan --stage merged --commit $SHA                                       # on merges to the default branch
```

- **You get:**
  - from wave 1, the first full scan of the default branch within 1 hour (XC-7), and every later pull request and merge scanned into the graph;
  - from wave 3, a report on every later pull request within 5 minutes (IA-1). In waves 1 and 2 the `impact` command posts nothing.
- **Guarantees, from wave 1:**
  - A wrong `.lineage.yaml` never fails your build; the step names the field to fix (XC-7).
  - If the platform is down, the step passes and raises an alert; from wave 3 it also comments "lineage check unavailable" (IA-6).
  - Only changed units are re-read (IN-1).
- **Done when:** the first scan's manifest lists a unit for every configured service, schema and project.

### Step 3. Owners, contracts and checks

- **Owners and tiers.** One line per service and dataset in the catalog:
  ```yaml
  checkout: {criticality: critical, tier: 1, owner: team-payments, kind: service}
  ```
- **Contracts for tier 1 data:** fields, types, compatibility mode and forbidden fields.
- **Checks** on the elements that matter. Thresholds are set before any incident and never tuned on one:
  ```yaml
  - id: orders-rate
    node: kafka://prod/orders
    metric: kafka.partition.current_offset
    where: {topic: orders}
    fail_if: rate_ratio < 0.5 or rate_ratio > 3.0
    min_events: 20
  ```
- **Done when:** every node of the flow has an owner and a tier, and every tier 1 element has a contract and at least one check.

### Step 4. Reconcile

The first owner queue lists edges the platform is unsure about:

- edges seen in code but never at runtime, such as a path only browsers trigger;
- edges seen at runtime but not in code;
- edges where code and runtime disagree.

Owners confirm or dispute each one, and edges move from probable to confirmed or verified.

- **Effort:** a few minutes per item; the queue shrinks as runtime evidence accumulates.
- **Done when:** the first queue is empty, and every tier 1 path is confirmed or verified.

### Step 5. Certify (optional)

- **Golden graph:** owners and the platform write the truth for the flow, each edge cited to a line of code or a document, and it is signed at gate G3. On the reference flow that was 23 service edges and 36 field edges.
- **Owner time:** the plan's estimate is about two hours per owner in the first week.
- **Corpora:** at least 20 changes and 20 incidents for the flow, a third of each family held out. The holdout is written by people who do not build the platform, and kept outside its repository.
- **You get:** accuracy measured every week, and a PR gate allowed to block.
- **Done when:** G3 is signed and the first weekly accuracy report meets 90% precision and recall.

### Step 6. Steady state

- **Kept current:** merges re-scan only what changed, and new edges appear within 15 minutes at p95 (IN-10, wave 1). From wave 3, a change upstream also re-scans the units that depend on it (WP-30).
- **History:** an edge with no runtime evidence for 30 days is marked dormant, not deleted (IN-8). Every version of every edge is kept, so the graph can be read as of any time (IN-4, IN-5). Both from wave 1.
- **Incidents:** each records when bad data landed, when the alert fired, when the cause was identified and when it was fixed (IR-9, wave 4).

## Who provides what

| Your team | The platform |
| --- | --- |
| One `.lineage.yaml` and one CI step per repository | The `lineage-ci` runner and the extractors behind it |
| Service names in traces that match `.lineage.yaml` | Trace, topic and gateway collection; name matching |
| Read access to warehouse query history, or statements in database spans | Access-history collection and SQL parsing to columns |
| Owners and tiers; contracts and checks for tier 1 data | The check runner, the contract gate and incident analysis |
| Answers to the owner queue | The queue, routed to the owners in the catalog |
| For certification: about two hours per owner, and a signature at G3 | The golden-graph tooling, the replays and the weekly accuracy report |

## Limits

- **Code-only edges are probable, not confirmed.** Runtime evidence is what confirms them.
- **A language or framework without an extractor is a stated gap.** You get table-level edges, runtime evidence, and candidate edges from a model that never become confirmed on their own. One extractor, once built, serves every flow that uses its technology.
- **Analysis starts from a failing check.** A silent failure needs a check of its own, such as items per order. In the platform's own test runs, a silent cart failure and a traffic flood fired no check.
- **The platform stores metadata only:** names, schemas and expressions, never data values or row-level provenance (XC-1).
- **Nothing in your request path changes.** Collection is asynchronous and fails open (XC-3, IA-6).
- **Code sent to a model leaves only through the approved endpoint** in the platform account (XC-6, D19), and only for units no rule can read.

## Service levels by wave

None of these is live today. Waves run in order and are not dated. A bar holds for teams once the release that contains the work package carrying it passes the release gate, G4. The rules for G4 are proposed in [G1 amendment 2](../factory/gates/proposed/G1-amendment-2.md):
- every metric at its bar;
- nothing that passed in the last approved release now failing;
- zero must-not-flow violations, stored values and blocked builds;
- each timing measured against its bar.

IA-8 and IR-5 are declared held only once the holdout corpora exist (WP-02). Until slice 2, the gate replays the twin only, so it cannot catch a difference between the twin and production.

| What you can count on | Bar | Requirement | From | Carried by |
| --- | --- | --- | --- | --- |
| What is stored | Metadata only: names, schemas, expressions, counts and times; never data values | XC-1 | Wave 1 | WP-11 |
| Your build and your services | Never blocked or slowed: emission is asynchronous and droppable, and the CI step passes when the platform is down | XC-3, IA-6 | Wave 1 | WP-11, WP-18; the "unavailable" PR comment with WP-33 in wave 3 |
| First full scan after onboarding a repository | Within 1 hour | XC-7 | Wave 1 | WP-18 |
| A merge or run visible in the graph | Within 15 minutes at p95 | IN-10 | Wave 1 | WP-13; held again in wave 3 by WP-30 |
| Service and topic edges | Precision at least 95%, recall at least 90% | BL-6 | Wave 1 | WP-19 |
| Field edges from code | Precision and recall at least 90%, per extractor | BL-6 | Wave 2, one extractor at a time | Each extractor's done-when: SQL and dbt in WP-20, PyFlink and features in WP-22 and WP-25, Go in WP-23, C# in WP-24 |
| Impact report on a pull request | Within 5 minutes at p95 | IA-1 | Wave 3 | WP-33 |
| Consumers that actually broke, listed in the report | At least 80%, on visible and holdout change replays | IA-8 | Wave 3 | WP-33 |
| Blocking tier 1 contract breaks | Only after the warn period shows at least 95% precision on what it would have blocked | IA-5 | Wave 3 | WP-34; the warn-period bar is in [`parameters.yaml`](../factory/parameters.yaml) |
| Alert enriched with path, ranked causes and blast radius | Within 2 minutes at p95 | IR-1 | Wave 4 | WP-42 |
| True cause of an incident | First at least 70% of the time, in the top three at least 90% | IR-5 | Wave 4 | WP-42 |

Wave 0 is the platform's own groundwork (the twin, the golden graph, the corpora and the scoring harness) and gives teams nothing directly.

## What is available, and when

| After | An onboarded flow gets |
| --- | --- |
| Today (prototypes) | The quick map (step 1), run by the platform team |
| Wave 1 | Service-level lineage from traces, topics and gateway logs; repository onboarding with the `lineage-ci` runner; owners and tiers; the owner queue; `/upstream`, `/diff` and `/explain` |
| Wave 2 | Field-level lineage from code: protobuf and Avro, Go, C# with Entity Framework, SQL and dbt, PyFlink and Feast first; Kotlin and other languages follow |
| Wave 3 | PR impact reports, the `/impact` API and the contract gate |
| Wave 4 | Alerts with the upstream path and ranked causes; the check runner; the change-event timeline |
| Wave 5 | Search, a lineage UI, and projections into Unity Catalog and Snowflake Horizon |

The first flow from your own estate to go through these steps is slice 2 (decision D22).

## Checklist

```text
[ ] Flow named, with repositories, services, data stores, owners and tier
[ ] Self-check done; coverage list reviewed
[ ] Quick map from a stage capture reviewed
[ ] Every repository: .lineage.yaml merged and lineage-ci in CI
[ ] Service names in traces match .lineage.yaml
[ ] Warehouse query history readable by the platform, or statements in database spans
[ ] Every node has an owner and a tier in the catalog
[ ] Every tier 1 element has a contract and a check
[ ] First owner queue cleared
[ ] Certification only: golden graph signed at G3; corpora written; first weekly report at 90%
```

## Questions

**Do we need a golden graph?** Only to certify the flow. Covered flows rely on the scoring, the owner queue and sampled audits.

**Our CI is not GitHub.** The `lineage-ci` CLI is the product; run the same commands in any CI system.

**Will this slow our builds or services?** A PR scan stays within 5 minutes at p95 and reuses what your build already produces. Runtime collection reads exported telemetry and never sits in a request path.

**A service is written in a language nobody supports.** It shows as a gap with a reason, its runtime edges still appear, and candidate edges can be proposed. Ask for an extractor; one serves every flow that uses that language.

**Who owns an edge?** The owner of the dataset or service it writes to, as recorded in the catalog. That owner receives the queue items and review requests.

**What leaves our systems?** Metadata only. Source code goes to a model only for units no rule can read, and only through the approved endpoint.
