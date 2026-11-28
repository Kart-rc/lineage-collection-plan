"""WP-19: synthetic OTLP parser tests, and separately labeled stored summaries."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging

import pytest

from lineage.config import repository_root
from lineage.evidence import validate_event
from lineage.service_edges import collect_capture, is_control_edge, score_summary

FIXTURES = repository_root() / "fixtures/otel-demo-3.1.0"
BASE_NS = int(datetime(2026, 11, 27, 14, 17, tzinfo=timezone.utc).timestamp()) * 1_000_000_000


def attributes(**values):
    return [{"key": key.replace("__", "."), "value": {"stringValue": value}} for key, value in values.items()]


def span(trace, identity, kind, *, parent="", offset=0, attrs=None, links=None):
    return {"traceId": trace, "spanId": identity, "parentSpanId": parent, "kind": kind,
            "startTimeUnixNano": str(BASE_NS + offset), "attributes": attrs or [], "links": links or []}


def resource(service, *spans):
    return {"resource": {"attributes": attributes(service__name=service)}, "scopeSpans": [{"spans": list(spans)}]}


def write_traces(folder, *resources):
    (folder / "traces.jsonl").write_text(json.dumps({"resourceSpans": list(resources)}) + "\n")


def keys(events):
    return {(e["edge"]["from"]["namespace"] + "/" + e["edge"]["from"]["name"], e["edge"]["type"], e["edge"]["to"]["namespace"] + "/" + e["edge"]["to"]["name"]): e for e in events}


def test_synthetic_trace_server_identity_wins_and_topic_join_uses_no_links(tmp_path):
    write_traces(tmp_path,
        resource("frontend", span("one", "a", 3, attrs=attributes(server__address="172.18.0.9", rpc__service="oteldemo.CurrencyService"))),
        resource("checkout", span("one", "b", 2, parent="a"),
                 span("one", "c", 4, parent="b", attrs=attributes(messaging__system="kafka", messaging__destination__name="orders")),
                 span("one", "d", 3, parent="b", attrs=attributes(server__address="flagd", server__port="8013"))),
        resource("flagd", span("one", "e", 2, parent="d")),
        resource("accounting", span("unrelated-accounting", "f", 5, attrs=attributes(messaging__system="kafka", messaging__destination__name="orders"))),
        resource("fraud-detection", span("unrelated-fraud", "g", 5, attrs=attributes(messaging__system="kafka", messaging__destination__name="orders"))),
    )
    result = collect_capture(tmp_path)
    observed = keys(result.events)
    assert set(observed) == {
        ("svc://otel-demo/frontend", "CALLS", "svc://otel-demo/checkout"),
        ("svc://otel-demo/checkout", "CALLS", "svc://otel-demo/flagd"),
        ("svc://otel-demo/checkout", "PRODUCES", "kafka://otel-demo/orders"),
        ("kafka://otel-demo/orders", "CONSUMES", "svc://otel-demo/accounting"),
        ("kafka://otel-demo/orders", "CONSUMES", "svc://otel-demo/fraud-detection"),
    }
    assert len(result.control_events) == 1
    assert all(not is_control_edge(event) for event in result.data_events)
    assert all(event["eventTime"] == "2026-11-27T14:17:00Z" for event in result.events)
    for event in result.events:
        validate_event(event)


def test_synthetic_sql_exports_only_tables_columns_never_values_or_statement(tmp_path):
    write_traces(tmp_path,
        resource("accounting", span("one", "a", 3, attrs=attributes(
            db__system__name="postgresql", db__user="astronomy_user",
            db__query__text="INSERT INTO accounting.shipping (order_id, zip_code) VALUES ('SECRET_SENTINEL', '99999'); INSERT INTO accounting.orderitem (order_id) VALUES ('SECRET_SENTINEL');")),
            span("one", "b", 3, attrs=attributes(db__system__name="postgresql", db__user="astronomy_user"))),
    )
    result = collect_capture(tmp_path)
    serialized = json.dumps(result.events)
    assert len(result.events) == 2
    assert "SECRET_SENTINEL" not in serialized
    assert "99999" not in serialized
    assert "INSERT" not in serialized
    assert "astronomy_user" not in serialized
    edge = keys(result.events)[("svc://otel-demo/accounting", "WRITES", "postgres://astronomy-db/astronomy_db.accounting.shipping")]
    assert edge["edge"]["columns"] == ["order_id", "zip_code"]
    assert edge["evidence"]["source"] == "db_span"


@pytest.mark.parametrize("statement", [
    "EXECUTE secret_stmt('SYNTHETIC_PAYLOAD_SENTINEL')",
    "DO $$ BEGIN RAISE NOTICE 'SYNTHETIC_PAYLOAD_SENTINEL'; END $$",
    "INSERT INTO accounting.shipping (order_id) VALUES ('SYNTHETIC_PAYLOAD_SENTINEL'",
    "SELECT 'SYNTHETIC_PAYLOAD_SENTINEL",
])
def test_synthetic_unsupported_and_malformed_sql_never_escape_to_logs_or_outputs(tmp_path, capsys, caplog, statement):
    write_traces(tmp_path, resource("accounting", span("one", "a", 3, attrs=attributes(
        db__system__name="postgresql", db__query__text=statement))))
    result = collect_capture(tmp_path)
    assert result.events == []
    assert sum(result.diagnostics.values()) >= 1
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert not [record for record in caplog.records if record.name.startswith("sqlglot")]
    assert "SYNTHETIC_PAYLOAD_SENTINEL" not in json.dumps(result.__dict__)


def test_synthetic_concurrent_sql_parsing_keeps_logger_state_and_valid_results(tmp_path, capsys, caplog):
    logger = logging.getLogger("sqlglot")
    before = (logger.level, logger.disabled, logger.propagate, list(logger.handlers), list(logger.filters))
    folders = []
    for index in range(8):
        folder = tmp_path / str(index)
        folder.mkdir()
        statement = ("EXECUTE secret_stmt('SYNTHETIC_PAYLOAD_SENTINEL')" if index % 2 else
                     "SELECT order_id FROM accounting.shipping WHERE zip_code = 'SYNTHETIC_PAYLOAD_SENTINEL'")
        write_traces(folder, resource("accounting", span("one", "a", 3, attrs=attributes(
            db__system__name="postgresql", db__query__text=statement))))
        folders.append(folder)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(collect_capture, folders))
    assert [len(result.events) for result in results] == [1, 0] * 4
    assert before == (logger.level, logger.disabled, logger.propagate, list(logger.handlers), list(logger.filters))
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert not [record for record in caplog.records if record.name.startswith("sqlglot")]
    assert "SYNTHETIC_PAYLOAD_SENTINEL" not in json.dumps([result.__dict__ for result in results])


def test_synthetic_rollup_is_per_edge_per_minute_and_duplicate_export_is_not_double_counted(tmp_path):
    one = span("one", "a", 4, attrs=attributes(messaging__destination__name="orders"))
    write_traces(tmp_path, resource("checkout", one, one,
        span("two", "b", 4, offset=30_000_000_000, attrs=attributes(messaging__destination__name="orders")),
        span("three", "c", 4, offset=60_000_000_000, attrs=attributes(messaging__destination__name="orders"))))
    result = collect_capture(tmp_path)
    assert [(e["eventTime"], e["evidence"]["count"]) for e in result.events] == [("2026-11-27T14:17:00Z", 2), ("2026-11-27T14:18:00Z", 1)]
    assert result.diagnostics["duplicate_spans"] == 1


def test_synthetic_ingress_resolves_cluster_never_upstream_ip_or_log_body(tmp_path):
    record = {"timeUnixNano": str(BASE_NS), "body": {"stringValue": "SECRET_SENTINEL"},
              "attributes": attributes(event__name="proxy.access", upstream__cluster="frontend", upstream__host="172.18.0.4:8080")}
    document = {"resourceLogs": [{"resource": {"attributes": attributes(service__name="frontend-proxy")}, "scopeLogs": [{"logRecords": [record]}]}]}
    (tmp_path / "logs.jsonl").write_text(json.dumps(document))
    result = collect_capture(tmp_path)
    assert set(keys(result.events)) == {("svc://otel-demo/frontend-proxy", "CALLS", "svc://otel-demo/frontend")}
    assert "SECRET_SENTINEL" not in json.dumps(result.events)
    assert "172.18.0.4" not in json.dumps(result.events)


def test_synthetic_missing_timestamp_is_reported_not_replaced_with_wall_clock(tmp_path):
    item = span("one", "a", 4, attrs=attributes(messaging__destination__name="orders"))
    del item["startTimeUnixNano"]
    write_traces(tmp_path, resource("checkout", item))
    result = collect_capture(tmp_path)
    assert result.events == []
    assert result.diagnostics["missing_timestamps"] == 1


def test_synthetic_consumer_with_trace_parent_still_joins_only_by_topic(tmp_path):
    write_traces(tmp_path,
        resource("checkout", span("same-trace", "a", 4, attrs=attributes(messaging__destination__name="orders"))),
        resource("accounting", span("same-trace", "b", 5, parent="a", attrs=attributes(messaging__destination__name="orders"),
                                    links=[{"traceId": "other", "spanId": "irrelevant"}])))
    result = collect_capture(tmp_path)
    assert {event["edge"]["type"] for event in result.events} == {"PRODUCES", "CONSUMES"}


def test_missing_raw_captures_are_explicit_not_replaced_with_summaries():
    with pytest.raises(FileNotFoundError, match="not a telemetry replay"):
        collect_capture(FIXTURES / "capture-2026-11-27")


@pytest.mark.parametrize("filename", ["observed-edges.json", "observed-edges-run2.json"])
def test_stored_summary_scores_meet_visible_bars_without_claiming_raw_replay(filename):
    summary = json.loads((FIXTURES / "capture-2026-11-27" / filename).read_text())
    golden = json.loads((FIXTURES / "golden-graph.json").read_text())
    report = score_summary(summary, golden)
    assert report["evidence_kind"] == "stored-summary-validation"
    assert report["raw_capture_replayed"] is False
    assert report["precision"] == 1.0
    assert report["recall"] == 0.90
    assert report["upstream_asserted_hit"] == report["upstream_asserted_total"] == 13
    assert report["topic_consumers"] == 2
    assert report["control_edges"] == 6
    assert report["declared_resolved_names"] == 55
