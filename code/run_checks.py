"""Evaluate fixtures/otel-demo-3.1.0/checks.yaml over a capture run, window by window (prototype of WP-39).

Then, for the first failing window, rank the change events by what the lineage graph says about them (prototype of
the narrowing step in WP-41): which failing check, which node it sits on, which services that node depends on, which
of those had failing calls, and which flag changes touch those services.

    python3 code/run_checks.py <capture folder> fixtures/otel-demo-3.1.0 [--events <change-events.jsonl>] [--verbose] [--json <out.json>]

Reads metrics.jsonl (OTLP/JSON, one export request per line) written by the collector's file exporter.
"""
import json, os, re, sys
from collections import defaultdict, deque
from datetime import datetime, timezone

import yaml


def attrs(items):
    return {a["key"]: next(iter(a.get("value", {}).values()), None) for a in items or []}


def load_series(folder, names):
    """{(metric, frozenset(attributes)): [(t seconds, value)]}; histograms keep (count, buckets, bounds)."""
    series = defaultdict(list)
    with open(os.path.join(folder, "metrics.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            for rm in doc.get("resourceMetrics", []):
                res = attrs(rm.get("resource", {}).get("attributes"))
                for sm in rm.get("scopeMetrics", []):
                    for m in sm.get("metrics", []):
                        if m["name"] not in names:
                            continue
                        body = m.get("sum") or m.get("gauge") or m.get("histogram") or {}
                        for dp in body.get("dataPoints", []):
                            a = {**res, **attrs(dp.get("attributes"))}
                            a.pop("collector.instance.id", None)
                            t = int(dp["timeUnixNano"]) / 1e9
                            if "histogram" in m:
                                v = (int(dp.get("count", 0)), [int(x) for x in dp.get("bucketCounts", [])], dp.get("explicitBounds", []))
                            else:
                                v = float(dp.get("asInt", dp.get("asDouble", 0)) or 0)
                            series[(m["name"], frozenset((k, str(x)) for k, x in a.items()))].append((t, v))
    for pts in series.values():
        pts.sort(key=lambda p: p[0])
    return series


def at(points, t):
    """Last value at or before t, or None."""
    last = None
    for ts, v in points:
        if ts > t:
            break
        last = v
    return last


def matching(series, metric, where):
    want = {(k, str(v)) for k, v in (where or {}).items()}
    return {k: pts for k, pts in series.items() if k[0] == metric and want <= k[1]}


def evaluate(check, series, t, window, baseline):
    """Return (values dict, failed bool) for one check at time t, or (None, None) when there is not enough data."""
    sel = matching(series, check["metric"], check.get("where"))
    if not sel:
        return None, None
    m = check["metric"]
    def total(when, key=None):
        # A counter series that has not started yet counts as zero (the error series appears with the first error).
        vals = [at(p, when) for k, p in sel.items() if key is None or key(k)]
        return None if all(v is None for v in vals) else sum(v for v in vals if v is not None)
    if m in ("kafka.partition.current_offset", "postgresql.operations"):
        # A rate needs enough events to mean anything: widen the window until the baseline expects min_events in it.
        w, min_events = window, check.get("min_events", 20)
        while True:
            now, w0, b0 = total(t), total(t - w), total(t - w - baseline)
            if None in (now, w0, b0) or now < w0 or w0 < b0:
                return None, None          # not enough history yet, or a counter reset
            base = (w0 - b0) / (baseline / 60)
            if base * w / 60 >= min_events or w >= baseline:
                break
            w += 60
        rate = (now - w0) / (w / 60)
        v = {"window_min": w // 60, "per_min": round(rate, 2), "baseline_per_min": round(base, 2),
             "rate_ratio": round(rate / base, 2) if base else None}
        if v["rate_ratio"] is None or base * w / 60 < min_events:
            return v, None                 # too few events for a verdict, even at the widest window
    elif m == "kafka.consumer_group.lag_sum":
        vals = [v for p in sel.values() for ts, v in p if t - window < ts <= t]
        if not vals:
            return None, None
        v = {"value": max(vals)}
    elif m == "traces.span.metrics.calls":
        err = lambda k: ("status.code", "STATUS_CODE_ERROR") in k[1]
        a_now, a_w0 = total(t), total(t - window)
        e_now, e_w0 = total(t, err) or 0, total(t - window, err) or 0
        if None in (a_now, a_w0) or a_now - a_w0 <= 0:
            return None, None
        v = {"calls": int(a_now - a_w0), "errors": int(e_now - e_w0), "error_share": round((e_now - e_w0) / (a_now - a_w0), 3)}
    elif m == "traces.span.metrics.duration":
        buckets, bounds = None, None
        for p in sel.values():
            now, w0 = at(p, t), at(p, t - window)
            if now is None or w0 is None:
                continue
            delta = [x - y for x, y in zip(now[1], w0[1])]
            buckets = delta if buckets is None else [x + y for x, y in zip(buckets, delta)]
            bounds = now[2]
        if not buckets or sum(buckets) == 0:
            return None, None
        n, run, p95 = sum(buckets), 0, float("inf")
        for i, c in enumerate(buckets):
            run += c
            if run >= 0.95 * n:
                p95 = bounds[i] if i < len(bounds) else float("inf")
                break
        v = {"calls": n, "p95": p95}
    else:
        return None, None
    return v, fails(check["fail_if"], v)


COND = re.compile(r"^\s*(\w+)\s*(<=|>=|<|>|==)\s*(\d+(?:\.\d+)?)(s)?\s*$")
OPS = {"<": float.__lt__, ">": float.__gt__, "<=": float.__le__, ">=": float.__ge__, "==": float.__eq__}


def fails(expr, values):
    """Evaluate 'name op number [s]' terms joined by 'or' / 'and' (no precedence mixing). A trailing s means seconds; values are ms."""
    def term(t):
        m = COND.match(t)
        if not m:
            raise ValueError(f"cannot read condition {t!r}")
        name, op, num, sec = m.groups()
        x = values.get(name)
        return x is not None and OPS[op](float(x), float(num) * (1000 if sec else 1))
    if " and " in expr:
        return all(term(t) for t in expr.split(" and "))
    return any(term(t) for t in expr.split(" or "))


def dependencies(golden, start):
    """Breadth-first walk of what a node depends on: callees, the topic a consumer reads, a topic's producer, a table's writer."""
    dep = defaultdict(set)
    for e in golden["service_edges"]:
        a, b, t = e["from"], e["to"], e["type"]
        if t == "CALLS":
            dep[a].add(b)
        elif t == "CONSUMES":
            dep[b].add(a)              # consumer depends on the topic
        elif t == "PRODUCES":
            dep[b].add(a)              # topic depends on its producer
        elif t in ("WRITES", "READS_WRITES"):
            dep[b].add(a)              # dataset depends on its writer
        if t in ("READS", "READS_WRITES"):
            dep[a].add(b)              # reader depends on the dataset
    dist, q = {start: 0}, deque([start])
    while q:
        n = q.popleft()
        for m in dep[n] | {x for k, v in dep.items() if "*" in k and re.fullmatch(k.replace(".", r"\.").replace("*", ".*"), n) for x in v}:
            if m not in dist:
                dist[m] = dist[n] + 1
                q.append(m)
    return dist


def failing_calls(series, t, window):
    """Service graph edges with failed requests in the window: {(client, server): failures}."""
    out = {}
    for k, pts in matching(series, "traces_service_graph_request_failed_total", {}).items():
        a = dict(k[1])
        now, w0 = at(pts, t), at(pts, t - window)
        if now is not None and now - (w0 or 0) > 0:
            out[(a.get("client"), a.get("server"))] = int(now - (w0 or 0))
    return out


def main(folder, fixtures, events_path=None, verbose=False):
    checks = yaml.safe_load(open(os.path.join(fixtures, "checks.yaml")))
    golden = json.load(open(os.path.join(fixtures, "golden-graph.json")))
    window = int(checks["window"].rstrip("m")) * 60
    baseline = int(checks["baseline"].rstrip("m")) * 60
    names = {c["metric"] for c in checks["checks"] if c.get("metric")} | {"traces_service_graph_request_failed_total"}
    series = load_series(folder, names)
    times = [t for pts in series.values() for t, _ in pts]
    t0, t1 = min(times), max(times)
    clock = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M:%S")
    events = [json.loads(l) for l in open(events_path)] if events_path and os.path.exists(events_path) else []
    for e in events:
        e["t"] = datetime.fromisoformat(e["at"]).timestamp()

    print(f"capture {clock(t0)} to {clock(t1)} UTC; window {window // 60} min, baseline {baseline // 60} min")
    for e in events:
        print(f"  change {clock(e['t'])}  {e['flag']}: {e['from']} -> {e['to']}")
    first_fail, results = {}, []
    t = t0 + window + baseline
    while t <= t1:
        row = []
        for c in checks["checks"]:
            if not c.get("metric"):
                continue
            v, failed = evaluate(c, series, t, window, baseline)
            row.append((c["id"], v, failed))
            if failed and c["id"] not in first_fail:
                first_fail[c["id"]] = t
            results.append({"at": clock(t), "check": c["id"], "values": v, "failed": failed})
        show = lambda v: "" if not v else "(" + ",".join(f"{k}={x}" for k, x in v.items() if k in ("window_min", "rate_ratio", "error_share", "value", "p95", "calls")) + ")"
        marks = "  ".join(f"{cid}={'FAIL' if f else ('ok' if f is False else 'n/a')}{show(v) if verbose else ''}" for cid, v, f in row)
        print(f"{clock(t)}  {marks}")
        t += 60
    print()
    summary = {"events": [{k: e[k] for k in ("at", "flag", "from", "to")} for e in events], "checks": {}, "windows": results}
    for c in checks["checks"]:
        if c["id"] in first_fail:
            ft = first_fail[c["id"]]
            prior = [e for e in events if e["t"] <= ft]
            lag = f"{(ft - prior[-1]['t']) / 60:.1f} min after the last change" if prior else "with no change before it"
            mine = [r for r in results if r["check"] == c["id"]]
            last_fail = max(i for i, r in enumerate(mine) if r["failed"])
            back = next((r["at"] for r in mine[last_fail + 1:] if r["failed"] is False), None)
            print(f"first failure  {c['id']:26} {clock(ft)}  {lag}; passing again from {back or 'not yet'}")
            summary["checks"][c["id"]] = {"first_failure": clock(ft), "minutes_after_change": round((ft - prior[-1]["t"]) / 60, 1) if prior else None,
                                          "passing_again": back}
        else:
            print(f"never failed   {c['id']}")
            summary["checks"][c["id"]] = {"first_failure": None}

    if not first_fail:
        return summary
    # Narrowing: start at the earliest failing check's node, walk what it depends on, keep nodes with failing calls.
    cid, ft = min(first_fail.items(), key=lambda kv: kv[1])
    check = next(c for c in checks["checks"] if c["id"] == cid)
    dist = dependencies(golden, check["node"])
    fails = failing_calls(series, ft, window)
    svc = lambda s: f"svc://otel-demo/{s}"
    origins = {svc(server) for (client, server), n in fails.items() if svc(client) in dist and svc(server) in dist}
    deepest = {o for o in origins if not any(svc(c) == o and svc(s) in dist for c, s in fails)}
    print(f"\nnarrowing from {cid} on {check['node']} at {clock(ft)}")
    print(f"  depends on {len(dist) - 1} nodes; calls failing in the window: "
          + (", ".join(f"{c}->{s} x{n}" for (c, s), n in sorted(fails.items())) or "none"))
    print(f"  where the failures stop (deepest failing callee): {sorted(deepest) or 'none'}")
    readers = defaultdict(set)
    for e in golden.get("flag_edges", []):
        readers[e["from"]].add(e["to"])
    ranked = []
    for e in events:
        if e["t"] > ft:
            continue
        touch = readers.get(e["urn"], set())
        ranked.append((0 if touch & deepest else (1 if touch & set(dist) else 2), ft - e["t"], e, touch))
    ranked.sort(key=lambda r: (r[0], r[1]))
    label = {0: "touches the failing callee", 1: "touches a dependency", 2: "outside the lineage of the check"}
    summary["narrowing"] = {"from_check": cid, "node": check["node"], "at": clock(ft), "depends_on": sorted(set(dist) - {check["node"]}),
                            "failing_calls": [{"client": c, "server": s, "count": n} for (c, s), n in sorted(fails.items())],
                            "deepest_failing_callee": sorted(deepest), "ranking": []}
    for rank, (tier, ago, e, touch) in enumerate(ranked, 1):
        print(f"  {rank}. {e['flag']} {e['from']} -> {e['to']} at {clock(e['t'])}, {ago / 60:.1f} min before; "
              f"{label[tier]}; read by {sorted(s.split('/')[-1] for s in touch)}")
        summary["narrowing"]["ranking"].append({"rank": rank, "flag": e["flag"], "change": f"{e['from']} -> {e['to']}", "at": e["at"],
                                                "minutes_before": round(ago / 60, 1), "why": label[tier], "read_by": sorted(touch)})
    return summary


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--verbose"]
    if len(args) >= 2:
        opts = dict(zip(args[2::2], args[3::2]))
        out = main(args[0], args[1], opts.get("--events"), verbose)
        if "--json" in opts:
            json.dump(out, open(opts["--json"], "w"), indent=1)
            print(f"wrote {opts['--json']}")
    else:
        print(__doc__)
