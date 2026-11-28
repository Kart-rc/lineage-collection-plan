"""Synthetic captures test only WP-03 smoke scoring, never live workload acceptance."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("twin_smoke", ROOT / "twin/smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
TIME = "1795824000000000000"
SENTINEL = "SYNTHETIC_PAYLOAD_SENTINEL"


def attrs(values):
    return [{"key": key, "value": {"stringValue": value}} for key, value in values.items()]


def span(identity, kind, parent="", attributes=None):
    return {"traceId": "synthetic", "spanId": identity, "parentSpanId": parent,
            "startTimeUnixNano": TIME, "kind": kind, "attributes": attrs(attributes or {})}


def resource(name, *spans):
    return {"resource": {"attributes": attrs({"service.name": name})}, "scopeSpans": [{"spans": list(spans)}]}


def write_capture(folder, *, target="checkout", control=False, statement=None, payload=False):
    resources = [resource("frontend", span("one", 3)), resource(target, span("two", 2, "one", {"payload": SENTINEL} if payload else {}))]
    if control:
        resources += [resource("checkout", span("three", 3)), resource("flagd", span("four", 2, "three"))]
    if statement:
        resources += [resource("accounting", span("db", 3, attributes={"db.system.name": "postgresql", "db.query.text": statement}))]
    path = folder / "traces.jsonl"
    path.write_text(json.dumps({"resourceSpans": resources}) + "\n")
    return path


def test_exact_precision_comparison_never_rounds_up():
    result = smoke.precision_check(2374, 2500, 2500, 0.95)
    assert f"{result['value']:.2f}" == "0.95"
    assert result["value"] == 0.9496 and not result["holds"]
    assert smoke.precision_check(19, 20, 20, 0.95)["holds"]
    assert not smoke.precision_check(0, 0, 20, 0.95)["holds"]
    assert smoke.precision_check(0, 0, 20, 0.95)["value"] is None


def test_actual_raw_files_processed_with_control_edges_separate(tmp_path):
    path = write_capture(tmp_path, control=True)
    window = {"started_at": "2026-11-28T00:00:00Z", "ended_at": "2026-11-28T00:10:00Z", "duration_seconds": 600,
              "ignored_payload": SENTINEL}
    result = smoke.score_capture(tmp_path, window)
    assert result["status"] == "pass", result
    assert result["raw_capture_replayed"] is True
    assert result["replay_scope"] == ["traces.jsonl"]
    assert result["precision"]["hit"] == result["precision"]["observed"] == 1
    assert result["precision"]["bar"] == 0.95
    assert result["counts"]["data_edges"] == result["counts"]["control_edges"] == 1
    assert result["edges"]["control"][0]["to"] == "svc://otel-demo/flagd"
    assert all(edge["to"] != "svc://otel-demo/flagd" for edge in result["edges"]["extra"])
    raw = result["raw_files"]["traces.jsonl"]
    assert raw["sha256"] == sha256(path.read_bytes()).hexdigest()
    assert raw["size_bytes"] == raw["max_complete_jsonl_line_bytes"] == path.stat().st_size
    assert raw["complete_jsonl_lines"] == 1 and raw["trailing_bytes"] == 0
    assert raw["processed"] and raw["jsonl_validated"]
    assert result["run_window"]["duration_seconds"] == 600
    assert result["run_window"]["verified_by_this_scorer"] is False
    assert not any(result["claims"].values())
    assert SENTINEL not in json.dumps(result)


def test_false_edge_fails_but_actual_replay_is_acknowledged(tmp_path):
    write_capture(tmp_path, target="payment")  # frontend -> payment is not in the oracle
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "blocked"
    assert result["failure_categories"] == ["precision_below_floor"]
    assert result["precision"]["value"] == 0
    assert result["raw_capture_replayed"] is True
    assert result["edges"]["extra"] == [{"from": "svc://otel-demo/frontend", "type": "CALLS", "to": "svc://otel-demo/payment"}]


@pytest.mark.parametrize("contents,category", [(None, "raw_capture_missing"), (b"", "empty_capture"),
    (b'{"resourceSpans":', "truncated_jsonl"), (b'{"resourceSpans":}\n', "malformed_jsonl"),
    (b'{}\n', "invalid_otlp"), (b'{"resourceSpans":[{"scopeSpans":[{"spans":[{}]}]}]}\n', "invalid_otlp")])
def test_missing_empty_malformed_and_truncated_captures_cannot_pass(tmp_path, contents, category):
    if contents is not None:
        (tmp_path / "traces.jsonl").write_bytes(contents)
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "blocked"
    assert category in result["failure_categories"]
    assert result["raw_capture_replayed"] is False
    assert result["precision"] is None


def test_valid_but_empty_export_has_no_precision_success(tmp_path):
    (tmp_path / "traces.jsonl").write_text('{"resourceSpans": []}\n')
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "blocked"
    assert result["failure_categories"] == ["no_service_edges"]
    assert result["precision"]["value"] is None


def test_metrics_are_validated_and_inventoried_but_not_claimed_replayed(tmp_path):
    write_capture(tmp_path)
    (tmp_path / "metrics.jsonl").write_text('{"resourceMetrics": []}\n')
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "pass"
    assert result["raw_files"]["metrics.jsonl"]["jsonl_validated"]
    assert not result["raw_files"]["metrics.jsonl"]["processed"]
    assert "metrics.jsonl" not in result["replay_scope"]


@pytest.mark.parametrize("statement", ["EXECUTE secret_stmt('SYNTHETIC_PAYLOAD_SENTINEL')",
    "INSERT INTO accounting.shipping (order_id) VALUES ('SYNTHETIC_PAYLOAD_SENTINEL'",
    "INSERT INTO accounting.shipping (order_id) VALUES ('SYNTHETIC_PAYLOAD_SENTINEL')"])
def test_payload_sentinels_never_escape_report_logs_or_new_files(tmp_path, capsys, caplog, statement):
    write_capture(tmp_path, payload=True, statement=statement)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "pass", result
    assert SENTINEL not in json.dumps(result)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert not caplog.records


def test_payload_disguised_as_unknown_service_urn_is_redacted_not_dropped(tmp_path):
    write_capture(tmp_path, target="svc://otel-demo/" + SENTINEL)
    result = smoke.score_capture(tmp_path)
    assert result["status"] == "blocked"
    assert result["precision"]["observed"] == 1 and result["precision"]["hit"] == 0
    assert result["counts"]["redacted_endpoints"] == 1
    assert result["edges"]["extra"][0]["to"] is None
    assert SENTINEL not in json.dumps(result)


def test_streaming_stats_cover_multiple_lines_and_trailing_bytes(tmp_path):
    content = b'{"resourceSpans":[]}\n' * 2 + b'{partial'
    (tmp_path / "traces.jsonl").write_bytes(content)
    report, _, failures = smoke._raw_stats(tmp_path, 1000, 1000)
    row = report["traces.jsonl"]
    assert row["complete_jsonl_lines"] == 2
    assert row["max_complete_jsonl_line_bytes"] == len(b'{"resourceSpans":[]}\n')
    assert row["trailing_bytes"] == len(b'{partial')
    assert row["sha256"] == sha256(content).hexdigest()
    assert failures == ["truncated_jsonl"]


def test_safety_limits_prevent_parser_invocation(tmp_path, monkeypatch):
    write_capture(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("parser should not be started")
    monkeypatch.setattr(smoke, "_run_worker", forbidden)
    assert smoke.score_capture(tmp_path, max_capture_bytes=1)["failure_categories"] == ["capture_size_limit"]
    assert smoke.score_capture(tmp_path, max_line_bytes=1)["failure_categories"] == ["line_size_limit"]
    assert smoke.score_capture(tmp_path, memory_limit_mb=16384)["failure_categories"] == ["invalid_limits"]


def test_worker_timeout_is_sanitized(tmp_path, monkeypatch):
    write_capture(tmp_path)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(SENTINEL, 180, output=SENTINEL, stderr=SENTINEL)
    monkeypatch.setattr(smoke.subprocess, "run", timeout)
    result = smoke.score_capture(tmp_path)
    assert result["failure_categories"] == ["parser_timeout"]
    assert not result["raw_capture_replayed"]
    assert SENTINEL not in json.dumps(result)


def test_worker_kill_is_sanitized(tmp_path, monkeypatch):
    write_capture(tmp_path)
    monkeypatch.setattr(smoke.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], -9, SENTINEL.encode()))
    result = smoke.score_capture(tmp_path)
    assert result["failure_categories"] == ["worker_failed"]
    assert not result["raw_capture_replayed"]
    assert SENTINEL not in json.dumps(result)


def test_cli_writes_only_metadata_and_cannot_overwrite_raw(tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    raw = write_capture(capture, payload=True)
    output = tmp_path / "smoke.json"
    assert smoke.main(["--capture", str(capture), "--output", str(output)]) == 0
    assert SENTINEL not in output.read_text()
    before = raw.read_bytes()
    assert smoke.main(["--capture", str(capture), "--output", str(raw)]) == 2
    assert raw.read_bytes() == before


def test_capture_stats_never_parses_or_claims_replay(tmp_path, monkeypatch):
    write_capture(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("stats must not run collector")
    monkeypatch.setattr(smoke, "_run_worker", forbidden)
    result = smoke.capture_stats(tmp_path)
    assert set(result) == {"raw_files", "failure_categories"}
    assert result["raw_files"]["traces.jsonl"]["sha256"] is not None
    assert all(not row["processed"] and not row["jsonl_validated"] for row in result["raw_files"].values())
    oversized = smoke.capture_stats(tmp_path, max_capture_bytes=1)
    assert oversized["failure_categories"] == ["capture_size_limit"]
    assert oversized["raw_files"]["traces.jsonl"]["size_bytes"] > 1
    assert oversized["raw_files"]["traces.jsonl"]["sha256"] is None


def test_new_source_created_after_inventory_blocks_replay(tmp_path, monkeypatch):
    write_capture(tmp_path)
    original = smoke._run_worker
    def mutate(request, timeout_seconds):
        (tmp_path / "logs.jsonl").write_text('{"resourceLogs": []}\n')
        return original(request, timeout_seconds)
    monkeypatch.setattr(smoke, "_run_worker", mutate)
    result = smoke.score_capture(tmp_path)
    assert result["failure_categories"] == ["capture_changed"]
    assert not result["raw_capture_replayed"]
