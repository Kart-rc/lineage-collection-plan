"""Complete-unit transport for the shared-filesystem twin.

Reserve before extraction; immutable metadata objects precede completion
manifests. Only the completion manifest goes to lineage.unit-snapshots. A local
completion is durable publication, not graph acceptance. Kafka retries can
redeliver, and no S3 or distributed-filesystem guarantee is claimed.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from jsonschema import Draft202012Validator, FormatChecker

from .config import schema
from .evidence import prepare_event, validate_event
from .graph import timestamp
from .merge import UnitSnapshot, snapshot_digest
from .urn import normalize

PRODUCER = re.compile(r"^[a-z0-9][a-z0-9._/-]*@[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$")
OBJECT_REF = re.compile(r"^snapshot://sha256/([0-9a-f]{64})$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def validate_route(route: dict) -> dict:
    if not isinstance(route, dict) or set(route) != {"repository", "stage", "pr"}:
        raise ValueError("Snapshot route requires repository, stage and pr")
    if not isinstance(route["repository"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", route["repository"]) or any(part in {".", ".."} for part in route["repository"].split("/")):
        raise ValueError("Snapshot repository must be a canonical slug")
    if route["stage"] == "merged":
        if route["pr"] is not None:
            raise ValueError("Merged route cannot carry a PR")
    elif route["stage"] == "proposed":
        if type(route["pr"]) is not int or route["pr"] < 1:
            raise ValueError("Proposed route requires a positive PR")
    else:
        raise ValueError("Unknown snapshot stage")
    return deepcopy(route)


def route_namespace(route: dict) -> str:
    route = validate_route(route)
    return "lineage-" + route["stage"] + "-" + hashlib.sha256(canonical(route).encode()).hexdigest()[:16]


def _scope(route, unit, producer):
    route = validate_route(route)
    if not isinstance(producer, str) or not PRODUCER.fullmatch(producer):
        raise ValueError("A versioned snapshot producer is required")
    if not isinstance(unit, str) or normalize(unit) != unit or not unit.startswith(f"unit://git/{route['repository']}/"):
        raise ValueError("Snapshot unit must belong to route repository")
    if any(segment in {".", ".."} for segment in unit.split("/")):
        raise ValueError("Invalid snapshot unit path")
    return canonical({"route": route, "unit": unit, "producer": producer.rsplit("@", 1)[0]})


def _root(root):
    path = Path(root).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Snapshot archive cannot use symlink paths")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _safe_file(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or path.parent.resolve() != root:
        raise ValueError("Snapshot archive path escaped its root")
    return path


def _immutable(root: Path, name: str, value: dict) -> None:
    destination = _safe_file(root, name)
    body = canonical(value).encode()
    if destination.exists():
        if destination.read_bytes() != body:
            raise ValueError("Immutable snapshot content conflict")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if _safe_file(root, name).read_bytes() != body:
                raise ValueError("Immutable snapshot content conflict")
        directory = os.open(root, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


class SnapshotCoordinator:
    def __init__(self, root):
        self.root = _root(root)
        self.database = _safe_file(self.root, "reservations.sqlite")
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS reservations(
                scope TEXT NOT NULL, request_id TEXT NOT NULL, producer TEXT NOT NULL,
                generation INTEGER NOT NULL, reserved_at TEXT NOT NULL,
                PRIMARY KEY(scope,request_id), UNIQUE(scope,generation))""")

    @contextmanager
    def _connect(self):
        _safe_file(self.root, "reservations.sqlite")
        connection = sqlite3.connect(self.database, timeout=5)
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def reserve(self, route, unit, producer, request_id) -> int:
        scope = _scope(route, unit, producer)
        if not isinstance(request_id, str) or not re.fullmatch(r"\S{1,256}", request_id):
            raise ValueError("Invalid snapshot request identity")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT generation,producer FROM reservations WHERE scope=? AND request_id=?", (scope, request_id)).fetchone()
            if row:
                if row[1] != producer:
                    raise ValueError("Retry request changed producer version")
                return row[0]
            generation = connection.execute("SELECT COALESCE(MAX(generation),0)+1 FROM reservations WHERE scope=?", (scope,)).fetchone()[0]
            at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            connection.execute("INSERT INTO reservations VALUES (?,?,?,?,?)", (scope, request_id, producer, generation, at))
            return generation

    def reservation(self, route, unit, producer, request_id) -> dict:
        scope = _scope(route, unit, producer)
        with self._connect() as connection:
            row = connection.execute("SELECT generation,reserved_at,producer FROM reservations WHERE scope=? AND request_id=?", (scope, request_id)).fetchone()
        if not row or row[2] != producer:
            raise ValueError("Snapshot generation was not reserved for this request")
        return {"generation": row[0], "reserved_at": row[1]}


def validate_manifest(manifest: dict) -> None:
    validator = Draft202012Validator(schema("factory/specs/evidence/interfaces/unit-snapshot.schema.json"), format_checker=FormatChecker())
    if next(validator.iter_errors(manifest), None) is not None:
        raise ValueError("Invalid complete-unit manifest")
    _scope(manifest["route"], manifest["unit"]["urn"], manifest["producer"])
    if manifest["unit"].get("pr") != manifest["route"]["pr"]:
        raise ValueError("Unit revision PR disagrees with route")
    if manifest["deleted"] and manifest["eventCount"]:
        raise ValueError("Deleted snapshot must be empty")
    if not OBJECT_REF.fullmatch(manifest["objectRef"]):
        raise ValueError("Invalid immutable snapshot reference")


class SnapshotPublisher:
    def __init__(self, root, sink=None):
        self.root = _root(root)
        self.coordinator = SnapshotCoordinator(self.root)
        self.sink = sink

    def _completion_name(self, route, unit, producer, request_id):
        return "completion-" + hashlib.sha256(canonical([_scope(route, unit, producer), request_id]).encode()).hexdigest() + ".json"

    def completed(self, route, unit, producer, request_id):
        path = _safe_file(self.root, self._completion_name(route, unit, producer, request_id))
        if not path.exists():
            return None
        manifest = json.loads(path.read_bytes())
        if manifest.get("route") != route or manifest.get("unit", {}).get("urn") != unit or manifest.get("producer") != producer or manifest.get("requestId") != request_id:
            raise ValueError("Stored completion does not match its reserved request")
        self.load(manifest)
        return manifest

    def publish(self, snapshot: UnitSnapshot, route: dict, request_id: str, *, unit_revision=None):
        route = validate_route(route)
        reserved = self.coordinator.reservation(route, snapshot.unit, snapshot.producer, request_id)
        if snapshot.generation != reserved["generation"] or snapshot.complete is not True:
            raise ValueError("Snapshot generation is not a complete reserved generation")
        events = [prepare_event(event) for event in snapshot.events]
        if snapshot.digest != snapshot_digest(events) or len({canonical(event) for event in events}) != len(events):
            raise ValueError("Snapshot event content differs from completion digest")
        events = sorted(events, key=canonical)
        revision = deepcopy(unit_revision if unit_revision is not None else events[0]["unit"] if events else None)
        if revision is None:
            raise ValueError("An empty snapshot requires an explicit unit revision")
        if revision.get("urn") != snapshot.unit:
            raise ValueError("Snapshot unit disagrees with its revision")
        body = {"route": route, "unit": revision, "producer": snapshot.producer, "generation": snapshot.generation,
                "requestId": request_id, "validAt": timestamp(snapshot.valid_at), "complete": True,
                "deleted": snapshot.deleted, "events": events}
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        manifest = {"schemaVersion": "1", "eventType": "UNIT_SNAPSHOT_COMPLETE",
                    **{key: value for key, value in body.items() if key != "events"},
                    "eventCount": len(events), "eventsHash": snapshot_digest(events), "objectRef": "snapshot://sha256/" + digest}
        self._validate_content(manifest, body)
        _immutable(self.root, digest + ".json", body)
        _immutable(self.root, self._completion_name(route, snapshot.unit, snapshot.producer, request_id), manifest)
        return self.resend(manifest)

    def resend(self, manifest):
        self.load(manifest)
        if self.sink is not None:
            key = hashlib.sha256(canonical(manifest).encode()).hexdigest()
            try:
                result = self.sink(key, deepcopy(manifest))
                if result is False:
                    raise ConnectionError()
            except Exception:
                raise ConnectionError("Snapshot completion delivery unavailable; immutable publication retained") from None
        return deepcopy(manifest)

    def _validate_content(self, manifest, body):
        validate_manifest(manifest)
        keys = {"route", "unit", "producer", "generation", "requestId", "validAt", "complete", "deleted", "events"}
        if set(body) != keys or any(body[key] != manifest[key] for key in keys - {"events"}):
            raise ValueError("Snapshot object metadata disagrees with completion")
        events = body["events"]
        if not isinstance(events, list) or len(events) != manifest["eventCount"] or snapshot_digest(events) != manifest["eventsHash"]:
            raise ValueError("Snapshot count or digest mismatch")
        if len({canonical(event) for event in events}) != len(events):
            raise ValueError("Snapshot contains duplicate evidence records")
        for event in events:
            validate_event(event)
            if prepare_event(event) != event:
                raise ValueError("Snapshot collector weight is not authoritative")
            if event["eventType"] != "EVIDENCE" or event["evidence"]["runtime"] or event["evidence"].get("replaces") != "unit":
                raise ValueError("Snapshot only accepts complete static unit replacements")
            if event.get("unit") != manifest["unit"] or event["producer"] != manifest["producer"]:
                raise ValueError("Snapshot contains mixed units, revisions or producers")
        expected = self.coordinator.reservation(manifest["route"], manifest["unit"]["urn"], manifest["producer"], manifest["requestId"])
        if expected["generation"] != manifest["generation"]:
            raise ValueError("Snapshot completion has an unreserved generation")

    def load(self, manifest) -> UnitSnapshot:
        validate_manifest(manifest)
        digest = OBJECT_REF.fullmatch(manifest["objectRef"])[1]
        raw = _safe_file(self.root, digest + ".json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Immutable snapshot object hash mismatch")
        body = json.loads(raw)
        if canonical(body).encode() != raw:
            raise ValueError("Snapshot object is not canonical immutable metadata")
        self._validate_content(manifest, body)
        return UnitSnapshot.build(manifest["unit"]["urn"], manifest["producer"], manifest["generation"], manifest["validAt"], manifest["validAt"], body["events"], manifest["deleted"])


class KafkaSnapshotSink:
    def __init__(self, broker, topic="lineage.unit-snapshots", *, ack_timeout=5.0):
        if topic == "lineage.evidence" or type(ack_timeout) not in (int, float) or not 0 < ack_timeout <= 60 or not math.isfinite(ack_timeout):
            raise ValueError("Snapshots need a separate topic and a bounded acknowledgement timeout")
        from confluent_kafka import Producer
        self.topic, self.ack_timeout = topic, ack_timeout
        self.producer = Producer({"bootstrap.servers": broker, "enable.idempotence": True,
            "message.timeout.ms": int(ack_timeout * 1000), "queue.buffering.max.messages": 1, "log_level": 0})

    def __call__(self, key, manifest):
        validate_manifest(manifest)
        delivered = []
        deadline = time.monotonic() + self.ack_timeout
        try:
            self.producer.poll(0)
            self.producer.produce(self.topic, key=key, value=canonical(manifest), on_delivery=lambda error, message: delivered.append(error is None))
            while not delivered and time.monotonic() < deadline:
                self.producer.poll(min(.05, max(0, deadline - time.monotonic())))
            if not delivered or not delivered[0]:
                raise ConnectionError()
        except Exception:
            raise ConnectionError("Snapshot completion delivery unavailable") from None
