# Collection and build guide

This tab answers the three questions the plan leaves open. Where does each collector get its data, and what does it produce? How do five separate collectors become one graph? And how do you build it, week by week? Every example uses the same slice as the plan, payments-svc through fraud-svc, and the same change, PR #482. The components named here are the ones in Architecture and deployment.

## How the five collectors come together

The collectors never talk to each other, and none of them writes the graph. Each one does exactly three things: read its own source, name both ends of what it saw, and publish one evidence event to the `lineage.evidence` topic. Everything after that is the core's job, and the core treats every collector the same way.

That works because of two rules.

- **One envelope:** every collector emits the same event shape, whatever it read. A gateway log line, a dbt model and a Snowflake query all become "this collector saw an edge of this type, from this thing to that thing, at this time, with this weight".
- **One key:** the identity resolver turns every name a collector used into one URN, and the edge key is `from URN | edge type | to URN`. Five collectors describing the same edge in five vocabularies end up on the same key, so their evidence lands in one record and adds up.

### The evidence envelope

It is shaped like an OpenLineage event, so the OpenLineage integrations need only a thin translation, plus one custom facet that carries the evidence.

```json
{
  "eventType": "EVIDENCE",
  "eventTime": "2026-11-12T02:10:04Z",
  "producer": "lineage-collectors/access-history@1.4.0",
  "edge": {
    "type": "DERIVES",
    "from": { "namespace": "snowflake://prod", "name": "PROD_DB.RAW.CARD_AUTH" },
    "to":   { "namespace": "snowflake://prod", "name": "PROD_DB.ANALYTICS.FCT_CARD_AUTH" },
    "columns": [ { "from": "MCC", "to": "MCC" } ]
  },
  "evidence": {
    "source": "access_history",
    "weight": 0.95,
    "runtime": true,
    "observedAt": "2026-11-12T02:04:51Z",
    "count": 24,
    "pr": null,
    "commit": null,
    "rawRef": "evidence_raw/access_history/dt=2026-11-12/part-0007.parquet"
  }
}
```

Collectors send names exactly as they saw them. They do not try to guess URNs, because only the resolver holds the alias table, and a guess in five places means five ways to be wrong.

### The seven steps from signal to graph

1. **Collect:** the collector reads its source on its own schedule (hourly logs, every PR, every job run).
2. **Normalize:** it maps what it read into the envelope and publishes it. The raw input is kept in Iceberg, and `rawRef` points to it, so any edge can be traced back to the exact line that produced it.
3. **Resolve:** the identity resolver looks up each `namespace + name` in the Aurora alias table and returns one URN. A name it cannot resolve goes to the unresolved queue for the owning team, and the edge waits there instead of creating a duplicate node.
4. **Key:** the core builds the edge key from the two URNs and the edge type, and re-partitions on it, so all evidence for one edge reaches the same worker.
5. **Merge:** the worker keeps one row per edge per collector: the highest weight that collector has given and when it last saw the edge. A chatty source sending the same edge a thousand times still counts once.
6. **Score:** confidence is noisy-OR over the collectors' weights, 1 − ∏(1 − w), and the state follows from the score and from whether any source is a runtime one.
7. **Write:** the versioned graph writer upserts the edge with its score, state, sources and columns, closing the old version (`valid_to`) when anything material changes.

Try it below. Switch collectors on and off, or jump to a phase, and click any edge to see the evidence each collector contributes and the merged record it produces.

&#91;embedded content: the nine slice edges, the collectors that see each one, and the merged record each produces\]

### What the resolver does with the names

This is the step that makes "five collectors" into "one graph". Here are the names the slice's collectors actually use for two of its nodes.

| Name as the collector saw it | Collector | Resolves to |
| --- | --- | --- |
| `txn-enrichment.payments.svc.cluster.local` | Gateway and mesh logs | `svc://prod/txn-enrichment` |
| `spiffe://prod/ns/payments/sa/txn-enrichment` | Mesh mTLS identity | `svc://prod/txn-enrichment` |
| `txn-enrichment` in catalog-info.yaml | Registry crawler | `svc://prod/txn-enrichment` |
| Flink job `txn-enrichment-v3` | OpenLineage (Flink) | `svc://prod/txn-enrichment` |
| `PROD_DB.RAW.CARD_AUTH` | Access history | `warehouse://prod/raw.card_auth` |
| `source('raw', 'card_auth')` | CI scanner (dbt) | `warehouse://prod/raw.card_auth` |
| `snowflake://prod` / `prod_db.raw.card_auth` | OpenLineage (dbt-ol) | `warehouse://prod/raw.card_auth` |

The alias table is filled in three ways: registry crawlers write the names each catalog uses, simple rules handle patterns (lower-case, strip the cluster suffix, drop the database prefix), and owners settle whatever remains in the unresolved queue. The phase 2 gate, under 5% unresolved callers, is a measure of this table.

### The merged edge, worked through

Take raw.card\_auth to fct\_card\_auth. Three collectors see it, in three vocabularies, and the resolver puts them on one key.

```json
{
  "edgeKey": "warehouse://prod/raw.card_auth|DERIVES|warehouse://prod/analytics.fct_card_auth",
  "sources": {
    "ci_static":      { "weight": 0.60, "lastSeen": "2026-11-11T17:02Z", "pr": 482, "commit": "9f3c2e1" },
    "openlineage":    { "weight": 0.95, "lastSeen": "2026-11-12T02:05Z", "job": "dbt.fct_card_auth" },
    "access_history": { "weight": 0.95, "lastSeen": "2026-11-12T02:04Z", "queries": 24 }
  },
  "columns": [ { "from": "mcc", "to": "mcc" }, { "from": "card_bin", "to": "card_bin" } ],
  "confidence": 0.999,
  "state": "confirmed",
  "validFrom": "2026-11-12T02:05Z",
  "validTo": null
}
```

The confidence is 1 − (0.40 × 0.05 × 0.05) = 0.999. It is confirmed because it clears 0.9 and two of its sources are runtime ones. Had only the CI scanner seen it, it would stand at 0.60, probable, which is exactly right for code that has merged but not yet run.

### What each collector adds that the others cannot

| Collector | What only it gives you | Where it is blind |
| --- | --- | --- |
| Gateway and mesh logs | Which service calls are live, how often, from which caller | Anything that is not an HTTP or gRPC call, such as topics and tables |
| Registry crawlers | Owners, tiers, declared intent, and the names the alias table needs | Whether the declaration is still true |
| CI scanners | The edge before it ships, column by column, tied to a PR | Dynamic names and config set at deploy time |
| Runtime events (OpenLineage, OTel) | What actually ran, with column lineage from Spark and dbt | Jobs nobody has instrumented |
| Access history | Warehouse truth, including notebooks and ad hoc queries | Anything outside the warehouse, and it lags by up to three hours |

That is why the design adds collectors in the plan's order. Each new one fills the previous one's blind spot, and the overlap is what lifts edges from probable to confirmed.

## How each collector gets its data

Each section gives the source, how it is read and how often, a real raw input from the slice, and the evidence event it becomes. To keep the examples short, the result shows only the `edge` and `evidence` parts of the envelope.

### 1. Gateway and mesh logs

- **Source:** API Gateway access logs and the Envoy access logs from the service mesh.
- **Access:** both already ship to CloudWatch. A subscription filter sends them through Firehose into the Iceberg table `gw_access_raw`, and the collector only reads that table.
- **How often:** an hourly PySpark job on EMR Serverless, started by Step Functions.
- **What it does:** groups an hour of calls by caller, callee and route, drops health checks and anything under 10 calls, and emits one CALLS edge per group. The caller comes from the mTLS identity when there is one, and from the `x-client-id` header otherwise.

Raw input, one Envoy log line:

```json
{
  "start_time": "2026-11-12T01:14:22.381Z",
  "method": "POST",
  "path": "/v1/score",
  "response_code": 200,
  "duration": 38,
  "upstream_cluster": "outbound|80||fraud-svc.fraud.svc.cluster.local",
  "downstream_peer_uri_san": "spiffe://prod/ns/payments/sa/txn-enrichment",
  "x_client_id": "txn-enrichment"
}
```

Result, after an hour of 41,200 such lines:

```json
"edge": {
  "type": "CALLS",
  "from": { "namespace": "mesh://prod", "name": "spiffe://prod/ns/payments/sa/txn-enrichment" },
  "to":   { "namespace": "mesh://prod", "name": "fraud-svc.fraud.svc.cluster.local" },
  "route": "POST /v1/score"
},
"evidence": { "source": "gateway_log", "weight": 0.90, "runtime": true, "count": 41200,
              "observedAt": "2026-11-12T02:00:00Z" }
```

### 2. Registry crawlers

- **Source:** the systems where teams already declare things: the service catalog (catalog-info.yaml files), the schema registry, the data catalog, the feature store registry and the model registry.
- **Access:** read-only API tokens for each, with no access to the data itself.
- **How often:** a full crawl every 15 minutes, plus webhooks where a registry offers them, so a new schema version shows up in seconds.
- **What it does:** emits OWNS edges and node attributes (owner, tier, schema version), declared edges at weight 0.5, and the alias rows the resolver needs.

Raw input, the feature view in the fraud team's feature repo:

```python
mcc_decline_7d = FeatureView(
    name="mcc_decline_7d",
    entities=[merchant_category],
    ttl=timedelta(days=7),
    source=SnowflakeSource(table="ANALYTICS.FCT_CARD_AUTH", timestamp_field="AUTH_TS"),
    owner="fraud-ml@company",
    tags={"tier": "1"},
)
```

Result, one declared edge plus an ownership edge:

```json
"edge": {
  "type": "DERIVES",
  "from": { "namespace": "snowflake://prod", "name": "ANALYTICS.FCT_CARD_AUTH" },
  "to":   { "namespace": "feast://fraud", "name": "mcc_decline_7d" }
},
"evidence": { "source": "declared", "weight": 0.50, "runtime": false,
              "observedAt": "2026-11-12T02:15:00Z", "attrs": { "owner": "fraud-ml", "tier": 1 } }
```

### 3. CI scanners

- **Source:** the code itself, on every pull request and every merge to main.
- **Access:** a GitHub Action in each slice repo, which runs the scanners and posts its results. It needs read access to the repo and a write token for the evidence topic, nothing else.
- **How often:** every PR (results marked as proposed, for the PR bot and the gate) and every merge (results marked as merged, which the graph uses).
- **What it does:** one scanner per kind of code. Producer and consumer calls in Java, Kotlin and Python are found with Semgrep rules. Flink job graphs come from the job's plan. dbt models go through the dbt manifest and SQLGlot for column lineage. Feature repos and training configs are parsed directly. Service clients come from config and OpenAPI files.

Raw input, the dbt model as changed by PR #482:

```sql
-- models/analytics/fct_card_auth.sql
select
    a.auth_id,
    a.auth_ts,
    a.mcc,                      -- was a.merchant_category_code
    a.card_bin,
    a.amount,
    a.declined
from {{ source('raw', 'card_auth') }} a
```

Result, a column-level edge tied to the PR:

```json
"edge": {
  "type": "DERIVES",
  "from": { "namespace": "dbt://analytics", "name": "source.raw.card_auth" },
  "to":   { "namespace": "dbt://analytics", "name": "model.fct_card_auth" },
  "columns": [ { "from": "mcc", "to": "mcc" }, { "from": "card_bin", "to": "card_bin" } ]
},
"evidence": { "source": "ci_static", "weight": 0.60, "runtime": false, "stage": "proposed",
              "pr": 482, "commit": "9f3c2e1", "observedAt": "2026-11-11T17:02:00Z" }
```

The same scanner run also reports what disappeared: `merchant_category_code` is no longer produced. That removal, not the new edge, is what the impact check follows downstream.

### 4. Runtime: OpenLineage and OpenTelemetry

- **Source:** jobs and services as they run. Spark, Flink, dbt, Airflow and training jobs emit OpenLineage events. Services emit OpenTelemetry spans for their Kafka producers and consumers and their database calls.
- **Access:** OpenLineage events go over the Kafka transport to a raw topic, and the runtime normalizer turns them into evidence. Spans go to an OpenTelemetry Collector, which rolls them up into per-minute counts before anything reaches the lineage system, so no single span is stored.
- **How often:** continuous. A job's event arrives when it starts and when it completes, and span counts arrive every minute.
- **What it does:** confirms that an edge really ran, adds column lineage where the engine reports it, and keeps `lastSeen` fresh, which is what the dormant state is measured from.

Raw input, the OpenLineage completion event from the dbt run (trimmed):

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2026-11-12T02:05:12Z",
  "job": { "namespace": "dbt://analytics", "name": "fct_card_auth" },
  "inputs":  [ { "namespace": "snowflake://prod", "name": "prod_db.raw.card_auth" } ],
  "outputs": [ { "namespace": "snowflake://prod", "name": "prod_db.analytics.fct_card_auth",
    "facets": { "columnLineage": { "fields": {
      "mcc": { "inputFields": [ { "namespace": "snowflake://prod",
               "name": "prod_db.raw.card_auth", "field": "mcc" } ] } } } } } ]
}
```

Raw input, the span attributes the payments-svc producer sends:

```json
{ "service.name": "payments-svc", "span.kind": "PRODUCER",
  "messaging.system": "kafka", "messaging.destination.name": "auth.events.v1",
  "messaging.operation.type": "send" }
```

Results, one from each:

```json
"edge":     { "type": "DERIVES", "from": { "namespace": "snowflake://prod", "name": "prod_db.raw.card_auth" },
              "to": { "namespace": "snowflake://prod", "name": "prod_db.analytics.fct_card_auth" },
              "columns": [ { "from": "mcc", "to": "mcc" } ] },
"evidence": { "source": "openlineage", "weight": 0.95, "runtime": true, "job": "dbt.fct_card_auth" }

"edge":     { "type": "PRODUCES", "from": { "namespace": "otel://prod", "name": "payments-svc" },
              "to": { "namespace": "kafka://msk-prod", "name": "auth.events.v1" } },
"evidence": { "source": "otel_span", "weight": 0.90, "runtime": true, "count": 18240 }
```

### 5. Access history

- **Source:** the warehouse's own record of every query: `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` on Snowflake, or the `system.access.table_lineage` and `system.access.column_lineage` tables on Databricks.
- **Access:** a service role with read access to that view only, which needs no access to the business tables.
- **How often:** hourly, reading only rows newer than the last watermark. Snowflake can lag by up to three hours, so this collector confirms edges rather than alerting on them.
- **What it does:** turns each write into a DERIVES or WRITES edge with its columns, and each read by a person or notebook into a READS edge. The notebook reading `fct_card_auth#card_bin` in the plan was found this way, because nobody declared it and no code scanner can see a notebook.

Raw input, one access history row (the columns that matter):

```json
{
  "QUERY_ID": "01b8c2d4-0000-7a1f-0000-0004c2e3a111",
  "QUERY_START_TIME": "2026-11-12T02:04:51Z",
  "USER_NAME": "DBT_PROD",
  "OBJECTS_MODIFIED": [ {
    "objectName": "PROD_DB.ANALYTICS.FCT_CARD_AUTH",
    "columns": [ { "columnName": "MCC",
      "directSources": [ { "objectName": "PROD_DB.RAW.CARD_AUTH", "columnName": "MCC" } ] } ] } ]
}
```

Result: the envelope at the top of this tab. It is the same edge the CI scanner and dbt-ol reported, under a third name.

## How to build it

The build follows the plan's phases and its six-person team. Four repos keep ownership clear.

- **lineage-infra:** Terraform for MSK, Aurora, OpenSearch, the graph store, S3 and IAM, plus Helm charts and Argo CD apps.
- **lineage-platform:** the core (resolver, merge, scorer, reconciler, graph writer) and the impact and RCA API.
- **lineage-collectors:** one folder per collector, and the shared evidence library every collector uses.
- **lineage-ci:** the GitHub Action, the PR bot and the contract gate.

| Step | Weeks | What you build | Repo | Owner | Done when |
| --- | --- | --- | --- | --- | --- |
| 1 | 1–2 | Evidence topic, envelope schema, evidence library, golden graph | lineage-infra, lineage-collectors | Platform backend | A test event reaches Iceberg, and the slice's golden graph is written down |
| 2 | 2–5 | Core v1: resolver, merge, scorer, graph writer | lineage-platform | Platform backend | Golden edges loaded by hand appear in the graph with the right states |
| 3 | 2–5 | Gateway log edge builder | lineage-collectors/gateway | Streaming | At least 90% of golden service edges found (phase 1 gate) |
| 4 | 4–7 | Registry crawlers and alias table | lineage-collectors/registry | Platform backend, ML platform | 95% of nodes owned, under 5% unresolved callers (phase 2 gate) |
| 5 | 6–11 | CI scanners, PR bot | lineage-ci, lineage-collectors/ci | Developer productivity, analytics engineer | Change replay finds 8 of 10 broken consumers (phase 3 gate) |
| 6 | 9–14 | OpenLineage, OTel and access history collectors | lineage-collectors/runtime, /access | Streaming, analytics engineer, ML platform | Precision at least 95%, freshness under 15 minutes (phase 4 gate) |
| 7 | 13–18 | Contract gate, DQ and deploy events, RCA | lineage-ci, lineage-platform | Platform backend, analytics engineer | MTTD and MTTR halved on slice incidents (phase 5 gate) |

The skeletons below are starting points, not finished code. Each one shows the part that is specific to lineage, and leaves out retries, metrics and tests.

### Step 1: the evidence library (weeks 1–2)

Every collector imports this, so the envelope is defined once. Weights live here too, which keeps a collector from choosing its own.

```python
# lineage-collectors/evidence/emit.py
import json
from datetime import datetime, timezone
from confluent_kafka import Producer

WEIGHTS = {"access_history": 0.95, "openlineage": 0.95, "gateway_log": 0.90,
           "otel_span": 0.90, "ci_static": 0.60, "declared": 0.50, "iam": 0.20}
RUNTIME = {"access_history", "openlineage", "gateway_log", "otel_span"}

class Evidence:
    def __init__(self, bootstrap: str, producer_name: str):
        self.p = Producer({"bootstrap.servers": bootstrap, "acks": "all",
                           "enable.idempotence": True})
        self.name = producer_name

    def edge(self, edge_type, from_ns, from_name, to_ns, to_name, source,
             observed_at=None, columns=None, **extra):
        event = {
            "eventType": "EVIDENCE",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "producer": self.name,
            "edge": {"type": edge_type,
                     "from": {"namespace": from_ns, "name": from_name},
                     "to": {"namespace": to_ns, "name": to_name},
                     "columns": columns or []},
            "evidence": {"source": source, "weight": WEIGHTS[source],
                         "runtime": source in RUNTIME,
                         "observedAt": observed_at or datetime.now(timezone.utc).isoformat(),
                         **extra},
        }
        key = f"{from_ns}/{from_name}"          # keeps one producer's events in order
        self.p.produce("lineage.evidence", key=key, value=json.dumps(event))

    def flush(self):
        self.p.flush()
```

The golden graph is a hand-written YAML file of every edge on the slice, agreed with the slice owners. Every later gate is measured against it, so it comes first.

### Step 2: core v1 (weeks 2–5)

The core is one consumer group on `lineage.evidence`. The first version can be a plain Python service on EKS. Move it to Flink only when volume needs it.

```python
# lineage-platform/core/merge.py
def noisy_or(weights):
    miss = 1.0
    for w in weights:
        miss *= (1 - w)
    return 1 - miss

def state_for(score, has_runtime, owner_verified):
    if owner_verified:
        return "verified"
    if score >= 0.9 and has_runtime:
        return "confirmed"
    return "probable" if score >= 0.6 else "candidate"

def handle(event, resolver, store, graph):
    e = event["edge"]
    src = resolver.resolve(e["from"]["namespace"], e["from"]["name"])
    dst = resolver.resolve(e["to"]["namespace"], e["to"]["name"])
    if src is None or dst is None:
        store.unresolved(event)                  # owner queue, no duplicate node
        return
    key = f"{src}|{e['type']}|{dst}"
    ev = event["evidence"]
    rec = store.get(key) or {"edgeKey": key, "sources": {}, "columns": []}
    prev = rec["sources"].get(ev["source"], {"weight": 0})
    rec["sources"][ev["source"]] = {"weight": max(prev["weight"], ev["weight"]),
                                    "lastSeen": ev["observedAt"],
                                    "runtime": ev["runtime"]}
    rec["columns"] = merge_columns(rec["columns"], e.get("columns", []), resolver)
    rec["confidence"] = noisy_or([s["weight"] for s in rec["sources"].values()])
    rec["state"] = state_for(rec["confidence"],
                             any(s["runtime"] for s in rec["sources"].values()),
                             rec.get("ownerVerified", False))
    if store.changed_materially(key, rec):
        graph.upsert(src, e["type"], dst, rec)   # closes the old version, opens a new one
    store.put(key, rec)
```

The resolver reads the Aurora alias table and caches it in memory.

```sql
create table alias (
  namespace   text not null,
  name        text not null,
  urn         text not null,
  set_by      text not null,        -- crawler, rule or owner
  updated_at  timestamptz not null default now(),
  primary key (namespace, name)
);
```

The graph writer runs one openCypher statement per edge type, because the edge type cannot be a parameter. On Neptune it looks like this.

```cypher
MERGE (a:Asset {urn: $from})
MERGE (b:Asset {urn: $to})
WITH a, b
OPTIONAL MATCH (a)-[old:DERIVES {current: true}]->(b)
SET old.current = false, old.valid_to = $now
CREATE (a)-[e:DERIVES {current: true, valid_from: $now, valid_to: null,
        confidence: $confidence, state: $state, sources: $sources,
        columns: $columns}]->(b)
```

If you choose DataHub in week 1 instead of Neptune, the same record is written as an `UpstreamLineage` aspect through DataHub's API, and DataHub keeps the history.

### Step 3: gateway log edge builder (weeks 2–5)

```python
# lineage-collectors/gateway/build_edges.py   (EMR Serverless, hourly)
from pyspark.sql import SparkSession, functions as F
from evidence.emit import Evidence

spark = SparkSession.builder.getOrCreate()
hour = spark.conf.get("lineage.hour")            # e.g. 2026-11-12T01

logs = spark.table("lineage.gw_access_raw").where(F.col("hour") == hour)
edges = (logs
    .where(~F.col("path").isin("/healthz", "/ready", "/metrics"))
    .withColumn("caller", F.coalesce("downstream_peer_uri_san", "x_client_id"))
    .withColumn("callee", F.regexp_extract("upstream_cluster", r"\|\|(.+)$", 1))
    .withColumn("route", F.concat_ws(" ", "method",
                F.regexp_replace("path", r"/[0-9a-f-]{8,}", "/{id}")))
    .groupBy("caller", "callee", "route")
    .agg(F.count("*").alias("calls"))
    .where(F.col("calls") >= 10))

ev = Evidence(bootstrap=spark.conf.get("lineage.bootstrap"),
              producer_name="lineage-collectors/gateway@1.0.0")
for r in edges.toLocalIterator():
    ev.edge("CALLS", "mesh://prod", r.caller, "mesh://prod", r.callee,
            "gateway_log", observed_at=f"{hour}:00:00Z", count=r.calls, route=r.route)
ev.flush()
```

Callers with no mTLS identity and no client header are counted rather than dropped. That count is the "unresolved callers" figure in the phase 2 gate.

### Step 4: registry crawlers (weeks 4–7)

Each crawler is a small scheduled job that lists one registry, emits declared edges and node attributes, and writes alias rows. The one for catalog-info.yaml files looks like this.

```python
# lineage-collectors/registry/service_catalog.py
for entity in catalog.list_entities(kind="Component"):
    urn = f"svc://prod/{entity.name}"
    aliases.upsert("catalog://prod", entity.name, urn, set_by="crawler")
    for host in entity.annotations.get("lineage/hosts", "").split(","):
        if host:
            aliases.upsert("mesh://prod", host.strip(), urn, set_by="crawler")
    for topic in entity.spec.get("produces", []):
        ev.edge("PRODUCES", "catalog://prod", entity.name,
                "kafka://msk-prod", topic, "declared", owner=entity.spec["owner"])
```

### Step 5: CI scanners and the PR bot (weeks 6–11)

The Action runs on every PR and every merge in the slice repos.

```yaml
# lineage-ci/action.yml, used from each slice repo
name: lineage-scan
on: [pull_request, push]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install lineage-ci
      - run: lineage-ci scan --stage ${{ github.event_name == 'push' && 'merged' || 'proposed' }}
               --pr ${{ github.event.number }} --commit ${{ github.sha }}
      - run: lineage-ci impact --pr ${{ github.event.number }} --comment
        if: github.event_name == 'pull_request'
```

The dbt scanner uses SQLGlot's lineage module on each compiled model to get column edges.

```python
# lineage-ci/scanners/dbt_sql.py
from sqlglot import exp
from sqlglot.lineage import lineage

def column_edges(model_name, compiled_sql, output_columns, schema):
    for col in output_columns:
        root = lineage(col, compiled_sql, schema=schema, dialect="snowflake")
        for node in root.walk():
            if isinstance(node.source, exp.Table):           # a source column
                yield {"from_table": exp.table_name(node.source),
                       "from_col": node.name.split(".")[-1],
                       "to_table": model_name, "to_col": col}
```

`impact` compares the proposed edges with the merged graph, lists every column the PR removes or renames, and walks downstream from each. For PR #482 that is the seven assets and five teams in the plan, posted as one PR comment.

### Step 6: runtime and access history (weeks 9–14)

Most of this step is configuration, because the integrations already exist. All OpenLineage sources send to the raw topic `lineage.ol.raw`, and one normalizer turns their events into evidence.

Spark on EMR, set on the job or the cluster:

```properties
spark.jars.packages=io.openlineage:openlineage-spark_2.12:<version>
spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener
spark.openlineage.namespace=emr-prod
spark.openlineage.transport.type=kafka
spark.openlineage.transport.topicName=lineage.ol.raw
spark.openlineage.transport.properties.bootstrap.servers=<msk brokers>
```

dbt, by swapping the command in the scheduler:

```bash
pip install openlineage-dbt
export OPENLINEAGE_CONFIG=/etc/openlineage/openlineage.yml   # Kafka transport, topic lineage.ol.raw
dbt-ol run --select fct_card_auth+
```

Airflow, by installing the provider and setting the transport:

```ini
# pip install apache-airflow-providers-openlineage
[openlineage]
namespace = airflow-prod
transport = {"type": "kafka", "topic": "lineage.ol.raw", "config": {"bootstrap.servers": "<msk brokers>"}}
```

Flink uses the OpenLineage Flink listener with the same transport. Training jobs call the OpenLineage Python client at start and end, naming the feature set as the input and the model version as the output.

Services need only standard OpenTelemetry instrumentation for their Kafka and database clients. The Collector rolls spans up into counts with the lineage dimensions kept.

```yaml
# otel-collector, lineage pipeline only
connectors:
  spanmetrics:
    dimensions:
      - name: messaging.destination.name
      - name: messaging.operation.type
      - name: db.namespace          # db.name on older SDKs
      - name: db.collection.name
    metrics_flush_interval: 60s
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [spanmetrics]
    metrics/lineage:
      receivers: [spanmetrics]
      exporters: [kafka/lineage]    # topic lineage.otel.counts
```

Field names in the Kafka exporter differ between Collector versions, so check them against the version you run. A small consumer turns each count row with a PRODUCER or CONSUMER span kind into a PRODUCES or CONSUMES edge, and each database row into READS or WRITES.

Access history, run hourly from the watermark:

```sql
select ah.query_id,
       ah.query_start_time,
       ah.user_name,
       tgt.value:"objectName"::string  as to_table,
       col.value:"columnName"::string  as to_column,
       src.value:"objectName"::string  as from_table,
       src.value:"columnName"::string  as from_column
from snowflake.account_usage.access_history ah,
     lateral flatten(input => ah.objects_modified) tgt,
     lateral flatten(input => tgt.value:"columns") col,
     lateral flatten(input => col.value:"directSources") src
where ah.query_start_time > :watermark;
```

A second query over `base_objects_accessed`, for queries that modify nothing, gives the READS edges from people and notebooks.

### Step 7: contracts, DQ and RCA (weeks 13–18)

Contract checks, DQ results, deploys and merged PRs are published to the same evidence topic as events on nodes, so they share the graph's names. The contract gate in CI then needs one query: does this PR remove or change a field that a confirmed downstream edge reads?

```cypher
MATCH (f:Asset {urn: 'kafka://msk-prod/auth.events.v1#merchant_category_code'})
      -[r*1..8 {current: true}]->(d:Asset)
WHERE all(x IN r WHERE x.state IN ['confirmed', 'verified'])
RETURN d.urn, d.owner, d.tier
```

The gate warns when the field has only probable consumers, and blocks when a tier 1 consumer is confirmed and has no alias or sign-off. For RCA, the same walk goes upstream from the failing DQ check on `mcc_decline_7d` and ranks every change event on that path in the last 24 hours, which is how the plan's 02:42 null-rate failure points straight to the 02:03 hotfix.

### What each producer team does

Each slice team makes one small PR, reviewed by the lineage team.

- **Services (payments-svc, fraud-svc):** add the standard OpenTelemetry Kafka and HTTP instrumentation, and the `lineage/hosts` annotation in catalog-info.yaml.
- **Streaming (txn-enrichment):** add the OpenLineage Flink listener and its Kafka transport settings.
- **Analytics (dbt project):** switch `dbt run` to `dbt-ol run` and add the lineage-scan Action.
- **ML (fraud features and model):** add the Action to the feature repo, and two OpenLineage client calls to the training job.

Nothing in these PRs changes business logic, and each can be rolled back on its own.
