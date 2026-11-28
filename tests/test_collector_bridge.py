"""Synthetic runtime bridge tests; no historical raw replay is asserted."""
from dataclasses import replace
import json
import multiprocessing
import multiprocessing.process
from pathlib import Path
import sqlite3
import subprocess
from threading import Event
import time

import pytest

from lineage.collector import CollectorBridge, Limits, event_key, health
from lineage.config import repository_root

SENTINEL = "SYNTHETIC_PAYLOAD_SENTINEL"


def attributes(**values):
    return [{"key": key.replace("__", "."), "value": {"stringValue": value}} for key, value in values.items()]


def trace(identity="a", offset=0, sql=None):
    attrs = attributes(messaging__destination__name="orders") if sql is None else attributes(db__system__name="postgresql", db__query__text=sql)
    return {"resourceSpans": [{"resource": {"attributes": attributes(service__name="checkout" if sql is None else "accounting")},
        "scopeSpans": [{"spans": [{"traceId": identity, "spanId": identity, "kind": 4 if sql is None else 3,
            "startTimeUnixNano": str(1795789020000000000 + offset), "attributes": attrs}]}]}]}


def jsonl(value):
    return json.dumps(value).encode() + b"\n"


class Sink:
    def __init__(self, acknowledge=True):
        self.calls = []
        self.acknowledge = acknowledge

    def send(self, key, event, timeout):
        self.calls.append((key, event))
        return self.acknowledge


@pytest.fixture
def files(tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "traces.jsonl").write_bytes(jsonl(trace()))
    return capture, tmp_path / "state"


def acknowledged(state):
    with sqlite3.connect(state / "progress.sqlite") as connection:
        return connection.execute("SELECT digest FROM acknowledged").fetchall()


def test_success_is_deduplicated_in_process_and_after_restart(files):
    capture, state = files
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink)
    try:
        first = bridge.run_once()
        assert first["status"] == "ok" and first["sent"] == 1
        assert bridge.run_once()["sent"] == 0
        assert len(acknowledged(state)) == 1
        assert sink.calls[0][0] == event_key(sink.calls[0][1])
    finally:
        bridge.close()
    restarted = CollectorBridge(capture, None, state, sink)
    try:
        assert restarted.run_once()["sent"] == 0
        assert len(sink.calls) == 1
    finally:
        restarted.close()


def test_outage_does_not_checkpoint_and_restart_redelivers_same_key(files):
    capture, state = files
    unavailable = Sink(False)
    bridge = CollectorBridge(capture, None, state, unavailable)
    try:
        report = bridge.run_once()
        assert report["category"] == "delivery_unavailable"
        assert acknowledged(state) == []
        assert health(state)["status"] == "error"
        with sqlite3.connect(state / "progress.sqlite") as connection:
            assert len(connection.execute("SELECT * FROM sources").fetchall()) == 1
    finally:
        bridge.close()
    recovered = Sink()
    bridge = CollectorBridge(capture, None, state, recovered)
    try:
        assert bridge.run_once()["sent"] == 1
        assert recovered.calls[0][0] == unavailable.calls[0][0]
    finally:
        bridge.close()


def test_pre_ack_outage_does_not_allow_rewritten_source_to_disappear_after_restart(files):
    capture, state = files
    bridge = CollectorBridge(capture, None, state, Sink(False))
    try:
        assert bridge.run_once()["category"] == "delivery_unavailable"
        assert acknowledged(state) == []
    finally:
        bridge.close()
    (capture / "traces.jsonl").write_bytes(jsonl(trace("b", 60_000_000_000)))
    recovered = Sink()
    bridge = CollectorBridge(capture, None, state, recovered)
    try:
        assert bridge.run_once()["category"] == "source_changed"
        assert recovered.calls == [] and acknowledged(state) == []
    finally:
        bridge.close()


def test_zero_event_parse_still_guards_source_identity_before_any_ack(files):
    capture, state = files
    (capture / "traces.jsonl").write_bytes(jsonl(trace(sql="EXECUTE unsupported_statement()")))
    bridge = CollectorBridge(capture, None, state, Sink())
    try:
        assert bridge.run_once()["sent"] == 0
        assert acknowledged(state) == []
    finally:
        bridge.close()
    (capture / "traces.jsonl").write_bytes(jsonl(trace()))
    bridge = CollectorBridge(capture, None, state, Sink())
    try:
        assert bridge.run_once()["category"] == "source_changed"
    finally:
        bridge.close()


def test_changing_configured_source_path_cannot_bypass_pre_ack_guard(files):
    capture, state = files
    bridge = CollectorBridge(capture, None, state, Sink(False))
    try:
        assert bridge.run_once()["category"] == "delivery_unavailable"
    finally:
        bridge.close()
    other = capture.parent / "other-capture"
    other.mkdir()
    (other / "traces.jsonl").write_bytes(jsonl(trace("b")))
    sink = Sink()
    bridge = CollectorBridge(other, None, state, sink)
    try:
        assert bridge.run_once()["category"] == "source_changed"
        assert sink.calls == []
    finally:
        bridge.close()


def test_destination_change_requires_separate_checkpoint_state(files):
    capture, state = files
    sink = Sink()
    sink.identity = "first-test-destination"
    bridge = CollectorBridge(capture, None, state, sink)
    bridge.close()
    sink.identity = "second-test-destination"
    with pytest.raises(ValueError, match="destination differs"):
        CollectorBridge(capture, None, state, sink)


def test_ack_before_checkpoint_failure_can_redeliver_without_claiming_exactly_once(files, monkeypatch):
    capture, state = files
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink)
    def unavailable_checkpoint(*args):
        raise OSError(SENTINEL)
    monkeypatch.setattr(bridge, "_acknowledge", unavailable_checkpoint)
    try:
        report = bridge.run_once()
        assert report["category"] == "checkpoint_unavailable"
        assert SENTINEL not in json.dumps(report)
        assert acknowledged(state) == []
    finally:
        bridge.close()
    restarted = CollectorBridge(capture, None, state, sink)
    try:
        assert restarted.run_once()["sent"] == 1
        assert len(sink.calls) == 2
        assert sink.calls[0][0] == sink.calls[1][0]
    finally:
        restarted.close()


def test_partial_append_is_deferred_then_emitted_as_minute_rollup_revision(files):
    capture, state = files
    second = jsonl(trace("b"))
    with (capture / "traces.jsonl").open("ab") as stream:
        stream.write(second[:len(second) // 2])
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink)
    try:
        first = bridge.run_once()
        assert first["sent"] == 1 and first["partial_lines"] == 1
        assert bridge.run_once()["sent"] == 0
        with (capture / "traces.jsonl").open("ab") as stream:
            stream.write(second[len(second) // 2:])
        second_report = bridge.run_once()
        assert second_report["sent"] == 1 and second_report["partial_lines"] == 0
        assert [event["evidence"]["count"] for _, event in sink.calls] == [1, 2]
        assert sink.calls[0][0] != sink.calls[1][0]
        assert bridge.run_once()["sent"] == 0
    finally:
        bridge.close()


@pytest.mark.parametrize("operation", ["truncate", "replace", "rewrite"])
def test_acknowledged_prefix_rotation_truncation_and_rewrite_stop_with_no_new_send(files, operation):
    capture, state = files
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink)
    try:
        assert bridge.run_once()["sent"] == 1
        path = capture / "traces.jsonl"
        if operation == "truncate":
            path.write_bytes(b"")
        elif operation == "replace":
            replacement = capture / "replacement"
            replacement.write_bytes(jsonl(trace("b")))
            replacement.replace(path)
        else:
            path.write_bytes(jsonl(trace("b")))
        report = bridge.run_once()
        assert report["status"] == "error" and report["category"] == "source_changed"
        assert len(sink.calls) == 1
    finally:
        bridge.close()


def test_hung_sink_uses_one_bounded_inflight_send_and_checkpoint_follows_late_ack(files):
    capture, state = files
    release = Event()
    calls = []
    def stalled(key, event, timeout):
        calls.append(key)
        release.wait(5)
        return True
    bridge = CollectorBridge(capture, None, state, stalled, limits=replace(Limits(), send_timeout=.02))
    try:
        assert bridge.run_once()["category"] == "delivery_pending"
        assert acknowledged(state) == []
        start = time.monotonic()
        assert bridge.run_once()["category"] == "delivery_pending"
        assert time.monotonic() - start < .2
        assert len(calls) == 1
        release.set()
        assert bridge._inflight["done"].wait(1)
        assert bridge.run_once()["sent"] == 1
        assert len(acknowledged(state)) == 1
        assert len(calls) == 1
    finally:
        release.set()
        bridge.close()


@pytest.mark.parametrize("overrides,category", [
    ({"max_input_bytes": 20}, "input_limit"),
    ({"max_line_bytes": 20}, "line_limit"),
    ({"max_metadata_bytes": 128}, "metadata_limit"),
    ({"parse_timeout": .001}, "parse_timeout"),
])
def test_input_line_metadata_and_parse_time_limits_hold_without_ack(files, overrides, category):
    capture, state = files
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink, limits=replace(Limits(), **overrides))
    try:
        start = time.monotonic()
        report = bridge.run_once()
        assert report["category"] == category
        assert time.monotonic() - start < 3
        assert sink.calls == [] and acknowledged(state) == []
        assert not list(state.glob("metadata-*.json"))
    finally:
        bridge.close()


def test_event_count_and_sends_per_cycle_are_bounded(files):
    capture, state = files
    with (capture / "traces.jsonl").open("ab") as stream:
        stream.write(jsonl(trace("b", 60_000_000_000)))
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink, limits=replace(Limits(), max_events=1))
    try:
        assert bridge.run_once()["category"] == "event_limit"
        assert sink.calls == []
    finally:
        bridge.close()
    bridge = CollectorBridge(capture, None, state, sink, limits=replace(Limits(), max_sends_per_cycle=1))
    try:
        first = bridge.run_once()
        assert first["sent"] == 1 and first["pending"] == 1
        assert bridge.run_once()["sent"] == 1
        assert bridge.run_once()["sent"] == 0
    finally:
        bridge.close()


def test_sql_payload_is_not_logged_sent_or_persisted_outside_source(files, capfd):
    capture, state = files
    (capture / "traces.jsonl").write_bytes(jsonl(trace(sql=f"EXECUTE secret_stmt('{SENTINEL}')")) +
        jsonl(trace("b", sql=f"INSERT INTO accounting.shipping (order_id) VALUES ('{SENTINEL}')")))
    sink = Sink()
    bridge = CollectorBridge(capture, None, state, sink)
    try:
        report = bridge.run_once()
        assert report["status"] == "ok" and report["sent"] == 1
        assert SENTINEL not in json.dumps(sink.calls)
        assert SENTINEL not in json.dumps(report)
        for path in state.iterdir():
            if path.is_file():
                assert SENTINEL.encode() not in path.read_bytes()
        captured = capfd.readouterr()
        assert SENTINEL not in captured.out + captured.err
    finally:
        bridge.close()


def test_committed_twin_changes_adapt_without_run_markers_or_note_payload(files):
    capture, state = files
    (capture / "traces.jsonl").write_bytes(b"")
    changes = repository_root() / "fixtures/otel-demo-3.1.0/capture-2026-11-27/change-events-run2.jsonl"
    records = [json.loads(line) for line in changes.read_text().splitlines()]
    expected = sum(record["kind"] != "run_marker" for record in records)
    sink = Sink()
    bridge = CollectorBridge(capture, changes, state, sink)
    try:
        assert bridge.run_once()["sent"] == expected
        assert all(event["eventType"] == "CHANGE_EVENT" for _, event in sink.calls)
        assert bridge.run_once()["sent"] == 0
    finally:
        bridge.close()


def test_change_partial_append_and_unknown_payload_field_are_not_checkpointed(files):
    capture, state = files
    (capture / "traces.jsonl").write_bytes(b"")
    changes = capture / "change-events.jsonl"
    record = {"at": "2026-11-27T14:22:19Z", "kind": "flag_change", "flag": "emitRawPii",
              "urn": "flag://otel-demo/emitRawPii", "from": "off", "to": "on", "payload": SENTINEL}
    changes.write_bytes(jsonl(record)[:-1])
    sink = Sink()
    bridge = CollectorBridge(capture, changes, state, sink)
    try:
        assert bridge.run_once()["partial_lines"] == 1
        assert sink.calls == []
        with changes.open("ab") as stream:
            stream.write(b"\n")
        assert bridge.run_once()["category"] == "change_type_rejected"
        assert acknowledged(state) == [] and sink.calls == []
        assert SENTINEL not in json.dumps(health(state))
    finally:
        bridge.close()


def test_static_v2_replacement_is_never_sent_through_changes_input(files):
    capture, state = files
    (capture / "traces.jsonl").write_bytes(b"")
    changes = capture / "change-events.jsonl"
    example = repository_root() / "factory/specs/evidence/examples/golden-field-edge.json"
    changes.write_bytes(example.read_bytes() + b"\n")
    # Fixtures are pretty printed, so write a complete JSONL record explicitly.
    changes.write_bytes(jsonl(json.loads(example.read_text())))
    sink = Sink()
    bridge = CollectorBridge(capture, changes, state, sink)
    try:
        assert bridge.run_once()["category"] == "change_type_rejected"
        assert sink.calls == []
    finally:
        bridge.close()


def test_health_probe_needs_only_state_and_reports_missing_or_stale(tmp_path):
    assert health(tmp_path)["status"] == "error"
    result = subprocess.run([__import__("sys").executable, "-m", "lineage.collector", "--state", str(tmp_path), "--health"], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["category"] == "state_unavailable"


def test_missing_capture_is_unavailable_but_empty_files_and_changes_only_are_explicit(tmp_path):
    capture = tmp_path / "capture"
    capture.mkdir()
    bridge = CollectorBridge(capture, None, tmp_path / "missing-state", Sink())
    try:
        assert bridge.run_once()["category"] == "input_missing"
    finally:
        bridge.close()
    (capture / "traces.jsonl").write_bytes(b"")
    bridge = CollectorBridge(capture, None, tmp_path / "empty-state", Sink())
    try:
        report = bridge.run_once()
        assert report["status"] == "ok" and report["sent"] == 0
    finally:
        bridge.close()
    (capture / "traces.jsonl").unlink()
    changes = capture / "change-events.jsonl"
    changes.write_bytes(jsonl({"kind": "service_start", "service": "accounting", "urn": "svc://otel-demo/accounting", "at": "2026-11-27T14:17:00Z"}))
    bridge = CollectorBridge(capture, changes, tmp_path / "changes-state", Sink())
    try:
        report = bridge.run_once()
        assert report["status"] == "ok" and report["sent"] == 1
    finally:
        bridge.close()


def test_second_writer_cannot_race_checkpoint(files):
    capture, state = files
    bridge = CollectorBridge(capture, None, state, Sink())
    try:
        with pytest.raises(ValueError, match="already has a writer"):
            CollectorBridge(capture, None, state, Sink())
    finally:
        bridge.close()


@pytest.mark.parametrize("name", list(Limits.__dataclass_fields__))
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), 0, -1, True, "1", None])
def test_every_limit_rejects_nonfinite_wrong_type_and_nonpositive_values(name, value):
    with pytest.raises(ValueError):
        Limits(**{name: value})


def test_count_limits_require_integers_and_timer_waits_remain_platform_representable():
    with pytest.raises(ValueError):
        Limits(max_events=1.5)
    with pytest.raises(ValueError):
        Limits(max_input_bytes=2 ** 128)
    with pytest.raises(ValueError):
        Limits(parse_timeout=1e300)


@pytest.mark.parametrize("option", ["--parse-timeout", "--send-timeout", "--poll-interval", "--health-max-age"])
@pytest.mark.parametrize("value", ["inf", "nan"])
def test_cli_rejects_nonfinite_timers_before_creating_state(tmp_path, option, value):
    state = tmp_path / "state"
    result = subprocess.run([__import__("sys").executable, "-m", "lineage.collector", "--state", str(state), "--health", option, value], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["category"] == "invalid_configuration"
    assert not state.exists()
    assert health(state, float("nan"))["category"] == "invalid_configuration"


def test_started_parser_is_reaped_before_temp_unlink_after_join_failure(files, monkeypatch):
    capture, state = files
    original_join = multiprocessing.process.BaseProcess.join
    failed = set()
    def first_join_fails(process, timeout=None):
        if process.pid not in failed:
            failed.add(process.pid)
            raise OverflowError(SENTINEL)
        return original_join(process, timeout)
    monkeypatch.setattr(multiprocessing.process.BaseProcess, "join", first_join_fails)
    before = {child.pid for child in multiprocessing.active_children()}
    bridge = CollectorBridge(capture, None, state, Sink())
    try:
        for _ in range(3):
            report = bridge.run_once()
            assert report["category"] == "parse_unavailable"
            assert SENTINEL not in json.dumps(report)
            assert bridge._parser_job is None
            assert not list(state.glob("metadata-*.json"))
            assert {child.pid for child in multiprocessing.active_children()} == before
        assert acknowledged(state) == []
    finally:
        bridge.close()
