"""The reference slice: the order flow of the OpenTelemetry Demo, release 3.1.0, as a golden graph.

Every edge cites the file and line in the demo's source that makes it true, plus a piece of text
that must appear on that line. Run it against a checkout of the demo to prove the citations still hold:

    git clone https://github.com/open-telemetry/opentelemetry-demo.git
    git -C opentelemetry-demo checkout 3.1.0
    python3 code/reference_slice.py --check opentelemetry-demo     # verify every citation
    python3 code/reference_slice.py --write fixtures/otel-demo-3.1.0 # write the fixture files

The demo is Apache-2.0 licensed: https://github.com/open-telemetry/opentelemetry-demo
"""
import json, os, sys

DEMO = {"repo": "https://github.com/open-telemetry/opentelemetry-demo", "tag": "3.1.0", "commit": "dedc017"}
PERMALINK = DEMO["repo"] + "/blob/" + DEMO["tag"] + "/"

# ---------------------------------------------------------------- names
SVC = lambda s: f"svc://otel-demo/{s}"
API = lambda s, call, side: f"api://otel-demo/{s}/{call}/{side}"        # a request or response message of one call
TOPIC = "kafka://otel-demo/orders"
PG = lambda t: f"postgres://astronomy-db/astronomy_db.{t}"
VALKEY = "valkey://valkey-cart/cart"

MAIN, CONSUMER, KT = "src/checkout/main.go", "src/accounting/Consumer.cs", "src/fraud-detection/src/main/kotlin/frauddetection/main.kt"
SERVICES_PY = "test/telemetry/services.py"

# ---------------------------------------------------------------- service and dataset edges
# (from, to, type, evidence path, line, text that must be on that line, upstream-asserted)
# "upstream-asserted" means the demo's own test suite asserts this edge in live traces (test/telemetry/services.py).
SERVICE_EDGES = [
    ("load-generator", "frontend-proxy", "CALLS", ".env", 106, "LOCUST_HOST=http://${FRONTEND_PROXY_ADDR}", False),
    ("frontend-proxy", "frontend", "CALLS", "src/frontend-proxy/envoy.tmpl.yaml", 96, "cluster: frontend", False),
    ("frontend", "ad", "CALLS", SERVICES_PY, 78, '("frontend", "ad")', True),
    ("frontend", "recommendation", "CALLS", SERVICES_PY, 79, '("frontend", "recommendation")', True),
    ("frontend", "product-catalog", "CALLS", SERVICES_PY, 80, '("frontend", "product-catalog")', True),
    ("frontend", "cart", "CALLS", SERVICES_PY, 81, '("frontend", "cart")', True),
    ("frontend", "checkout", "CALLS", SERVICES_PY, 82, '("frontend", "checkout")', True),
    ("frontend", "shipping", "CALLS", "src/frontend/gateways/http/Shipping.gateway.ts", 31, "/get-quote", False),
    ("checkout", "cart", "CALLS", MAIN, 528, "cartSvcClient.GetCart", True),
    ("checkout", "product-catalog", "CALLS", MAIN, 546, "productCatalogSvcClient.GetProduct", True),
    ("checkout", "currency", "CALLS", MAIN, 563, "currencySvcClient.Convert", True),
    ("checkout", "shipping", "CALLS", MAIN, 494, "/get-quote", True),
    ("checkout", "payment", "CALLS", MAIN, 361, "cs.chargeCard(ctx, total, req.CreditCard)", True),
    ("checkout", "email", "CALLS", MAIN, 603, "/send_order_confirmation", True),
    ("recommendation", "product-catalog", "CALLS", "src/recommendation/recommendation_server.py", 84, "ListProducts", True),
    ("shipping", "quote", "CALLS", SERVICES_PY, 95, '("shipping", "quote")', True),
    ("cart", "valkey-cart", "READS_WRITES", "src/cart/src/cartstore/ValkeyCartStore.cs", 16, "class ValkeyCartStore", False),
    ("product-catalog", "astronomy-db:catalog.products", "READS", "src/product-catalog/main.go", 234, "FROM catalog.products", False),
    ("checkout", "kafka:orders", "PRODUCES", MAIN, 671, "Topic: kafka.Topic", False),
    ("kafka:orders", "accounting", "CONSUMES", CONSUMER, 46, "_consumer.Subscribe(TopicName)", False),
    ("kafka:orders", "fraud-detection", "CONSUMES", KT, 55, "subscribe(listOf(topic))", False),
    ("accounting", "astronomy-db:accounting.*", "WRITES", CONSUMER, 130, "dbContext.SaveChanges()", False),
]

# ---------------------------------------------------------------- field edges
# (from element, to element, class, subtype, evidence path, line, text)
F = []
def fe(a, b, cls, sub, path, line, text):
    F.append((a, b, cls, sub, path, line, text))

PO_REQ = API("checkout", "PlaceOrder", "request")
ORDER = TOPIC
# 1. checkout assembles OrderResult and publishes it (Go)
for f in ["street_address", "city", "state", "country", "zip_code"]:
    fe(f"{PO_REQ}#address.{f}", f"{ORDER}#shipping_address.{f}", "DIRECT", "IDENTITY", MAIN, 387, "ShippingAddress:    req.Address")
fe(API("shipping", "POST /ship-order", "response") + "#tracking_id", f"{ORDER}#shipping_tracking_id", "DIRECT", "IDENTITY", MAIN, 385, "ShippingTrackingId: shippingTrackingID")
for f in ["units", "nanos"]:
    fe(API("shipping", "POST /get-quote", "response") + f"#cost_usd.{f}", f"{ORDER}#shipping_cost.{f}", "DIRECT", "TRANSFORMATION", MAIN, 386, "ShippingCost:       prep.shippingCostLocalized")
    fe(API("product-catalog", "GetProduct", "response") + f"#price_usd.{f}", f"{ORDER}#items[].cost.{f}", "DIRECT", "TRANSFORMATION", MAIN, 556, "Cost: price")
fe(f"{PO_REQ}#user_currency", f"{ORDER}#shipping_cost.currency_code", "DIRECT", "TRANSFORMATION", MAIN, 386, "ShippingCost:       prep.shippingCostLocalized")
fe(f"{PO_REQ}#user_currency", f"{ORDER}#items[].cost.currency_code", "DIRECT", "TRANSFORMATION", MAIN, 556, "Cost: price")
for f in ["product_id", "quantity"]:
    fe(API("cart", "GetCart", "response") + f"#items[].{f}", f"{ORDER}#items[].item.{f}", "DIRECT", "IDENTITY", MAIN, 555, "Item: item")

# 2. accounting writes the order to Postgres (C#, Entity Framework, snake_case columns)
fe(f"{ORDER}#order_id", PG('accounting."order"') + "#order_id", "DIRECT", "IDENTITY", CONSUMER, 98, "Id = order.OrderId")
for src, col, line, text in [
    ("items[].cost.currency_code", "item_cost_currency_code", 105, "ItemCostCurrencyCode = item.Cost.CurrencyCode"),
    ("items[].cost.units", "item_cost_units", 106, "ItemCostUnits = item.Cost.Units"),
    ("items[].cost.nanos", "item_cost_nanos", 107, "ItemCostNanos = item.Cost.Nanos"),
    ("items[].item.product_id", "product_id", 108, "ProductId = item.Item.ProductId"),
    ("items[].item.quantity", "quantity", 109, "Quantity = item.Item.Quantity"),
    ("order_id", "order_id", 110, "OrderId = order.OrderId"),
]:
    fe(f"{ORDER}#{src}", PG("accounting.orderitem") + f"#{col}", "DIRECT", "IDENTITY", CONSUMER, line, text)
for src, col, line, text in [
    ("shipping_tracking_id", "shipping_tracking_id", 118, "ShippingTrackingId = order.ShippingTrackingId"),
    ("shipping_cost.currency_code", "shipping_cost_currency_code", 119, "ShippingCostCurrencyCode = order.ShippingCost.CurrencyCode"),
    ("shipping_cost.units", "shipping_cost_units", 120, "ShippingCostUnits = order.ShippingCost.Units"),
    ("shipping_cost.nanos", "shipping_cost_nanos", 121, "ShippingCostNanos = order.ShippingCost.Nanos"),
    ("shipping_address.street_address", "street_address", 122, "StreetAddress = order.ShippingAddress.StreetAddress"),
    ("shipping_address.city", "city", 123, "City = order.ShippingAddress.City"),
    ("shipping_address.state", "state", 124, "State = order.ShippingAddress.State"),
    ("shipping_address.country", "country", 125, "Country = order.ShippingAddress.Country"),
    ("shipping_address.zip_code", "zip_code", 126, "ZipCode = order.ShippingAddress.ZipCode"),
    ("order_id", "order_id", 127, "OrderId = order.OrderId"),
]:
    fe(f"{ORDER}#{src}", PG("accounting.shipping") + f"#{col}", "DIRECT", "IDENTITY", CONSUMER, line, text)

# 3. checkout passes the card through to payment, which masks it (Go, then Node.js)
for f in ["credit_card_number", "credit_card_cvv", "credit_card_expiration_year", "credit_card_expiration_month"]:
    fe(f"{PO_REQ}#credit_card.{f}", API("payment", "Charge", "request") + f"#credit_card.{f}", "DIRECT", "IDENTITY", MAIN, 583, "CreditCard: paymentInfo")
fe(API("payment", "Charge", "request") + "#credit_card.credit_card_number", "logs://otel-demo/payment#lastFourDigits", "DIRECT", "TRANSFORMATION", "src/payment/charge.js", 60, "number.substr(-4)")

# What each consumer reads without writing a dataset
READS = [
    (f"{ORDER}#order_id", "fraud-detection", KT, 70, "OrderResult.parseFrom(record.value())"),
]

# Flows that must NOT exist. The oracle treats any path between these as a defect.
MUST_NOT_FLOW = [
    (f"{PO_REQ}#credit_card.*", TOPIC, "Card data never reaches the orders topic"),
    (f"{PO_REQ}#credit_card.*", PG("accounting.*"), "Card data never reaches the accounting tables"),
    (f"{PO_REQ}#email", TOPIC, "The customer email is sent to the email service, not published"),
]

# ---------------------------------------------------------------- real changes, from the demo's git history
CHANGES = [
    {"id": "C1", "commit": "133d089", "date": "2022-11-21", "title": "[protobuf] - encode zipcode as a string (#587)",
     "change": "Address.zip_code retyped from int32 to string in pb/demo.proto",
     "class": "BREAKING", "why": "int32 and string are not wire-compatible in protobuf; every reader of the field must regenerate",
     "elements": [f"{PO_REQ}#address.zip_code", f"{ORDER}#shipping_address.zip_code"],
     "readers_at_3_1_0": ["accounting.shipping#zip_code", "shipping (quote and ship-order)", "frontend", "load-generator"]},
    {"id": "C2", "commit": "8a28923", "date": "2023-02-11", "title": "rename proto package from hipstershop to oteldemo (#740)",
     "change": "Protobuf package renamed; every generated client and type name changes",
     "class": "BREAKING (build), wire-compatible", "why": "field numbers and types are unchanged, so bytes on the topic still parse; code that names the type does not compile",
     "elements": [TOPIC], "readers_at_3_1_0": ["every service"]},
    {"id": "C3", "commit": "42da57b", "date": "2025-06-25", "title": "store order to postgresql from accounting service (#2175)",
     "change": "accounting starts writing orders to three new Postgres tables",
     "class": "NON-BREAKING (new consumer and new datasets)", "why": "nothing existing changes; lineage must discover 17 new field edges and three tables",
     "elements": [PG("public.order"), PG("public.orderitem"), PG("public.shipping")], "readers_at_3_1_0": []},
    {"id": "C4", "commit": "5f83ad1", "date": "2025-11-07", "title": "Add a Product Review service with GenAI-powered summaries (#2663)",
     "change": "the three accounting tables move from the public schema to an accounting schema",
     "class": "BREAKING for readers of the old names", "why": "the dataset identity changes; old edges must close and new ones open, or history breaks",
     "elements": [PG("public.order"), PG('accounting."order"')], "readers_at_3_1_0": ["accounting"]},
    {"id": "C5", "commit": "66a5b73", "date": "2026-06-29", "title": "[cleanup] Remove product reviews from frontend (#3568)",
     "change": "the product review service and its proto messages are removed",
     "class": "RETIREMENT", "why": "a node and its edges must move to retired, not vanish",
     "elements": [SVC("product-reviews")], "readers_at_3_1_0": []},
    {"id": "C6", "commit": "c7b195f", "date": "2026-10-12", "title": "Rewrite the recommendation service in Spring Boot 4 (#3966)",
     "change": "recommendation rewritten from Python to Java; it still calls product-catalog ListProducts",
     "class": "NO LINEAGE CHANGE", "why": "the edge must survive while its static evidence moves to a new file, language and extractor; a rescan that drops it is a defect",
     "elements": [SVC("recommendation") + " -> " + SVC("product-catalog")], "readers_at_3_1_0": []},
]

# ---------------------------------------------------------------- real failure scenarios, from the demo's feature flags (3.1.0)
INCIDENTS = [
    {"id": "I1", "flag": "paymentFailure", "variant": "50%", "injected_at": SVC("payment"),
     "first_symptom": "checkout PlaceOrder errors", "downstream_effect": "fewer messages on orders, fewer rows in accounting.order, fewer records consumed by fraud-detection",
     "true_cause": "payment Charge failing", "lineage_walk": "accounting.order row rate drops -> orders topic rate drops -> checkout errors -> payment"},
    {"id": "I2", "flag": "kafkaQueueProblems", "variant": "on", "injected_at": SVC("checkout") + " and " + SVC("fraud-detection"),
     "first_symptom": "consumer lag on group fraud-detection", "downstream_effect": "checkout sends 100 extra copies of each order; accounting skips the duplicates on its primary key",
     "true_cause": "producer overload plus a 1 second consumer delay", "lineage_walk": "lag on orders/fraud-detection -> orders topic volume spike -> checkout producer"},
    {"id": "I3", "flag": "productCatalogLockContention", "variant": "on", "injected_at": PG("catalog.products"),
     "first_symptom": "slow GetProduct calls", "downstream_effect": "slow checkout and frontend pages; no data written wrongly",
     "true_cause": "an ACCESS EXCLUSIVE lock on catalog.products", "lineage_walk": "checkout latency -> product-catalog -> catalog.products"},
    {"id": "I4", "flag": "paymentUnreachable", "variant": "on", "injected_at": SVC("checkout") + " (calls a bad address)",
     "first_symptom": "checkout PlaceOrder errors", "downstream_effect": "no new orders anywhere downstream",
     "true_cause": "checkout's payment address, not the payment service", "lineage_walk": "orders topic silent -> checkout errors -> payment edge has no traffic"},
]

# What the upstream project says about tracing the Kafka hop (quoted from test/telemetry/services.py)
UPSTREAM_NOTE = (SERVICES_PY, 96, "async Kafka edges (checkout->accounting, checkout->fraud-detection)")


def node(name):
    if name.startswith("kafka:"):
        return TOPIC
    if name.startswith("astronomy-db:"):
        return PG(name.split(":", 1)[1])
    if name == "valkey-cart":
        return VALKEY
    return SVC(name)


def citations():
    for e in SERVICE_EDGES:
        yield e[3], e[4], e[5], f"{e[0]} -> {e[1]}"
    for e in F:
        yield e[4], e[5], e[6], f"{e[0]} -> {e[1]}"
    for e in READS:
        yield e[2], e[3], e[4], f"{e[0]} read by {e[1]}"
    yield UPSTREAM_NOTE[0], UPSTREAM_NOTE[1], UPSTREAM_NOTE[2], "upstream note on Kafka trace links"


def check(root):
    bad, n = [], 0
    for path, line, text, what in citations():
        n += 1
        try:
            lines = open(os.path.join(root, path), encoding="utf-8").read().splitlines()
        except OSError as err:
            bad.append(f"{what}: cannot read {path} ({err.strerror})")
            continue
        got = lines[line - 1] if 0 < line <= len(lines) else ""
        if text not in got:
            bad.append(f"{what}: {path}:{line} does not contain {text!r}; it reads {got.strip()[:90]!r}")
    print(f"checked {n} citations against {root}: {n - len(bad)} hold, {len(bad)} do not")
    for b in bad:
        print("  " + b)
    return not bad


def write(out):
    os.makedirs(out, exist_ok=True)
    ev = lambda p, l, t: {"path": p, "line": l, "text": t, "url": f"{PERMALINK}{p}#L{l}"}
    graph = {
        "source": DEMO,
        "naming": {"service": "svc://otel-demo/<service>", "message": "api://otel-demo/<service>/<call>/<request|response>#<field path>",
                   "topic": TOPIC + "#<field path>", "table": "postgres://astronomy-db/astronomy_db.<schema>.<table>#<column>",
                   "field paths": "dotted for nested fields, [] for repeated fields"},
        "service_edges": [{"from": node(a), "to": node(b), "type": t, "upstream_asserted": up, "evidence": ev(p, l, x)}
                          for a, b, t, p, l, x, up in SERVICE_EDGES],
        "field_edges": [{"from": a, "to": b, "type": "DERIVES", "class": c, "subtype": s, "evidence": ev(p, l, x)} for a, b, c, s, p, l, x in F],
        "field_reads": [{"element": a, "reader": SVC(r), "evidence": ev(p, l, x)} for a, r, p, l, x in READS],
        "must_not_flow": [{"from": a, "to": b, "why": w} for a, b, w in MUST_NOT_FLOW],
        "generated_without_source": [{"element": f"{ORDER}#order_id", "how": "uuid.NewUUID() in checkout", "evidence": ev(MAIN, 339, "uuid.NewUUID()")}],
    }
    json.dump(graph, open(os.path.join(out, "golden-graph.json"), "w"), indent=1)
    json.dump({"source": DEMO, "changes": CHANGES}, open(os.path.join(out, "change-replay.json"), "w"), indent=1)
    json.dump({"source": DEMO, "incidents": INCIDENTS}, open(os.path.join(out, "incident-scenarios.json"), "w"), indent=1)
    print(f"wrote {len(SERVICE_EDGES)} service edges, {len(F)} field edges, {len(CHANGES)} changes and {len(INCIDENTS)} incidents to {out}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        sys.exit(0 if check(sys.argv[2]) else 1)
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        write(sys.argv[2]); sys.exit(0)
    print(__doc__)
