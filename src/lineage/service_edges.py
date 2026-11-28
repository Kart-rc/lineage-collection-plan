"""Exported OTLP to metadata-only minute rollups (WP-19).

The existing observed_edges prototype supplies its OTLP constants. Its supported
SQL metadata projection is reused here behind a parser that never logs input.
This library adds deterministic timestamps, ingress, strict identity resolution
and v2 envelopes. Historical summary scoring is explicitly separate from replay.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from typing import Iterator

from sqlglot import exp
from sqlglot.dialects.postgres import Postgres
from sqlglot.errors import ErrorLevel

from .catalog import dataset_ref
from .config import repository_root
from .evidence import prepare_event
from .resolve import Resolver
from .urn import normalize

FLAGD = "svc://otel-demo/flagd"


class _MetadataPostgresParser(Postgres.Parser):
    def _warn_unsupported(self) -> None:
        """SQLGlot's default hook logs raw SQL regardless of error_level.

        Disable the hook on this parser only: changing the shared sqlglot logger
        or redirecting stderr would race other collectors in the same process.
        Unsupported Command nodes are counted below, without retaining text.
        """


def _sql_access(statement: str, diagnostics: Counter) -> list[tuple[str, str, list[str]]]:
    """Project recognized SQL to names only; contain every parser failure.

    No regex fallback runs against unsupported syntax, whose string literals
    could otherwise be mistaken for table references. Exceptions may contain
    input SQL and must never be formatted, logged, or returned to the caller.
    """
    try:
        dialect = Postgres()
        parser = _MetadataPostgresParser(dialect=dialect, error_level=ErrorLevel.IMMEDIATE,
                                        error_message_context=0)
        statements = parser.parse(dialect.tokenize(statement), statement)
        accesses = []
        for parsed in statements:
            if isinstance(parsed, exp.Insert):
                schema = parsed.this if isinstance(parsed.this, exp.Schema) else None
                table = schema.this if schema else parsed.this
                accesses.append(("WRITES", f"{table.db}.{table.name}".strip("."),
                                 [column.name for column in schema.expressions] if schema else []))
            elif isinstance(parsed, exp.Update):
                table = parsed.this
                accesses.append(("WRITES", f"{table.db}.{table.name}".strip("."),
                                 [assignment.this.name for assignment in parsed.expressions if isinstance(assignment, exp.EQ)]))
            elif isinstance(parsed, exp.Delete):
                table = parsed.find(exp.Table)
                accesses.append(("WRITES", f"{table.db}.{table.name}".strip("."), []))
            elif parsed is not None and not isinstance(parsed, exp.Command) and parsed.find(exp.Select):
                tables = {table.alias_or_name: f"{table.db}.{table.name}".strip(".") for table in parsed.find_all(exp.Table)}
                for alias, table in tables.items():
                    columns = sorted({column.name for column in parsed.find_all(exp.Column)
                                      if column.table == alias or (not column.table and len(tables) == 1)})
                    accesses.append(("READS", table, columns))
            elif parsed is not None:
                diagnostics["unsupported_sql_statements"] += 1
        return accesses
    except Exception:
        diagnostics["sql_parse_failures"] += 1
        return []


@lru_cache(maxsize=1)
def _prototype():
    path = repository_root() / "code/observed_edges.py"
    spec = importlib.util.spec_from_file_location("lineage_observed_edges_prototype", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_control_edge(event_or_edge: dict) -> bool:
    edge = event_or_edge.get("edge", event_or_edge)
    target = edge["to"]
    target = target if isinstance(target, str) else target["namespace"] + "/" + target["name"]
    return edge["type"] == "CONFIGURES" or normalize(target) == FLAGD


@dataclass
class CollectionResult:
    events: list[dict] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)

    @property
    def data_events(self) -> list[dict]:
        return [e for e in self.events if not is_control_edge(e)]

    @property
    def control_events(self) -> list[dict]:
        return [e for e in self.events if is_control_edge(e)]


def _documents(path: Path, diagnostics: Counter) -> Iterator[tuple[int, dict]]:
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                document = json.loads(line)
                if not isinstance(document, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                diagnostics["malformed_export_lines"] += 1
                continue
            yield line_number, document


def _minute(nanoseconds) -> str | None:
    try:
        # Integer arithmetic avoids boundary rounding from nanosecond floats.
        seconds = int(nanoseconds) // 1_000_000_000
        return datetime.fromtimestamp(seconds - seconds % 60, timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def collect_capture(capture_dir: str | Path, *, resolver: Resolver | None = None,
                    export_documents: dict[str, list[dict]] | None = None) -> CollectionResult:
    """Read exported traces/logs only; raise FileNotFoundError if raw files absent.

Span links are never read. Consumer and producer evidence share the resolved
topic node even if their trace identifiers are unrelated or links are absent.
Missing timestamps are diagnosed and skipped, never assigned today's time.
The bounded bridge may supply transient export_documents snapshots; raw source
paths are still used for provenance and no temporary raw capture is written.
"""
    folder = Path(capture_dir)
    if export_documents is None and not any((folder / filename).is_file() for filename in ("traces.jsonl", "logs.jsonl")):
        raise FileNotFoundError("Raw OTLP capture absent; edge summaries are not a telemetry replay")
    resolve = resolver or Resolver()
    prototype = _prototype()
    diagnostics = Counter()
    rows = []
    index = {}
    parent_servers = set()
    buckets = {}

    def documents(path):
        if export_documents is not None:
            return enumerate(export_documents.get(path.name, []), 1)
        return _documents(path, diagnostics)

    def add(source, target, edge_type, minute, raw_path, evidence_source="otel_span", columns=()):
        if not source or not target:
            diagnostics["unresolved_endpoints"] += 1
            return
        if not minute:
            diagnostics["missing_timestamps"] += 1
            return
        key = (source, target, edge_type, minute, evidence_source)
        bucket = buckets.setdefault(key, {"count": 0, "columns": set(), "rawRef": raw_path.resolve().as_uri()})
        bucket["count"] += 1
        bucket["columns"].update(columns)

    traces = folder / "traces.jsonl"
    if traces.exists() or export_documents is not None:
        for line_number, document in documents(traces):
            for resource in document.get("resourceSpans", []):
                service = prototype.attrs(resource.get("resource", {}).get("attributes")).get("service.name")
                for scope in resource.get("scopeSpans", []):
                    for span in scope.get("spans", []):
                        attributes = prototype.attrs(span.get("attributes"))
                        kind = span.get("kind", 0)
                        kind = prototype.KIND.get(kind, kind)
                        row = {"trace": span.get("traceId"), "id": span.get("spanId"), "parent": span.get("parentSpanId"),
                               "service": resolve("service.name", service), "kind": kind, "attrs": attributes,
                               "minute": _minute(span.get("startTimeUnixNano"))}
                        if row["trace"] and row["id"]:
                            identity = (row["trace"], row["id"])
                            if identity in index:
                                diagnostics["duplicate_spans"] += 1
                                continue
                            index[identity] = row
                        rows.append(row)
                        if kind == prototype.SERVER and row["parent"]:
                            parent_servers.add((row["trace"], row["parent"]))

    for row in rows:
        service, kind, attributes, minute = (row[k] for k in ("service", "kind", "attrs", "minute"))
        parent = index.get((row["trace"], row["parent"]))
        topic_name = attributes.get("messaging.destination.name") or attributes.get("messaging.destination")
        if parent and parent["service"] != service and kind in (prototype.SERVER, prototype.CONSUMER) and not (attributes.get("messaging.system") or topic_name):
            add(parent["service"], service, "CALLS", minute, traces)
        if topic_name and kind in (prototype.PRODUCER, prototype.CONSUMER):
            topic = resolve("messaging.destination.name", topic_name)
            if kind == prototype.PRODUCER:
                add(service, topic, "PRODUCES", minute, traces)
            else:
                add(topic, service, "CONSUMES", minute, traces)
        system = attributes.get("db.system.name") or attributes.get("db.system")
        if system and kind == prototype.CLIENT:
            statement = attributes.get("db.query.text") or attributes.get("db.statement") or ""
            if system == "redis":
                verb = "WRITES" if statement.split(" ", 1)[0].upper() in prototype.REDIS_WRITES else "READS"
                add(service, resolve("db.system+address", f"redis@{attributes.get('server.address', '')}"), verb, minute, traces, "db_span")
            elif statement or attributes.get("db.collection.name"):
                accesses = _sql_access(statement, diagnostics) if statement else [("READS", attributes["db.collection.name"], [])]
                for verb, table, columns in accesses:
                    add(service, resolve("db.table", table), verb, minute, traces, "db_span", columns)
            continue
        if kind == prototype.CLIENT and (row["trace"], row["id"]) not in parent_servers and not system:
            host = attributes.get("server.address") or attributes.get("net.peer.name")
            port = attributes.get("server.port") or attributes.get("net.peer.port")
            address = f"{host}:{port}" if host and port and ":" not in str(host) else host
            target = resolve("address", address) if address else None
            if target is None and attributes.get("rpc.service"):
                target = resolve("rpc.service", attributes["rpc.service"])
            if target:
                add(service, target, "CALLS", minute, traces)

    logs = folder / "logs.jsonl"
    if logs.exists() or export_documents is not None:
        for line_number, document in documents(logs):
            for resource in document.get("resourceLogs", []):
                service_name = prototype.attrs(resource.get("resource", {}).get("attributes")).get("service.name")
                service = resolve("service.name", service_name)
                for scope in resource.get("scopeLogs", []):
                    for record in scope.get("logRecords", []):
                        attributes = prototype.attrs(record.get("attributes"))
                        if attributes.get("event.name") != "proxy.access":
                            continue
                        minute = _minute(record.get("timeUnixNano") or record.get("observedTimeUnixNano"))
                        target = resolve("envoy.cluster", attributes.get("upstream.cluster", "-"))
                        if target:
                            add(service, target, "CALLS", minute, logs, "gateway_log")

    result = CollectionResult(diagnostics=dict(diagnostics))
    for (source, target, edge_type, minute, evidence_source), bucket in sorted(buckets.items()):
        edge = {"from": dataset_ref(source), "to": dataset_ref(target), "type": edge_type}
        if bucket["columns"]:
            edge["columns"] = sorted(bucket["columns"])
        result.events.append(prepare_event({
            "schemaVersion": "2", "eventType": "EVIDENCE", "eventTime": minute,
            "producer": "lineage-collectors/service-edges@0.1.0", "edge": edge,
            "evidence": {"source": evidence_source, "observedAt": minute, "count": bucket["count"],
                         "rawRef": bucket["rawRef"], "replaces": "none"},
        }))
    return result


def iter_capture_events(capture_dir: str | Path, *, resolver: Resolver | None = None) -> Iterator[dict]:
    yield from collect_capture(capture_dir, resolver=resolver).events


def score_summary(summary: dict, golden: dict) -> dict:
    """Recompute metrics from stored summary edges, never trust saved scores."""
    types = {"CALLS", "PRODUCES", "CONSUMES"}
    def key(edge):
        return normalize(edge["from"]), edge["type"], normalize(edge["to"])
    expected = {key(e) for e in golden["service_edges"] if e["type"] in types}
    observed = {key(e) for e in summary["edges"] if e["type"] in types and not is_control_edge(e)}
    asserted = {key(e) for e in golden["service_edges"] if e.get("upstream_asserted")}
    hit = expected & observed
    coverage = summary.get("coverage", {})
    return {"evidence_kind": "stored-summary-validation", "raw_capture_replayed": False,
            "precision": len(hit) / len(observed) if observed else 0.0,
            "recall": len(hit) / len(expected) if expected else 0.0,
            "upstream_asserted_hit": len(asserted & observed), "upstream_asserted_total": len(asserted),
            "topic_consumers": len([e for e in observed if e[1] == "CONSUMES"]),
            "control_edges": len([e for e in summary["edges"] if is_control_edge(e)]),
            "declared_resolved_names": sum(v["ok"] for v in coverage.get("kinds", {}).values()),
            "declared_ip_references_unaliased": coverage.get("ip_references"),
            "missing": [list(e) for e in sorted(expected - observed)],
            "extra": [list(e) for e in sorted(observed - expected)]}
