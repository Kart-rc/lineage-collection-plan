"""Check and render the factory's spec pack (WP-00).

    python3 code/spec_pack.py --check     # validate everything; exit 1 on any error
    python3 code/spec_pack.py --write     # render work package and requirement pages, write schema examples, then check

What it checks:
  requirements   41 unique IDs; each served by at least one work package and traced by at least one visible scenario
  work packages  39 unique IDs; dependencies exist, are acyclic and not in a later wave; every requirement served exists;
                 every done-when line is measurable (has a number, a percentage or a named sign-off); fixtures exist
  scenarios      unique scenario IDs; every requirement tag exists; every fixture path named in a step exists
  interfaces     envelope v2 and lineage.changes are valid JSON Schema; the OpenAPI document parses and has the four
                 queries; every golden edge, check result and change event from the run converts to a valid envelope;
                 the deliberately invalid examples are rejected
"""
import glob, hashlib, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timedelta

import yaml
import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = lambda *p: os.path.join(ROOT, *p)
FIX = F("fixtures", "otel-demo-3.1.0")
ENVELOPE = F("factory", "specs", "evidence", "interfaces", "envelope-v2.schema.json")
CHANGES = F("factory", "specs", "changes", "interfaces", "lineage-changes.schema.json")
OPENAPI = F("factory", "specs", "query-api", "interfaces", "openapi.yaml")
EXAMPLES = F("factory", "specs", "evidence", "examples")
WEIGHTS = yaml.safe_load(open(F("factory", "parameters.yaml")))["evidence"]["weights"]
MEASURABLE = re.compile(r"\d|signed|sign the|sign it", re.I)


# ---------------------------------------------------------------- loading
def load():
    reqs = yaml.safe_load(open(F("factory", "specs", "requirements.yaml")))["requirements"]
    wps = yaml.safe_load(open(F("factory", "work-packages", "work-packages.yaml")))
    scen = []
    for path in sorted(glob.glob(F("factory", "specs", "*", "scenarios", "visible", "*.feature"))):
        tags, title, body = [], None, []
        for line in open(path, encoding="utf-8"):
            s = line.strip()
            if s.startswith("@"):
                tags = s.split()
            elif s.startswith(("Scenario:", "Scenario Outline:")):
                title, body = s.split(":", 1)[1].strip(), []
                scen.append({"file": os.path.relpath(path, ROOT), "tags": tags, "title": title, "body": body})
                tags = []
            elif scen and title:
                body.append(s)
    return reqs, wps, scen


# ---------------------------------------------------------------- URNs and envelope examples
def split(urn):
    """scheme://host/rest#field -> (namespace, name, field)"""
    urn, _, field = urn.partition("#")
    m = re.match(r"^([a-z][a-z0-9+.-]*://[^/]+)/(.+)$", urn)
    if not m:
        raise ValueError(f"not a URN: {urn}")
    return m.group(1), m.group(2), field or None


def sha(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def evidence_event(edge_from, edge_to, etype, source, at, rawref, elements=None, location=None, unit=None, condition=None, columns=None):
    fns, fname, _ = split(edge_from)
    tns, tname, _ = split(edge_to)
    edge = {"type": etype, "from": {"namespace": fns, "name": fname}, "to": {"namespace": tns, "name": tname}}
    if elements:
        edge["elements"] = elements
    if columns:
        edge["columns"] = columns
    if condition:
        edge["condition"] = condition
    ev = {"source": source, "weight": WEIGHTS[source], "runtime": source in ("otel_span", "db_span", "gateway_log", "openlineage", "access_history"),
          "observedAt": at, "rawRef": rawref, "replaces": "unit" if unit else "none"}
    if location:
        ev["location"] = location
    out = {"schemaVersion": "2", "eventType": "EVIDENCE", "eventTime": at, "producer": f"lineage-examples/{source}@0.1.0",
           "edge": edge, "evidence": ev}
    if unit:
        out["unit"] = unit
    return out


def golden_events():
    """Every golden field edge, flag-gated edge and flag edge, as an envelope v2 EVIDENCE event."""
    g = json.load(open(os.path.join(FIX, "golden-graph.json")))
    commit = g["source"]["commit"]
    at = "2026-11-27T12:00:00Z"
    events = []
    def static(e, etype, cond=None):
        f_urn, t_urn = e["from"], e["to"]
        _, _, ff = split(f_urn)
        _, _, tf = split(t_urn)
        loc = {"path": e["evidence"]["path"], "line": e["evidence"]["line"], "text": e["evidence"]["text"]}
        unit = {"urn": "unit://git/opentelemetry-demo/" + loc["path"], "contentHash": sha(loc["path"]), "commit": commit}
        elements = None
        if etype == "DERIVES":
            el = {"from": ff, "to": tf, "class": e["class"], "subtype": e["subtype"], "exprHash": sha(loc["text"])}
            if e.get("masking"):
                el["masking"] = True
            elements = [el]
        return evidence_event(f_urn, t_urn, etype, "ci_static", at, f"archive://ci_static/dt=2026-11-27/{sha(f_urn + t_urn)[7:19]}",
                              elements=elements, location=loc, unit=unit, condition=cond)
    for e in g["field_edges"]:
        events.append(("golden field edge", static(e, "DERIVES")))
    for e in g["gated_field_edges"]:
        events.append(("golden flag-gated edge", static(e, "DERIVES", e["condition"])))
    for e in g["flag_edges"]:
        events.append(("golden flag edge", static(e, "CONFIGURES")))
    return events


def run_events():
    """Check results and change events from the 27 November run, as QUALITY_ASSERTION and CHANGE_EVENT."""
    out = []
    checks = {c["id"]: c for c in yaml.safe_load(open(os.path.join(FIX, "checks.yaml")))["checks"]}
    run = json.load(open(os.path.join(FIX, "capture-2026-11-27", "checks-run.json")))
    for w in run["windows"]:
        if w["failed"] is None:
            continue
        end = datetime.strptime("2026-11-27 " + w["at"], "%Y-%m-%d %H:%M:%S")
        a = {"check": w["check"], "node": checks[w["check"]]["node"], "result": "fail" if w["failed"] else "pass",
             "window": {"start": (end - timedelta(minutes=2)).isoformat() + "Z", "end": end.isoformat() + "Z"},
             "values": {k: v for k, v in (w["values"] or {}).items() if isinstance(v, (int, float)) or v is None},
             "rule": checks[w["check"]]["fail_if"]}
        if checks[w["check"]].get("reader"):
            a["reader"] = checks[w["check"]]["reader"]
        out.append(("check result", {"schemaVersion": "2", "eventType": "QUALITY_ASSERTION", "eventTime": a["window"]["end"],
                                     "producer": "lineage-collectors/checks@0.1.0", "assertion": a}))
    for path in sorted(glob.glob(os.path.join(FIX, "capture-*", "change-events*.jsonl"))):
        for line in open(path):
            e = json.loads(line)
            if e["kind"] == "run_marker":
                continue
            at = e["at"].replace("+00:00", "Z")
            out.append(("change event", {"schemaVersion": "2", "eventType": "CHANGE_EVENT", "eventTime": at, "producer": "twin/flip@0.1.0",
                                         "change": {"kind": e["kind"], "subject": e["urn"], "at": at, "from": e.get("from"), "to": e.get("to")}}))
    return out


def runtime_examples():
    obs = json.load(open(os.path.join(FIX, "capture-2026-11-27", "observed-edges.json")))
    at = "2026-11-27T14:17:00Z"
    out = []
    for d in obs["database"]:
        out.append(("runtime database edge", evidence_event(d["from"], d["to"], d["type"], "db_span", at,
                    f"archive://db_span/dt=2026-11-27/{sha(d['from'] + d['to'])[7:19]}", columns=d["columns"] or None)))
    for a, b in obs["data_flow"]["observed"][:5]:
        etype = "PRODUCES" if b.startswith("kafka://") else "CONSUMES" if a.startswith("kafka://") else "CALLS"
        out.append(("runtime service edge", evidence_event(a, b, etype, "otel_span", at, f"archive://otel_span/dt=2026-11-27/{sha(a + b)[7:19]}")))
    return out


def invalid_examples():
    base = golden_events()[0][1]
    bad = []
    def mutate(name, fn):
        e = json.loads(json.dumps(base)); fn(e); bad.append((name, e))
    mutate("weight above 1", lambda e: e["evidence"].update(weight=1.5))
    mutate("DIRECT with an indirect subtype", lambda e: e["edge"]["elements"][0].update(subtype="FILTER"))
    mutate("runtime source marked static", lambda e: e["evidence"].update(source="otel_span", runtime=False))
    mutate("unit replacement without a unit", lambda e: e.pop("unit"))
    mutate("a payload value smuggled into an element", lambda e: e["edge"]["elements"][0].update(sampleValue="4432-8015-6152-0454"))
    mutate("CONFIGURES from something that is not a flag", lambda e: e["edge"].update(type="CONFIGURES"))
    mutate("DERIVES with neither elements nor opaque", lambda e: e["edge"].pop("elements"))
    return bad


def changes_example():
    return {"schemaVersion": "1", "eventType": "EDGE_CHANGE", "recordedAt": "2026-11-27T14:22:20Z",
            "edgeKey": "api://otel-demo/checkout/PlaceOrder/request#credit_card.credit_card_number | DERIVES | otel://otel-demo/checkout/span#demo.payment.card_number",
            "edge": {"from": "api://otel-demo/checkout/PlaceOrder/request#credit_card.credit_card_number",
                     "to": "otel://otel-demo/checkout/span#demo.payment.card_number", "type": "DERIVES", "class": "DIRECT", "subtype": "IDENTITY"},
            "change": "condition_activated",
            "previous": {"state": "probable", "confidence": 0.6, "condition": "flag://otel-demo/emitRawPii == on", "conditionState": "latent",
                         "validFrom": "2026-11-27T12:00:00Z", "validTo": "2026-11-27T14:22:19Z", "sources": ["ci_static"]},
            "current": {"state": "probable", "confidence": 0.6, "condition": "flag://otel-demo/emitRawPii == on", "conditionState": "active",
                        "validFrom": "2026-11-27T14:22:19Z", "validTo": None, "sources": ["ci_static"]},
            "causes": [{"kind": "change_event", "ref": "flag://otel-demo/emitRawPii off->on 2026-11-27T14:22:19Z"}]}


# ---------------------------------------------------------------- checks
def check(write=False):
    errors, notes = [], []
    reqs, wps, scen = load()
    rid = [r["id"] for r in reqs]
    if len(rid) != len(set(rid)):
        errors.append("duplicate requirement IDs")
    rset = set(rid)

    # work packages
    W = wps["work_packages"]
    ids = [w["id"] for w in W]
    if len(ids) != len(set(ids)):
        errors.append("duplicate work package IDs")
    byid = {w["id"]: w for w in W}
    served = defaultdict(list)
    for w in W:
        for r in w.get("serves", []):
            if r not in rset:
                errors.append(f"{w['id']} serves unknown requirement {r}")
            served[r].append(w["id"])
        for d in w.get("depends", []):
            if d not in byid:
                errors.append(f"{w['id']} depends on unknown {d}")
            elif byid[d]["wave"] > w["wave"]:
                errors.append(f"{w['id']} (wave {w['wave']}) depends on {d} from a later wave ({byid[d]['wave']})")
        if not w.get("done_when"):
            errors.append(f"{w['id']} has no done-when")
        for line in w.get("done_when", []):
            if not MEASURABLE.search(line):
                errors.append(f"{w['id']} done-when is not measurable: {line!r}")
        for fx in w.get("fixtures", []):
            if fx.startswith("planned:"):
                continue
            if not os.path.exists(F(fx.rstrip("/"))):
                errors.append(f"{w['id']} fixture missing: {fx}")
    # cycles
    seen, stack = set(), set()
    def visit(n):
        if n in stack:
            errors.append(f"dependency cycle through {n}"); return
        if n in seen:
            return
        stack.add(n)
        for d in byid.get(n, {}).get("depends", []):
            visit(d)
        stack.discard(n); seen.add(n)
    for n in byid:
        visit(n)

    # scenarios
    sids, traced = [], defaultdict(list)
    for s in scen:
        sid = next((t for t in s["tags"] if t.startswith("@S-")), None)
        if not sid:
            errors.append(f"{s['file']}: scenario without an @S- ID: {s['title']}")
            continue
        sids.append(sid)
        for t in s["tags"]:
            t = t[1:]
            if re.match(r"^(BL|IN|IA|IR|XC)-\d+$", t):
                if t not in rset:
                    errors.append(f"{sid} traces unknown requirement {t}")
                traced[t].append(sid)
        for p in re.findall(r"(fixtures/[\w./-]+|factory/[\w./-]+)", " ".join(s["body"])):
            p = p.rstrip(".,)")
            if not os.path.exists(F(p)) and not glob.glob(F(p)):
                errors.append(f"{sid} names a missing path: {p}")
    if len(sids) != len(set(sids)):
        errors.append("duplicate scenario IDs: " + ", ".join(sorted({x for x in sids if sids.count(x) > 1})))
    for r in rid:
        if not served.get(r):
            errors.append(f"{r} is served by no work package")
        if not traced.get(r):
            errors.append(f"{r} is traced by no visible scenario")

    # owners and tiers: every golden node has one (WP-01, WP-17)
    cat = yaml.safe_load(open(os.path.join(FIX, "catalog.yaml")))
    svcs, dsets, flags = set(cat.get("services") or {}), set(cat.get("datasets") or {}), set(cat.get("flags") or {})
    gg = json.load(open(os.path.join(FIX, "golden-graph.json"))); gd = json.load(open(os.path.join(FIX, "dbt", "golden-dbt.json")))
    nodes = set(gd["datasets"])
    for k in ["service_edges", "field_edges", "gated_field_edges", "flag_edges"]:
        for e in gg[k]:
            nodes |= {e["from"].split("#")[0], e["to"].split("#")[0]}
    for e in gd["field_edges"]:
        nodes |= {e["from"].split("#")[0], e["to"].split("#")[0]}
    def owned(n):
        scheme = n.split("://")[0]
        if scheme == "svc":
            return n.split("/")[-1] in svcs
        if scheme in ("api", "otel", "logs"):
            return n.split("/")[3] in svcs          # a call's messages and a service's spans and logs belong to the service
        return n in dsets or n in flags
    unowned = sorted(n for n in nodes if not owned(n))
    for n in unowned:
        errors.append(f"golden node without owner and tier in catalog.yaml: {n}")

    # interfaces
    env = json.load(open(ENVELOPE)); jsonschema.Draft202012Validator.check_schema(env)
    chg = json.load(open(CHANGES)); jsonschema.Draft202012Validator.check_schema(chg)
    V = jsonschema.Draft202012Validator(env, format_checker=jsonschema.FormatChecker())
    VC = jsonschema.Draft202012Validator(chg, format_checker=jsonschema.FormatChecker())
    good = golden_events() + run_events() + runtime_examples()
    kinds = defaultdict(int)
    for what, e in good:
        errs = sorted(V.iter_errors(e), key=lambda x: x.path)
        if errs:
            errors.append(f"envelope rejects a valid {what}: {errs[0].message[:160]}")
        kinds[what] += 1
    for what, e in invalid_examples():
        if V.is_valid(e):
            errors.append(f"envelope accepts an invalid example: {what}")
    ce = changes_example()
    for err in VC.iter_errors(ce):
        errors.append(f"lineage.changes rejects its example: {err.message[:160]}")
    api = yaml.safe_load(open(OPENAPI))
    for p in ["/impact", "/upstream", "/diff", "/explain"]:
        if p not in api.get("paths", {}):
            errors.append(f"OpenAPI is missing {p}")
    try:
        from openapi_spec_validator import validate as oas_validate
        oas_validate(api)
        notes.append("OpenAPI 3.1 document validated")
    except ImportError:
        notes.append("OpenAPI checked for structure only (install openapi-spec-validator for full validation)")

    if write:
        render(reqs, W, served, traced, scen)
        os.makedirs(os.path.join(EXAMPLES, "invalid"), exist_ok=True)
        picks = {}
        for what, e in good:
            picks.setdefault(what, e)
        for what, e in picks.items():
            json.dump(e, open(os.path.join(EXAMPLES, what.replace(" ", "-") + ".json"), "w"), indent=1)
        for what, e in invalid_examples():
            json.dump(e, open(os.path.join(EXAMPLES, "invalid", re.sub(r"[^a-z0-9]+", "-", what.lower()).strip("-") + ".json"), "w"), indent=1)
        json.dump(ce, open(F("factory", "specs", "changes", "example-condition-activated.json"), "w"), indent=1)

    print(f"requirements {len(rid)}: served {sum(1 for r in rid if served.get(r))}, traced by a visible scenario {sum(1 for r in rid if traced.get(r))}")
    print(f"work packages {len(W)}: done-when lines {sum(len(w['done_when']) for w in W)}, all measurable: {not any('not measurable' in e for e in errors)}")
    print(f"visible scenarios {len(sids)} in {len({s['file'] for s in scen})} files")
    print(f"golden nodes {len(nodes)}: {len(nodes) - len(unowned)} with an owner and a tier")
    print("envelope v2 accepts " + ", ".join(f"{n} {k}s" for k, n in sorted(kinds.items())) + f"; rejects {len(invalid_examples())} of {len(invalid_examples())} invalid examples")
    gates = sorted(os.path.basename(g)[:-3] for g in glob.glob(F("factory", "gates", "G*.md")))
    print("gates signed: " + (", ".join(gates) if gates else "none") + "; open: " + (", ".join(g for g in ["G1", "G3"] if not any(x.startswith(g) for x in gates)) or "none"))
    for n in notes:
        print(n)
    print(f"{len(errors)} errors")
    for e in errors:
        print("  " + e)
    return not errors


# ---------------------------------------------------------------- rendering
def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48].strip("-")


def render(reqs, W, served, traced, scen):
    outdir = F("factory", "work-packages")
    for old in glob.glob(os.path.join(outdir, "WP-*.md")):
        os.remove(old)
    rtext = {r["id"]: r["text"] for r in reqs}
    index = ["# Work packages", "", "Rendered from `work-packages.yaml` by `python3 code/spec_pack.py --write`. Edit the YAML, not these files.", "",
             "| Id | Work package | Wave | Level | Serves | Depends on | Done when |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for w in W:
        name = f"{w['id']}-{slug(w['name'])}.md"
        lines = [f"# {w['id']}: {w['name']}", "",
                 f"Wave {w['wave']} · family {w['family']} · start level {w['level']}"
                 + (" (level 2 until wave 1 meets its holdout pass rate, D18)" if w["level"] == 3 else "")
                 + " · limits: 6 build attempts, 1 working day, cost recorded", "",
                 f"**Serves:** {', '.join(w['serves']) or 'the factory itself'}  ", f"**Depends on:** {', '.join(w['depends']) or 'nothing'}", "",
                 "## Scope", "", w["scope"], "", "## Inputs", ""] + [f"- {x}" for x in w["inputs"]] + \
                ["", "## Outputs", ""] + [f"- {x}" for x in w["outputs"]] + ["", "## Must hold", ""] + [f"- {x}" for x in w["must_hold"]] + \
                ["", "## Done when", ""] + [f"- {x}" for x in w["done_when"]] + \
                ["- Every visible scenario traced to the requirements above passes",
                 "- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios",
                 "- `python3 code/spec_pack.py --check` reports 0 errors", "", "## Fixtures", ""] + \
                ([f"- `{x}`" for x in w["fixtures"]] or ["- none"]) + ["", "## Requirements", ""] + \
                [f"- **{r}**: {rtext[r]}" + (f" Scenarios: {', '.join(s[1:] for s in traced.get(r, []))}." if traced.get(r) else "") for r in w["serves"]] + [""]
        open(os.path.join(outdir, name), "w").write("\n".join(lines))
        index.append(f"| [{w['id']}]({name}) | {w['name']} | {w['wave']} | {w['level']} | {', '.join(w['serves']) or '-'} | {', '.join(w['depends']) or '-'} | {len(w['done_when'])} |")
    open(os.path.join(outdir, "README.md"), "w").write("\n".join(index) + "\n")
    caps = defaultdict(list)
    for r in reqs:
        caps[r["capability"]].append(r)
    for cap, rs in caps.items():
        os.makedirs(F("factory", "specs", cap), exist_ok=True)
        lines = [f"# Requirements: {cap}", "", "Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.", "",
                 "| Id | Requirement | Verified by | Work packages | Visible scenarios |", "| --- | --- | --- | --- | --- |"]
        for r in rs:
            lines.append(f"| {r['id']} | {r['text']} | {r['verified_by']} | {', '.join(served.get(r['id'], []))} | {', '.join(s[1:] for s in traced.get(r['id'], []))} |")
        open(F("factory", "specs", cap, "requirements.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        sys.exit(0 if check() else 1)
    if sys.argv[1:] == ["--write"]:
        sys.exit(0 if check(write=True) else 1)
    print(__doc__)
