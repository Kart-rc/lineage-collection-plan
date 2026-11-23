"""First edges from mesh access logs, checked against the golden graph.

Runs as is with sample data:   python3 first_edges.py
Run on a real export:          python3 first_edges.py access.jsonl golden.json aliases.json
"""
import json, re, sys
from collections import Counter, defaultdict

MIN_CALLS = 10                      # drop anything quieter than this per window
SKIP_PATHS = {"/healthz", "/ready", "/metrics"}

SAMPLE_LOGS = [  # (count, log line): stands in for one day of Envoy JSON logs
    (41200, {"path": "/v1/score", "method": "POST", "upstream_cluster": "outbound|80||fraud-svc.fraud.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/payments/sa/txn-enrichment"}),
    (9800,  {"path": "/invocations", "method": "POST", "upstream_cluster": "outbound|443||fraud-score-prod.ml.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/fraud/sa/fraud-svc"}),
    (18240, {"path": "/v1/authorize", "method": "POST", "upstream_cluster": "outbound|80||payments-svc.payments.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/edge/sa/card-gateway"}),
    (18100, {"path": "/v1/tokens/9f1c2a7e-77b0", "method": "GET", "upstream_cluster": "outbound|80||token-svc.vault.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/payments/sa/payments-svc"}),
    (6400,  {"path": "/v2/merchants/4412aa90-1e2f", "method": "GET", "upstream_cluster": "outbound|80||merchant-svc.ref.svc.cluster.local",
             "downstream_peer_uri_san": "", "x_client_id": ""}),            # caller has no sidecar and no header
    (48,    {"path": "/v1/cases", "method": "POST", "upstream_cluster": "outbound|80||case-mgmt.fraud.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/fraud/sa/fraud-svc"}),
    (310,   {"path": "/v1/export", "method": "GET", "upstream_cluster": "outbound|80||payments-svc.payments.svc.cluster.local",
             "downstream_peer_uri_san": "", "x_client_id": "legacy-reporting"}),
    (2880,  {"path": "/healthz", "method": "GET", "upstream_cluster": "outbound|80||payments-svc.payments.svc.cluster.local",
             "downstream_peer_uri_san": "spiffe://prod/ns/kube-system/sa/kubelet"}),
]

SAMPLE_GOLDEN = [  # hand-checked with the slice owners in week 1
    ["svc://prod/card-gateway", "svc://prod/payments-svc"],
    ["svc://prod/payments-svc", "svc://prod/token-svc"],
    ["svc://prod/txn-enrichment", "svc://prod/fraud-svc"],
    ["svc://prod/txn-enrichment", "svc://prod/merchant-svc"],
    ["svc://prod/fraud-svc", "svc://prod/fraud-score-prod"],
    ["svc://prod/fraud-svc", "svc://prod/case-mgmt"],
]

SAMPLE_ALIASES = {  # seeded by hand for the slice; registry crawlers take over in phase 2
    "spiffe://prod/ns/payments/sa/txn-enrichment": "svc://prod/txn-enrichment",
    "spiffe://prod/ns/payments/sa/payments-svc": "svc://prod/payments-svc",
    "spiffe://prod/ns/fraud/sa/fraud-svc": "svc://prod/fraud-svc",
    "spiffe://prod/ns/edge/sa/card-gateway": "svc://prod/card-gateway",
    "legacy-reporting": "svc://prod/legacy-reporting",
}

def callee_urn(cluster):
    host = cluster.split("||")[-1]                   # fraud-svc.fraud.svc.cluster.local
    return "svc://prod/" + host.split(".")[0]

def route(method, path):
    return method + " " + re.sub(r"/[0-9a-f-]{8,}", "/{id}", path)

def build_edges(lines, aliases):
    calls, unresolved = Counter(), Counter()
    routes = defaultdict(set)
    for count, log in lines:
        if log["path"] in SKIP_PATHS:
            continue
        raw_caller = log.get("downstream_peer_uri_san") or log.get("x_client_id") or ""
        caller = aliases.get(raw_caller)
        callee = callee_urn(log["upstream_cluster"])
        if caller is None:
            unresolved[callee] += count
            continue
        calls[(caller, callee)] += count
        routes[(caller, callee)].add(route(log["method"], log["path"]))
    edges = {k: v for k, v in calls.items() if v >= MIN_CALLS}
    return edges, routes, unresolved

def main():
    if len(sys.argv) == 4:
        lines = [(1, json.loads(l)) for l in open(sys.argv[1]) if l.strip()]
        golden = json.load(open(sys.argv[2]))
        aliases = json.load(open(sys.argv[3]))
    else:
        lines, golden, aliases = SAMPLE_LOGS, SAMPLE_GOLDEN, SAMPLE_ALIASES

    edges, routes, unresolved = build_edges(lines, aliases)
    golden_set = {tuple(e) for e in golden}
    found = golden_set & edges.keys()
    missing = golden_set - edges.keys()
    unexpected = edges.keys() - golden_set

    print("CALLS edges built from the logs")
    for (a, b), n in sorted(edges.items(), key=lambda x: -x[1]):
        mark = "golden" if (a, b) in golden_set else "NOT IN GOLDEN"
        print(f"  {a:30} -> {b:28} {n:>7,} calls  {', '.join(sorted(routes[(a, b)]))}  [{mark}]")
    print("\nMissing golden edges")
    for a, b in sorted(missing):
        why = "caller unresolved" if b in unresolved else "below threshold or not an HTTP call"
        print(f"  {a} -> {b}   ({why})")
    total_unresolved = sum(unresolved.values())
    total = total_unresolved + sum(edges.values())
    recall = len(found) / len(golden_set)
    print(f"\nUnresolved caller traffic: {total_unresolved:,} of {total:,} calls ({total_unresolved / total:.1%})")
    print(f"Golden edges found: {len(found)} of {len(golden_set)} = {recall:.0%}  "
          f"(phase 1 gate needs 90%: {'PASS' if recall >= 0.9 else 'NOT YET'})")
    print(f"Unexpected edges to review with owners: {len(unexpected)}")

if __name__ == "__main__":
    main()
