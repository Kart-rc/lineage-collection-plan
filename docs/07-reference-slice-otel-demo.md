# Reference slice: the OpenTelemetry Demo order flow

Nov 27, 2026 · Replaces the illustrative card-authorization slice as the system the build is developed and tested against. The decisions that follow from it are in [doc 08](08-build-decisions.md).

## On a page

The plan, spec and pages so far used an illustrative slice: `payments-svc` to `fraud-svc`, with names, volumes and incidents made up. That was enough to design with. It is not enough to build or test against, because nobody can run it, read its code or check a lineage edge against it.

The [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) can stand in for it. It is an Apache-2.0 project maintained by the OpenTelemetry community: an online shop of fifteen application services in twelve languages, plus Kafka, Postgres, Valkey and a feature-flag service, with a real order path from a web request through a payment call to a Kafka topic and into Postgres. It is pinned here at release **3.1.0** (18 September 2026, commit `dedc017`).

What makes it fit for this build, and not only for a demo:

- **A real order flow across services, a topic and a database.** Checkout charges a card, ships, publishes the order to Kafka as protobuf, and two consumers read it. One writes 17 columns into three Postgres tables.
- **Ten languages on the order path.** TypeScript, Go, C#, C++, Rust, PHP, JavaScript, Ruby and Kotlin, with Python driving load. That is the honest test of a service-code scanner.
- **Its own golden list of service edges.** The project's test suite asserts 13 service-to-service edges in live traces. Those become owner-confirmed edges for free.
- **Real schema changes in its history.** Six changes since 2022 are replayable from git: a field retype, a package rename, a new consumer, tables moving schema, a service retired, a service rewritten in another language.
- **Faults on a switch.** Feature flags inject payment failures, Kafka overload, a database lock and an unreachable dependency. Four of them make realistic incidents for root-cause replay.
- **Already instrumented.** Every service emits OpenTelemetry traces, metrics and logs, and Postgres has `pg_stat_statements` on. The runtime evidence the plan's Phases 1 and 4 need is produced by the system itself.

What it does not have: a stream processor, a warehouse with dbt, a feature store or a model. Those hops need a second, smaller reference, covered at the end of this document.

The golden graph, change set and incident set are in [`fixtures/otel-demo-3.1.0/`](../fixtures/otel-demo-3.1.0/). [`code/reference_slice.py`](../code/reference_slice.py) holds them with a citation for every edge and checks each citation against the demo's source. At 3.1.0, all 89 citations hold.

## How the illustrative slice maps

| Illustrative slice | Reference slice (demo 3.1.0) | Same mechanism? |
| --- | --- | --- |
| `mobile-bff` through an API gateway | `load-generator` → `frontend-proxy` (Envoy) → `frontend` | Yes. A gateway in front of a web tier |
| `payments-svc` builds and publishes the event | `checkout` builds `OrderResult` and publishes it (Go) | Yes. One service assembles fields from several calls |
| card details sent to a payment call | `checkout` → `payment` `Charge` with `CreditCardInfo` (Node.js) | Yes, and the card never reaches the topic |
| `auth.events.v1`, Avro with a schema registry | `orders`, protobuf defined in `pb/demo.proto`, no registry | Partly. The schema lives in the repository, not a registry |
| `txn-enrichment` Flink job | none | No. Needs the complement |
| `raw.card_auth`, a sink that bypasses SQL | `accounting` consumer writes `accounting.order`, `orderitem`, `shipping` through an ORM (C#) | Yes. A write path that never appears as SQL in a repository |
| `fct_card_auth` dbt model, BI dashboard | none | No. Needs the complement |
| `mcc_decline_7d` feature, an aggregation | `fraud-detection` consumer (Kotlin). At 3.1.0 it reads only `order_id`; after 3.1.0 it sums item cost by currency | Partly |
| `fraud-score-v12`, `fraud-svc` | none | No. Needs the complement |
| Reference data read by a service | `product-catalog` reads `catalog.products` in Postgres | Yes |

## The flow

```text
load-generator ──HTTP──▶ frontend-proxy (Envoy) ──HTTP──▶ frontend (Next.js)
                                                            │ gRPC PlaceOrder
                                                            ▼
             cart ◀── GetCart ── checkout (Go) ── Charge ──▶ payment (Node.js)
     (valkey-cart)                 │  │  │  └── GetProduct ──▶ product-catalog ──▶ Postgres catalog.products
                                   │  │  └──── Convert ────▶ currency (C++)
                                   │  └─ get-quote, ship-order ▶ shipping (Rust) ──▶ quote (PHP)
                                   │  send_order_confirmation ─▶ email (Ruby)
                                   ▼ publish OrderResult (protobuf)
                             Kafka topic "orders"
                       ┌───────────┴────────────┐
                 accounting (C#)          fraud-detection (Kotlin)
                       ▼
     Postgres accounting."order", accounting.orderitem, accounting.shipping
```

## The golden graph

[`fixtures/otel-demo-3.1.0/golden-graph.json`](../fixtures/otel-demo-3.1.0/golden-graph.json), produced by `python3 code/reference_slice.py --write`.

| Part | Count | Notes |
| --- | --- | --- |
| Service and dataset edges | 23 | 13 are asserted in live traces by the demo's own test suite. The other 10 come from code and configuration; `frontend → currency` was added after the first capture |
| Field edges | 36 | 29 identity, 7 transformation (currency conversion and masking) |
| Field reads without a write | 1 | `fraud-detection` reads `order_id` |
| Flag-gated field edges | 8 | Exist only while `emitRawPii` is on: card number, CVV and email into span attributes, then the collector's hashing and masking (decision D30) |
| Flag edges | 20 | Which service reads which of the 18 feature flags, from code (D29) |
| Flows that must not exist | 5 | Card fields to the topic, card fields to the accounting tables, the customer email to the topic, the CVV and the raw email to the collector's export |
| Fields generated with no source | 1 | `order_id`, from `uuid.NewUUID()` in checkout |

Names follow one scheme, which [doc 08](08-build-decisions.md) adopts for the build:

| Kind | Example |
| --- | --- |
| Service | `svc://otel-demo/checkout` |
| Feature flag | `flag://otel-demo/paymentFailure` |
| Span attribute | `otel://otel-demo/checkout/span#user.email` |
| A call's message field | `api://otel-demo/checkout/PlaceOrder/request#address.zip_code` |
| Topic field | `kafka://otel-demo/orders#shipping_address.zip_code` |
| Repeated field | `kafka://otel-demo/orders#items[].cost.units` |
| Table column | `postgres://astronomy-db/astronomy_db.accounting.shipping#zip_code` |

**One field end to end.** The shipping zip code, from the web form to the database:

| Hop | From | To | Evidence at 3.1.0 |
| --- | --- | --- | --- |
| Checkout assembles the order | `PlaceOrder/request#address.zip_code` | `orders#shipping_address.zip_code` | [`src/checkout/main.go:387`](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/src/checkout/main.go#L387) `ShippingAddress: req.Address` |
| Checkout publishes | `OrderResult` | topic `orders` | [`main.go:671`](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/src/checkout/main.go#L671) `Topic: kafka.Topic` |
| Accounting writes it | `orders#shipping_address.zip_code` | `accounting.shipping#zip_code` | [`src/accounting/Consumer.cs:126`](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/src/accounting/Consumer.cs#L126) `ZipCode = order.ShippingAddress.ZipCode` |

This field was retyped from `int32` to `string` in 2022 (change C1 below), so it doubles as the first change-replay case.

## What each collector sees here

Reading the code before running anything already settles five questions the plan left open.

1. **Gateway logs do not see service-to-service calls.** Envoy sits only in front of the web tier. Its access log goes to the collector over OTLP and identifies the caller by remote address, which here is the load generator. Checkout's calls to payment, cart and shipping go direct over gRPC and HTTP and never pass a gateway. The plan's riskiest assumption, that gateway logs carry caller identity for internal calls, does not hold in this system, and it will not hold in any estate without a service mesh. Service-to-service edges must come from traces.
2. **Traces do not link the Kafka hop.** The demo's own test file says the producer spans on checkout and the consumer spans on accounting and fraud detection "live in separate traces", so the parent-child walk that finds the 13 synchronous edges cannot find these two ([`test/telemetry/services.py:96`](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/test/telemetry/services.py#L96)). Checkout does put trace context in the message headers, but the consumers do not continue it. The topic has to be a node of its own, joined from both sides on the destination name and the consumer group.
3. **Runtime misses rare paths, and code catches them.** Upstream leaves `frontend → currency` out of its test because only browser traffic triggers it. `frontend → shipping` is in the code ([`Shipping.gateway.ts:31`](https://github.com/open-telemetry/opentelemetry-demo/blob/3.1.0/src/frontend/gateways/http/Shipping.gateway.ts#L31)) but not asserted. Both are exactly the "static only" items the reconciliation queue exists for.
4. **Field truth lives in three places.** Topic and call fields are in `pb/demo.proto`. Table columns are in the ORM entities and `src/postgresql/init.sql`. How a field gets from one to the other is only in service code: Go in checkout, C# in accounting. No schema registry or catalog holds that mapping. Runtime column evidence for Postgres comes from `pg_stat_statements`, which the demo turns on in its init script.
5. **Telemetry is a data sink too.** With the `emitRawPii` flag on, checkout writes the card number and CVV into span attributes; the collector then drops the CVV and masks the number. In a card estate the observability pipeline is a destination that lineage and the must-not-flow checks have to cover.

## Real changes to replay

From the demo's git history, in [`change-replay.json`](../fixtures/otel-demo-3.1.0/change-replay.json). Each can be checked out at the commit before and after.

| Id | Commit | Date | What changed | Class | What the impact check must say |
| --- | --- | --- | --- | --- | --- |
| C1 | `133d089` | 2022-11-21 | `Address.zip_code` retyped `int32` → `string` | Breaking | Every reader of the field breaks; today that includes `accounting.shipping#zip_code` |
| C2 | `8a28923` | 2023-02-11 | Protobuf package renamed `hipstershop` → `oteldemo` | Breaking for builds, wire-compatible | Bytes on the topic still parse; every generated client must change |
| C3 | `42da57b` | 2025-06-25 | Accounting starts writing orders to Postgres | New consumer and datasets | 17 field edges and three tables appear; nothing existing breaks |
| C4 | `5f83ad1` | 2025-11-07 | The three tables move from `public` to an `accounting` schema | Breaking for readers of old names | Old dataset edges close, new ones open, history stays readable |
| C5 | `66a5b73` | 2026-06-29 | Product review service removed | Retirement | The node and its edges retire; they do not vanish |
| C6 | `c7b195f` | 2026-10-12 | Recommendation rewritten from Python to Java | No lineage change | The call to product-catalog survives while its evidence moves to a new language |
| C7 | `484dfd6` (adds the flag) | flipped 2026-11-27 | `emitRawPii` switched on in the twin, with no code change | Runtime lineage change | Five latent edges turn active on the flag event and the collector's three masking edges start carrying data; the CVV and raw email still never leave the collector |

C6 is after 3.1.0. So is the reason the citation checker matters: run against the demo's `main` branch today, 299 commits later, 33 of the first 60 citations no longer point at the right line, even though most of the edges still exist.

## Real failures to replay

From the demo's flags at 3.1.0, in [`incident-scenarios.json`](../fixtures/otel-demo-3.1.0/incident-scenarios.json).

| Id | Flag | First symptom | What lineage should lead to |
| --- | --- | --- | --- |
| I1 | `paymentFailure` at 50% | Checkout `PlaceOrder` errors | Fewer orders on the topic and in `accounting.order`; the cause is the payment call |
| I2 | `kafkaQueueProblems` | Consumer lag on the `fraud-detection` group | Checkout publishes 100 extra copies of each order; accounting skips them on its primary key |
| I3 | `productCatalogLockContention` | Slow `GetProduct` | A lock on `catalog.products`, two hops below the symptom |
| I4 | `paymentUnreachable` | Checkout errors, topic goes silent | Checkout's payment address, not the payment service itself |
| I5 | `cartFailure` 50% | None: checkout ignores the failed `EmptyCart` | A silent failure. Carts are not emptied and later orders can carry stale items; no check watches it |
| I6 | `productCatalogFailure` (through its targeting rule) | Checkout errors for orders containing product `OLJCESPC7Z` | The catalog's failing reads of one product |
| I7 | accounting stopped for 4 minutes | Accounting insert rate | The consumer, not the topic: orders keep flowing |
| I8 | `intlShippingSlowdown` 10sec | Checkout latency | Shipping's international quotes; no data lost |
| I9 | `recommendationCacheFailure`, then `paymentFailure` 25% | Checkout errors | Payment; the recommendation change is a decoy outside checkout's lineage |
| I10 | `loadGeneratorFloodHomepage` | None of the checks | Traffic from a caller, which a dependency walk cannot reach |

I1 to I4 come from the demo's documentation. I5 to I10 were added on 27 November to grow the visible corpus to ten incidents across nine families (D36).

## Running it

The demo runs with Docker Compose. The run that produces runtime evidence uses release 3.1.0, the full profile (which adds Kafka, accounting and fraud detection), and one collector add-on of this project's: file exporters for traces, logs and metrics, plus the collector's `servicegraph` connector, which turns traces into service-to-service edges.

```text
git clone https://github.com/open-telemetry/opentelemetry-demo.git && cd opentelemetry-demo
git checkout 3.1.0
DEMO_VERSION=3.1.0 OTEL_COLLECTOR_CONFIG_EXTRAS=/path/to/otelcol-capture.yml \
  docker compose -f compose.yaml -f compose.full.yaml -f capture.override.yaml up -d
```

In a sandbox without IPv6, or one that refuses `ulimit`, run `sh sandbox.sh <demo checkout>` first and add `-f sandbox.override.yaml`. It mounts IPv4-only copies of two nginx templates and the flag UI's runtime config, and starts the flag UI without its `ulimit` call.

The add-on and override are in [`fixtures/otel-demo-3.1.0/run/`](../fixtures/otel-demo-3.1.0/run/). After the load generator has run for ten minutes, score what was captured against the golden graph:

```text
python3 code/observed_edges.py <capture folder> fixtures/otel-demo-3.1.0/golden-graph.json --aliases fixtures/otel-demo-3.1.0/aliases.json
python3 code/run_checks.py <capture folder> fixtures/otel-demo-3.1.0 --events <change events>
```

[`code/observed_edges.py`](../code/observed_edges.py) builds call edges from the trace walk (D7) and Kafka edges from the topic name (D8), then lists golden edges not seen and observed edges not in the golden graph: the first entries for the reconciliation queue. It also scores database access down to columns and checks that every name in the capture resolves. [`code/run_checks.py`](../code/run_checks.py) evaluates the checks window by window and, at the first failure, narrows the change events through the graph. Note that the demo's collector, as shipped, mounts the host's Docker socket and root filesystem; the add-on replaces both with empty placeholders and drops the two receivers that use them.

**Status: ran twice on 27 November 2026.** The first run went from 14:06 to 14:39 UTC, with 23 containers, the load generator's HTTP users, and two flags flipped: `emitRawPii` for two minutes, then `paymentFailure` at 50% for five (incident I1). Results are in [doc 09](09-component-build-sheet.md#evidence-from-the-first-capture-run) and the evidence files in [`fixtures/otel-demo-3.1.0/capture-2026-11-27/`](../fixtures/otel-demo-3.1.0/capture-2026-11-27/). In short:

- Every service and topic edge observed is golden.
- All 13 upstream-asserted edges were seen.
- Runtime confirms all 17 accounting columns the code says are written.
- The flag-gated card and email edges appeared 13 seconds after the flip, masked as the collector config says.
- Checkout errors caught I1 two minutes after the flip.

A second run, from 16:54 to 18:43 UTC with 15 simulated shoppers, played incidents I2 to I10. Over both runs:

- 8 of 10 incidents were detected, each within 2 minutes.
- In every one of those 8, the true cause ranked first.
- The two misses are I5, a silent failure no check watches, and I10, a traffic flood no check noticed.

Details and the caveats are in doc 09.

## The hops it does not cover

The demo has no stream processor, warehouse, dbt project, feature store or model. A survey cloned and read 24 open-source repositories to find a complement ([notes](../research_notes/Reference%20slice/oss_reference_flow_survey.md)). None joins a stream processor, dbt and a feature store end to end in a form that runs locally under an open licence. Decision D2 in [doc 08](08-build-decisions.md) assembles the downstream half from the strongest parts instead:

| Hop | Tested against | Why this one | Watch out for |
| --- | --- | --- | --- |
| Stream processor, feature store, training, serving | [`satyazm/Fraud-Detection-using-MLOps`](https://github.com/satyazm/Fraud-Detection-using-MLOps) at commit `d1692f9`, MIT | A PyFlink job computes features and writes them to Feast; a FastAPI service reads them and calls a model trained in MLflow. Every feature declares its source columns in `src/fraud_detection/features/registry.py`, so the golden set comes with the code | One author, published as a single commit in November 2026: fork it. Features are per transaction, so a windowed aggregate is not exercised. PyFlink runs outside Compose |
| SQL models | `dbt-labs/jaffle-shop`, 13 models | The canonical dbt project: an independent test of the SQL extractor on code nobody here wrote | No licence file: use it as a read-only corpus, do not copy it into this repository |
| Warehouse hop into the slice | The thin dbt model in [`fixtures/otel-demo-3.1.0/dbt/`](../fixtures/otel-demo-3.1.0/dbt/), written 27 November (D37): three staging models, a join-heavy mart `fct_order_value`, a dashboard exposure, a 15-minute schedule with a circuit-breaker opt-in, and its own `analytics_dbt` login | Connects the demo's Postgres tables to an aggregate the way `fct_card_auth` did in the illustrative slice, and gives BL-5, IN-3, IR-6 and IR-8 something to test. Its 35 golden edges are hand-written; SQLGlot's column lineage of the compiled SQL agrees on all 30 direct ones | It is code written here, so score the SQL extractor on jaffle-shop, not only on this |
| Join between the two systems | An adapter from the demo's `OrderResult` to the complement's transaction schema | Makes the slice continuous from web request to model | It is itself a field-level hop, so it enters the golden graph like any other. Build it only after each half passes its own gate |

Runner-up for the stream hop, if the feature store can wait: `lahiruweerasingha/realtime-fraud-detection` (MIT), PyFlink with a local Spark SQL feature model.

## Sources

All read at the source on 27 November 2026 from the demo's repository at tag 3.1.0 and its git history: `pb/demo.proto`, `src/checkout/main.go`, `src/accounting/Consumer.cs` and `Entities.cs`, `src/fraud-detection/.../main.kt`, `src/payment/charge.js`, `src/postgresql/init.sql`, `src/frontend-proxy/envoy.tmpl.yaml`, `src/otel-collector/otelcol-config.yml`, `src/flagd/demo.flagd.json`, `test/telemetry/services.py`, `compose.yaml`, `compose.full.yaml` and `.env`.
