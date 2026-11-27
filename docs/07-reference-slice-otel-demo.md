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

The golden graph, change set and incident set are in [`fixtures/otel-demo-3.1.0/`](../fixtures/otel-demo-3.1.0/). [`code/reference_slice.py`](../code/reference_slice.py) holds them with a citation for every edge and checks each citation against the demo's source. At 3.1.0, all 60 citations hold.

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
| Service and dataset edges | 22 | 13 are asserted in live traces by the demo's own test suite. The other 9 come from code and configuration |
| Field edges | 36 | 29 identity, 7 transformation (currency conversion and masking) |
| Field reads without a write | 1 | `fraud-detection` reads `order_id` |
| Flows that must not exist | 3 | Card fields to the topic, card fields to the accounting tables, the customer email to the topic |
| Fields generated with no source | 1 | `order_id`, from `uuid.NewUUID()` in checkout |

Names follow one scheme, which [doc 08](08-build-decisions.md) adopts for the build:

| Kind | Example |
| --- | --- |
| Service | `svc://otel-demo/checkout` |
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

C6 is after 3.1.0. So is the reason the citation checker matters: run against the demo's `main` branch today, 299 commits later, 33 of the 60 citations no longer point at the right line, even though most of the edges still exist.

## Real failures to replay

From the demo's flags at 3.1.0, in [`incident-scenarios.json`](../fixtures/otel-demo-3.1.0/incident-scenarios.json).

| Id | Flag | First symptom | What lineage should lead to |
| --- | --- | --- | --- |
| I1 | `paymentFailure` at 50% | Checkout `PlaceOrder` errors | Fewer orders on the topic and in `accounting.order`; the cause is the payment call |
| I2 | `kafkaQueueProblems` | Consumer lag on the `fraud-detection` group | Checkout publishes 100 extra copies of each order; accounting skips them on its primary key |
| I3 | `productCatalogLockContention` | Slow `GetProduct` | A lock on `catalog.products`, two hops below the symptom |
| I4 | `paymentUnreachable` | Checkout errors, topic goes silent | Checkout's payment address, not the payment service itself |

## Running it

The demo runs with Docker Compose. The run that produces runtime evidence uses release 3.1.0, the full profile (which adds Kafka, accounting and fraud detection), and one collector add-on of this project's: file exporters for traces, logs and metrics, plus the collector's `servicegraph` connector, which turns traces into service-to-service edges.

```text
git clone https://github.com/open-telemetry/opentelemetry-demo.git && cd opentelemetry-demo
git checkout 3.1.0
DEMO_VERSION=3.1.0 OTEL_COLLECTOR_CONFIG_EXTRAS=/path/to/otelcol-capture.yml \
  docker compose -f compose.yaml -f compose.full.yaml -f capture.override.yaml up -d
```

The add-on and override are in [`fixtures/otel-demo-3.1.0/run/`](../fixtures/otel-demo-3.1.0/run/). After the load generator has run for ten minutes, score what was captured against the golden graph:

```text
python3 code/observed_edges.py <capture folder> fixtures/otel-demo-3.1.0/golden-graph.json
```

[`code/observed_edges.py`](../code/observed_edges.py) builds call edges from the trace walk (D7) and Kafka edges from the topic name (D8), then lists golden edges not seen and observed edges not in the golden graph: the first entries for the reconciliation queue. Its self-test passes; it has not yet seen a real capture. Note that the demo's collector, as shipped, mounts the host's Docker socket and root filesystem; the add-on replaces both with empty placeholders and drops the two receivers that use them.

**Status: not yet run.** The images were pulled in the build session on 27 November 2026, and starting the containers was refused by that session's permission check. The runtime evidence (observed edges, Kafka consumer lag, Postgres row counts, the effect of each flag) is the first task once a person allows Docker in the factory's sandbox. Until then, the golden graph rests on code, configuration and the upstream test suite.

## The hops it does not cover

The demo has no stream processor, warehouse, dbt project, feature store or model. A survey of open-source projects that cover those hops is running; this section and decision D2 in doc 08 are filled from its findings.

## Sources

All read at the source on 27 November 2026 from the demo's repository at tag 3.1.0 and its git history: `pb/demo.proto`, `src/checkout/main.go`, `src/accounting/Consumer.cs` and `Entities.cs`, `src/fraud-detection/.../main.kt`, `src/payment/charge.js`, `src/postgresql/init.sql`, `src/frontend-proxy/envoy.tmpl.yaml`, `src/otel-collector/otelcol-config.yml`, `src/flagd/demo.flagd.json`, `test/telemetry/services.py`, `compose.yaml`, `compose.full.yaml` and `.env`.
