#!/usr/bin/env python3
"""Bounded, metadata-only WP-03 service-edge smoke scoring.

The external runner measures the load window. This step evaluates only service
edge precision; it never establishes full WP-03, timing, or holdout acceptance.
Raw captures stay in place and are never copied into result artifacts.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

RAW_FILES = {"traces.jsonl": ("resourceSpans", "scopeSpans", "spans"),
             "logs.jsonl": ("resourceLogs", "scopeLogs", "logRecords"),
             "metrics.jsonl": ("resourceMetrics", "scopeMetrics", "metrics")}
DATA_TYPES = frozenset({"CALLS", "PRODUCES", "CONSUMES"})
MAX_MEMORY_MB = 8192
MAX_CAPTURE_BYTES = 4 * 1024 ** 3
MAX_LINE_BYTES = 128 * 1024 ** 2
MAX_RESULT_BYTES = 2 * 1024 ** 2
DIAGNOSTICS = frozenset({"malformed_export_lines", "duplicate_spans", "unresolved_endpoints", "missing_timestamps",
                         "unsupported_sql_statements", "sql_parse_failures"})
FAILURES = frozenset({"raw_capture_missing", "empty_capture", "unsupported_file", "capture_size_limit", "line_size_limit",
                      "truncated_jsonl", "malformed_jsonl", "invalid_otlp", "capture_changed", "source_unavailable",
                      "collector_failed", "collector_incomplete", "parser_memory_limit", "parser_timeout", "worker_failed",
                      "worker_result_invalid", "result_size_limit", "precision_below_floor", "no_service_edges",
                      "invalid_run_window", "invalid_limits", "reference_unavailable"})


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _reject_constant(_value):
    raise ValueError()


def precision_check(hit: int, observed: int, expected: int, bar) -> dict:
    """Compare exact rational counts with the approved decimal bar, without rounding."""
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in (hit, observed, expected)) or hit > min(observed, expected):
        raise ValueError("invalid score counts")
    threshold = Fraction(str(bar))
    if not 0 <= threshold <= 1:
        raise ValueError("invalid precision floor")
    holds = observed > 0 and Fraction(hit, observed) >= threshold
    return {"hit": hit, "observed": observed, "expected": expected,
            "value": hit / observed if observed else None,
            "bar": float(threshold), "holds": holds,
            "exact": {"numerator": hit, "denominator": observed}}


def _fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _same_sources(folder, fingerprints):
    """Detect files being created/deleted as well as changed during the replay."""
    for name in RAW_FILES:
        try:
            current = _fingerprint((folder / name).lstat())
        except FileNotFoundError:
            current = None
        except OSError:
            return False
        if current != fingerprints.get(name):
            return False
    return True


def _raw_stats(folder: Path, max_capture_bytes: int, max_line_bytes: int):
    """Stream bytes only; line lengths include the final newline, without retaining lines."""
    reports, fingerprints, failures = {}, {}, []
    sizes = {}
    for name in RAW_FILES:
        path = folder / name
        row = {"present": False, "size_bytes": None, "sha256": None, "complete_jsonl_lines": None,
               "max_complete_jsonl_line_bytes": None, "trailing_bytes": None,
               "jsonl_validated": False, "processed": False}
        reports[name] = row
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            failures.append("source_unavailable")
            continue
        row["present"] = True
        if not stat.S_ISREG(info.st_mode):
            failures.append("unsupported_file")
            continue
        row["size_bytes"] = info.st_size
        sizes[name] = info.st_size
        fingerprints[name] = _fingerprint(info)
    if not any(reports[name]["present"] for name in ("traces.jsonl", "logs.jsonl")):
        failures.append("raw_capture_missing")
    if sum(sizes.values()) > max_capture_bytes:
        failures.append("capture_size_limit")
        return reports, fingerprints, sorted(set(failures))
    for name in sizes:
        row = reports[name]
        digest, complete, longest, trailing, consumed = hashlib.sha256(), 0, 0, 0, 0
        try:
            descriptor = os.open(folder / name, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                before = _fingerprint(os.fstat(stream.fileno()))
                if before != fingerprints[name]:
                    failures.append("capture_changed")
                    continue
                # Stop at the original size even if an exporter is still appending.
                while consumed < sizes[name]:
                    block = stream.read(min(1024 * 1024, sizes[name] - consumed))
                    if not block:
                        break
                    digest.update(block)
                    consumed += len(block)
                    chunks = block.split(b"\n")
                    if len(chunks) == 1:
                        trailing += len(block)
                    else:
                        longest = max(longest, trailing + len(chunks[0]) + 1,
                                      max((len(part) + 1 for part in chunks[1:-1]), default=0))
                        complete += len(chunks) - 1
                        trailing = len(chunks[-1])
                after = _fingerprint(os.fstat(stream.fileno()))
            if before != after or consumed != sizes[name] or _fingerprint((folder / name).lstat()) != before:
                failures.append("capture_changed")
            row.update(sha256=digest.hexdigest(), complete_jsonl_lines=complete,
                       max_complete_jsonl_line_bytes=longest, trailing_bytes=trailing)
            if trailing:
                failures.append("truncated_jsonl")
            if max(longest, trailing) > max_line_bytes:
                failures.append("line_size_limit")
        except OSError:
            failures.append("source_unavailable")
    if not any((reports[name]["size_bytes"] or 0) > 0 for name in ("traces.jsonl", "logs.jsonl")):
        failures.append("empty_capture")
    return reports, fingerprints, sorted(set(failures))


def _window(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError()
    result = {"measurement_source": "external_runner", "verified_by_this_scorer": False}
    for name in ("started_at", "ended_at"):
        raw = value.get(name)
        if not isinstance(raw, str) or len(raw) > 64:
            raise ValueError()
        instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError()
        result[name] = instant.isoformat()
    seconds = value.get("duration_seconds")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError()
    if datetime.fromisoformat(result["ended_at"]) < datetime.fromisoformat(result["started_at"]):
        raise ValueError()
    result["duration_seconds"] = seconds
    return result


def capture_stats(capture_dir: str | Path, *, max_capture_bytes=MAX_CAPTURE_BYTES,
                  max_line_bytes=MAX_LINE_BYTES) -> dict:
    """Inventory a failed/stopped run without invoking any parser or collector.

    Statistics do not establish JSON validity or replay. Oversized sources have
    known byte sizes but unavailable hashes/line counts, not invented zeros.
    """
    limits = ((max_capture_bytes, MAX_CAPTURE_BYTES), (max_line_bytes, MAX_LINE_BYTES))
    if any(type(value) is not int or not 1 <= value <= maximum for value, maximum in limits):
        return {"raw_files": {}, "failure_categories": ["invalid_limits"]}
    files, _, failures = _raw_stats(Path(capture_dir), max_capture_bytes, max_line_bytes)
    return {"raw_files": files, "failure_categories": failures}


def _base_report(window=None):
    return {"schema_version": 1, "status": "blocked", "scope": "WP-03 service-edge smoke only",
            "raw_capture_replayed": False, "replay_scope": [], "run_window": window,
            "precision": None, "edges": {"hit": [], "missed": [], "extra": [], "control": []},
            "counts": {"data_edges": None, "control_edges": None, "collector_events": None, "redacted_endpoints": 0},
            "raw_files": {}, "diagnostics": {}, "failure_categories": [],
            "claims": {"full_wp03_accepted": False, "timings_measured": False, "holdout_measured": False}}


def _reference():
    import yaml
    from lineage.urn import normalize
    fixtures = ROOT / "fixtures/otel-demo-3.1.0"
    golden = json.loads((fixtures / "golden-graph.json").read_text())
    aliases = json.loads((fixtures / "aliases.json").read_text())
    parameters = yaml.safe_load((ROOT / "factory/parameters.yaml").read_text())
    expected = {(normalize(e["from"]), e["type"], normalize(e["to"]))
                for e in golden["service_edges"] if e["type"] in DATA_TYPES}
    safe_names = {endpoint for edge in expected for endpoint in (edge[0], edge[2])}
    safe_names.update(normalize(row["urn"]) for row in aliases["aliases"] if row.get("urn") and "{" not in row["urn"])
    return expected, safe_names, parameters["baseline_accuracy"]["service_edges"]["precision"], aliases


def _shape(document, filename):
    top, scope, records = RAW_FILES[filename]
    if not isinstance(document, dict) or not isinstance(document.get(top), list):
        return False
    for group in document[top]:
        if not isinstance(group, dict) or not isinstance(group.get(scope), list):
            return False
        for batch in group[scope]:
            if not isinstance(batch, dict) or not isinstance(batch.get(records), list) or not all(isinstance(row, dict) for row in batch[records]):
                return False
            if filename == "traces.jsonl":
                for span in batch[records]:
                    if not all(isinstance(span.get(key), str) and span[key] for key in ("traceId", "spanId")):
                        return False
    return True


def _validate_raw(folder, names, max_line_bytes):
    documents = {name: 0 for name in names}
    for name in names:
        with (folder / name).open("rb") as stream:
            while True:
                line = stream.readline(max_line_bytes + 1)
                if not line:
                    break
                if len(line) > max_line_bytes:
                    return documents, "line_size_limit"
                if not line.endswith(b"\n"):
                    return documents, "truncated_jsonl"
                if not line.strip():
                    continue
                try:
                    document = json.loads(line, parse_constant=_reject_constant)
                except (ValueError, UnicodeError):
                    return documents, "malformed_jsonl"
                if not _shape(document, name):
                    return documents, "invalid_otlp"
                documents[name] += 1
    return documents, None


def _project_edges(events, expected, safe_names, bar):
    from lineage.service_edges import is_control_edge
    from lineage.urn import normalize
    def key(event):
        edge = event["edge"]
        def urn(ref):
            return normalize(ref if isinstance(ref, str) else ref["namespace"] + "/" + ref["name"])
        return urn(edge["from"]), edge["type"], urn(edge["to"])
    data = {key(event) for event in events if event["edge"]["type"] in DATA_TYPES and not is_control_edge(event)}
    control = {key(event) for event in events if is_control_edge(event)}
    hit = expected & data
    redacted = 0
    def rows(keys):
        nonlocal redacted
        output = []
        for source, kind, target in sorted(keys):
            redacted += int(source not in safe_names) + int(target not in safe_names)
            output.append({"from": source if source in safe_names else None,
                           "type": kind if kind in DATA_TYPES | {"CONFIGURES"} else "OTHER",
                           "to": target if target in safe_names else None})
        return output
    edges = {"hit": rows(hit), "missed": rows(expected - data), "extra": rows(data - expected), "control": rows(control)}
    return {"precision": precision_check(len(hit), len(data), len(expected), bar), "edges": edges,
            "counts": {"data_edges": len(data), "control_edges": len(control), "collector_events": len(events),
                       "redacted_endpoints": redacted}}


def _worker(request):
    """Child only: cap total parser memory, CPU, file writes, and core dumps."""
    limit = request["memory_limit_mb"] * 1024 ** 2
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    resource.setrlimit(resource.RLIMIT_CPU, (request["timeout_seconds"], request["timeout_seconds"]))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    result = {"failure_categories": [], "validated_files": [], "processed_files": []}
    try:
        folder = Path(request["capture"])
        names = sorted(request["fingerprints"])
        if not _same_sources(folder, request["fingerprints"]):
            result["failure_categories"] = ["capture_changed"]
            return result
        documents, failure = _validate_raw(folder, names, request["max_line_bytes"])
        if failure:
            result["failure_categories"] = [failure]
            return result
        result["validated_files"] = names
        if not any(documents.get(name, 0) for name in ("traces.jsonl", "logs.jsonl")):
            result["failure_categories"] = ["empty_capture"]
            return result
        from lineage.resolve import Resolver
        from lineage.service_edges import collect_capture
        expected, safe_names, bar, aliases = _reference()
        collected = collect_capture(folder, resolver=Resolver(aliases=aliases))
        projected = _project_edges(collected.events, expected, safe_names, bar)
        result.update(projected)
        result["diagnostics"] = {key: int(value) for key, value in collected.diagnostics.items()
                                 if key in DIAGNOSTICS and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
        result["processed_files"] = [name for name in ("traces.jsonl", "logs.jsonl") if documents.get(name, 0)]
        if not _same_sources(folder, request["fingerprints"]):
            result["failure_categories"].append("capture_changed")
        if any(result["diagnostics"].get(name, 0) for name in ("malformed_export_lines", "unresolved_endpoints", "missing_timestamps")):
            result["failure_categories"].append("collector_incomplete")
    except MemoryError:
        result = {"failure_categories": ["parser_memory_limit"], "validated_files": [], "processed_files": []}
    except Exception:
        # Parser exceptions, names, paths and tracebacks can contain payloads.
        result = {"failure_categories": ["collector_failed"], "validated_files": [], "processed_files": []}
    return result


def _run_worker(request, timeout_seconds):
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LINEAGE_REPO_ROOT": str(ROOT)}
    try:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_worker"],
                                   input=_json_bytes(request), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   timeout=timeout_seconds, env=environment, check=False, start_new_session=True)
    except subprocess.TimeoutExpired:
        return {"failure_categories": ["parser_timeout"]}
    except OSError:
        return {"failure_categories": ["worker_failed"]}
    if completed.returncode != 0:
        return {"failure_categories": ["worker_failed"]}
    if len(completed.stdout) > MAX_RESULT_BYTES:
        return {"failure_categories": ["result_size_limit"]}
    try:
        result = json.loads(completed.stdout, parse_constant=_reject_constant)
        if not isinstance(result, dict) or set(result) - {"failure_categories", "validated_files", "processed_files", "precision", "edges", "counts", "diagnostics"}:
            raise ValueError()
        if not isinstance(result.get("failure_categories"), list) or any(item not in FAILURES for item in result["failure_categories"]):
            raise ValueError()
        for name in ("validated_files", "processed_files"):
            if name in result and (not isinstance(result[name], list) or any(item not in RAW_FILES for item in result[name])):
                raise ValueError()
        if "metrics.jsonl" in result.get("processed_files", []):
            raise ValueError()
        if "diagnostics" in result and (not isinstance(result["diagnostics"], dict) or
                any(key not in DIAGNOSTICS or type(value) is not int or value < 0 for key, value in result["diagnostics"].items())):
            raise ValueError()
        if "precision" in result:
            expected, safe_names, bar, _ = _reference()
            precision = result["precision"]
            if not isinstance(precision, dict) or set(precision) != {"hit", "observed", "expected", "value", "bar", "holds", "exact"}:
                raise ValueError()
            if precision["expected"] != len(expected):
                raise ValueError()
            result["precision"] = precision_check(precision["hit"], precision["observed"], len(expected), bar)
            if set(result.get("counts", {})) != {"data_edges", "control_edges", "collector_events", "redacted_endpoints"}:
                raise ValueError()
            if any(type(value) is not int or value < 0 for value in result["counts"].values()):
                raise ValueError()
            if set(result.get("edges", {})) != {"hit", "missed", "extra", "control"}:
                raise ValueError()
            for rows in result["edges"].values():
                if not isinstance(rows, list):
                    raise ValueError()
                for row in rows:
                    if not isinstance(row, dict) or set(row) != {"from", "type", "to"} or row["type"] not in DATA_TYPES | {"CONFIGURES", "OTHER"}:
                        raise ValueError()
                    if any(row[key] is not None and row[key] not in safe_names for key in ("from", "to")):
                        raise ValueError()
        elif not result["failure_categories"]:
            raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        return {"failure_categories": ["worker_result_invalid"]}
    return result


def score_capture(capture_dir: str | Path, run_window: dict | None = None, *, timeout_seconds=180,
                  memory_limit_mb=8192, max_line_bytes=MAX_LINE_BYTES, max_capture_bytes=MAX_CAPTURE_BYTES) -> dict:
    """Return only metadata; a pass applies to precision on this capture, not full WP-03."""
    report = _base_report()
    limits = ((timeout_seconds, 1, 300), (memory_limit_mb, 256, MAX_MEMORY_MB),
              (max_line_bytes, 1, MAX_LINE_BYTES), (max_capture_bytes, 1, MAX_CAPTURE_BYTES))
    if any(isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high for value, low, high in limits):
        report["failure_categories"] = ["invalid_limits"]
        return report
    try:
        report["run_window"] = _window(run_window)
    except (ValueError, TypeError, OverflowError):
        report["failure_categories"] = ["invalid_run_window"]
        return report
    folder = Path(capture_dir)
    files, fingerprints, failures = _raw_stats(folder, max_capture_bytes, max_line_bytes)
    report["raw_files"] = files
    if failures:
        report["failure_categories"] = failures
        return report
    worker = _run_worker({"capture": str(folder.resolve()), "fingerprints": fingerprints,
                          "timeout_seconds": timeout_seconds, "memory_limit_mb": memory_limit_mb,
                          "max_line_bytes": max_line_bytes}, timeout_seconds)
    failures = worker["failure_categories"]
    for key in ("precision", "edges", "counts", "diagnostics"):
        if key in worker:
            report[key] = worker[key]
    for name in worker.get("validated_files", []):
        if name in files:
            files[name]["jsonl_validated"] = True
    for name in worker.get("processed_files", []):
        if name in files:
            files[name]["processed"] = True
    if not failures:
        report["raw_capture_replayed"] = bool(worker.get("processed_files"))
        report["replay_scope"] = worker.get("processed_files", [])
        if not report["precision"] or not report["precision"]["observed"]:
            failures.append("no_service_edges")
        elif not report["precision"]["holds"]:
            failures.append("precision_below_floor")
    report["failure_categories"] = sorted(set(failures))
    report["status"] = "blocked" if failures else "pass"
    return report


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ["--_worker"]:
        # Suppression is limited to the isolated child process. Never retain
        # library output or exception text in pipes or filesystem artifacts.
        result = {"failure_categories": ["worker_failed"]}
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            try:
                request = json.loads(sys.stdin.buffer.read(65536), parse_constant=_reject_constant)
                result = _worker(request)
                data = _json_bytes(result)
                if len(data) > MAX_RESULT_BYTES:
                    data = _json_bytes({"failure_categories": ["result_size_limit"]})
            except BaseException:
                data = _json_bytes({"failure_categories": ["worker_failed"]})
        sys.stdout.buffer.write(data)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--run-window")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--memory-limit-mb", type=int, default=MAX_MEMORY_MB)
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES)
    parser.add_argument("--max-capture-bytes", type=int, default=MAX_CAPTURE_BYTES)
    options = parser.parse_args(args)
    if Path(options.output).resolve() in {(Path(options.capture) / name).resolve() for name in RAW_FILES}:
        return 2
    try:
        window = None
        if options.run_window:
            with Path(options.run_window).open("rb") as stream:
                encoded = stream.read(65537)
            if len(encoded) > 65536:
                raise ValueError()
            window = json.loads(encoded, parse_constant=_reject_constant)
        report = score_capture(options.capture, window, timeout_seconds=options.timeout_seconds,
                               memory_limit_mb=options.memory_limit_mb, max_line_bytes=options.max_line_bytes,
                               max_capture_bytes=options.max_capture_bytes)
    except (OSError, ValueError, TypeError):
        report = _base_report()
        report["failure_categories"] = ["invalid_run_window" if options.run_window else "source_unavailable"]
    try:
        destination = Path(options.output)
        destination.write_bytes(_json_bytes(report))
    except OSError:
        return 2
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
