"""Append-only bitemporal edge assertions and a common Bolt persistence adapter.

Corrections append complete timelines for affected edges. Select transaction time
first, then valid time, so late knowledge cannot leak into earlier recorded views.
"""
from __future__ import annotations
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Mapping
from .diff import material


def timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a timezone-aware ISO timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("A timestamp requires a timezone")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _row(value) -> dict:
    return value.as_dict() if hasattr(value, "as_dict") else deepcopy(value)


def visible_row(row: dict) -> dict:
    return {k: deepcopy(v) for k, v in row.items() if not k.startswith("_effective")}


def interval_start(row: dict) -> str:
    return row.get("_effectiveFrom", row["validFrom"])


def interval_end(row: dict) -> str | None:
    return row.get("_effectiveTo", row["validTo"])


def histories_from_snapshots(snapshots: list[tuple[str, Mapping]]) -> dict[str, list[dict]]:
    """Separate valid edge versions from time-specific provenance assertions.

    A repeated observation splits the provenance interval, preserving the valid
    edge version's original start. This keeps later citations out of past reads
    without reporting a source refresh as a new material lineage version.
    """
    histories: dict[str, list[dict]] = {}
    opened: dict[str, dict] = {}
    segments: dict[str, list[dict]] = {}
    for at, snapshot in sorted(snapshots, key=lambda item: item[0]):
        at = timestamp(at)
        rows = {k: _row(v) for k, v in snapshot.items()}
        for key in sorted(set(opened) | set(rows)):
            old, new = opened.get(key), rows.get(key)
            if old is not None and new is not None and material(old) == material(new):
                new["validFrom"], new["validTo"] = old["validFrom"], None
                if visible_row(old) == new:
                    continue
                old["_effectiveTo"] = at
                new["_effectiveFrom"], new["_effectiveTo"] = at, None
                histories[key].append(new)
                segments[key].append(new)
                opened[key] = new
                continue
            if old is not None:
                for segment in segments.pop(key):
                    segment["validTo"] = at
                old["_effectiveTo"] = at
                opened.pop(key)
            if new is not None:
                new["validFrom"], new["validTo"] = at, None
                new["_effectiveFrom"], new["_effectiveTo"] = at, None
                histories.setdefault(key, []).append(new)
                opened[key], segments[key] = new, [new]
    return histories


class BitemporalGraph:
    def __init__(self, store=None):
        self.store = store
        self._assertions = store.load() if store is not None else []
        self._snapshots: list[tuple[str, dict]] = []

    @property
    def assertions(self) -> tuple[dict, ...]:
        return tuple(deepcopy(self._assertions))

    def replace_history(self, histories: Mapping[str, list[dict]], recorded_at: str, *, operation_id: str = "") -> None:
        recorded_at = timestamp(recorded_at)
        latest = self._latest(recorded_at)
        pending = []
        sequence = max((a["sequence"] for a in self._assertions), default=0) + 1
        for key in sorted(set(latest) | set(histories)):
            timeline = deepcopy(histories.get(key, []))
            if canonical(timeline) == canonical(latest.get(key, {}).get("timeline", [])):
                continue
            for row in timeline:
                row["validFrom"] = timestamp(row["validFrom"])
                if row.get("validTo") is not None:
                    row["validTo"] = timestamp(row["validTo"])
                    if row["validTo"] <= row["validFrom"]:
                        raise ValueError("Valid intervals must be nonempty and half-open")
            assertion = {"key": key, "recordedAt": recorded_at, "sequence": sequence, "timeline": timeline}
            assertion["id"] = content_hash({**assertion, "operation": operation_id})
            pending.append(assertion)
        if self.store is not None and pending:
            self.store.append(pending)
        self._assertions.extend(pending)

    def commit(self, snapshot: Mapping, valid_at: str, recorded_at: str, *, operation_id: str = "") -> None:
        at = timestamp(valid_at)
        pending = [(t, r) for t, r in self._snapshots if t != at] + [(at, {k: _row(v) for k, v in snapshot.items()})]
        self.replace_history(histories_from_snapshots(pending), recorded_at, operation_id=operation_id)
        self._snapshots = pending

    def _latest(self, recorded_at: str | None) -> dict[str, dict]:
        cutoff = timestamp(recorded_at) if recorded_at is not None else None
        latest = {}
        for a in self._assertions:
            if cutoff is not None and a["recordedAt"] > cutoff:
                continue
            old = latest.get(a["key"])
            if old is None or (a["recordedAt"], a["sequence"], a["id"]) > (old["recordedAt"], old["sequence"], old["id"]):
                latest[a["key"]] = a
        return latest

    def as_of(self, valid_at: str, recorded_at: str | None = None) -> dict[str, dict]:
        at = timestamp(valid_at)
        return {key: visible_row(row) for key, a in self._latest(recorded_at).items() for row in a["timeline"]
                if interval_start(row) <= at and (interval_end(row) is None or at < interval_end(row))}

    def during(self, start: str, end: str, recorded_at: str | None = None) -> list[dict]:
        start, end = timestamp(start), timestamp(end)
        if end < start:
            raise ValueError("Incident window ends before it starts")
        return [visible_row(row) for a in self._latest(recorded_at).values() for row in a["timeline"]
                if interval_start(row) <= end and (interval_end(row) is None or interval_end(row) > start)]

    def graph_hash(self, valid_at: str, recorded_at: str | None = None) -> str:
        return content_hash(self.as_of(valid_at, recorded_at))


class BoltGraphStore:
    """Parameterized common openCypher; single writer per namespace.

    No APOC, schema constraints, or mutable edge relationships. AWS compatibility
    remains unverified until the adapter is actually run against stage Neptune.
    """
    def __init__(self, uri: str, auth: tuple[str, str] | None = None, *, namespace: str = "lineage-candidate", database: str | None = None, driver=None):
        if driver is None:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=auth)
        self.driver, self.namespace, self.database = driver, namespace, database

    def _session(self):
        return self.driver.session(**({"database": self.database} if self.database else {}))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def append(self, assertions: list[dict]) -> None:
        def write(tx):
            for assertion in assertions:
                params = {"namespace": self.namespace, "id": assertion["id"]}
                if tx.run("MATCH (a:LineageRevision {namespace: $namespace, id: $id}) RETURN a.id AS id", **params).single():
                    continue
                tx.run("CREATE (a:LineageRevision {namespace: $namespace, id: $id, body: $body})", **params, body=canonical(assertion)).consume()
                for row in assertion["timeline"]:
                    edge = row["edge"]
                    tx.run("MERGE (s:LineageNode {namespace: $namespace, urn: $source}) "
                           "MERGE (t:LineageNode {namespace: $namespace, urn: $target}) "
                           "CREATE (s)-[r:LINEAGE_VERSION {assertionId: $id, versionId: $version, "
                           "edgeKey: $edge_key, validFrom: $valid_from, validTo: $valid_to, recordedAt: $recorded_at, body: $body}]->(t)",
                           **params, source=edge["from"], target=edge["to"], version=content_hash({"key": assertion["key"], "row": row}),
                           edge_key=row["edgeKey"], valid_from=row["validFrom"], valid_to=row["validTo"], recorded_at=assertion["recordedAt"], body=canonical(row)).consume()
        with self._session() as session:
            session.execute_write(write)

    def load(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute_read(lambda tx: [r["body"] for r in tx.run(
                "MATCH (a:LineageRevision {namespace: $namespace}) RETURN a.body AS body", namespace=self.namespace)])
        return sorted((json.loads(row) for row in rows), key=lambda a: (a["recordedAt"], a["sequence"], a["id"]))

    def close(self) -> None:
        self.driver.close()
