"""Synthetic harness regressions; these are NOT release or holdout evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest
import yaml

from lineage.evaluation import (
    AGGREGATE_SCHEMA, BUNDLE_SCHEMA, EvidenceError, FIXTURES, G4_SECTIONS,
    canonical_bytes, capture_incidents, capture_score, load_json, main,
    must_not_flow, oracle_pins, release_report, render_g4, replay_changes,
    replay_incidents, run_private, score_edges, sha256, validate, validate_custody,
    validate_holdout,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def truth():
    return load_json(ROOT / FIXTURES / "golden-graph.json")


@pytest.fixture
def graph(truth):
    # Copying public truth here creates a controlled test input, not a measurement.
    dbt = load_json(ROOT / FIXTURES / "dbt/golden-dbt.json")
    graph = {kind: [{k: e[k] for k in ("from", "to", "type", "class", "subtype", "masking", "condition") if k in e} for e in truth[kind]]
             for kind in ("service_edges", "field_edges", "gated_field_edges", "flag_edges")}
    graph["field_edges"] += [{k: e[k] for k in ("from", "to", "class", "subtype") if k in e} for e in dbt["field_edges"]]
    graph["dataset_edges"] = [{k: e[k] for k in ("from", "to", "type")} for e in dbt["dataset_edges"]]
    return graph


@pytest.fixture
def candidate(graph):
    changes = load_json(ROOT / FIXTURES / "change-replay.json")["changes"]
    incidents = load_json(ROOT / FIXTURES / "incident-scenarios.json")["incidents"]
    return {"schema_version": 1, "commit": "synthetic-test-only", "work_packages": ["WP-04", "WP-23", "WP-26", "WP-53"],
            "graph": graph,
            "changes": [{"id": r["id"], "readers": r["expected_readers"], "gate": r["expected_gate"]} for r in changes],
            "incidents": [{"id": r["id"], "detected": True, "ranking": [r.get("flag") or "accounting"], "minutes_to_detect": 2.0} for r in incidents]}


def test_all_eight_oracle_pins_match():
    report = oracle_pins(ROOT)
    assert report["status"] == "pass"
    assert len(report["files"]) == 8
    assert all(len(row["sha256"]) == 64 and row["matches"] for row in report["files"])


def test_seed_lost_golden_field_edge_above_floor(candidate):
    current = deepcopy(candidate)
    removed = current["graph"]["field_edges"].pop()
    report = release_report(current, candidate, root=ROOT)
    assert report["status"] == "blocked"
    assert any(removed["from"] in row["case"] and removed["to"] in row["case"] for row in report["lost_cases"])
    recall = next(row for row in report["floor"] if row["metric"] == "field_edges.recall")
    assert recall["value"] > recall["bar"]


def test_seed_forbidden_card_edge_is_unwaivable(candidate):
    current = deepcopy(candidate)
    current["graph"]["field_edges"].append({"from": "api://otel-demo/checkout/PlaceOrder/request#credit_card.credit_card_number",
                                               "to": "kafka://otel-demo/orders#credit_card", "class": "DIRECT", "subtype": "IDENTITY"})
    report = release_report(current, candidate, root=ROOT)
    assert report["hard_zeros"]["must_not_flow_violations"]["value"] > 0
    assert "hard zero failed: must_not_flow_violations" in report["blockers"]


def test_seed_rank_first_to_second_caught_above_both_floors(candidate):
    current = deepcopy(candidate)
    current["incidents"][0]["ranking"].insert(0, "decoy")
    report = release_report(current, candidate, root=ROOT)
    assert any(row["case"] == "incident:I1:rank_first" for row in report["lost_cases"])
    values = {row["metric"]: row for row in report["floor"]}
    assert values["rank_first_share"]["holds"]
    assert values["rank_top3_share"]["holds"]


def test_identical_inputs_deterministic_and_no_lost_cases(candidate):
    reports = [release_report(candidate, candidate, root=ROOT) for _ in range(3)]
    assert len({canonical_bytes(report) for report in reports}) == 1
    assert reports[0]["lost_cases"] == []
    assert reports[0]["status"] == "blocked"  # absent operational evidence cannot become zero
    assert reports[0]["hard_zeros"]["payload_values_stored"]["value"] is None
    assert reports[0]["hard_zeros"]["blocked_producers_or_merges_in_fault_scenarios"]["value"] is None
    assert reports[0]["service_levels_declared_held"] == []


def test_first_release_skips_only_no_loss(candidate):
    report = release_report(candidate, root=ROOT)
    assert not report["no_loss_applicable"]
    assert report["lost_cases"] == []
    assert report["floor"]
    assert report["status"] == "blocked"
    assert any("fresh_twin_run" in b for b in report["blockers"])
    assert any("holdout" in b for b in report["blockers"])


def test_work_package_scope_not_every_possible_metric():
    report = release_report({"schema_version": 1, "commit": "test", "work_packages": ["WP-10"]}, root=ROOT)
    assert report["floor"] == []
    assert all(row["status"] == "not yet carried" for row in report["timings"])
    assert all(row["status"] == "not yet carried" for row in report["hard_zeros"].values())
    assert not any("holdout" in b for b in report["blockers"])


def test_missing_outcomes_are_unavailable_and_not_success():
    changes = load_json(ROOT / FIXTURES / "change-replay.json")["changes"]
    incidents = load_json(ROOT / FIXTURES / "incident-scenarios.json")["incidents"]
    assert replay_changes([], changes)["consumer_recall"] is None
    assert replay_incidents([], incidents)["rank_first_share"] is None
    assert all(v is None for v in replay_incidents([], incidents)["cases"].values())


def test_replay_rejects_duplicate_and_unknown_case_ids(candidate):
    truth = load_json(ROOT / FIXTURES / "incident-scenarios.json")["incidents"]
    with pytest.raises(EvidenceError, match="duplicate"):
        replay_incidents(candidate["incidents"] * 2, truth)
    with pytest.raises(EvidenceError, match="absent"):
        replay_incidents([{"id": "I999", "detected": False, "ranking": [], "minutes_to_detect": None}], truth)


def test_schema_rejects_precomputed_success(candidate):
    candidate["passed"] = True
    with pytest.raises(EvidenceError, match="schema"):
        release_report(candidate, root=ROOT)


def test_truth_rank_is_not_accepted():
    with pytest.raises(EvidenceError, match="schema"):
        replay_incidents([{"id": "I1", "detected": True, "rank": 1, "ranking": [], "minutes_to_detect": 2}], [])


def test_transitive_latent_forbidden_flow_walk():
    graph = {"field_edges": [{"from": "api#credit_card.number", "to": "internal#item[]", "state": "latent"},
                               {"from": "internal#item[]", "to": "topic#payload"}]}
    assert must_not_flow(graph, [{"from": "api#credit_card.*", "to": "topic"}])
    assert must_not_flow(graph, [{"from": "internal#item[]", "to": "topic"}])


def test_template_contains_exact_ten_sections_and_pins_report(candidate):
    report = release_report(candidate, root=ROOT)
    content = render_g4(report, "evaluation/report.json", hashlib.sha256(canonical_bytes(report)).hexdigest())
    assert re.findall(r"^## (.+)$", content, re.M) == list(G4_SECTIONS)
    assert "## Decision" not in content
    assert "Visible only" in content
    assert "Not applicable: first release" in content


def test_summaries_cannot_reproduce_historical_capture():
    folder = ROOT / FIXTURES / "capture-2026-11-27"
    with pytest.raises(EvidenceError, match="raw capture unavailable"):
        capture_score(folder, ROOT)
    with pytest.raises(EvidenceError, match="raw capture unavailable"):
        capture_incidents(folder, folder / "change-events.jsonl", folder / "observed-edges.json", ROOT)


def test_raw_trace_extraction_uses_actual_spans(tmp_path):
    def resource(service, span):
        return {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                "scopeSpans": [{"spans": [span]}]}
    export = {"resourceSpans": [resource("frontend", {"traceId": "t", "spanId": "1", "kind": 3}),
                                 resource("checkout", {"traceId": "t", "spanId": "2", "parentSpanId": "1", "kind": 2})]}
    (tmp_path / "traces.jsonl").write_text(json.dumps(export) + "\n")
    report = capture_score(tmp_path, ROOT)
    assert report["metrics"]["service_edges"]["observed"] == 1
    assert report["metrics"]["field_edges"]["observed"] is None
    assert report["source"]["sha256"] == sha256(tmp_path / "traces.jsonl")


def _source(tmp_path, commit, kind, run_id, events):
    content = {"run_id": run_id, "commit": commit, "started_at": "2026-11-28T00:00:00Z",
               "ended_at": "2026-11-28T00:01:00Z", "events": events}
    path = tmp_path / f"{run_id}.json"
    path.write_bytes(canonical_bytes(content))
    return {"kind": kind, "path": str(path), "sha256": sha256(path), "run_id": run_id, "commit": commit,
            "started_at": content["started_at"], "ended_at": content["ended_at"], "event_count": len(events)}


def test_fresh_timing_p95_is_measured_and_digest_bound(tmp_path):
    candidate = {"schema_version": 1, "commit": "test", "work_packages": ["WP-30"]}
    timing = {"requirement": "IN-10", "source_run_id": "fresh", "samples_seconds": [10] * 19 + [1000]}
    candidate["timings"] = [timing]
    candidate["sources"] = [_source(tmp_path, "test", "fresh_twin_run", "fresh", [{"kind": "timing", "value": timing}])]
    report = release_report(candidate, root=ROOT)
    result = next(t for t in report["timings"] if t["requirement"] == "IN-10")
    assert result["status"] == "pass" and result["p95_seconds"] == 10
    candidate["sources"][0]["sha256"] = "0" * 64
    report = release_report(candidate, root=ROOT)
    result = next(t for t in report["timings"] if t["requirement"] == "IN-10")
    assert result["p95_seconds"] is None and result["status"] == "blocked"


def test_hard_zero_counts_require_fresh_source_observations(tmp_path):
    observation = {"source_run_id": "fresh", "observations": [{"name": "broker_down", "count": 0}]}
    candidate = {"schema_version": 1, "commit": "test", "work_packages": ["WP-53"], "fault_scenarios": observation}
    candidate["sources"] = [_source(tmp_path, "test", "fresh_twin_run", "fresh", [{"kind": "fault_scenarios", "value": observation}])]
    report = release_report(candidate, candidate, root=ROOT)
    assert report["lost_cases"] == []
    assert report["hard_zeros"]["blocked_producers_or_merges_in_fault_scenarios"]["value"] == 0
    observation["observations"][0]["count"] = 1
    report = release_report(candidate, root=ROOT)
    assert any("unbound" in b for b in report["blockers"])
    assert report["hard_zeros"]["blocked_producers_or_merges_in_fault_scenarios"]["status"] == "blocked"


def test_wp02_reports_real_corpus_gaps_without_generating_cases():
    result = validate_custody(root=ROOT)
    assert result["status"] == "blocked"
    assert result["visible"]["changes"]["visible"] == 13
    assert result["visible"]["incidents"]["visible"] == 10
    assert "two_changes_one_service" in result["visible"]["incidents"]["uncovered_families"]
    assert result["holdout"]["families"] == {}


def test_private_runner_not_configured_is_blocked():
    assert run_private({"candidate_commit": "x"}, None, None, ROOT)["status"] == "blocked"


def _aggregate():
    params = yaml.safe_load((ROOT / "factory/parameters.yaml").read_text())
    pins = oracle_pins(ROOT)
    corpora = {}
    for kind, family_key in [("changes", "change_families"), ("incidents", "incident_families")]:
        families = params["corpora"][family_key]
        corpora[kind] = {"visible": len(families) * 2, "holdout": len(families),
                         "families": {f: {"visible": 2, "holdout": 1} for f in families}}
    report = {"schema_version": 1,
        "provenance": {"store_id": "private-test", "job_id": "independent-test", "run_id": "test-run", "candidate_commit": "test",
                       "oracle_sha256": {r["path"]: r["sha256"] for r in pins["files"]}, "independent_author": "test-custodian",
                       "approved_by": "test-platform-lead", "builders_cannot_read": True},
        "families": {f: {"total": 10, "passed": 10, "failure_categories": {}} for f in params["factory"]["holdout_pass_rate"]},
        "corpora": corpora, "signatures": {"owners": ["test-owner"], "platform_lead": "test-platform-lead"},
        "coverage": {k: True for k in ("near_simultaneous_changes", "silent_failure", "caller_cause", "targeting_rule", "no_visible_copies")}}
    policy = {k: report["provenance"][k] for k in ("store_id", "job_id", "approved_by", "independent_author")}
    policy.update(aggregate_sha256=hashlib.sha256(canonical_bytes(report)).hexdigest(), required_owner_signatures=["test-owner"])
    return report, policy, params, pins


def test_private_aggregate_verified_only_with_independent_policy():
    report, policy, params, pins = _aggregate()
    assert validate_holdout(report, policy, "test", pins, params, {"platform"})["status"] == "pass"
    assert validate_holdout(report, None, "test", pins, params)["status"] == "blocked"
    assert validate_holdout(report, policy, "other-commit", pins, params)["status"] == "blocked"
    report["provenance"]["oracle_sha256"] = {}
    assert validate_holdout(report, policy, "test", pins, params)["status"] == "blocked"


def test_private_cases_and_arbitrary_failure_text_are_rejected_without_echo():
    report, policy, params, pins = _aggregate()
    report["cases"] = ["SENSITIVE HOLDOUT TEXT"]
    with pytest.raises(EvidenceError) as error:
        validate_holdout(report, policy, "test", pins, params)
    assert "SENSITIVE" not in str(error.value)
    del report["cases"]
    report["families"]["platform"]["failure_categories"] = {"SENSITIVE HOLDOUT TEXT": 1}
    with pytest.raises(EvidenceError) as error:
        validate_holdout(report, policy, "test", pins, params)
    assert "SENSITIVE" not in str(error.value)


def test_custody_one_third_per_family_not_just_global_share():
    report, policy, params, pins = _aggregate()
    report["corpora"]["changes"]["families"]["retype"] = {"visible": 3, "holdout": 0}
    result = validate_holdout(report, policy, "test", pins, params)
    assert "changes/retype: at least one third must be holdout" in result["blockers"]


def test_cli_blocks_missing_raw_input_and_produces_json(tmp_path):
    output = tmp_path / "report.json"
    assert main(["score", "--capture", str(tmp_path / "missing"), "--output", str(output)]) == 2
    assert load_json(output)["status"] == "blocked"
    assert main(["gate", "verify", "--output", str(output)]) == 0
    assert len(load_json(output)["files"]) == 8


def test_raw_metrics_are_replayed_with_candidate_dependencies(tmp_path, capsys, caplog):
    from datetime import datetime, timezone
    def attrs(values):
        return [{"key": key, "value": {"stringValue": value}} for key, value in values.items()]
    origin = datetime(2026, 11, 28, tzinfo=timezone.utc).timestamp()
    points = []
    failing = []
    for minute in range(21):
        timestamp = str(int((origin + minute * 60) * 1e9))
        for status, value in [("STATUS_CODE_UNSET", minute * 100), ("STATUS_CODE_ERROR", max(0, minute - 13) * 20)]:
            points.append({"timeUnixNano": timestamp, "asInt": str(value), "attributes": attrs({
                "service.name": "checkout", "span.kind": "SPAN_KIND_SERVER", "span.name": "oteldemo.CheckoutService/PlaceOrder", "status.code": status,
                "db.query.text": "EXECUTE secret_stmt('SYNTHETIC_PAYLOAD_SENTINEL')"})})
        failing.append({"timeUnixNano": timestamp, "asInt": str(max(0, minute - 13) * 20),
                        "attributes": attrs({"client": "checkout", "server": "payment"})})
    export = {"resourceMetrics": [{"scopeMetrics": [{"metrics": [
        {"name": "traces.span.metrics.calls", "sum": {"dataPoints": points}},
        {"name": "traces_service_graph_request_failed_total", "sum": {"dataPoints": failing}},
    ]}]}]}
    (tmp_path / "metrics.jsonl").write_text(json.dumps(export) + "\n")
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"at": "2026-11-28T00:12:00Z", "kind": "flag_change", "flag": "paymentFailure",
                                 "urn": "flag://otel-demo/paymentFailure", "from": "off", "to": "50%"}) + "\n")
    graph = tmp_path / "candidate-graph.json"
    graph.write_text(json.dumps({"service_edges": [{"from": "svc://otel-demo/checkout", "to": "svc://otel-demo/payment", "type": "CALLS"}],
                                  "flag_edges": [{"from": "flag://otel-demo/paymentFailure", "to": "svc://otel-demo/payment"}]}))
    report = capture_incidents(tmp_path, events, graph, ROOT)
    row = next(row for row in report["results"] if row["id"] == "I1")
    assert row["minutes_to_detect"] == 2.0 and row["rank"] == 1
    assert report["observations"][0]["ranking"][0] == "paymentFailure"
    assert report["status"] == "blocked"  # the other nine public cases were not replayed
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert not caplog.records
    assert "SYNTHETIC_PAYLOAD_SENTINEL" not in json.dumps(report)


def test_unbound_zero_is_unavailable_not_measured_success():
    result = release_report({"schema_version": 1, "commit": "test", "work_packages": ["WP-53"],
                             "fault_scenarios": {"source_run_id": "absent", "observations": [{"name": "fault", "count": 0}]}}, root=ROOT)
    value = result["hard_zeros"]["blocked_producers_or_merges_in_fault_scenarios"]
    assert value == {"status": "blocked", "value": None}


def test_nonfinite_measurements_are_rejected():
    with pytest.raises(EvidenceError, match="invalid JSON"):
        validate({"schema_version": 1, "commit": "test", "work_packages": ["WP-30"],
                  "timings": [{"requirement": "IN-10", "source_run_id": "x", "samples_seconds": [float('nan')]}]}, BUNDLE_SCHEMA, "bundle")


def test_unknown_private_corpus_family_does_not_echo_text():
    report, policy, params, pins = _aggregate()
    report["corpora"]["changes"]["families"]["PRIVATE CASE TEXT"] = {"visible": 2, "holdout": 1}
    with pytest.raises(EvidenceError) as error:
        validate_holdout(report, policy, "test", pins, params)
    assert "PRIVATE CASE TEXT" not in str(error.value)


def test_empty_private_score_families_cannot_pass():
    report, policy, params, pins = _aggregate()
    report["families"] = {}
    policy["aggregate_sha256"] = hashlib.sha256(canonical_bytes(report)).hexdigest()
    result = validate_holdout(report, policy, "test", pins, params)
    assert result["status"] == "blocked"
    assert "platform: holdout family result unavailable" in result["blockers"]


def test_complete_reference_and_dbt_oracles_are_scored(graph, truth):
    full = score_edges(graph, truth)
    assert full["status"] == "pass"
    assert full["metrics"]["field_edges"]["expected"] == 71
    assert full["metrics"]["gated_field_edges"]["expected"] == 8
    assert full["metrics"]["flag_edges"]["expected"] == 20
    assert full["per_hop"]["dbt"]["recall"] == 1.0
    assert full["per_hop"]["accounting"]["expected"] == 17
    assert full["per_edge_type"]["field_edges:INDIRECT/JOIN"]["expected"] > 0
    graph["field_edges"] = graph["field_edges"][:36]
    result = score_edges(graph, truth)
    assert result["status"] == "blocked"
    assert result["metrics"]["field_edges"]["recall"] == 36 / 71
    assert result["per_hop"]["dbt"]["recall"] == 0


def test_field_semantics_cannot_be_omitted_or_mutated(graph, truth):
    current = deepcopy(graph)
    del current["field_edges"][0]["class"]
    with pytest.raises(EvidenceError):
        score_edges(current, truth)
    current = deepcopy(graph)
    current["field_edges"][0]["subtype"] = "TRANSFORMATION"
    result = score_edges(current, truth)
    assert result["metrics"]["field_edges"]["recall"] == 70 / 71
    assert any(not value for key, value in result["cases"].items() if key.startswith("field_edges:"))
    current = deepcopy(graph)
    masked = next(e for e in current["gated_field_edges"] if e.get("masking"))
    masked["masking"] = False
    result = score_edges(current, truth)
    assert result["metrics"]["gated_field_edges"]["recall"] == 7 / 8
    assert result["status"] == "blocked"


def test_extractor_only_scope_grades_own_hop_and_detects_losses(candidate):
    candidate["work_packages"] = ["WP-20"]
    baseline = deepcopy(candidate)
    candidate["graph"]["field_edges"] = candidate["graph"]["field_edges"][:36]
    report = release_report(candidate, baseline, root=ROOT)
    assert any(row["metric"] == "hop.dbt.recall" and row["value"] == 0 for row in report["floor"])
    assert len(report["lost_cases"]) == 35
    assert all("postgres://" in row["case"] for row in report["lost_cases"])
    assert not any(row["metric"].startswith("hop.accounting") for row in report["floor"])


def test_dbt_indirect_loss_not_hidden_by_aggregate(candidate):
    candidate["work_packages"] = ["WP-20"]
    candidate["graph"]["field_edges"] = [e for e in candidate["graph"]["field_edges"] if e["class"] != "INDIRECT"]
    report = release_report(candidate, root=ROOT)
    assert any(row["metric"] == "dbt.INDIRECT.recall" and row["value"] == 0 for row in report["floor"])


def test_three_cli_release_outputs_are_byte_identical(candidate, tmp_path):
    bundle = tmp_path / "candidate.json"
    output = tmp_path / "accuracy.json"
    record = tmp_path / "candidate.md"
    bundle.write_bytes(canonical_bytes(candidate))
    outputs = []
    for _ in range(3):
        assert main(["release", "--candidate", str(bundle), "--output", str(output), "--record", str(record)]) == 2
        outputs.append((output.read_bytes(), record.read_bytes()))
    assert len(set(outputs)) == 1
    assert sha256(output) in record.read_text()
    assert len(re.findall(r"^## ", record.read_text(), re.M)) == 10


@pytest.mark.parametrize("statement", [
    "EXECUTE secret_stmt('SYNTHETIC_PAYLOAD_SENTINEL')",
    "DO $$ BEGIN RAISE NOTICE 'SYNTHETIC_PAYLOAD_SENTINEL'; END $$",
    "INSERT INTO accounting.shipping (order_id) VALUES ('SYNTHETIC_PAYLOAD_SENTINEL'",
    "SELECT 'SYNTHETIC_PAYLOAD_SENTINEL",
    "EXECUTE secret_stmt('INSERT INTO SYNTHETIC_PAYLOAD_SENTINEL (value) VALUES (1)')",
])
def test_raw_evaluation_sql_values_never_escape_logs_or_report(tmp_path, capsys, caplog, statement):
    attributes = [{"key": key, "value": {"stringValue": value}}
                  for key, value in {"db.system.name": "postgresql", "db.query.text": statement}.items()]
    export = {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "accounting"}}]},
        "scopeSpans": [{"spans": [{"traceId": "trace", "spanId": "span", "kind": 3, "attributes": attributes}]}],
    }]}
    (tmp_path / "traces.jsonl").write_text(json.dumps(export) + "\n")
    report = capture_score(tmp_path, ROOT)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert not caplog.records
    assert "SYNTHETIC_PAYLOAD_SENTINEL" not in json.dumps(report)
    assert report["metrics"]["service_edges"]["observed"] == 0
    assert all(row["observed"] == 0 for row in report["per_edge_type"].values() if row["observed"] is not None)


def test_raw_evaluation_preserves_supported_sql_metadata(tmp_path, capsys, caplog):
    from lineage.evaluation import _legacy
    module = _legacy(ROOT, "observed_edges")
    statement = (
        "INSERT INTO accounting.shipping (order_id, zip_code) VALUES ('SYNTHETIC_PAYLOAD_SENTINEL', '12345'); "
        "UPDATE accounting.shipping SET zip_code = 'SYNTHETIC_PAYLOAD_SENTINEL'; "
        "DELETE FROM accounting.shipping WHERE order_id = 'SYNTHETIC_PAYLOAD_SENTINEL'; "
        "SELECT s.order_id, s.zip_code FROM accounting.shipping s WHERE s.zip_code = 'SYNTHETIC_PAYLOAD_SENTINEL'"
    )
    assert module.sql_access(statement) == [
        ("WRITES", "accounting.shipping", ["order_id", "zip_code"]),
        ("WRITES", "accounting.shipping", ["zip_code"]),
        ("WRITES", "accounting.shipping", []),
        ("READS", "accounting.shipping", ["order_id", "zip_code"]),
    ]
    export = {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "accounting"}}]},
        "scopeSpans": [{"spans": [{"traceId": "trace", "spanId": "span", "kind": 3, "attributes": [
            {"key": "db.system.name", "value": {"stringValue": "postgresql"}},
            {"key": "db.query.text", "value": {"stringValue": statement}},
        ]}]}],
    }]}
    (tmp_path / "traces.jsonl").write_text(json.dumps(export) + "\n")
    report = capture_score(tmp_path, ROOT)
    assert report["per_edge_type"]["service_edges:WRITES"]["observed"] == 1
    assert report["per_edge_type"]["service_edges:READS"]["observed"] == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert not caplog.records
    assert "SYNTHETIC_PAYLOAD_SENTINEL" not in json.dumps(report)
