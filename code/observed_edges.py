"""Turn a capture run of the reference slice into observed edges, and score them against the golden graph.

Implements decisions in docs/08-build-decisions.md:
  D7   service-to-service CALLS edges come from traces: a server or consumer span whose parent belongs to another service
  D8   Kafka hops join on the topic: PRODUCES from producer spans, CONSUMES from consumer spans, never from trace links
  D27  database access is attributed by the client span's service, never by the shared login; statements are parsed
       with SQLGlot's Postgres dialect, one statement at a time, down to columns
  D29  calls to flagd are configuration reads, scored apart from data flow
  D31  every name is resolved through the alias table (fixtures/otel-demo-3.1.0/aliases.json); IP addresses never are

Input is the folder the capture add-on writes (fixtures/otel-demo-3.1.0/run/otelcol-capture.yml):
traces.jsonl, one OTLP/JSON export request per line, as written by the collector's file exporter.

    python3 code/observed_edges.py <capture folder> fixtures/otel-demo-3.1.0/golden-graph.json [--aliases <aliases.json>] [--json <out.json>]
    python3 code/observed_edges.py --selftest
"""
import fnmatch, json, os, re, sys
from collections import Counter, defaultdict

try:
    import sqlglot
    from sqlglot import exp
except ImportError:          # the regex fallback still finds tables, not columns
    sqlglot = None

SERVER, CLIENT, PRODUCER, CONSUMER = 2, 3, 4, 5
KIND = {"SPAN_KIND_SERVER": SERVER, "SPAN_KIND_CLIENT": CLIENT, "SPAN_KIND_PRODUCER": PRODUCER, "SPAN_KIND_CONSUMER": CONSUMER}
TABLE = re.compile(r'\b(?:insert\s+into|update|delete\s+from|from|join)\s+((?:"?\w+"?\.)?"?\w+"?)', re.I)
REDIS_WRITES = {"SET", "HSET", "HMSET", "HDEL", "DEL", "EXPIRE", "LPUSH", "RPUSH", "SADD", "SREM", "ZADD", "INCR", "INCRBY"}
FLAGD = "svc://otel-demo/flagd"


# ---------------------------------------------------------------- reading the capture
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
            try:
                doc = json.loads(line)
            except ValueError:   # the exporter may be mid-write on the last line
                continue
            for rs in doc.get("resourceSpans", []):
                service = attrs(rs.get("resource", {}).get("attributes")).get("service.name", "unknown")
                for ss in rs.get("scopeSpans", []):
                    for s in ss.get("spans", []):
                        kind = s.get("kind", 0)
                        kind = KIND.get(kind, kind) if isinstance(kind, str) else kind
                        yield s["traceId"], s["spanId"], s.get("parentSpanId", ""), service, kind, attrs(s.get("attributes")), s.get("name", "")


# ---------------------------------------------------------------- resolving names (WP-15 prototype)
class Resolver:
    """Exact rows first, then pattern rows. Unknown names come back as 'unresolved:<kind>=<value>'."""

    def __init__(self, path=None):
        self.exact, self.patterns, self.misses = {}, [], Counter()
        rows = json.load(open(path, encoding="utf-8"))["aliases"] if path else [
            {"kind": "service.name", "value": "*", "urn": "svc://otel-demo/{value}", "pattern": True},
            {"kind": "messaging.destination.name", "value": "*", "urn": "kafka://otel-demo/{value}", "pattern": True},
            {"kind": "db.table", "value": "*", "urn": "table:{value}", "pattern": True},
            {"kind": "db.system+address", "value": "*", "urn": "store:{value}", "pattern": True}]
        for row in rows:
            (self.patterns.append(row) if row.get("pattern") else self.exact.__setitem__((row["kind"], row["value"]), row))

    def __call__(self, kind, value):
        row = self.exact.get((kind, value))
        if row is None:
            row = next((p for p in self.patterns if p["kind"] == kind and fnmatch.fnmatchcase(value, p["value"])), None)
        if row is None or not row.get("urn"):
            self.misses[(kind, value)] += 1
            return f"unresolved:{kind}={value}"
        return row["urn"].replace("{value}", value)


# ---------------------------------------------------------------- database statements
def sql_access(text):
    """[(verb, table, [columns])] for every statement in a possibly batched SQL text."""
    out = []
    if sqlglot:
        try:
            for st in sqlglot.parse(text, read="postgres"):
                if isinstance(st, exp.Insert):
                    schema = st.this if isinstance(st.this, exp.Schema) else None
                    t = schema.this if schema else st.this
                    out.append(("WRITES", f"{t.db}.{t.name}".strip("."), [c.name for c in schema.expressions] if schema else []))
                elif isinstance(st, exp.Update):
                    t = st.this
                    out.append(("WRITES", f"{t.db}.{t.name}".strip("."), [e.this.name for e in st.expressions if isinstance(e, exp.EQ)]))
                elif isinstance(st, exp.Delete):
                    t = st.find(exp.Table)
                    out.append(("WRITES", f"{t.db}.{t.name}".strip("."), []))
                elif st is not None and st.find(exp.Select):
                    tabs = {t.alias_or_name: f"{t.db}.{t.name}".strip(".") for t in st.find_all(exp.Table)}
                    for alias, table in tabs.items():
                        cols = sorted({c.name for c in st.find_all(exp.Column) if c.table == alias or (not c.table and len(tabs) == 1)})
                        out.append(("READS", table, cols))
            if out:
                return out
        except Exception:
            out = []
    for stmt in filter(str.strip, text.split(";")):
        m = TABLE.search(stmt)
        if m:
            verb = "WRITES" if re.match(r"\s*(insert|update|delete|merge)", stmt, re.I) else "READS"
            out.append((verb, m.group(1).replace('"', ""), []))
    return out


# ---------------------------------------------------------------- building edges
def observe(span_rows, resolve):
    """Counter of (from, to, type) and, for database edges, the columns seen per edge."""
    index, rows = {}, list(span_rows)
    for t, sid, parent, svc, kind, a, name in rows:
        index[(t, sid)] = (svc, kind)
    edges, columns = Counter(), defaultdict(Counter)
    for t, sid, parent, svc, kind, a, name in rows:
        me = resolve("service.name", svc)
        p = index.get((t, parent))
        if p and p[0] != svc and kind in (SERVER, CONSUMER) and not a.get("messaging.system"):
            edges[(resolve("service.name", p[0]), me, "CALLS")] += 1                                   # D7
        topic = a.get("messaging.destination.name") or a.get("messaging.destination")
        if topic and kind == PRODUCER:
            edges[(me, resolve("messaging.destination.name", topic), "PRODUCES")] += 1                  # D8
        if topic and kind == CONSUMER:
            edges[(resolve("messaging.destination.name", topic), me, "CONSUMES")] += 1                  # D8
        system = a.get("db.system.name") or a.get("db.system")
        if not system or kind != CLIENT:
            continue
        text = a.get("db.query.text") or a.get("db.statement") or ""
        if system == "redis":
            verb = "WRITES" if text.split(" ", 1)[0].upper() in REDIS_WRITES else "READS"
            edges[(me, resolve("db.system+address", f"redis@{a.get('server.address', '')}"), verb)] += 1
            continue
        if not text and not a.get("db.collection.name"):
            continue                                       # a connection span: no statement, no table, not an access
        for verb, table, cols in (sql_access(text) if text else [("READS", a["db.collection.name"], [])]):
            key = (me, resolve("db.table", table), verb)                                               # D27
            edges[key] += 1
            columns[key].update(cols)
    return edges, columns


# ---------------------------------------------------------------- scoring against the golden graph
def score(edges, columns, golden_path, resolver):
    g = json.load(open(golden_path, encoding="utf-8"))
    golden, flag_edges = g["service_edges"], g.get("flag_edges", [])
    report = {}

    # 1. data flow between services and topics
    gold = {(e["from"], e["to"]) for e in golden if e["type"] in ("CALLS", "PRODUCES", "CONSUMES")}
    asserted = {(e["from"], e["to"]) for e in golden if e["upstream_asserted"]}
    seen_all = {(a, b) for a, b, t in edges if t in ("CALLS", "PRODUCES", "CONSUMES")}
    seen = {(a, b) for a, b in seen_all if b != FLAGD}
    hit = gold & seen
    print(f"DATA FLOW   observed {len(seen)} service and topic edges; golden has {len(gold)}")
    print(f"  precision {len(hit) / max(len(seen), 1):.2f}   recall {len(hit) / max(len(gold), 1):.2f}"
          f"   recall on the {len(asserted)} upstream-asserted edges {len(asserted & seen) / max(len(asserted), 1):.2f}")
    for a, b in sorted(gold - seen):
        print(f"  golden, not observed: {a} -> {b}" + ("   (upstream asserts it)" if (a, b) in asserted else "   (static only: reconciliation queue)"))
    for a, b in sorted(seen - gold):
        print(f"  observed, not golden: {a} -> {b}   (runtime only: reconciliation queue)")
    report["data_flow"] = {"observed": sorted(map(list, seen)), "golden": len(gold), "hit": len(hit),
                           "missed": sorted(map(list, gold - seen)), "extra": sorted(map(list, seen - gold))}

    # 2. configuration reads: services calling flagd, against the services the code says read a flag
    readers = {e["to"] for e in flag_edges}
    calling = {a for a, b in seen_all if b == FLAGD}
    print(f"CONTROL     {len(calling)} services seen calling flagd; code says {len(readers)} read a flag")
    for s in sorted(readers - calling):
        print(f"  reads a flag, no flagd span: {s}   (flag-to-service edge comes from code only)")
    for s in sorted(calling - readers):
        print(f"  calls flagd, reads no flag in code: {s}")
    report["control"] = {"calling_flagd": sorted(calling), "flag_readers_in_code": sorted(readers), "code_only": sorted(readers - calling)}

    # 3. database access, table level then column level
    gdb = [(e["from"], e["to"], e["type"]) for e in golden if e["type"] in ("READS", "WRITES", "READS_WRITES")]
    def covered(a, b, t):
        return any(a == ga and fnmatch.fnmatchcase(b, gb) and (gt == t or gt == "READS_WRITES") for ga, gb, gt in gdb)
    obs_db = {k: n for k, n in edges.items() if k[2] in ("READS", "WRITES")}
    print(f"DATABASE    {len(obs_db)} access edges observed")
    for (a, b, t), n in sorted(obs_db.items()):
        print(f"  {'ok ' if covered(a, b, t) else 'NEW'} {a} {t} {b}  x{n}")
    for ga, gb, gt in gdb:
        if not any(a == ga and fnmatch.fnmatchcase(b, gb) for a, b, t in obs_db):
            print(f"  golden, not observed: {ga} {gt} {gb}")
    golden_cols = defaultdict(set)
    for e in g["field_edges"]:
        if e["to"].startswith("postgres://"):
            table, col = e["to"].split("#")
            golden_cols[table].add(col)
    report["database"] = []
    for (a, b, t), cols in sorted(columns.items()):
        want = golden_cols.get(b, set())
        got = set(cols)
        line = f"  columns {t.lower()} by {a.split('/')[-1]} on {b.split('.', 1)[-1]}: {len(got)}"
        if t == "WRITES" and want:
            line += f"; golden field edges land on {len(want)}; runtime confirms {len(got & want)}"
            if want - got:
                line += f"; not seen {sorted(want - got)}"
            if got - want:
                line += f"; not in golden {sorted(got - want)}"
        print(line)
        report["database"].append({"from": a, "to": b, "type": t, "columns": sorted(got), "golden_columns": sorted(want)})

    # 4. names that did not resolve
    print(f"RESOLVER    {len(resolver.misses)} distinct names did not resolve")
    for (k, v), n in resolver.misses.most_common():
        print(f"  {k} = {v}  x{n}")
    report["unresolved"] = [{"kind": k, "value": v, "count": n} for (k, v), n in resolver.misses.most_common()]
    return report


# ---------------------------------------------------------------- does every name in the capture resolve?
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$")


def records(folder, name, top, scope_key, items_key):
    """Yield (resource attributes, record) from logs.jsonl or metrics.jsonl."""
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            for r in doc.get(top, []):
                res = attrs(r.get("resource", {}).get("attributes"))
                for sc in r.get(scope_key, []):
                    for item in sc.get(items_key, []):
                        yield res, item


def coverage(folder, resolver):
    """Resolve every addressing name in traces, logs and metrics. IP addresses are counted, never resolved (rule no-ip)."""
    names = Counter()
    hosts = {row["value"].split(":")[0] for (k, v), row in resolver.exact.items() if k == "address"}
    for t, sid, parent, svc, kind, a, name in spans(folder):
        names[("service.name", svc)] += 1
        if a.get("rpc.service"):
            names[("rpc.service", a["rpc.service"])] += 1
        host = a.get("server.address") or a.get("net.peer.name")
        if host:
            port = a.get("server.port") or a.get("net.peer.port")
            if IPV4.match(str(host)):
                names[("ip", "*")] += 1
            elif kind in (CLIENT, PRODUCER):
                hp = str(host) if ":" in str(host) or not port else f"{host}:{port}"
                names[("address", hp if hp in {v for k, v in resolver.exact if k == "address"} or host not in hosts
                       else next(v for k, v in resolver.exact if k == "address" and v.startswith(f"{host}:")))] += 1
        if a.get("messaging.kafka.consumer.group"):
            names[("kafka.consumer_group", a["messaging.kafka.consumer.group"])] += 1
        if a.get("db.namespace"):
            names[("db.namespace", a["db.namespace"])] += 1
    for res, rec in records(folder, "logs.jsonl", "resourceLogs", "scopeLogs", "logRecords"):
        la = attrs(rec.get("attributes"))
        names[("service.name", res.get("service.name", "unknown"))] += 1
        if la.get("event.name") == "proxy.access":
            names[("envoy.cluster", la.get("upstream.cluster") or "-")] += 1
            names[("user_agent", la.get("user_agent.original") or "-")] += 1
    for res, m in records(folder, "metrics.jsonl", "resourceMetrics", "scopeMetrics", "metrics"):
        if res.get("postgresql.table.name") and m["name"] == "postgresql.operations":
            names[("postgresql.table.name", res["postgresql.table.name"])] += 1
        for dp in (m.get("sum") or m.get("gauge") or m.get("histogram") or {}).get("dataPoints", []):
            da = attrs(dp.get("attributes"))
            if m["name"].startswith("kafka.") and da.get("topic"):
                names[("kafkametrics.topic", da["topic"])] += 1
            if m["name"].startswith("kafka.consumer_group") and da.get("group"):
                names[("kafka.consumer_group", da["group"])] += 1
            if m["name"] == "traces_service_graph_request_total":
                for side in ("client", "server"):
                    v = da.get(side)
                    names[("servicegraph.node" if v in ("user", "unknown") else "service.name", v)] += 1
    by_kind, missing = defaultdict(lambda: [0, 0]), []
    for (kind, value), n in sorted(names.items()):
        if kind == "ip":
            continue
        exact = resolver.exact.get((kind, value))
        ok = exact is not None or not resolver(kind, value).startswith("unresolved:")
        by_kind[kind][0 if ok else 1] += 1
        if not ok:
            missing.append((kind, value, n))
    print(f"COVERAGE    {sum(v[0] for v in by_kind.values())} distinct names resolve or are declared, "
          f"{len(missing)} do not; {names[('ip', '*')]} references by IP address left unresolved by rule")
    for kind, (ok, bad) in sorted(by_kind.items()):
        print(f"  {kind:28} {ok} ok" + (f", {bad} missing" if bad else ""))
    for kind, value, n in missing:
        print(f"  missing {kind} = {value}  x{n}")
    return {"kinds": {k: {"ok": v[0], "missing": v[1]} for k, v in by_kind.items()}, "ip_references": names[("ip", "*")],
            "missing": [{"kind": k, "value": v, "count": n} for k, v, n in missing]}


# ---------------------------------------------------------------- self test
def selftest():
    """frontend -> checkout, a publish, a consume in another trace, a batched insert, a connection span, a flag read, a cache write."""
    def span(t, sid, parent, kind, name, **a):
        return {"traceId": t, "spanId": sid, "parentSpanId": parent, "kind": kind, "name": name,
                "attributes": [{"key": k.replace("__", "."), "value": {"stringValue": v}} for k, v in a.items()]}
    def rs(service, *ss):
        return {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]}, "scopeSpans": [{"spans": list(ss)}]}
    batch = 'INSERT INTO accounting."order" (order_id) VALUES (@p0);\nINSERT INTO accounting.shipping (order_id, zip_code) VALUES (@p1, @p2);'
    lines = [
        {"resourceSpans": [rs("frontend", span("t1", "a", "", CLIENT, "oteldemo.CheckoutService/PlaceOrder"))]},
        {"resourceSpans": [rs("checkout", span("t1", "b", "a", SERVER, "oteldemo.CheckoutService/PlaceOrder"),
                                          span("t1", "c", "b", PRODUCER, "orders publish", messaging__system="kafka", messaging__destination__name="orders"),
                                          span("t1", "f", "b", CLIENT, "flagd.evaluation.v2.Service/ResolveBoolean"))]},
        {"resourceSpans": [rs("flagd", span("t1", "g", "f", SERVER, "flagd.evaluation.v2.Service/ResolveBoolean"))]},
        {"resourceSpans": [rs("accounting", span("t2", "d", "", CONSUMER, "orders process", messaging__system="kafka", messaging__destination__name="orders"),
                                            span("t2", "h", "d", CLIENT, "astronomy_db", db__system__name="postgresql", db__query__text=batch),
                                            span("t2", "i", "d", CLIENT, "astronomy_db", db__system__name="postgresql"))]},
        {"resourceSpans": [rs("product-catalog", span("t3", "e", "", CLIENT, "SELECT", db__system__name="postgresql",
                                                      db__query__text="SELECT p.id, p.name FROM catalog.products p WHERE p.id = $1"))]},
        {"resourceSpans": [rs("cart", span("t4", "j", "", CLIENT, "HMSET", db__system="redis", db__statement="HMSET abc", server__address="valkey-cart"))]},
    ]
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".selftest-capture")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "traces.jsonl"), "w") as fh:
        fh.write("\n".join(json.dumps(x) for x in lines))
    try:
        got, cols = observe(spans(folder), Resolver())
    finally:
        os.remove(os.path.join(folder, "traces.jsonl")); os.rmdir(folder)
    want = {("svc://otel-demo/frontend", "svc://otel-demo/checkout", "CALLS"),
            ("svc://otel-demo/checkout", "svc://otel-demo/flagd", "CALLS"),
            ("svc://otel-demo/checkout", "kafka://otel-demo/orders", "PRODUCES"),
            ("kafka://otel-demo/orders", "svc://otel-demo/accounting", "CONSUMES"),
            ("svc://otel-demo/accounting", "table:accounting.order", "WRITES"),
            ("svc://otel-demo/accounting", "table:accounting.shipping", "WRITES"),
            ("svc://otel-demo/product-catalog", "table:catalog.products", "READS"),
            ("svc://otel-demo/cart", "store:redis@valkey-cart", "WRITES")}
    assert set(got) == want, set(got) ^ want
    if sqlglot:
        assert set(cols[("svc://otel-demo/accounting", "table:accounting.shipping", "WRITES")]) == {"order_id", "zip_code"}
        assert set(cols[("svc://otel-demo/product-catalog", "table:catalog.products", "READS")]) == {"id", "name"}
    print("selftest passed: call, flag read, publish, consume in another trace, batched insert split by table"
          + (" with columns" if sqlglot else "") + ", connection span skipped, cache write")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--selftest"]:
        selftest()
    elif len(args) >= 2:
        opts = dict(zip(args[2::2], args[3::2]))
        resolver = Resolver(opts.get("--aliases"))
        edges, columns = observe(spans(args[0]), resolver)
        report = score(edges, columns, args[1], resolver)
        if "--aliases" in opts:
            report["coverage"] = coverage(args[0], resolver)
        if "--json" in opts:
            report["edges"] = [{"from": a, "to": b, "type": t, "count": n} for (a, b, t), n in sorted(edges.items())]
            json.dump(report, open(opts["--json"], "w"), indent=1)
            print(f"wrote {opts['--json']}")
    else:
        print(__doc__)
