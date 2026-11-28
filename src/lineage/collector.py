"""Bounded local capture-to-Kafka bridge; never a producer/request-path agent.

This candidate rereads append-only capture files, not arbitrary-scale streaming.
Defaults: 16 MiB combined input, 1 MiB per JSONL line, 4,096 events, 8 MiB
metadata output, 512 MiB parser address space, 10 s parsing, 5 s per send,
128 sends/cycle and 100,000 acknowledged event digests. All are configurable.
Size/count limits require positive platform-sized integers; timer limits require
positive finite seconds no greater than one day (including poll/health timers).
Large saved reference captures require explicitly raised limits and are not
claimed accepted under the defaults.

Only newline-terminated records are processed. Source rotation, truncation of
an acknowledged prefix, or rewriting that prefix stops collection; use a new
source/state pair after operator review. Trailing partial lines remain deferred.
Late append-only spans produce cumulative minute-rollup revisions: changed
count/columns produces a new content digest; identical metadata is deduplicated.
Consumers must interpret these as updated observations, not increment counters.

SQLite stores acknowledged digests, source prefix fingerprints and health only.
Validated source fingerprints are guarded before any send, including empty
collections, so pre-ack outages cannot hide source loss. They are identity guards,
never resume offsets: every cycle still rereads the sources. Delivery checkpoint
writes follow acknowledgement. Ack-before-checkpoint crashes
can redeliver; this is at-least-once delivery, never an exactly-once guarantee.
Pending metadata is reconstructed from retained sources after restart. Raw OTLP
and SQL are read only from sources, never copied to state, stderr or output.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import resource
import signal
import sqlite3
import sys
import tempfile
from threading import Event, Thread
import time

from .evidence import prepare_event
from .resolve import Resolver
from .service_edges import collect_capture


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def event_key(event: dict) -> str:
    """Stable, metadata-only event identity; retries retain this Kafka key."""
    return hashlib.sha256(_canonical(prepare_event(event)).encode()).hexdigest()


def _validate_seconds(value) -> None:
    if type(value) not in (int, float) or not 0 < value <= 86400 or not math.isfinite(value):
        raise ValueError("Collector timings require positive finite seconds up to one day")


@dataclass(frozen=True)
class Limits:
    max_input_bytes: int = 16 * 1024 * 1024
    max_line_bytes: int = 1024 * 1024
    max_events: int = 4096
    max_metadata_bytes: int = 8 * 1024 * 1024
    max_memory_bytes: int = 512 * 1024 * 1024
    max_sends_per_cycle: int = 128
    max_acknowledged: int = 100_000
    parse_timeout: float = 10.0
    send_timeout: float = 5.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name in {"parse_timeout", "send_timeout"}:
                _validate_seconds(value)
            elif type(value) is not int or not 0 < value <= sys.maxsize:
                raise ValueError("Collector size/count limits require positive platform-sized integers")


class _ControlledError(Exception):
    def __init__(self, category):
        self.category = category


def _snapshot(path: Path, previous: dict | None, remaining: int, limits: Limits):
    """Read one bounded prefix; return transient objects and a metadata guard."""
    if not path.is_file():
        if previous is not None:
            raise _ControlledError("source_changed")
        return [], None, 0, 0
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > remaining:
            raise _ControlledError("input_limit")
        if previous and (before.st_dev != previous["device"] or before.st_ino != previous["inode"] or before.st_size < previous["complete_bytes"]):
            raise _ControlledError("source_changed")
        raw = stream.read(before.st_size)
        if len(raw) != before.st_size or os.fstat(stream.fileno()).st_size < before.st_size:
            raise _ControlledError("source_changed")
    if previous and hashlib.sha256(raw[:previous["complete_bytes"]]).hexdigest() != previous["prefix_sha256"]:
        raise _ControlledError("source_changed")
    end = raw.rfind(b"\n") + 1
    records = []
    for number, line in enumerate(raw.splitlines(keepends=True), 1):
        if len(line) > limits.max_line_bytes:
            raise _ControlledError("line_limit")
        if not line.endswith(b"\n"):
            break
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise _ControlledError("input_invalid")
        records.append((number, record))
    guard = {"device": before.st_dev, "inode": before.st_ino, "complete_bytes": end,
             "prefix_sha256": hashlib.sha256(raw[:end]).hexdigest()}
    return records, guard, before.st_size, int(end < len(raw))


def _change_event(record: dict, source: Path, line_number: int) -> dict | None:
    if "schemaVersion" in record:
        event = prepare_event(record)
        if event["eventType"] != "CHANGE_EVENT":
            raise _ControlledError("change_type_rejected")
        return event
    kind = record.get("kind")
    allowed = {
        "run_marker": {"kind", "at", "note"},
        "flag_change": {"kind", "at", "flag", "urn", "from", "to", "via"},
        "service_stop": {"kind", "at", "service", "urn"},
        "service_start": {"kind", "at", "service", "urn"},
    }
    if kind not in allowed or set(record) - allowed[kind]:
        raise _ControlledError("change_type_rejected")
    if kind == "run_marker":
        return None
    subject = Resolver()("urn", record["urn"])
    expected_scheme = "flag://" if kind == "flag_change" else "svc://"
    if not subject or not subject.startswith(expected_scheme):
        raise _ControlledError("change_type_rejected")
    at = record["at"].replace("+00:00", "Z")
    return prepare_event({"schemaVersion": "2", "eventType": "CHANGE_EVENT", "eventTime": at,
                          "producer": "twin/flip@0.1.0", "change": {"kind": kind, "subject": subject,
                          "at": at, "from": record.get("from"), "to": record.get("to"),
                          "ref": source.resolve().as_uri() + f"#line={line_number}"}})


def _parse_worker(capture_dir, changes, previous, limit_values, output_path):
    """Child process bounds parser CPU time externally and memory internally."""
    limits = Limits(**limit_values)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limits.max_memory_bytes, limits.max_memory_bytes))
        exports, sources, used, partial = {}, {}, 0, 0
        change_rows = []
        paths = [Path(capture_dir) / filename for filename in ("traces.jsonl", "logs.jsonl")]
        if changes:
            paths.append(Path(changes))
        if set(previous) - {str(path.resolve()) for path in paths}:
            raise _ControlledError("source_changed")
        for path in paths:
            identity = str(path.resolve())
            rows, guard, size, tail = _snapshot(path, previous.get(identity), limits.max_input_bytes - used, limits)
            used += size
            partial += tail
            if guard is not None:
                sources[identity] = guard
            if changes and path == Path(changes):
                change_rows = rows
            else:
                exports[path.name] = [record for _, record in rows]
        collected = collect_capture(capture_dir, export_documents=exports)
        if not sources:
            raise _ControlledError("input_missing")
        events = list(collected.events)
        for number, record in change_rows:
            event = _change_event(record, Path(changes), number)
            if event is not None:
                events.append(event)
        if len(events) > limits.max_events:
            raise _ControlledError("event_limit")
        for event in events:
            prepare_event(event)
            if event["eventType"] == "EVIDENCE" and (not event["evidence"]["runtime"] or event["evidence"].get("replaces") == "unit"):
                raise _ControlledError("static_protocol_rejected")
        result = {"status": "ok", "events": events, "sources": sources,
                  "partial_lines": partial, "input_bytes": used, "diagnostics": collected.diagnostics}
        encoded = _canonical(result).encode()
        if len(encoded) > limits.max_metadata_bytes:
            raise _ControlledError("metadata_limit")
    except _ControlledError as error:
        encoded = _canonical({"status": "error", "category": error.category}).encode()
    except BaseException:
        # SQL/JSON/parser exceptions can include payloads; never serialize them.
        encoded = b'{"status":"error","category":"input_invalid"}'
    try:
        Path(output_path).write_bytes(encoded)
    except BaseException:
        pass


class KafkaEvidenceSink:
    """One bounded outstanding Kafka message, acknowledged before success."""
    def __init__(self, broker: str, topic: str = "lineage.evidence", *, send_timeout: float = 5.0):
        _validate_seconds(send_timeout)
        from confluent_kafka import Producer
        self.topic = topic
        self.identity = _canonical({"broker": broker, "topic": topic})
        self.producer = Producer({"bootstrap.servers": broker, "enable.idempotence": True,
                                  "message.timeout.ms": max(1, int(send_timeout * 1000)),
                                  "queue.buffering.max.messages": 1, "queue.buffering.max.kbytes": 8192,
                                  "max.in.flight.requests.per.connection": 1, "log_level": 0})

    def send(self, key: str, event: dict, timeout: float) -> bool:
        _validate_seconds(timeout)
        delivered = []
        deadline = time.monotonic() + timeout
        try:
            self.producer.poll(0)
            self.producer.produce(self.topic, key=key, value=_canonical(event),
                                  on_delivery=lambda error, message: delivered.append(error is None))
            while not delivered and time.monotonic() < deadline:
                self.producer.poll(min(0.05, max(0.0, deadline - time.monotonic())))
            return bool(delivered and delivered[0])
        except Exception:
            return False


class CollectorBridge:
    """Single-writer bridge with bounded parsing and one send thread at a time.

    sink.send(key, event, timeout) returns True only after broker acknowledgement.
    A timed-out custom sink occupies one daemon thread; no more are spawned until
    it finishes. Only safe event metadata can enter that thread or temporary file.
    """
    def __init__(self, capture_dir, changes, state_dir, sink, *, limits: Limits | None = None):
        self.capture_dir = Path(capture_dir)
        self.changes = Path(changes) if changes else None
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.limits = limits or Limits()
        self.sink = sink
        self._inflight = None
        self._parser_job = None
        self._lock = (self.state_dir / "collector.lock").open("a")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise ValueError("Collector state already has a writer") from None
        self.connection = sqlite3.connect(self.state_dir / "progress.sqlite", timeout=1)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS acknowledged (digest TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS sources (identity TEXT PRIMARY KEY, guard TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS health (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS destination (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL);
        """)
        destination = getattr(sink, "identity", "custom-sink")
        previous = self.connection.execute("SELECT identity FROM destination WHERE id=1").fetchone()
        if previous and previous[0] != destination:
            self.close()
            raise ValueError("Collector destination differs from persisted state")
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO destination VALUES (1, ?)", (destination,))
        # A prior crash may leave only a bounded, validated metadata result file.
        # The writer lock ensures no live parser owns these files now.
        for stale in self.state_dir.glob("metadata-*.json"):
            stale.unlink()

    def close(self):
        if self._parser_job is not None:
            self._cleanup_parser(*self._parser_job)
        self.connection.close()
        self._lock.close()

    def _health(self, report):
        value = dict(report, updated_at=time.time())
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO health VALUES (1, ?)", (_canonical(value),))
        return report

    def _acknowledge(self, key, sources):
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO acknowledged VALUES (?)", (key,))

    def _guard_sources(self, sources):
        """Guard observed input identity independently of delivery acceptance."""
        with self.connection:
            for identity, guard in sources.items():
                self.connection.execute("INSERT OR REPLACE INTO sources VALUES (?, ?)", (identity, _canonical(guard)))

    def _cleanup_parser(self, process, output_path):
        """Reap before unlinking so a surviving writer cannot recreate output.

        An OS-level termination failure retains one tracked job and blocks new
        parsing. No exception path may lose the process handle or spawn extras.
        """
        if process is not None and process.pid is not None:
            for stop in (process.terminate, process.kill):
                try:
                    if not process.is_alive():
                        break
                    stop()
                    process.join(0.5)
                except Exception:
                    continue
            if process.is_alive():
                self._parser_job = (process, output_path)
                return
        if process is not None:
            process.close()
        self._parser_job = None
        Path(output_path).unlink(missing_ok=True)

    def _parse(self):
        if self._parser_job is not None:
            self._cleanup_parser(*self._parser_job)
            if self._parser_job is not None:
                return {"status": "error", "category": "parse_unavailable"}
        previous = {identity: json.loads(guard) for identity, guard in self.connection.execute("SELECT identity, guard FROM sources")}
        # This file contains validated metadata only; never a raw snapshot.
        descriptor, output_path = tempfile.mkstemp(prefix="metadata-", suffix=".json", dir=self.state_dir)
        os.close(descriptor)
        process = None
        try:
            process = multiprocessing.get_context("spawn").Process(target=_parse_worker, args=(
                str(self.capture_dir), str(self.changes) if self.changes else None, previous, asdict(self.limits), output_path))
            process.start()
            process.join(self.limits.parse_timeout)
            if process.is_alive():
                return {"status": "error", "category": "parse_timeout"}
            output = Path(output_path)
            if output.stat().st_size > self.limits.max_metadata_bytes:
                return {"status": "error", "category": "metadata_limit"}
            return json.loads(output.read_bytes())
        except Exception:
            return {"status": "error", "category": "parse_unavailable"}
        finally:
            self._cleanup_parser(process, output_path)

    def _begin_send(self, key, event, sources):
        pending = {"key": key, "sources": sources, "done": Event(), "acknowledged": False}
        def send():
            try:
                sender = self.sink.send if hasattr(self.sink, "send") else self.sink
                pending["acknowledged"] = sender(key, event, self.limits.send_timeout) is True
            except BaseException:
                pending["acknowledged"] = False
            finally:
                pending["done"].set()
        self._inflight = pending
        Thread(target=send, name="lineage-collector-send", daemon=True).start()
        pending["done"].wait(self.limits.send_timeout)

    def run_once(self) -> dict:
        sent = 0
        try:
            if self._inflight is not None:
                if not self._inflight["done"].is_set():
                    return self._health({"status": "error", "category": "delivery_pending", "sent": 0})
                if self._inflight["acknowledged"]:
                    self._acknowledge(self._inflight["key"], self._inflight["sources"])
                    sent += 1
                self._inflight = None
            parsed = self._parse()
            if parsed["status"] != "ok":
                return self._health(dict(parsed, sent=sent))
            self._guard_sources(parsed["sources"])
            acknowledged = {row[0] for row in self.connection.execute("SELECT digest FROM acknowledged")}
            pending = {}
            for event in parsed["events"]:
                key = event_key(event)
                if key not in acknowledged:
                    pending[key] = event
            for key, event in list(pending.items())[:self.limits.max_sends_per_cycle]:
                if len(acknowledged) >= self.limits.max_acknowledged:
                    return self._health({"status": "error", "category": "state_limit", "sent": sent})
                self._begin_send(key, event, parsed["sources"])
                if not self._inflight["done"].is_set():
                    return self._health({"status": "error", "category": "delivery_pending", "sent": sent})
                if not self._inflight["acknowledged"]:
                    self._inflight = None
                    return self._health({"status": "error", "category": "delivery_unavailable", "sent": sent})
                self._acknowledge(key, parsed["sources"])
                self._inflight = None
                acknowledged.add(key)
                del pending[key]
                sent += 1
                self._health({"status": "ok", "category": "sending", "sent": sent})
            return self._health({"status": "ok", "category": "complete" if not pending else "more_pending",
                                 "sent": sent, "pending": len(pending), "partial_lines": parsed["partial_lines"],
                                 "input_bytes": parsed["input_bytes"], "diagnostics": parsed["diagnostics"]})
        except Exception:
            # Errors from sqlite/transport/parsing must not carry raw source text.
            report = {"status": "error", "category": "checkpoint_unavailable", "sent": sent}
            try:
                return self._health(report)
            except Exception:
                return report


def health(state_dir, max_age: float = 60.0) -> dict:
    try:
        _validate_seconds(max_age)
    except ValueError:
        return {"status": "error", "category": "invalid_configuration"}
    try:
        path = (Path(state_dir) / "progress.sqlite").resolve()
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            row = connection.execute("SELECT value FROM health WHERE id=1").fetchone()
        finally:
            connection.close()
        if not row:
            return {"status": "error", "category": "not_started"}
        report = json.loads(row[0])
        if time.time() - report["updated_at"] > max_age:
            return {"status": "error", "category": "stale"}
        return report
    except Exception:
        return {"status": "error", "category": "state_unavailable"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--changes", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--broker")
    parser.add_argument("--topic", default="lineage.evidence")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--health-max-age", type=float, default=60.0)
    defaults = Limits()
    for name, default in asdict(defaults).items():
        parser.add_argument("--" + name.replace("_", "-"), type=type(default), default=default)
    args = parser.parse_args(argv)
    try:
        limits = Limits(**{name: getattr(args, name) for name in asdict(defaults)})
        _validate_seconds(args.poll_interval)
        _validate_seconds(args.health_max_age)
    except ValueError:
        print('{"status":"error","category":"invalid_configuration"}', flush=True)
        return 1
    if args.health:
        result = health(args.state, args.health_max_age)
        print(_canonical(result))
        return 0 if result["status"] == "ok" else 1
    if not args.capture_dir or not args.broker:
        parser.error("Collection requires --capture-dir and --broker")
    bridge = None
    try:
        sink = KafkaEvidenceSink(args.broker, args.topic, send_timeout=limits.send_timeout)
        bridge = CollectorBridge(args.capture_dir, args.changes, args.state, sink, limits=limits)
        stopped = Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: stopped.set())
        while not stopped.is_set():
            result = bridge.run_once()
            print(_canonical(result), flush=True)
            if args.once:
                return 0 if result["status"] == "ok" else 1
            stopped.wait(args.poll_interval)
        return 0
    except Exception:
        print('{"status":"error","category":"collector_unavailable"}', flush=True)
        return 1
    finally:
        if bridge is not None:
            bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
