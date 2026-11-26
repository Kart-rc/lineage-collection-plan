"""Element-level lineage on the card-authorization slice, end to end.

Runs the four objectives of docs/06 on toy versions of the slice's repositories, in the order one night plays out:
  O1 baseline     extract field-to-field edges per unit, score them against a golden graph
  O3 impact       classify a pull request's change and list who reads the field, before merge
  O2 incremental  re-read only the units a change touches, replace their evidence, emit a diff
  O4 incident     walk upstream from a failing check, rank the changes, order the fix

Needs SQLGlot:  pip install sqlglot
Run:            python3 code/element_lineage_demo.py
Check:          python3 code/element_lineage_demo.py --check     (asserts the expected results)
Names, times and counts are the plan's illustrative slice, not measurements.
"""
import hashlib, json, sys
from collections import defaultdict

try:
    import sqlglot
    from sqlglot import exp
    from sqlglot.optimizer.qualify import qualify
    from sqlglot.optimizer.scope import build_scope
except ImportError:
    sys.exit("This demo parses SQL with SQLGlot. Install it first:  pip install sqlglot")

EXTRACTOR_VERSION = "demo-1"
MODEL, SERVICE = "mlreg://fraud-score/12", "svc://prod/fraud-svc"
URN = {  # the identity resolver in miniature: the name a unit uses -> one URN
    "svc.payments_svc": "svc://prod/payments-svc",
    "kafka.auth_events_v1": "kafka://msk-prod/auth.events.v1",
    "kafka.auth_enrich_v1": "kafka://msk-prod/auth.enrich.v1",
    "raw.card_auth": "warehouse://prod/raw.card_auth",
    "analytics.fct_card_auth": "warehouse://prod/analytics.fct_card_auth",
    "feast.mcc_decline_7d": "feast://fraud/mcc_decline_7d",
    "bi.approval_rate": "bi://prod/approval-rate",
}
OWNER = {  # dataset URN -> (team, tier), from the catalog overlay
    URN["kafka.auth_events_v1"]: ("payments", 1), URN["kafka.auth_enrich_v1"]: ("streaming-platform", 1),
    URN["raw.card_auth"]: ("data-platform", 2), URN["analytics.fct_card_auth"]: ("analytics-eng", 1),
    URN["bi.approval_rate"]: ("payments-analytics", 2), URN["feast.mcc_decline_7d"]: ("fraud-ml", 1),
    MODEL: ("fraud-ml", 1), SERVICE: ("fraud-ml", 1),
}
AVRO_V7 = ["auth_id", "card_bin", "merchant_category_code", "amount", "status", "auth_ts"]
AVRO_V8 = ["auth_id", "card_bin", "mcc", "amount", "status", "auth_ts"]          # PR #482


def units(avro_fields, dbt_sql=None):
    """The slice's repositories as extraction units, listed in dependency order."""
    return [
        {"id": "payments-svc/auth-event.avsc", "kind": "schema", "writes": "kafka.auth_events_v1", "fields": avro_fields},
        {"id": "txn-enrichment/enrich.sql", "kind": "sql", "reads": ["kafka.auth_events_v1"], "writes": "kafka.auth_enrich_v1",
         "sql": "SELECT auth_id, card_bin, merchant_category_code AS mcc, amount, status, auth_ts FROM kafka.auth_events_v1"},
        {"id": "connect/raw-card-auth-sink.json", "kind": "sink", "reads": ["kafka.auth_enrich_v1"], "writes": "raw.card_auth"},
        {"id": "analytics-dbt/fct_card_auth.sql", "kind": "sql", "reads": ["raw.card_auth"], "writes": "analytics.fct_card_auth",
         "sql": dbt_sql or """SELECT auth_id, card_bin, mcc, amount, CAST(auth_ts AS DATE) AS auth_date,
                              CASE WHEN status = 'DECLINED' THEN 1 ELSE 0 END AS declined
                       FROM raw.card_auth WHERE status IN ('AUTH', 'DECLINED')"""},
        {"id": "fraud-features/mcc_decline_7d.sql", "kind": "sql", "reads": ["analytics.fct_card_auth"], "writes": "feast.mcc_decline_7d",
         "sql": """SELECT mcc, SUM(declined) AS decline_count_7d, COUNT(*) AS auth_count_7d
                   FROM analytics.fct_card_auth WHERE auth_date >= CURRENT_DATE - 7 GROUP BY mcc"""},
        {"id": "bi/approval-rate.sql", "kind": "sql", "reads": ["analytics.fct_card_auth"], "writes": "bi.approval_rate",
         "sql": "SELECT mcc, 1 - AVG(declined) AS approval_rate FROM analytics.fct_card_auth GROUP BY mcc"},
        {"id": "fraud-model/training.json", "kind": "declared", "reads": ["feast.mcc_decline_7d"],
         "edges": [(URN["feast.mcc_decline_7d"] + "#decline_count_7d", MODEL, "FEEDS"),
                   (URN["feast.mcc_decline_7d"] + "#auth_count_7d", MODEL, "FEEDS")]},
        {"id": "fraud-svc/serving.json", "kind": "declared", "reads": [], "edges": [(MODEL, SERVICE, "SERVES")]},
    ]


# Hand-written with the owners, independent of the extractors. One line per hop:
#   source > target : field pairs.  a=b renames, ~T transformation, ~A aggregation, ~C conditional,
#   =*~F filter and =*~G group by point at the whole target dataset (an indirect dependency).
GOLDEN = """
svc.payments_svc > kafka.auth_events_v1 : request.merchant.category=merchant_category_code request.card.bin=card_bin
kafka.auth_events_v1 > kafka.auth_enrich_v1 : auth_id card_bin merchant_category_code=mcc amount status auth_ts
kafka.auth_enrich_v1 > raw.card_auth : auth_id card_bin mcc amount status auth_ts
raw.card_auth > analytics.fct_card_auth : auth_id card_bin mcc amount auth_ts=auth_date~T status=declined~C status=*~F
analytics.fct_card_auth > feast.mcc_decline_7d : mcc declined=decline_count_7d~A mcc=*~G auth_date=*~F
analytics.fct_card_auth > bi.approval_rate : mcc declined=approval_rate~A mcc=*~G
"""
KINDS = {"I": ("DIRECT", "IDENTITY"), "T": ("DIRECT", "TRANSFORMATION"), "A": ("DIRECT", "AGGREGATION"),
         "C": ("INDIRECT", "CONDITIONAL"), "F": ("INDIRECT", "FILTER"), "G": ("INDIRECT", "GROUP_BY")}


def golden_edges():
    out = {}
    for line in GOLDEN.strip().splitlines():
        hop, pairs = line.split(" : ")
        src, dst = (URN[x.strip()] for x in hop.split(" > "))
        for pair in pairs.split():
            pair, kind = (pair.split("~") + ["I"])[:2]
            a, b = (pair.split("=") + [pair])[:2]
            out[(src + "#" + a, dst if b == "*" else dst + "#" + b)] = KINDS[kind] + (src + " > " + dst,)
    return out


def h(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:12]


def content_hash(unit):
    """Hash of the unit's normalized source, so a reformat is not a change."""
    if unit["kind"] == "sql":
        return h(sqlglot.parse_one(unit["sql"]).sql(normalize=True))
    return h(json.dumps({k: v for k, v in unit.items() if k not in ("id", "sql")}, sort_keys=True, default=list))


def input_hash(unit, schemas):
    """Hash of the schemas the unit reads. Catches SELECT * and renamed inputs when the unit's own text is unchanged."""
    return h(json.dumps({t: schemas.get(t) for t in unit.get("reads", [])}, sort_keys=True))


def extract(unit, schemas):
    """Return (edges, output fields, gaps). An edge is (from, to, type, class, subtype, expression hash)."""
    edges, gaps = [], []
    if unit["kind"] == "schema":
        return edges, list(unit["fields"]), gaps
    if unit["kind"] == "declared":
        return [(a, b, typ, "DIRECT", "IDENTITY", h(a + b)) for a, b, typ in unit["edges"]], None, gaps
    src, dst = (URN[unit["reads"][0]] if unit["reads"] else None), URN[unit["writes"]]
    if unit["kind"] == "sink":                                   # a sink copies every field of its topic by name
        fields = list(schemas[unit["reads"][0]])
        return [(f"{src}#{f}", f"{dst}#{f}", "DERIVES", "DIRECT", "IDENTITY", h(f)) for f in fields], fields, gaps
    schema = defaultdict(dict)
    for name in unit["reads"]:
        db, table = name.split(".")
        schema[db][table] = {f: "unknown" for f in schemas[name]}
    tree = qualify(sqlglot.parse_one(unit["sql"]), schema=dict(schema), validate_qualify_columns=False)
    tables = {alias: f"{t.db}.{t.name}" for alias, t in build_scope(tree).sources.items()}
    sources = {alias: URN[name] for alias, name in tables.items()}

    def canon(node):
        """The expression as text with every column qualified by its real table, so a reformat or a new alias is not a change."""
        def real_table(n):
            return exp.column(n.name, table=tables[n.table]) if isinstance(n, exp.Column) and n.table in tables else n
        return node.copy().transform(real_table).sql(normalize=True)

    fields = []
    for proj in tree.expressions:
        out = proj.alias_or_name
        inner = proj.this if isinstance(proj, exp.Alias) else proj
        fields.append(out)
        for col in proj.find_all(exp.Column):
            if col.table not in sources:                         # the input field does not exist: say so, do not guess
                gaps.append((f"{dst}#{out}", f"unresolved input column {col.name}"))
                continue
            cond = col.find_ancestor(exp.If)
            if cond is not None and any(col is c for c in cond.this.find_all(exp.Column)):
                cls, sub = "INDIRECT", "CONDITIONAL"
            elif isinstance(inner, exp.Column):
                cls, sub = "DIRECT", "IDENTITY"
            else:
                cls, sub = "DIRECT", "AGGREGATION" if inner.find(exp.AggFunc) else "TRANSFORMATION"
            edges.append((f"{sources[col.table]}#{col.name}", f"{dst}#{out}", "DERIVES", cls, sub, h(canon(inner))))
    for clause, sub in (("where", "FILTER"), ("group", "GROUP_BY")):   # indirect: stored once, against the dataset
        node = tree.args.get(clause)
        for col in (node.find_all(exp.Column) if node else []):
            if col.table in sources:
                edges.append((f"{sources[col.table]}#{col.name}", dst, "DERIVES", "INDIRECT", sub, h(canon(node))))
    return sorted(set(edges)), fields, gaps


class Graph:
    """Edge versions with valid-from and valid-to. Static evidence is owned by the unit that produced it.

    A version is one (edge key, attributes) pair. If two units describe the same edge differently, both versions
    stay live side by side, each with its own support. That is a disagreement for the reconciler, never an overwrite.
    """

    def __init__(self):
        self.live, self.closed, self.changes = {}, [], []

    def _versions(self, keys):
        return {k: {vid[1] for vid in self.live if vid[0] == k} for k in keys}

    def replace_unit(self, unit_id, edges, t):
        new = {((e[0], e[1], e[2]), e[3:]) for e in edges}
        dropped = [vid for vid, edge in self.live.items() if unit_id in edge["support"] and vid not in new]
        touched = {vid[0] for vid in dropped} | {vid[0] for vid in new if vid not in self.live}
        before = self._versions(touched)
        for vid in dropped:
            self.live[vid]["support"].discard(unit_id)
            if not self.live[vid]["support"]:                    # nothing supports it any more: close, never delete
                self.closed.append({**self.live.pop(vid), "valid_to": t})
        for vid in new:
            if vid in self.live:
                self.live[vid]["support"].add(unit_id)
            else:
                self.live[vid] = {"key": vid[0], "attrs": vid[1], "support": {unit_id}, "valid_from": t, "valid_to": None}
        after = self._versions(touched)
        for key in sorted(touched):
            if before[key] != after[key]:
                what = "added" if not before[key] else "removed" if not after[key] else "changed"
                self.changes.append((t, what, key, unit_id))

    def as_of(self, t):
        return [e for e in list(self.live.values()) + self.closed
                if e["valid_from"] <= t and (e["valid_to"] is None or e["valid_to"] > t)]

    def window(self, t0, t1):
        """Every edge valid at any moment between t0 and t1, including ones that closed in between."""
        return [e for e in list(self.live.values()) + self.closed
                if e["valid_from"] <= t1 and (e["valid_to"] is None or e["valid_to"] > t0)]

    def digest(self):
        rows = sorted((e["key"], e["attrs"], e["valid_from"], e["valid_to"]) for e in list(self.live.values()) + self.closed)
        return h(json.dumps(rows))


def refresh(graph, unit_list, state, t):
    """Re-read only the units whose content, input schemas or extractor version changed."""
    schemas, reread, skipped = {}, [], []
    for unit in unit_list:
        key = (content_hash(unit), input_hash(unit, schemas), EXTRACTOR_VERSION)
        if state.get(unit["id"], {}).get("key") != key:
            edges, fields, gaps = extract(unit, schemas)
            graph.replace_unit(unit["id"], edges, t)
            state[unit["id"]] = {"key": key, "fields": fields, "gaps": gaps}
            reread.append(unit["id"])
        else:
            skipped.append(unit["id"])
        if unit.get("writes"):
            schemas[unit["writes"]] = state[unit["id"]]["fields"]
    return reread, skipped


def score(graph, t):
    """Precision and recall of element edges against the golden graph, with what was missed."""
    gold = golden_edges()
    found = {(e["key"][0], e["key"][1]): e["attrs"][:2] for e in graph.as_of(t) if e["key"][2] == "DERIVES"}
    hits = [k for k in found if k in gold and gold[k][:2] == found[k]]
    missed = sorted(k for k in gold if k not in hits)
    return len(hits) / len(found), len(hits) / len(gold), missed


def dataset(urn):
    return urn.split("#")[0]


def short(urn):
    return "fraud-score-v12" if urn == MODEL else urn.split("/")[-1]


def downstream(graph, starts, t):
    """Walk the data flow. Direct edges carry value impact; an indirect edge turns everything after it into row-set impact."""
    out = defaultdict(list)
    for e in graph.as_of(t):
        out[e["key"][0]].append(e)
    fields = defaultdict(set)
    for e in graph.as_of(t):
        for end in e["key"][:2]:
            if "#" in end:
                fields[dataset(end)].add(end)
    reached, queue, seen = {}, [], set()
    for start in starts:                                         # a dataset-level change touches every field of that dataset
        whole = "#" not in start
        for node in [start] + (sorted(fields[start]) if whole else []):
            if node not in seen:
                seen.add(node)
                queue.append((node, 0, "row set" if whole else "value"))
    while queue:
        node, hops, kind = queue.pop(0)
        for e in out.get(node, []):
            to = e["key"][1]
            k = kind if e["attrs"][0] == "DIRECT" else "row set"
            hop = hops + (dataset(to) != dataset(node))
            best = reached.get(dataset(to))
            if best is None or (hop, k != "value") < (best[0], best[1] != "value"):
                reached[dataset(to)] = (hop, k)
            for nxt in [to] + (sorted(fields[to]) if "#" not in to else []):   # a dataset-level hit touches all its fields
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, hop, k))
    return reached


def pr_impact(graph, state, base, head, t):
    """Before merge: diff the changed units by element, classify, then walk the base graph downstream."""
    changes = []
    for b, hd in zip(base, head):
        if content_hash(b) == content_hash(hd):
            continue
        if b["kind"] == "schema":
            target = URN[b["writes"]]
            gone = [f for f in b["fields"] if f not in hd["fields"]]
            new = [f for f in hd["fields"] if f not in b["fields"]]
            for f in gone:
                twin = [n for n in new if hd["fields"].index(n) == b["fields"].index(f)]   # same slot: a probable rename
                changes.append({"element": f"{target}#{f}", "kind": "renamed to " + twin[0] if twin else "removed", "class": "BREAKING"})
            changes += [{"element": f"{target}#{f}", "kind": "added", "class": "NON-BREAKING"}
                        for f in new if not any(c["kind"].endswith(f) for c in changes)]
        else:                                                    # extract twice, then compare what feeds each output element
            schemas = {u["writes"]: state[u["id"]]["fields"] for u in base if u.get("writes") and u["id"] in state}
            target, feeds = URN[b["writes"]] if b.get("writes") else None, []
            for unit in (b, hd):
                into = defaultdict(set)
                for e in extract(unit, schemas)[0]:
                    into[e[1]].add((e[0],) + e[3:])
                feeds.append(into)
            old, new = feeds
            for el in sorted(set(old) | set(new)):
                if old.get(el) == new.get(el):
                    continue                                     # same inputs, same normalized expression: not a change
                if el == target:
                    kind, cls = "row set changed", "POTENTIALLY BREAKING"          # a filter, join or grouping moved
                elif el not in new:
                    kind, cls = "removed", "BREAKING"
                elif el not in old:
                    kind, cls = "added", "NON-BREAKING"
                else:
                    kind, cls = "logic changed", "POTENTIALLY BREAKING"
                changes.append({"element": el, "kind": kind, "class": cls})
    breaking = [c["element"] for c in changes if c["class"] != "NON-BREAKING"]
    return changes, downstream(graph, breaking, t)


DBT_VARIANTS = {  # other pull requests against the same model, to show how each is classified
    "a changed expression": """SELECT auth_id, card_bin, mcc, amount, CAST(auth_ts AS DATE) AS auth_date,
           CASE WHEN status IN ('DECLINED', 'REVERSED') THEN 1 ELSE 0 END AS declined
           FROM raw.card_auth WHERE status IN ('AUTH', 'DECLINED')""",
    "a changed filter": """SELECT auth_id, card_bin, mcc, amount, CAST(auth_ts AS DATE) AS auth_date,
           CASE WHEN status = 'DECLINED' THEN 1 ELSE 0 END AS declined
           FROM raw.card_auth WHERE status = 'DECLINED'""",
    "a table alias and a reformat": """select c.auth_id, c.card_bin, c.mcc, c.amount, cast(c.auth_ts as date) as auth_date,
           case when c.status = 'DECLINED' then 1 else 0 end as declined
           from raw.card_auth as c where c.status in ('AUTH', 'DECLINED')""",
}

EVENTS = [  # (time, kind, owner of the change, detail, elements touched, class) across the estate that night
    ("01:55", "deploy", "txn-enrichment", "config only", set(), "config"),
    ("02:03", "deploy", "payments-svc", "4f3c2a1, PR #482", {URN["kafka.auth_events_v1"] + "#merchant_category_code"}, "breaking"),
    ("02:05", "schema", "payments-svc", "auth.events.v1 v8 registered, field removed", {URN["kafka.auth_events_v1"] + "#merchant_category_code"}, "breaking"),
    ("02:10", "deploy", "case-mgmt", "routine release", set(), "config"),
    ("02:20", "schema", "merchant-svc", "merchant.ref.v3 registered, field added", set(), "non-breaking"),
    ("02:30", "deploy", "mobile-bff", "routine release", set(), "config"),
]
PRODUCER = {URN["kafka.auth_events_v1"]: "payments-svc", URN["kafka.auth_enrich_v1"]: "txn-enrichment",
            URN["raw.card_auth"]: "raw-card-auth-sink"}
CHECKS = {URN["raw.card_auth"] + "#mcc": "FAIL null 41%", URN["kafka.auth_enrich_v1"] + "#mcc": "FAIL null 43%"}
BAD_DATA_ARRIVES = {URN["kafka.auth_enrich_v1"]: "02:05", URN["raw.card_auth"]: "02:06",          # streaming hops
                    URN["analytics.fct_card_auth"]: "03:00", URN["bi.approval_rate"]: "03:00",   # next dbt run
                    URN["feast.mcc_decline_7d"]: "04:00", MODEL: "04:00", SERVICE: "04:00"}       # next feature job
FIX = {URN["kafka.auth_events_v1"]: "payments-svc: re-add merchant_category_code as an alias",
       URN["kafka.auth_enrich_v1"]: "txn-enrichment: replay auth.events.v1 from the 02:05 offsets",
       URN["raw.card_auth"]: "raw.card_auth: rewrite the partitions for hours 02 and 03",
       URN["analytics.fct_card_auth"]: "resume dbt and rerun fct_card_auth for the day",
       URN["bi.approval_rate"]: "notify the Approval rate dashboard owners",
       URN["feast.mcc_decline_7d"]: "re-materialize mcc_decline_7d",
       MODEL: "fraud-score-v12: no action if the feature is fixed before 04:00", SERVICE: "fraud-svc: no action"}


def rca(graph, failing, t_last_pass, t_fail):
    """Walk upstream over the incident window, find the first failing element, rank the changes on that path."""
    back = defaultdict(list)
    for e in graph.window(t_last_pass, t_fail):
        if e["attrs"][0] == "DIRECT":
            back[e["key"][1]].append(e)
    path, node = [failing], failing
    while back.get(node):                                        # the slice has one direct parent per field
        node = back[node][0]["key"][0]
        path.append(node)
    first_failing = [n for n in path if n in CHECKS][-1]
    removed = [key[0] for t, what, key, _ in graph.changes if what == "removed" and t_last_pass < t <= t_fail and key[0] in path]
    on_path = {PRODUCER.get(dataset(n)) for n in path}
    ranked = []
    for time, kind, who, detail, touches, cls in EVENTS:
        if not t_last_pass < time <= t_fail:
            continue
        terms = {"on the path": 3 * (who in on_path), "touches a path element": 3 * bool(touches & set(path)),
                 "breaking class": 2 * (cls == "breaking"), "schema change": 1 * (kind == "schema" and who in on_path)}
        ranked.append((sum(terms.values()), time, kind, who, detail, {k: v for k, v in terms.items() if v}))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return path, first_failing, removed, ranked


def run(check=False):
    say = print
    graph, state = Graph(), {}
    base, head = units(AVRO_V7), units(AVRO_V8)

    say("O1 BASELINE at 00:00")
    reread, _ = refresh(graph, base, state, "00:00")
    precision, recall, missed = score(graph, "00:00")
    say(f"   units read: {len(reread)}   element edges: {sum(1 for e in graph.as_of('00:00') if e['key'][2] == 'DERIVES')}")
    say(f"   against the golden graph: precision {precision:.2f}, recall {recall:.2f}")
    for a, b in missed:
        say(f"   missed: {a} -> {b}   (no service-code extractor in this demo: WP-23)")
    tidy = units(AVRO_V7, dbt_sql="select auth_id,card_bin,mcc,amount,cast(auth_ts as date) as auth_date,\n case when status='DECLINED' then 1 else 0 end as declined from raw.card_auth where status in ('AUTH','DECLINED')")
    same = content_hash(tidy[3]) == content_hash(base[3])
    say(f"   a reformatted fct_card_auth.sql hashes the same: {same}")

    say("\nO3 CHANGE IMPACT for PR #482 at 01:30, before merge")
    changes, reached = pr_impact(graph, state, base, head, "01:30")
    for c in changes:
        say(f"   {c['class']:<12} {c['element']}  {c['kind']}")
    rows = sorted((hop, urn, kind) + OWNER[urn] for urn, (hop, kind) in reached.items())
    for hop, urn, kind, team, tier in rows:
        say(f"   hop {hop}  {urn:<48} {team:<19} tier {tier}  {kind} impact")
    teams, tier1 = {r[3] for r in rows}, sum(1 for r in rows if r[4] == 1)
    say(f"   downstream: {len(rows)} assets, {len(teams)} teams, {tier1} tier 1.  Registry BACKWARD check would pass.")
    say("   three other edits to fct_card_auth.sql, classified the same way:")
    variants = {}
    for label, sql in DBT_VARIANTS.items():
        v_changes, v_reached = pr_impact(graph, state, base, units(AVRO_V7, dbt_sql=sql), "01:30")
        variants[label] = (v_changes, v_reached)
        what = "; ".join(f"{short(c['element'])} {c['kind']}" for c in v_changes) or "no element changed: non-breaking"
        kinds = sorted({k for _, k in v_reached.values()})
        say(f"     {label:<30} {what}" + (f"  ->  {len(v_reached)} assets, {' and '.join(kinds)} impact" if v_reached else ""))

    say("\nO2 INCREMENTAL: the change ships as a hotfix that skips the gate; schema v8 is registered at 02:05")
    before = len(graph.changes)
    reread, skipped = refresh(graph, head, state, "02:05")
    say(f"   re-read {len(reread)} units: {', '.join(reread)}")
    say(f"   skipped {len(skipped)} units whose three hashes did not change")
    diff = graph.changes[before:]
    for t, what, key, unit in diff:
        say(f"   {t} {what:<7} {key[0]} -> {key[1]}")
    gaps = [g for s in state.values() for g in s["gaps"]]
    for element, why in gaps:
        say(f"   gap: {element}  {why}")
    old = (URN["kafka.auth_events_v1"] + "#merchant_category_code", URN["kafka.auth_enrich_v1"] + "#mcc", "DERIVES")
    was, now = (any(e["key"] == old for e in graph.as_of(t)) for t in ("02:00", "02:10"))
    say(f"   graph as of 02:00 has the old edge: {was}.  As of 02:10: {now}.")
    replay, replay_state = Graph(), {}
    refresh(replay, base, replay_state, "00:00"); refresh(replay, head, replay_state, "02:05")
    say(f"   rebuilt from the same evidence, same graph hash: {replay.digest() == graph.digest()}")

    say("\nO4 DETECT AND RESOLVE: raw.card_auth#mcc null_rate 41% (threshold 1%) at 02:42, last pass 01:40")
    failing = URN["raw.card_auth"] + "#mcc"
    path, first_failing, removed, ranked = rca(graph, failing, "01:40", "02:42")
    say("   upstream walk over the incident window:")
    for n in path:
        say(f"     {n:<55} {CHECKS.get(n, 'removed at 02:05' if n in removed else 'no check')}")
    say(f"   first failing element: {first_failing}")
    in_window = [e for e in EVENTS if "01:40" < e[0] <= "02:42"]
    on_path = [r for r in ranked if "on the path" in r[5]]
    say(f"   changes in the window: {len(in_window)} across the estate, {len(on_path)} on the lineage path. Ranked:")
    for n, (total, time, kind, who, detail, terms) in enumerate(ranked[:3], 1):
        say(f"     {n}. {time} {kind:<6} {who:<15} {detail}   score {total}: {', '.join(terms)}")
    blast = downstream(graph, [first_failing], "02:42")
    blast[dataset(first_failing)] = (0, "value")
    affected = sorted(u for u in blast if BAD_DATA_ARRIVES[u] <= "02:42")
    not_yet = sorted((BAD_DATA_ARRIVES[u], u) for u in blast if BAD_DATA_ARRIVES[u] > "02:42")
    say(f"   already affected: {', '.join(short(a) for a in affected)}")
    say(f"   not yet affected: {', '.join(short(u) + ' (' + t + ')' for t, u in not_yet)}")
    say("   remediation, upstream first:")
    say("     0. circuit breaker: pause the dbt run of fct_card_auth and the mcc_decline_7d feature job")
    order = [URN["kafka.auth_events_v1"]] + [u for _, u in sorted((hop, u) for u, (hop, _) in blast.items())]
    for n, u in enumerate(order, 1):
        say(f"     {n}. {FIX[u]}   ({OWNER[u][0]})")
    say("   timestamps: bad data landed 02:05, alert fired 02:42, cause ranked first in the same step.")

    if check:
        assert precision == 1.0 and len(missed) == 2 and all(a.startswith("svc://") for a, _ in missed), (precision, missed)
        assert same
        assert [c["kind"] for c in changes] == ["renamed to mcc"] and changes[0]["class"] == "BREAKING", changes
        assert (len(rows), len(teams), tier1) == (7, 5, 5), rows
        fct, consumers = URN["analytics.fct_card_auth"], {URN["feast.mcc_decline_7d"], URN["bi.approval_rate"], MODEL, SERVICE}
        v_changes, v_reached = variants["a changed expression"]
        assert [(c["element"], c["kind"]) for c in v_changes] == [(fct + "#declined", "logic changed")], v_changes
        assert set(v_reached) == consumers and {k for _, k in v_reached.values()} == {"value"}, v_reached
        v_changes, v_reached = variants["a changed filter"]
        assert [(c["element"], c["kind"]) for c in v_changes] == [(fct, "row set changed")], v_changes
        assert set(v_reached) == consumers and {k for _, k in v_reached.values()} == {"row set"}, v_reached
        assert variants["a table alias and a reformat"] == ([], {})
        schemas = {u["writes"]: state[u["id"]]["fields"] for u in base if u.get("writes")}
        aliased = units(AVRO_V7, dbt_sql=DBT_VARIANTS["a table alias and a reformat"])[3]
        assert extract(aliased, schemas)[0] == extract(base[3], schemas)[0]          # same edges, same expression hashes
        shared, k = Graph(), ("a#x", "b#y", "DERIVES")                               # two units, one edge, then they disagree
        shared.replace_unit("u1", [k + ("DIRECT", "IDENTITY", "h1")], "01:00")
        shared.replace_unit("u2", [k + ("DIRECT", "IDENTITY", "h1")], "01:00")
        shared.replace_unit("u1", [k + ("DIRECT", "TRANSFORMATION", "h2")], "02:00")
        assert {v[1][1]: sorted(e["support"]) for v, e in shared.live.items()} == {"IDENTITY": ["u2"], "TRANSFORMATION": ["u1"]}
        assert [e["attrs"][1] for e in shared.as_of("01:30")] == ["IDENTITY"]
        shared.replace_unit("u2", [k + ("DIRECT", "TRANSFORMATION", "h2")], "03:00")
        assert len(shared.live) == 1 and [e["valid_to"] for e in shared.closed] == ["03:00"]
        assert [e["attrs"][1] for e in shared.as_of("01:30")] == ["IDENTITY"] and [c[1] for c in shared.changes] == ["added", "changed", "changed"]
        assert reread == ["payments-svc/auth-event.avsc", "txn-enrichment/enrich.sql"] and len(skipped) == 6, (reread, skipped)
        assert [d[1:3] for d in diff] == [("removed", old)] and gaps and was and not now
        assert replay.digest() == graph.digest()
        assert first_failing == URN["kafka.auth_enrich_v1"] + "#mcc" and removed == [old[0]]
        assert ranked[0][1:4] == ("02:05", "schema", "payments-svc") and (len(in_window), len(on_path)) == (6, 3)
        assert len(affected) == 2 and len(not_yet) == 5
        say("\nAll checks passed.")


if __name__ == "__main__":
    run(check="--check" in sys.argv)
