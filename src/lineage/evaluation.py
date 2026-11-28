"""Candidate evaluation tooling; never an approved oracle or a G4 decision.

Observations and expected truth are separate. Missing evidence is unavailable,
never zero. Private runners return aggregates, never holdout cases.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from contextlib import redirect_stdout
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Callable

from jsonschema import Draft202012Validator
import yaml

from .config import repository_root

FIXTURES = Path("fixtures/otel-demo-3.1.0")
G4_SECTIONS = ("Release", "Oracle", "Replay", "Floor", "Lost cases", "Hard zeros",
               "Timings", "Holdout", "Accuracy report", "Service levels declared held")
FAMILIES = ("core_semantics", "extractors", "impact", "detect_resolve", "platform")
FAILURE_CATEGORIES = ("accuracy", "coverage", "schema", "custody", "timing", "regression", "hard_zero", "unavailable")
STRING = {"type": "string", "minLength": 1}
NUMBER = {"type": "number", "minimum": 0}
COUNT = {"type": "integer", "minimum": 0}
DIGEST = {"type": "string", "pattern": "^[a-f0-9]{64}$"}


def obj(properties: dict, required: tuple | list = ()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def array(items: dict, **extra) -> dict:
    return {"type": "array", "items": items, **extra}


EDGE_SCHEMA = obj({"from": STRING, "to": STRING, "type": STRING, "state": STRING}, ("from", "to", "type"))
FIELD_SCHEMA = obj({"from": STRING, "to": STRING, "type": {"const": "DERIVES"}, "state": STRING,
                    "class": {"enum": ["DIRECT", "INDIRECT"]},
                    "subtype": {"enum": ["IDENTITY", "TRANSFORMATION", "AGGREGATION", "JOIN", "FILTER", "GROUP_BY", "SORT", "WINDOW", "CONDITIONAL"]},
                    "masking": {"type": "boolean"}, "condition": {"type": ["string", "null"], "minLength": 1}}, ("from", "to", "class", "subtype"))
FIELD_SCHEMA["allOf"] = [
    {"if": {"properties": {"class": {"const": "DIRECT"}}}, "then": {"properties": {"subtype": {"enum": ["IDENTITY", "TRANSFORMATION", "AGGREGATION"]}}}},
    {"if": {"properties": {"class": {"const": "INDIRECT"}}}, "then": {"properties": {"subtype": {"enum": ["JOIN", "FILTER", "GROUP_BY", "SORT", "WINDOW", "CONDITIONAL"]}}}},
]
GRAPH_SCHEMA = obj({"service_edges": array(EDGE_SCHEMA), "field_edges": array(FIELD_SCHEMA),
                    "gated_field_edges": array({**FIELD_SCHEMA, "required": FIELD_SCHEMA["required"] + ["condition"]}),
                    "flag_edges": array(EDGE_SCHEMA), "dataset_edges": array(EDGE_SCHEMA)})
CHANGE_SCHEMA = obj({"id": STRING, "readers": array(STRING, uniqueItems=True),
                     "gate": {"enum": ["pass", "warn", "block", "unavailable"]}}, ("id", "readers", "gate"))
INCIDENT_SCHEMA = obj({"id": STRING, "detected": {"type": "boolean"}, "ranking": array(STRING),
                       "minutes_to_detect": {"type": ["number", "null"], "minimum": 0}},
                      ("id", "detected", "ranking", "minutes_to_detect"))
SOURCE_SCHEMA = obj({"kind": {"enum": ["recorded_twin_captures", "recorded_corpora", "fresh_twin_run", "one_day_of_production_evidence"]},
                     "path": STRING, "sha256": DIGEST, "run_id": STRING, "commit": STRING,
                     "started_at": STRING, "ended_at": STRING, "event_count": {"type": "integer", "minimum": 1}},
                    ("kind", "path", "sha256", "run_id", "commit", "started_at", "ended_at", "event_count"))
TIMING_SCHEMA = obj({"requirement": {"enum": ["IA-1", "IN-10", "IR-1", "XC-7"]},
                     "source_run_id": STRING, "samples_seconds": array(NUMBER, minItems=1)},
                    ("requirement", "source_run_id", "samples_seconds"))
ZERO_OBSERVATIONS = obj({"source_run_id": STRING, "observations": array(obj({"name": STRING, "count": COUNT}, ("name", "count")), minItems=1)},
                        ("source_run_id", "observations"))
BUNDLE_SCHEMA = obj({"schema_version": {"const": 1}, "commit": STRING,
                     "work_packages": array({"type": "string", "pattern": "^WP-[0-9]{2}$"}, minItems=1, uniqueItems=True),
                     "graph": GRAPH_SCHEMA, "changes": array(CHANGE_SCHEMA), "incidents": array(INCIDENT_SCHEMA),
                     "sources": array(SOURCE_SCHEMA), "timings": array(TIMING_SCHEMA),
                     "payload_scan": ZERO_OBSERVATIONS, "fault_scenarios": ZERO_OBSERVATIONS,
                     "rebuild": obj({"live_sha256": DIGEST, "replayed_sha256": DIGEST, "as_of": STRING, "source_run_id": STRING},
                                    ("live_sha256", "replayed_sha256", "as_of", "source_run_id")),
                     "slice": {"type": "integer", "minimum": 1}}, ("schema_version", "commit", "work_packages"))
AGGREGATE_SCHEMA = obj({"schema_version": {"const": 1},
    "provenance": obj({"store_id": STRING, "job_id": STRING, "run_id": STRING, "candidate_commit": STRING,
        "oracle_sha256": {"type": "object", "additionalProperties": DIGEST}, "independent_author": STRING,
        "approved_by": STRING, "builders_cannot_read": {"const": True}},
        ("store_id", "job_id", "run_id", "candidate_commit", "oracle_sha256", "independent_author", "approved_by", "builders_cannot_read")),
    "families": {"type": "object", "additionalProperties": False, "properties": {name: obj({
        "total": {"type": "integer", "minimum": 1}, "passed": COUNT,
        "failure_categories": {"type": "object", "additionalProperties": False,
                               "properties": {cat: COUNT for cat in FAILURE_CATEGORIES}}},
        ("total", "passed", "failure_categories")) for name in FAMILIES}},
    "corpora": obj({kind: obj({"visible": COUNT, "holdout": COUNT,
        "families": {"type": "object", "additionalProperties": obj({"visible": COUNT, "holdout": COUNT}, ("visible", "holdout"))}},
        ("visible", "holdout", "families")) for kind in ("changes", "incidents")}, ("changes", "incidents")),
    "signatures": obj({"owners": array(STRING, minItems=1, uniqueItems=True), "platform_lead": STRING}, ("owners", "platform_lead")),
    "coverage": obj({name: {"const": True} for name in ("near_simultaneous_changes", "silent_failure", "caller_cause", "targeting_rule", "no_visible_copies")},
                    ("near_simultaneous_changes", "silent_failure", "caller_cause", "targeting_rule", "no_visible_copies"))},
    ("schema_version", "provenance", "families", "corpora", "signatures", "coverage"))


class EvidenceError(ValueError):
    """Malformed or unavailable evidence; never interpreted as success."""


def validate(value: object, schema: dict, label: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EvidenceError(f"{label}: invalid JSON value") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        # Never echo input values; invalid private reports could contain case text.
        raise EvidenceError(f"{label}: schema violation")


def load_json(path: str | Path) -> dict:
    try:
        return json.loads(Path(path).read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"JSON input unavailable or invalid: {path}") from exc


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _unique(rows: list[dict], label: str) -> dict:
    indexed = {r["id"]: r for r in rows}
    if len(indexed) != len(rows):
        raise EvidenceError(f"duplicate {label} IDs")
    return indexed


def oracle_pins(root: Path | None = None) -> dict:
    root = root or repository_root()
    records = sorted((root / "factory/gates").glob("G3-*.md"))
    if not records:
        return {"status": "blocked", "record": None, "files": [], "blockers": ["G3 record unavailable"]}
    record = records[-1]
    rows = re.findall(r"\| `([^`]+)` \| `([a-f0-9]{16,64})` \|", record.read_text())
    files, blockers = [], []
    if len(rows) != 8:
        blockers.append("G3 record must identify all 8 approved oracle files")
    for name, prefix in rows:
        path = root / name
        actual = sha256(path) if path.is_file() else None
        matches = actual is not None and actual.startswith(prefix)
        files.append({"path": name, "sha256": actual, "g3_digest": prefix, "matches": matches})
        if not matches:
            blockers.append(f"oracle digest mismatch or unavailable: {name}")
    return {"status": "blocked" if blockers else "pass", "record": str(record.relative_to(root)), "files": files, "blockers": blockers}


def _edge_key(edge: dict, fields: bool = False) -> tuple:
    if fields:
        return (edge["from"], edge["to"], edge.get("type", "DERIVES"), edge["class"], edge["subtype"],
                str(edge.get("masking", False)).lower(), edge.get("condition") or "")
    return (edge["from"], edge["to"], edge.get("type", ""))


def must_not_flow(graph: dict, rules: list[dict]) -> list[dict]:
    """Walk all candidate field edges, including latent ones; do not infer truth flows."""
    adjacent: dict[str, set] = defaultdict(set)
    for edge in graph.get("field_edges", []) + graph.get("gated_field_edges", []):
        adjacent[edge["from"]].add(edge["to"])
    violations = []
    # Only '*' is a wildcard; [] in nested field paths is literal.
    match = lambda value, pattern: re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), value) is not None
    for rule in rules:
        for start in sorted(n for n in adjacent if match(n, rule["from"])):
            queue, seen = deque([(start, [start])]), {start}
            while queue:
                node, path = queue.popleft()
                for dest in sorted(adjacent[node]):
                    reached = match(dest, rule["to"]) or ("#" not in rule["to"] and match(dest.split("#")[0], rule["to"]))
                    if reached:
                        violations.append({"from": rule["from"], "to": rule["to"], "path": path + [dest]})
                    if dest not in seen:
                        seen.add(dest)
                        queue.append((dest, path + [dest]))
    return sorted(violations, key=lambda v: (v["from"], v["to"], v["path"]))


def score_edges(candidate: dict, golden: dict, dbt_golden: dict | None = None) -> dict:
    validate(candidate, GRAPH_SCHEMA, "candidate graph")
    dbt = dbt_golden if dbt_golden is not None else load_json(repository_root() / FIXTURES / "dbt/golden-dbt.json")
    golden = {**golden, "field_edges": golden["field_edges"] + dbt["field_edges"],
              "dataset_edges": golden.get("dataset_edges", []) + dbt.get("dataset_edges", [])}
    metrics, cases = {}, {}
    for kind in ("service_edges", "field_edges"):
        fields = kind == "field_edges"
        select = lambda e: fields or (e.get("type") in {"CALLS", "PRODUCES", "CONSUMES"} and e["to"] != "svc://otel-demo/flagd")
        expected = {_edge_key(e, fields) for e in golden[kind] if select(e)}
        observed = {_edge_key(e, fields) for e in candidate.get(kind, []) if select(e)}
        available = kind in candidate
        hits = expected & observed
        metrics[kind] = {"precision": len(hits) / len(observed) if observed else (0.0 if available else None),
                         "recall": len(hits) / len(expected) if available and expected else None,
                         "expected": len(expected), "observed": len(observed) if available else None,
                         "missing": [list(k) for k in sorted(expected - observed)] if available else None,
                         "extra": [list(k) for k in sorted(observed - expected)] if available else None}
        if not fields:
            asserted = {_edge_key(e) for e in golden[kind] if e.get("upstream_asserted")}
            metrics[kind]["upstream_asserted_recall"] = len(asserted & observed) / len(asserted) if available and asserted else None
        for key in sorted(expected):
            cases[f"{kind}:{' -> '.join(key)}"] = key in observed if available else None
    def group_score(expected_rows, observed_rows, available, fields=True):
        expected_keys = {_edge_key(e, fields) for e in expected_rows}
        observed_keys = {_edge_key(e, fields) for e in observed_rows}
        hit = len(expected_keys & observed_keys)
        return {"expected": len(expected_keys), "observed": len(observed_keys) if available else None,
                "precision": hit / len(observed_keys) if available and observed_keys else (0.0 if available else None),
                "recall": hit / len(expected_keys) if available and expected_keys else None}
    for kind in ("gated_field_edges", "flag_edges", "dataset_edges"):
        fields = kind == "gated_field_edges"
        metrics[kind] = group_score(golden.get(kind, []), candidate.get(kind, []), kind in candidate, fields)
        for edge in golden.get(kind, []):
            key = _edge_key(edge, fields)
            cases[f"{kind}:{' -> '.join(key)}"] = key in {_edge_key(e, fields) for e in candidate.get(kind, [])} if kind in candidate else None
    # Partitions name the actual approved reference hops; they never manufacture
    # mappings for the complementary slice, whose oracle is not yet approved.
    hop = lambda e: ("dbt" if e["from"].startswith("postgres://") and e["to"].startswith("postgres://") else
                     "accounting" if e["from"].startswith("kafka://") and e["to"].startswith("postgres://") else
                     "checkout_orders" if e["from"].startswith("api://otel-demo/checkout/") and e["to"].startswith("kafka://") else
                     "checkout_payment" if e["from"].startswith("api://otel-demo/checkout/") and e["to"].startswith("api://otel-demo/payment/") else
                     "payment_logs" if e["to"].startswith("logs://") else "other")
    per_hop = {}
    for name in sorted({hop(e) for e in golden["field_edges"]} | {hop(e) for e in candidate.get("field_edges", [])}):
        per_hop[name] = group_score([e for e in golden["field_edges"] if hop(e) == name],
                                    [e for e in candidate.get("field_edges", []) if hop(e) == name], "field_edges" in candidate)
        per_hop[name]["case_ids"] = sorted(f"field_edges:{' -> '.join(_edge_key(e, True))}" for e in golden["field_edges"] if hop(e) == name)
    per_hop["telemetry_export"] = metrics["gated_field_edges"]
    per_hop["dashboard_exposure"] = metrics["dataset_edges"]
    for name, category, fields in (("telemetry_export", "gated_field_edges", True), ("dashboard_exposure", "dataset_edges", False)):
        per_hop[name]["case_ids"] = sorted(f"{category}:{' -> '.join(_edge_key(e, fields))}" for e in golden.get(category, []))
    per_edge_type = {}
    for category in ("service_edges", "field_edges", "gated_field_edges", "flag_edges", "dataset_edges"):
        fields = category in {"field_edges", "gated_field_edges"}
        classify = lambda e: f"{e['class']}/{e['subtype']}" if fields else e.get("type", "")
        for kind in sorted({classify(e) for e in golden.get(category, [])} | {classify(e) for e in candidate.get(category, [])}):
            per_edge_type[f"{category}:{kind}"] = group_score([e for e in golden.get(category, []) if classify(e) == kind],
                [e for e in candidate.get(category, []) if classify(e) == kind], category in candidate, fields)
    bars = yaml.safe_load((repository_root() / "factory/parameters.yaml").read_text())["baseline_accuracy"]
    available = [kind for kind in ("field_edges", "service_edges") if kind in candidate]
    holds = bool(available) and all(metrics[kind][metric] is not None and metrics[kind][metric] >= bars[kind][metric]
                                    for kind in available for metric in ("precision", "recall"))
    if "field_edges" in candidate:
        holds = holds and all(row[metric] is not None and row[metric] >= bars["deterministic_hops" if name == "accounting" else "per_hop_default"][metric]
                              for name, row in per_hop.items() for metric in ("precision", "recall"))
    violations = must_not_flow(candidate, golden.get("must_not_flow", [])) if "field_edges" in candidate else None
    return {"status": "pass" if holds and not violations else "blocked", "metrics": metrics, "cases": cases,
            "per_hop": per_hop, "per_edge_type": per_edge_type, "must_not_flow": violations}


def replay_changes(candidate: list[dict], truth: list[dict]) -> dict:
    validate(candidate, array(CHANGE_SCHEMA), "candidate changes")
    actual, expected = _unique(candidate, "change"), _unique(truth, "truth change")
    if set(actual) - set(expected):
        raise EvidenceError("candidate contains changes absent from the pinned corpus")
    cases, details, hit, total = {}, [], 0, 0
    for ident, case in sorted(expected.items()):
        row = actual.get(ident)
        readers = set(case["expected_readers"])
        total += len(readers)
        found = readers & set(row["readers"]) if row else set()
        hit += len(found)
        passed = readers <= set(row["readers"]) and row["gate"] == case["expected_gate"] if row else None
        cases[f"change:{ident}"] = passed
        details.append({"id": ident, "passed": passed, "missing_readers": sorted(readers - found),
                        "gate_matches": row["gate"] == case["expected_gate"] if row else None})
    recall = hit / total if total and actual else None
    bar = yaml.safe_load((repository_root() / "factory/parameters.yaml").read_text())["impact"]["replay_consumer_recall"]
    holds = recall is not None and recall >= bar and set(actual) == set(expected) and all(row["gate_matches"] for row in details)
    return {"status": "pass" if holds else "blocked", "consumer_recall": recall, "cases": cases, "results": details,
            "coverage": {"observed": len(actual), "expected": len(expected)}, "missing": sorted(set(expected) - set(actual))}


def _cause(case: dict) -> str:
    return case.get("flag") or case.get("service") or case["injected_at"].removeprefix("svc://otel-demo/")


def replay_incidents(candidate: list[dict], truth: list[dict]) -> dict:
    validate(candidate, array(INCIDENT_SCHEMA), "candidate incidents")
    actual, expected = _unique(candidate, "incident"), _unique(truth, "truth incident")
    if set(actual) - set(expected):
        raise EvidenceError("candidate contains incidents absent from the pinned corpus")
    cases, rows, first, top3 = {}, [], 0, 0
    for ident, case in sorted(expected.items()):
        row = actual.get(ident)
        if row and ((not row["detected"] and (row["ranking"] or row["minutes_to_detect"] is not None)) or
                    (row["detected"] and row["minutes_to_detect"] is None)):
            raise EvidenceError(f"inconsistent detection evidence for {ident}")
        cause = _cause(case)
        rank = row["ranking"].index(cause) + 1 if row and row["detected"] and cause in row["ranking"] else None
        rank1, rank3 = rank == 1, rank is not None and rank <= 3
        first += rank1
        top3 += rank3
        cases[f"incident:{ident}:rank_first"] = rank1 if row else None
        cases[f"incident:{ident}:rank_top3"] = rank3 if row else None
        cases[f"incident:{ident}:detected"] = row["detected"] if row else None
        rows.append({"id": ident, "rank": rank, "detected": row["detected"] if row else None,
                     "minutes_to_detect": row["minutes_to_detect"] if row else None})
    bars = yaml.safe_load((repository_root() / "factory/parameters.yaml").read_text())["detect_resolve"]
    holds = bool(expected) and set(actual) == set(expected) and first / len(expected) >= bars["rank_first_share"] and top3 / len(expected) >= bars["rank_top3_share"]
    return {"status": "pass" if holds else "blocked", "rank_first_share": first / len(expected) if actual and expected else None,
            "rank_top3_share": top3 / len(expected) if actual and expected else None,
            "cases": cases, "results": rows, "coverage": {"observed": len(actual), "expected": len(expected)},
            "missing": sorted(set(expected) - set(actual))}


def _legacy(root: Path, name: str):
    spec = importlib.util.spec_from_file_location(f"lineage_legacy_{name}", root / "code" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw_jsonl(path: Path, top: str) -> None:
    if not path.is_file():
        raise EvidenceError(f"raw capture unavailable: {path}; checked-in summaries cannot reproduce a capture")
    count = 0
    with path.open() as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except ValueError as exc:
                raise EvidenceError(f"malformed raw capture: {path}") from exc
            if not isinstance(value, dict) or not value.get(top):
                raise EvidenceError(f"expected raw {top} export records: {path}")
            count += 1
    if not count:
        raise EvidenceError(f"empty raw capture: {path}")


def capture_score(folder: Path, root: Path | None = None) -> dict:
    root = root or repository_root()
    _raw_jsonl(folder / "traces.jsonl", "resourceSpans")
    module = _legacy(root, "observed_edges")
    resolver = module.Resolver(str(root / FIXTURES / "aliases.json"))
    try:
        edges, _ = module.observe(module.spans(str(folder)), resolver)
    except (TypeError, KeyError, ValueError) as exc:
        raise EvidenceError("raw trace replay contains malformed span observations") from exc
    graph = {"service_edges": [{"from": a, "to": b, "type": kind} for a, b, kind in sorted(edges)]}
    report = score_edges(graph, load_json(root / FIXTURES / "golden-graph.json"))
    report["source"] = {"path": str(folder / "traces.jsonl"), "sha256": sha256(folder / "traces.jsonl")}
    return report


def capture_incidents(folder: Path, events: Path, candidate_graph: Path, root: Path | None = None) -> dict:
    """Replay raw metrics with candidate dependencies; truth used for scoring/IDs."""
    root = root or repository_root()
    _raw_jsonl(folder / "metrics.jsonl", "resourceMetrics")
    _raw_jsonl(events, "at")
    graph = load_json(candidate_graph)
    if not isinstance(graph.get("service_edges"), list) or not isinstance(graph.get("flag_edges"), list):
        raise EvidenceError("candidate graph requires service_edges and flag_edges")
    module = _legacy(root, "run_checks")
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        (target / "golden-graph.json").write_bytes(canonical_bytes(graph))
        for name in ("checks.yaml", "incident-scenarios.json"):
            (target / name).write_bytes((root / FIXTURES / name).read_bytes())
        with redirect_stdout(io.StringIO()):
            try:
                observed = module.replay(str(folder), str(target), str(events))
            except (ValueError, KeyError) as exc:
                raise EvidenceError("raw incident replay could not produce observations") from exc
    # Discard the prototype's truth-derived rank; score independently.
    candidate = [{"id": row["id"], "detected": row["detected"], "minutes_to_detect": row.get("minutes_to_detect"),
                  "ranking": [c["change"].split()[0] + ("#revert" if c["terms"]["direction"] != 1.0 else "")
                              for c in row["candidates"]]} for row in observed]
    truth = load_json(root / FIXTURES / "incident-scenarios.json")["incidents"]
    return {"source": {"metrics_sha256": sha256(folder / "metrics.jsonl"), "events_sha256": sha256(events),
                       "candidate_graph_sha256": sha256(candidate_graph)},
            "observations": candidate, **replay_incidents(candidate, truth)}


def validate_holdout(aggregate: dict | None, trusted: dict | None, commit: str,
                     pins: dict, parameters: dict, required_families: set[str] | None = None) -> dict:
    """Accept only aggregate output pinned by an independently installed trust policy.

    The caller supplies trusted job configuration, NOT a policy from candidate
    output. No store credentials or case text enter the builder process.
    """
    blockers, rates = [], {}
    if aggregate is None:
        return {"status": "blocked", "label": "Visible only: WP-02 has not delivered the holdout",
                "families": {}, "blockers": ["private holdout aggregate unavailable"]}
    validate(aggregate, AGGREGATE_SCHEMA, "holdout aggregate")
    provenance = aggregate["provenance"]
    if trusted is None:
        blockers.append("independent private runner trust policy unavailable")
    else:
        for key in ("store_id", "job_id", "approved_by", "independent_author"):
            if not trusted.get(key) or trusted[key] != provenance[key]:
                blockers.append(f"holdout provenance mismatch: {key}")
        digest = hashlib.sha256(canonical_bytes(aggregate)).hexdigest()
        if trusted.get("aggregate_sha256") != digest:
            blockers.append("holdout aggregate digest is not pinned by the trusted job policy")
        owners = set(trusted.get("required_owner_signatures", []))
        if not owners or not owners <= set(aggregate["signatures"]["owners"]):
            blockers.append("required corpus owner signatures unavailable")
    if aggregate["signatures"]["platform_lead"] != provenance["approved_by"]:
        blockers.append("platform-lead corpus signature mismatch")
    if provenance["independent_author"] in {"builder", "candidate", commit}:
        blockers.append("holdout author is not independent")
    if provenance["candidate_commit"] != commit:
        blockers.append("holdout candidate commit mismatch")
    expected_pins = {r["path"]: r["sha256"] for r in pins["files"]}
    if provenance["oracle_sha256"] != expected_pins or pins["status"] != "pass":
        blockers.append("holdout oracle digest mismatch")
    for kind in ("changes", "incidents"):
        counts = aggregate["corpora"][kind]
        families = parameters["corpora"]["change_families" if kind == "changes" else "incident_families"]
        if set(counts["families"]) - set(families):
            raise EvidenceError("holdout aggregate: unknown corpus family")
        if set(counts["families"]) != set(families):
            blockers.append(f"{kind}: missing or unknown corpus families")
        if counts["visible"] + counts["holdout"] < parameters["corpora"][kind]["minimum"]:
            blockers.append(f"{kind}: fewer than 20 total cases")
        if counts["holdout"] < 7:
            blockers.append(f"{kind}: fewer than 7 holdout cases")
        for split in ("visible", "holdout"):
            if sum(r[split] for r in counts["families"].values()) != counts[split]:
                blockers.append(f"{kind}: {split} family counts disagree with total")
        for family, count in sorted(counts["families"].items()):
            total = count["visible"] + count["holdout"]
            if total == 0 or count["holdout"] * 3 < total:
                blockers.append(f"{kind}/{family}: at least one third must be holdout")
    bars = parameters["factory"]["holdout_pass_rate"]
    for family, count in sorted(aggregate["families"].items()):
        if count["passed"] > count["total"] or sum(count["failure_categories"].values()) != count["total"] - count["passed"]:
            blockers.append(f"{family}: inconsistent aggregate counts")
            continue
        rate = count["passed"] / count["total"]
        rates[family] = {"pass_rate": rate, "bar": bars[family], "failure_categories": count["failure_categories"]}
        if rate < bars[family]:
            blockers.append(f"{family}: holdout below family rate")
    needed = set(bars) if required_families is None else required_families
    for family in sorted(needed - set(rates)):
        blockers.append(f"{family}: holdout family result unavailable")
    return {"status": "blocked" if blockers else "pass", "label": "Visible only: holdout evidence unverified" if blockers else "Verified private aggregate",
            "families": rates, "blockers": sorted(set(blockers))}


def run_private(request: dict, runner: Callable[[dict], dict] | None, trusted: dict | None,
                root: Path | None = None) -> dict:
    """Pluggable boundary: a trusted adapter invokes a private job, returning aggregates only."""
    root = root or repository_root()
    pins = oracle_pins(root)
    if runner is None:
        return {"status": "blocked", "families": {}, "blockers": ["private runner/store not configured"]}
    validate(request, obj({"candidate_commit": STRING}, ("candidate_commit",)), "private job request")
    result = runner({"candidate_commit": request["candidate_commit"],
                     "oracle_sha256": {r["path"]: r["sha256"] for r in pins["files"]}})
    return validate_holdout(result, trusted, request["candidate_commit"], pins,
                            yaml.safe_load((root / "factory/parameters.yaml").read_text()))


def validate_custody(visible: dict | None = None, aggregate: dict | None = None,
                     trusted: dict | None = None, commit: str = "unconfigured", root: Path | None = None) -> dict:
    """Validate visible metadata plus private aggregate custody; never generate corpora."""
    root = root or repository_root()
    params = yaml.safe_load((root / "factory/parameters.yaml").read_text())
    metadata_schema = obj({kind: array(obj({"id": STRING, "family": {"enum": params["corpora"][family_key]},
        "base": STRING, "trigger": obj({"path": STRING, "sha256": DIGEST}, ("path", "sha256")),
        "expected_outcome": obj({"oracle_case": STRING}, ("oracle_case",))},
        ("id", "family", "base", "trigger", "expected_outcome")))
        for kind, family_key in (("changes", "change_families"), ("incidents", "incident_families"))})
    if visible is not None:
        validate(visible, metadata_schema, "visible corpus metadata")
    blockers, counts = [], {}
    for kind in ("changes", "incidents"):
        rows = load_json(root / FIXTURES / ("change-replay.json" if kind == "changes" else "incident-scenarios.json"))[kind]
        supplement = (visible or {}).get(kind, [])
        mapping = _unique(supplement, f"{kind} metadata")
        expected_ids = {row["id"] for row in rows}
        if set(mapping) - expected_ids:
            blockers.append(f"{kind}: metadata references cases outside the approved visible corpus")
        families = params["corpora"]["change_families" if kind == "changes" else "incident_families"]
        covered = defaultdict(int)
        missing = []
        for row in rows:
            metadata = mapping.get(row["id"], {})
            family = metadata.get("family", row.get("family"))
            if family in families:
                covered[family] += 1
            else:
                missing.append(f"{row['id']}: family")
            # Narrative injections/commit titles are not executable base/trigger/outcome records.
            for key in ("base", "trigger", "expected_outcome"):
                if not metadata.get(key):
                    missing.append(f"{row['id']}: {key}")
            if metadata:
                if metadata["expected_outcome"]["oracle_case"] != row["id"]:
                    missing.append(f"{row['id']}: expected outcome must reference the same approved oracle case")
                artifact = Path(metadata["trigger"]["path"])
                artifact = artifact if artifact.is_absolute() else root / artifact
                if not artifact.is_file() or sha256(artifact) != metadata["trigger"]["sha256"]:
                    missing.append(f"{row['id']}: trigger artifact unavailable or digest mismatch")
        counts[kind] = {"visible": len(rows), "families": dict(sorted(covered.items())),
                        "uncovered_families": sorted(set(families) - set(covered)), "missing_case_metadata": missing}
        if missing:
            blockers.append(f"{kind}: executable base/trigger/expected-outcome metadata or family unavailable")
        if set(families) - set(covered):
            blockers.append(f"{kind}: visible family coverage incomplete")
    holdout = validate_holdout(aggregate, trusted, commit, oracle_pins(root), params)
    blockers.extend(holdout["blockers"])
    if aggregate:
        for kind, count in counts.items():
            if aggregate["corpora"][kind]["visible"] != count["visible"]:
                blockers.append(f"{kind}: private aggregate visible count differs from approved corpus")
            for family, number in count["families"].items():
                if aggregate["corpora"][kind]["families"].get(family, {}).get("visible") != number:
                    blockers.append(f"{kind}/{family}: private and visible family counts disagree")
    return {"status": "blocked" if blockers else "pass", "visible": counts, "holdout": holdout,
            "blockers": sorted(set(blockers))}


def _verify_sources(sources: list[dict], root: Path, commit: str) -> tuple[list[str], list[dict]]:
    blockers, events, ids = [], [], set()
    for source in sources:
        label = source["run_id"]
        if label in ids:
            blockers.append(f"duplicate source run ID: {label}")
        ids.add(label)
        path = Path(source["path"])
        path = path if path.is_absolute() else root / path
        if not path.is_file() or sha256(path) != source["sha256"]:
            blockers.append(f"source artifact unavailable or digest mismatch: {label}")
            continue
        try:
            start, end = (datetime.fromisoformat(source[key].replace("Z", "+00:00")) for key in ("started_at", "ended_at"))
            if start.tzinfo is None or end.tzinfo is None or end < start:
                raise ValueError("invalid interval")
        except ValueError:
            blockers.append(f"invalid source time span: {label}")
            continue
        if source["kind"] == "one_day_of_production_evidence" and (end - start).total_seconds() < 86400:
            blockers.append(f"less than one day of production evidence: {label}")
        if source["commit"] != commit:
            blockers.append(f"source candidate commit mismatch: {label}")
            continue
        # Release evidence has typed observation events, not stored scores or summaries.
        try:
            artifact = load_json(path)
        except EvidenceError:
            blockers.append(f"source artifact malformed: {label}")
            continue
        if not isinstance(artifact, dict) or not isinstance(artifact.get("events"), list):
            blockers.append(f"source lacks candidate observation events: {label}")
            continue
        if artifact.get("run_id") != label or artifact.get("commit") != commit:
            blockers.append(f"source artifact identity mismatch: {label}")
            continue
        if len(artifact["events"]) != source["event_count"]:
            blockers.append(f"source event count mismatch: {label}")
            continue
        if artifact.get("started_at") != source["started_at"] or artifact.get("ended_at") != source["ended_at"]:
            blockers.append(f"source artifact time span mismatch: {label}")
            continue
        if not all(isinstance(row, dict) and set(row) == {"kind", "value"} for row in artifact["events"]):
            blockers.append(f"invalid candidate observation events: {label}")
            continue
        for row in artifact["events"]:
            events.append({**row, "source_run_id": label, "source_kind": source["kind"]})
    return sorted(set(blockers)), events


def _scope(work_packages: list[str], root: Path) -> tuple[dict, list[str]]:
    requirements, blockers = {}, []
    for wp in work_packages:
        paths = list((root / "factory/work-packages").glob(f"{wp}-*.md"))
        if len(paths) != 1:
            blockers.append(f"work package unavailable: {wp}")
            continue
        body = paths[0].read_text()
        serves = re.search(r"\*\*Serves:\*\*([^\n]+)", body)
        for req in re.findall(r"(?:BL|IA|IR|IN|XC)-\d+", serves.group(1) if serves else ""):
            requirements.setdefault(req, []).append(wp)
    return requirements, blockers


def _bound(events: list[dict], kind: str, value: object, source_run_id: str | None = None, fresh: bool = False) -> bool:
    return any(e["kind"] == kind and e["value"] == value and
               (source_run_id is None or source_run_id == e["source_run_id"]) and
               (not fresh or e["source_kind"] == "fresh_twin_run") for e in events)


def release_report(candidate: dict, baseline: dict | None = None, *, root: Path | None = None,
                   holdout: dict | None = None, trusted: dict | None = None) -> dict:
    """Compute a deterministic G4 recommendation, never approve a release.

    Unimplemented package done-when checks remain explicitly blocked for human
    review, even when this harness's supported measurements pass.
    """
    root = root or repository_root()
    validate(candidate, BUNDLE_SCHEMA, "candidate bundle")
    if baseline is not None:
        validate(baseline, BUNDLE_SCHEMA, "baseline bundle")
    params = yaml.safe_load((root / "factory/parameters.yaml").read_text())
    pins = oracle_pins(root)
    reqs, blockers = _scope(candidate["work_packages"], root)
    blockers += pins["blockers"]
    source_blockers, events = _verify_sources(candidate.get("sources", []), root, candidate["commit"])
    blockers += source_blockers
    required_sources = params["release_gate"]["replay"]["from_slice_2" if candidate.get("slice", 1) >= 2 else "until_slice_2"]
    for kind in required_sources:
        if not any(e["source_kind"] == kind for e in events):
            blockers.append(f"required replay source unavailable: {kind}")
    if baseline:
        if set(baseline["work_packages"]) - set(candidate["work_packages"]):
            blockers.append("candidate scope drops work packages carried by the baseline")
        old_blockers, _ = _verify_sources(baseline.get("sources", []), root, baseline["commit"])
        blockers += [f"baseline: {b}" for b in old_blockers]
        # An observed baseline is not automatically the last human-approved release.
        blockers.append("baseline G4 human approval record requires independent verification")
    golden = load_json(root / FIXTURES / "golden-graph.json")
    changes = load_json(root / FIXTURES / "change-replay.json")["changes"]
    incidents = load_json(root / FIXTURES / "incident-scenarios.json")["incidents"]
    dbt_golden = load_json(root / FIXTURES / "dbt/golden-dbt.json")
    graph = score_edges(candidate.get("graph", {}), golden, dbt_golden)
    change = replay_changes(candidate.get("changes", []), changes)
    incident = replay_incidents(candidate.get("incidents", []), incidents)
    floors, cases = [], {}

    def floor(name, requirement, value, bar, packages=None):
        holds = value is not None and value >= bar
        floors.append({"metric": name, "requirement": requirement, "work_packages": packages if packages is not None else reqs.get(requirement, []),
                       "bar": bar, "value": value, "holds": holds})
        if not holds:
            blockers.append(f"floor {'unavailable' if value is None else 'failed'}: {name}")

    if "BL-6" in reqs:
        for kind in ("field_edges", "service_edges"):
            for metric in ("precision", "recall"):
                floor(f"{kind}.{metric}", "BL-6", graph["metrics"][kind][metric], params["baseline_accuracy"][kind][metric])
        if "WP-19" in candidate["work_packages"]:
            floor("service_edges.upstream_asserted_recall", "BL-6", graph["metrics"]["service_edges"]["upstream_asserted_recall"], 1.0)
        cases.update(graph["cases"])
    hops = {"WP-20": ["dbt"], "WP-23": ["checkout_orders", "checkout_payment"],
            "WP-24": ["accounting"], "WP-28": ["dashboard_exposure"]}
    selected_hops = set(graph["per_hop"]) if "BL-6" in reqs else {hop for wp in candidate["work_packages"] for hop in hops.get(wp, [])}
    for name in sorted(selected_hops):
        row = graph["per_hop"].get(name, {})
        cases.update({case: graph["cases"][case] for case in row.get("case_ids", [])})
        packages = sorted(set(reqs.get("BL-6", [])) | {wp for wp in candidate["work_packages"] if name in hops.get(wp, [])})
        bars = params["baseline_accuracy"]["deterministic_hops" if name == "accounting" else "per_hop_default"]
        for metric in ("precision", "recall"):
            floor(f"hop.{name}.{metric}", "BL-6" if "BL-6" in reqs else "BL-3", row.get(metric), bars[metric], packages)
    for wp in set(candidate["work_packages"]) & {"WP-22", "WP-25"}:
        floor("hop.complement.recall", "BL-3", None, params["baseline_accuracy"]["per_hop_default"]["recall"], [wp])
    if "WP-20" in candidate["work_packages"]:
        # Report direct and indirect dbt accuracy independently; aggregate success
        # cannot hide all indirect dependencies disappearing.
        for dependency in ("DIRECT", "INDIRECT"):
            wanted = [e for e in dbt_golden["field_edges"] if e["class"] == dependency]
            got = [e for e in candidate.get("graph", {}).get("field_edges", [])
                   if e["class"] == dependency and e["from"].startswith("postgres://") and e["to"].startswith("postgres://")]
            expected_keys, observed_keys = {_edge_key(e, True) for e in wanted}, {_edge_key(e, True) for e in got}
            for metric, denominator in (("precision", len(observed_keys)), ("recall", len(expected_keys))):
                value = len(expected_keys & observed_keys) / denominator if denominator else (0.0 if "graph" in candidate else None)
                floor(f"dbt.{dependency}.{metric}", "BL-3", value, params["baseline_accuracy"]["per_hop_default"][metric], ["WP-20"])
    if "IA-8" in reqs:
        floor("consumer_recall", "IA-8", change["consumer_recall"], params["impact"]["replay_consumer_recall"])
        cases.update(change["cases"])
        if change["missing"]:
            blockers.append("change replay incomplete: " + ", ".join(change["missing"]))
    if "IR-5" in reqs:
        for metric in ("rank_first_share", "rank_top3_share"):
            floor(metric, "IR-5", incident[metric], params["detect_resolve"][metric])
        cases.update(incident["cases"])
        if incident["missing"]:
            blockers.append("incident replay incomplete: " + ", ".join(incident["missing"]))
    for kind, value, applicable in (("graph", candidate.get("graph"), "BL-6" in reqs or bool(selected_hops)),
                                    ("changes", candidate.get("changes"), "IA-8" in reqs),
                                    ("incidents", candidate.get("incidents"), "IR-5" in reqs)):
        if applicable and (value is None or not _bound(events, kind, value)):
            blockers.append(f"{kind} observations not bound to a verified source artifact")
    if "BL-7" in reqs:
        rebuild = candidate.get("rebuild")
        value = int(rebuild["live_sha256"] == rebuild["replayed_sha256"]) if rebuild else None
        floor("rebuild_hash_equal", "BL-7", value, 1)
        if not rebuild or not _bound(events, "rebuild", rebuild, rebuild["source_run_id"]):
            blockers.append("as-of rebuild hash evidence unavailable or unbound")
    lost = []
    if baseline:
        old = {}
        if "BL-6" in reqs or selected_hops:
            old_graph = score_edges(baseline.get("graph", {}), golden, dbt_golden)
            old.update({case: value for case, value in old_graph["cases"].items() if case in cases})
        if "IA-8" in reqs:
            old.update(replay_changes(baseline.get("changes", []), changes)["cases"])
        if "IR-5" in reqs:
            old.update(replay_incidents(baseline.get("incidents", []), incidents)["cases"])
        for name, passed in sorted(old.items()):
            if passed is True and cases.get(name) is not True:
                lost.append({"case": name, "reason": "baseline passed; candidate failed or unavailable", "waived_by": None})
        if lost:
            blockers.append(f"lost cases: {len(lost)}")
    hard_zeros = {}
    carried = set(candidate["work_packages"])
    for name, applicable, key in (("must_not_flow_violations", bool(carried & {"WP-23", "WP-34"}), None),
                                  ("payload_values_stored", "WP-26" in carried, "payload_scan"),
                                  ("blocked_producers_or_merges_in_fault_scenarios", bool(carried & {"WP-18", "WP-53"}), "fault_scenarios")):
        if not applicable:
            hard_zeros[name] = {"status": "not yet carried", "value": None}
            continue
        if key is None:
            value = len(graph["must_not_flow"]) if graph["must_not_flow"] is not None else None
            if not _bound(events, "graph", candidate.get("graph")):
                blockers.append("must-not-flow graph evidence unavailable or unbound")
                if value == 0:
                    value = None
        else:
            observation = candidate.get(key)
            value = sum(r["count"] for r in observation["observations"]) if observation else None
            if not observation or not _bound(events, key, observation, observation["source_run_id"], fresh=True):
                blockers.append(f"{name} observations unavailable or unbound to a fresh twin run")
                if value == 0:
                    value = None
        hard_zeros[name] = {"status": "pass" if value == 0 else "blocked", "value": value}
        if value != 0:
            blockers.append(f"hard zero {'unavailable' if value is None else 'failed'}: {name}")
    timings = []
    bars = {"IA-1": params["impact"]["pr_report_p95_minutes"] * 60,
            "IN-10": params["incremental"]["freshness_p95_minutes"] * 60,
            "IR-1": params["detect_resolve"]["alert_enrichment_p95_minutes"] * 60, "XC-7": 3600}
    measured = {}
    for row in candidate.get("timings", []):
        if row["requirement"] in measured:
            raise EvidenceError("duplicate timing requirement")
        measured[row["requirement"]] = row
    for req, bar in bars.items():
        if req not in reqs:
            timings.append({"requirement": req, "status": "not yet carried", "p95_seconds": None, "bar_seconds": bar})
            continue
        row = measured.get(req)
        bound = row and _bound(events, "timing", row, row["source_run_id"], fresh=True)
        samples = sorted(row["samples_seconds"]) if bound else []
        p95 = samples[math.ceil(len(samples) * 0.95) - 1] if samples else None
        status = "pass" if p95 is not None and p95 <= bar else "blocked"
        timings.append({"requirement": req, "status": status, "p95_seconds": p95, "bar_seconds": bar})
        if status == "blocked":
            blockers.append(f"fresh twin timing {'unavailable' if p95 is None else 'failed'}: {req}")
    families = {"impact" for _ in [0] if "IA-8" in reqs} | {"detect_resolve" for _ in [0] if "IR-5" in reqs}
    private = validate_holdout(holdout, trusted, candidate["commit"], pins, params, families)
    if families:
        blockers += private["blockers"]
    # This candidate does not invent measurements for package-specific done-when
    # lines, human review, scenario conformance, or historical raw capture checks.
    for wp in sorted(carried):
        blockers.append(f"{wp}: full done-when/visible-scenario evidence and human conformance review unavailable")
    if "WP-04" in carried:
        blockers.append("WP-04 historical capture acceptance unavailable until explicit raw run-1 inputs are replayed")
    return {"schema_version": 1, "status": "blocked" if blockers else "pass", "recommendation_only": True,
            "release": {"commit": candidate["commit"], "baseline": baseline["commit"] if baseline else "first release",
                        "work_packages": sorted(carried), "waves_completed": "not declared"},
            "oracle": pins, "replay": {"sources": candidate.get("sources", []),
                "limitation": "Twin only. This replay cannot catch a difference between the twin and production." if candidate.get("slice", 1) < 2 else "Production and twin replay; sources must be verified."},
            "floor": floors, "graph_accuracy": graph, "lost_cases": lost, "no_loss_applicable": baseline is not None,
            "hard_zeros": hard_zeros, "must_not_flow_violations": graph["must_not_flow"], "timings": timings,
            "holdout": private, "cases": cases, "service_levels_declared_held": [],
            "blockers": sorted(set(blockers))}


def render_g4(report: dict, accuracy_path: str, accuracy_sha256: str) -> str:
    """Ten machine-filled sections. Decision remains with the human approver."""
    def table(headers, rows):
        return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                         ["| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in rows])
    unavailable = lambda value: "Unavailable" if value is None else str(value)
    release = report["release"]
    sections = {
        "Release": f"- Commit: `{release['commit']}`\n- Baseline: {release['baseline']}\n- Change record: {', '.join(release['work_packages'])}\n- Waves this release completes: {release['waves_completed']}\n\nCandidate recommendation: **{report['status']}**. Human approval is pending.",
        "Oracle": table(["File", "SHA-256", "Equals the G3 record"], [[r["path"], r["sha256"], r["matches"]] for r in report["oracle"]["files"]]),
        "Replay": report["replay"]["limitation"] + "\n\n" + table(["Source", "Time span", "Events"], [[s["path"], f"{s['started_at']} to {s['ended_at']}", s["event_count"]] for s in report["replay"]["sources"]]),
        "Floor": table(["Metric", "Work package", "Bar", "Value", "Holds"], [[r["metric"], ", ".join(r["work_packages"]), r["bar"], unavailable(r["value"]), r["holds"]] for r in report["floor"]]),
        "Lost cases": "Not applicable: first release" if not report["no_loss_applicable"] else (table(["Case", "Metric", "Reason", "Waived by"], [[r["case"], "case success", r["reason"], "None"] for r in report["lost_cases"]]) if report["lost_cases"] else "None"),
        "Hard zeros": table(["Count", "Value"], [[name, value["status"] if value["status"] == "not yet carried" else unavailable(value["value"])] for name, value in report["hard_zeros"].items()]),
        "Timings": table(["Requirement", "Bar (p95 seconds)", "Measured", "Holds"], [[r["requirement"], r["bar_seconds"], unavailable(r["p95_seconds"]), r["status"]] for r in report["timings"]]),
        "Holdout": report["holdout"]["label"] + "\n\n" + table(["Family", "Pass rate", "Bar"], [[f, r["pass_rate"], r["bar"]] for f, r in sorted(report["holdout"]["families"].items())]),
        "Accuracy report": f"- Path: `{accuracy_path}`\n- SHA-256: `{accuracy_sha256}`",
        "Service levels declared held": "None. This candidate report does not approve a release.\n\nBlocking evidence:\n\n" + "\n".join(f"- {b}" for b in report["blockers"]),
    }
    return "# G4 candidate evidence (Decision intentionally omitted)\n\n" + "\n\n".join(f"## {name}\n\n{sections[name]}" for name in G4_SECTIONS) + "\n"


def _write(value: dict, output: str | None) -> None:
    data = canonical_bytes(value)
    if output:
        Path(output).write_bytes(data)
    else:
        print(data.decode(), end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score", help="score candidate edges or an explicitly supplied raw trace capture")
    source = score.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate")
    source.add_argument("--capture")
    score.add_argument("--output")
    replay = sub.add_parser("replay", help="score independently observed change/incident outcomes")
    replay.add_argument("kind", choices=["changes", "incidents"])
    source = replay.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate")
    source.add_argument("--capture")
    replay.add_argument("--events")
    replay.add_argument("--candidate-graph")
    replay.add_argument("--output")
    release = sub.add_parser("release", help="write a G4 recommendation; never an approval")
    release.add_argument("--candidate", required=True)
    release.add_argument("--baseline")
    release.add_argument("--holdout")
    release.add_argument("--trusted-policy")
    release.add_argument("--output", required=True)
    release.add_argument("--record")
    gate = sub.add_parser("gate", help="verify the current G3 oracle pins")
    gate.add_argument("action", choices=["verify"])
    gate.add_argument("--output")
    custody = sub.add_parser("custody", help="validate WP-02 custody and coverage without reading holdout cases")
    custody.add_argument("--visible-metadata")
    custody.add_argument("--aggregate")
    custody.add_argument("--trusted-policy")
    custody.add_argument("--commit", default="unconfigured")
    custody.add_argument("--output")
    private = sub.add_parser("holdout", help="validate private-job aggregate; never reads the private store")
    private.add_argument("--aggregate")
    private.add_argument("--trusted-policy")
    private.add_argument("--commit", required=True)
    private.add_argument("--output")
    args = parser.parse_args(argv)
    root = repository_root()
    try:
        if args.command == "gate":
            report = oracle_pins(root)
        elif args.command == "score":
            report = capture_score(Path(args.capture), root) if args.capture else score_edges(load_json(args.candidate), load_json(root / FIXTURES / "golden-graph.json"))
        elif args.command == "replay":
            if args.capture:
                if args.kind != "incidents" or not args.events or not args.candidate_graph:
                    raise EvidenceError("raw incident replay requires --events and --candidate-graph; changes require candidate outcome JSON")
                report = capture_incidents(Path(args.capture), Path(args.events), Path(args.candidate_graph), root)
            else:
                truth = load_json(root / FIXTURES / ("change-replay.json" if args.kind == "changes" else "incident-scenarios.json"))[args.kind]
                candidate = load_json(args.candidate)
                report = (replay_changes if args.kind == "changes" else replay_incidents)(candidate, truth)
        elif args.command == "release":
            report = release_report(load_json(args.candidate), load_json(args.baseline) if args.baseline else None, root=root,
                                    holdout=load_json(args.holdout) if args.holdout else None,
                                    trusted=load_json(args.trusted_policy) if args.trusted_policy else None)
        elif args.command == "custody":
            report = validate_custody(load_json(args.visible_metadata) if args.visible_metadata else None,
                                      load_json(args.aggregate) if args.aggregate else None,
                                      load_json(args.trusted_policy) if args.trusted_policy else None, args.commit, root)
        else:
            report = validate_holdout(load_json(args.aggregate) if args.aggregate else None,
                                      load_json(args.trusted_policy) if args.trusted_policy else None,
                                      args.commit, oracle_pins(root), yaml.safe_load((root / "factory/parameters.yaml").read_text()))
    except (EvidenceError, OSError) as exc:
        report = {"status": "blocked", "blockers": [str(exc)]}
    _write(report, args.output)
    if args.command == "release" and args.record and "release" in report:
        Path(args.record).write_text(render_g4(report, args.output, sha256(Path(args.output))))
    return 2 if report.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
