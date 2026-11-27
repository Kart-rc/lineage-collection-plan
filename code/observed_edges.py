"""Turn a capture run of the reference slice into observed edges, and score them against the golden graph.

Implements decisions D7 and D8 in docs/08-build-decisions.md:
  D7  service-to-service CALLS edges come from traces: a span whose parent belongs to another service
  D8  Kafka hops join on the topic: PRODUCES from producer spans, CONSUMES from consumer spans, never from trace links
Database edges come from client spans that name a database system.

Input is the folder the capture add-on writes (fixtures/otel-demo-3.1.0/run/otelcol-capture.yml):
traces.jsonl, one OTLP/JSON export request per line, as written by the collector's file exporter.

    python3 code/observed_edges.py <capture folder> fixtures/otel-demo-3.1.0/golden-graph.json
    python3 code/observed_edges.py --selftest
"""
import json, os, re, sys
from collections import Counter, defaultdict

SERVER, CLIENT, PRODUCER, CONSUMER = 2, 3, 4, 5
KIND = {"SPAN_KIND_SERVER": SERVER, "SPAN_KIND_CLIENT": CLIENT, "SPAN_KIND_PRODUCER": PRODUCER, "SPAN_KIND_CONSUMER": CONSUMER}
TABLE = re.compile(r'\b(?:from|into|update|join)\s+("?[\w.]+"?(?:\."?\w+"?)?)', re.I)


def attrs(items):
    out = {}
    for a in items or []:
        v = a.get("value", {})
        out[a["key"]] = next(iter(v.values()), None) if v else None
    return out


def spans(folder):
    """Yield (trace id, span id, parent span id, service, kind, attributes, name) from traces.jsonl."""
    with open(os.path.join(folder, "traces.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            for rs in json.loads(line).get("resourceSpans", []):
                service = attrs(rs.get("resource", {}).get("attributes")).get("service.name", "unknown")
                for ss in rs.get("scopeSpans", []):
                    for s in ss.get("spans", []):
                        kind = s.get("kind", 0)
                        kind = KIND.get(kind, kind) if isinstance(kind, str) else kind
                        yield s["traceId"], s["spanId"], s.get("parentSpanId", ""), service, kind, attrs(s.get("attributes")), s.get("name", "")


def observe(span_rows):
    index, rows = {}, list(span_rows)
    for t, sid, parent, svc, kind, a, name in rows:
        index[(t, sid)] = (svc, kind)
    edges = Counter()
    for t, sid, parent, svc, kind, a, name in rows:
        p = index.get((t, parent))
        if p and p[0] != svc and kind in (SERVER, CONSUMER) and not a.get("messaging.system"):
            edges[(f"svc://otel-demo/{p[0]}", f"svc://otel-demo/{svc}", "CALLS")] += 1      # D7
        topic = a.get("messaging.destination.name") or a.get("messaging.destination")
        if topic and kind == PRODUCER:
            edges[(f"svc://otel-demo/{svc}", f"kafka://otel-demo/{topic}", "PRODUCES")] += 1  # D8
        if topic and kind == CONSUMER:
            edges[(f"kafka://otel-demo/{topic}", f"svc://otel-demo/{svc}", "CONSUMES")] += 1  # D8
        system = a.get("db.system.name") or a.get("db.system")
        if system and kind == CLIENT:
            text = a.get("db.query.text") or a.get("db.statement") or ""
            table = a.get("db.collection.name") or next((m.group(1).replace('"', "") for m in TABLE.finditer(text)), "*")
            verb = "WRITES" if re.match(r"\s*(insert|update|delete|merge)", text, re.I) else "READS"
            edges[(f"svc://otel-demo/{svc}", f"{system}:{table}", verb)] += 1
    return edges


def score(edges, golden_path):
    golden = json.load(open(golden_path, encoding="utf-8"))["service_edges"]
    gold = {(g["from"], g["to"]) for g in golden if g["type"] in ("CALLS", "PRODUCES", "CONSUMES")}
    asserted = {(g["from"], g["to"]) for g in golden if g["upstream_asserted"]}
    seen = {(a, b) for a, b, t in edges if t in ("CALLS", "PRODUCES", "CONSUMES")}
    hit = gold & seen
    print(f"observed {len(seen)} service and topic edges; golden has {len(gold)}")
    print(f"precision {len(hit) / max(len(seen), 1):.2f}   recall {len(hit) / max(len(gold), 1):.2f}"
          f"   recall on the {len(asserted)} upstream-asserted edges {len(asserted & seen) / max(len(asserted), 1):.2f}")
    for a, b in sorted(gold - seen):
        print(f"  golden, not observed: {a} -> {b}" + ("   (upstream asserts it)" if (a, b) in asserted else "   (static only: reconciliation queue)"))
    for a, b in sorted(seen - gold):
        print(f"  observed, not golden: {a} -> {b}   (runtime only: reconciliation queue)")
    for (a, b, t), n in sorted(edges.items()):
        if t in ("READS", "WRITES"):
            print(f"  database: {a} {t} {b}  x{n}")
    return hit, gold, seen


def selftest():
    """A tiny trace in the shape the collector's file exporter writes: frontend -> checkout, a publish, a consume, a query."""
    def span(t, sid, parent, kind, name, **a):
        return {"traceId": t, "spanId": sid, "parentSpanId": parent, "kind": kind, "name": name,
                "attributes": [{"key": k.replace("__", "."), "value": {"stringValue": v}} for k, v in a.items()]}
    def rs(service, *ss):
        return {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]}, "scopeSpans": [{"spans": list(ss)}]}
    lines = [
        {"resourceSpans": [rs("frontend", span("t1", "a", "", CLIENT, "oteldemo.CheckoutService/PlaceOrder"))]},
        {"resourceSpans": [rs("checkout", span("t1", "b", "a", SERVER, "oteldemo.CheckoutService/PlaceOrder"),
                                          span("t1", "c", "b", PRODUCER, "orders publish", messaging__system="kafka", messaging__destination__name="orders"))]},
        {"resourceSpans": [rs("accounting", span("t2", "d", "", CONSUMER, "orders process", messaging__system="kafka", messaging__destination__name="orders"))]},
        {"resourceSpans": [rs("product-catalog", span("t3", "e", "", CLIENT, "SELECT", db__system__name="postgresql",
                                                      db__query__text="SELECT p.id FROM catalog.products p WHERE p.id = $1"))]},
    ]
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".selftest-capture")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "traces.jsonl"), "w") as fh:
        fh.write("\n".join(json.dumps(x) for x in lines))
    got = observe(spans(folder))
    os.remove(os.path.join(folder, "traces.jsonl")); os.rmdir(folder)
    want = {("svc://otel-demo/frontend", "svc://otel-demo/checkout", "CALLS"),
            ("svc://otel-demo/checkout", "kafka://otel-demo/orders", "PRODUCES"),
            ("kafka://otel-demo/orders", "svc://otel-demo/accounting", "CONSUMES"),
            ("svc://otel-demo/product-catalog", "postgresql:catalog.products", "READS")}
    assert set(got) == want, set(got) ^ want
    print("selftest passed: one call, one publish, one consume across separate traces, one database read")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    elif len(sys.argv) == 3:
        score(observe(spans(sys.argv[1])), sys.argv[2])
    else:
        print(__doc__)
