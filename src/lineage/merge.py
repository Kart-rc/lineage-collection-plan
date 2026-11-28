"""Deterministic evidence scoring and candidate atomic unit replacement.

Approved envelopes cannot mark a complete/empty extraction. UnitSnapshot is an
explicit local protocol proposal, not a new accepted Kafka envelope type.
"""
from __future__ import annotations

import math
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from jsonschema import Draft202012Validator, FormatChecker

from .config import parameters, schema
from .diff import diff_snapshots, material
from .graph import canonical, content_hash, histories_from_snapshots, timestamp, interval_start, interval_end
from .urn import normalize, parse


def snapshot_digest(events: Iterable[dict]) -> str:
    return "sha256:" + content_hash(sorted({canonical(event) for event in events}))


@dataclass(frozen=True)
class UnitSnapshot:
    unit: str
    producer: str
    generation: int
    valid_at: str
    recorded_at: str
    events: tuple[dict, ...]
    digest: str
    complete: bool = True
    deleted: bool = False

    @classmethod
    def build(cls, unit: str, producer: str, generation: int, valid_at: str, recorded_at: str, events: Iterable[dict], deleted: bool = False):
        rows = tuple(json.loads(row) for row in sorted({canonical(event) for event in events}))
        return cls(unit, producer, generation, valid_at, recorded_at, rows, snapshot_digest(rows), True, deleted)

    def as_dict(self) -> dict:
        return {"unit": self.unit, "producer": self.producer, "generation": self.generation,
                "valid_at": self.valid_at, "recorded_at": self.recorded_at, "events": deepcopy(list(self.events)),
                "digest": self.digest, "complete": self.complete, "deleted": self.deleted}

    @classmethod
    def from_dict(cls, value: dict):
        return cls(**{**deepcopy(value), "events": tuple(value["events"])})


@dataclass(frozen=True)
class EdgeState:
    id: str
    edge: dict
    confidence: float
    state: str
    condition: str | None
    condition_state: str | None
    sources: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evidence: tuple[dict, ...]
    valid_from: str
    last_runtime_at: str | None = None
    valid_to: str | None = None
    expression_hashes: tuple[str, ...] = ()

    @property
    def edge_key(self):
        return f'{self.edge["from"]} | {self.edge["type"]} | {self.edge["to"]}'

    @property
    def from_urn(self):
        return self.edge["from"]

    @property
    def to_urn(self):
        return self.edge["to"]

    @property
    def type(self):
        return self.edge["type"]

    @property
    def class_(self):
        return self.edge.get("class")

    @property
    def subtype(self):
        return self.edge.get("subtype")

    def as_dict(self):
        return {"id": self.id, "edgeKey": self.edge_key, "edge": deepcopy(self.edge), "confidence": self.confidence,
                "state": self.state, "condition": self.condition, "conditionState": self.condition_state,
                "sources": list(self.sources), "evidenceRefs": list(self.evidence_refs), "evidence": deepcopy(list(self.evidence)),
                "validFrom": self.valid_from, "validTo": self.valid_to, "lastRuntimeAt": self.last_runtime_at,
                "expressionHashes": list(self.expression_hashes)}

    @classmethod
    def from_dict(cls, row):
        return cls(row["id"], deepcopy(row["edge"]), row["confidence"], row["state"], row.get("condition"),
                   row.get("conditionState"), tuple(row["sources"]), tuple(row["evidenceRefs"]), tuple(deepcopy(row["evidence"])),
                   row["validFrom"], row.get("lastRuntimeAt"), row.get("validTo"), tuple(row.get("expressionHashes", [])))


@dataclass(frozen=True)
class MergeResult:
    operation_id: str
    changes: tuple[dict, ...] = ()
    held: bool = False
    alert: dict | None = None
    duplicate: bool = False


class MergeEngine:
    def __init__(self, initial_flags: dict[str, str] | None = None, graph=None):
        self.parameters = parameters()
        self.graph = graph
        self.initial_flags = {normalize(k): str(v) for k, v in (initial_flags or {}).items()}
        self._validator = Draft202012Validator(schema("factory/specs/evidence/interfaces/envelope-v2.schema.json"), format_checker=FormatChecker())
        self._operations: dict[str, dict] = {}
        self._held: dict[str, dict] = {}
        self._generation_content: dict[tuple, str] = {}

    def _validate(self, event: dict) -> dict:
        event = deepcopy(event)
        self._validator.validate(event)
        timestamp(event["eventTime"])
        if event["eventType"] == "EVIDENCE":
            evidence = event["evidence"]
            if evidence["weight"] != self.parameters["evidence"]["weights"][evidence["source"]]:
                raise ValueError("Evidence weight must be the approved source weight")
            timestamp(evidence["observedAt"])
            if evidence["runtime"] and evidence.get("replaces") == "unit":
                raise ValueError("Runtime evidence is additive and cannot replace a unit")
            for name in ("from", "to"):
                endpoint = parse(event["edge"][name]["namespace"] + "/" + event["edge"][name]["name"])
                event["edge"][name] = {"namespace": endpoint.namespace, "name": endpoint.name}
            if event.get("unit", {}).get("pr") is not None:
                raise ValueError("PR evidence belongs in an isolated overlay, not the production merger")
        return event

    def ingest(self, envelope: dict, recorded_at: str | None = None) -> MergeResult:
        event = self._validate(envelope)
        if event["eventType"] == "EVIDENCE" and event["evidence"].get("replaces") == "unit":
            raise ValueError("Unit replacement needs a complete UnitSnapshot; one envelope is not a batch boundary")
        at = event.get("evidence", {}).get("observedAt", event.get("change", {}).get("at", event["eventTime"]))
        op = {"kind": "event", "at": timestamp(at), "recordedAt": timestamp(recorded_at or event["eventTime"]), "event": event}
        op["id"] = content_hash({"kind": "event", "event": event})
        return self._submit(op)

    def replace_unit(self, snapshot: UnitSnapshot) -> MergeResult:
        return self._replace_unit(snapshot)

    def apply_released_snapshot(self, snapshot: UnitSnapshot, *, owner_action_id: str,
                                held_operation_id: str) -> MergeResult:
        """Apply a durable approval after its receipt and actor were verified.

        The pipeline checks the approval against its persisted held
        receipt. Core revalidates the entire snapshot and original identity,
        bypassing only the mass-close decision. The supplied recorded_at is the
        approval transaction time; valid_at and the operation identity stay put.
        """
        if not isinstance(owner_action_id, str) or not owner_action_id.strip():
            raise ValueError("An attributable owner action is required")
        if not isinstance(held_operation_id, str) or not held_operation_id:
            raise ValueError("The original held operation identity is required")
        return self._replace_unit(snapshot, release=(owner_action_id, held_operation_id))

    def _replace_unit(self, snapshot: UnitSnapshot, *, release: tuple[str, str] | None = None) -> MergeResult:
        if snapshot.complete is not True or type(snapshot.generation) is not int or snapshot.generation < 0:
            raise ValueError("A complete snapshot and nonnegative generation are required")
        if snapshot.deleted and snapshot.events:
            raise ValueError("A deleted unit must have an empty complete event set")
        if snapshot.digest != snapshot_digest(snapshot.events):
            raise ValueError("Incomplete or corrupted snapshot: completion hash mismatch")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*@[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?", snapshot.producer):
            raise ValueError("A versioned producer is required even for empty snapshots")
        unit = normalize(snapshot.unit)
        if parse(unit).scheme != "unit":
            raise ValueError("Expected a unit:// identifier")
        rows = []
        for envelope in snapshot.events:
            event = self._validate(envelope)
            if event["eventType"] != "EVIDENCE" or event["evidence"]["runtime"] or event["evidence"].get("replaces") != "unit":
                raise ValueError("A unit snapshot contains only replacing static evidence")
            if event["producer"] != snapshot.producer or normalize(event.get("unit", {}).get("urn", "")) != unit:
                raise ValueError("Snapshot producer and unit must match every event")
            rows.append(event)
        rows = [json.loads(row) for row in sorted({canonical(event) for event in rows})]
        if len({canonical(e["unit"]) for e in rows}) > 1:
            raise ValueError("All records in one snapshot must describe the same unit revision")
        body = snapshot.as_dict()
        body.update(unit=unit, events=rows, valid_at=timestamp(snapshot.valid_at), recorded_at=timestamp(snapshot.recorded_at))
        op = {"kind": "snapshot", "at": body["valid_at"], "recordedAt": body["recorded_at"], "snapshot": body}
        op["id"] = content_hash({k: v for k, v in body.items() if k != "recorded_at"})
        if release is not None:
            owner_action_id, held_operation_id = release
            if op["id"] != held_operation_id:
                raise ValueError("Released snapshot does not match the original held operation")
            op["releaseCause"] = {"kind": "owner_action", "ref": owner_action_id}
        if op["id"] in self._operations:
            return MergeResult(op["id"], duplicate=True)
        if release is None and op["id"] in self._held:
            return MergeResult(op["id"], held=True, duplicate=True)
        generation_key = (snapshot.producer.rsplit("@", 1)[0], unit, snapshot.generation)
        if generation_key in self._generation_content and self._generation_content[generation_key] != op["id"]:
            raise ValueError("Conflicting content for an already completed unit generation")
        before_rows = self._active_events(list(self._operations.values()), op["at"], None)[0]
        after_rows = self._active_events([*self._operations.values(), op], op["at"], None)[0]
        extractor = snapshot.producer.rsplit("@", 1)[0]
        owned = {key for e in before_rows if e["producer"].rsplit("@", 1)[0] == extractor for key, _, _ in self._flatten(e)}
        before_keys = {key for e in before_rows for key, _, _ in self._flatten(e)}
        after_keys = {key for e in after_rows for key, _, _ in self._flatten(e)}
        closed = (before_keys - after_keys) & owned
        limits = self.parameters["incremental"]["mass_close_hold"]
        share = len(closed) / len(owned) if owned else 0
        if release is None and len(closed) >= limits["min_edges"] and share > limits["max_share_of_extractor_edges"]:
            alert = {"unit": unit, "producer": snapshot.producer, "generation": snapshot.generation,
                     "closingEdges": len(closed), "extractorEdges": len(owned), "share": share,
                     "reason": "mass_close_hold", "operationId": op["id"]}
            self._held[op["id"]] = {"operation": op, "alert": alert}
            return MergeResult(op["id"], held=True, alert=deepcopy(alert))
        result = self._submit(op)
        if not result.held:
            self._generation_content[generation_key] = op["id"]
            if release is not None:
                self._held.pop(op["id"], None)
        return result

    def release_hold(self, operation_id: str, *, owner_action_id: str) -> MergeResult:
        held = self._held[operation_id]
        return self.apply_released_snapshot(UnitSnapshot.from_dict(held["operation"]["snapshot"]),
                                            owner_action_id=owner_action_id, held_operation_id=operation_id)

    def owner_action(self, edge_id: str, action: str, action_id: str, at: str, recorded_at: str | None = None) -> MergeResult:
        if action not in {"dispute", "confirm", "reject", "review"} or not action_id:
            raise ValueError("Expected a named owner dispute, confirm, reject or review action")
        if edge_id not in self.snapshot(at):
            raise ValueError("Owner action refers to an unknown edge")
        op = {"kind": "owner", "at": timestamp(at), "recordedAt": timestamp(recorded_at or at),
              "edge": edge_id, "action": action, "actionId": action_id}
        op["id"] = content_hash({k: v for k, v in op.items() if k != "recordedAt"})
        return self._submit(op)

    def advance_clock(self, at: str, recorded_at: str | None = None) -> MergeResult:
        op = {"kind": "clock", "at": timestamp(at), "recordedAt": timestamp(recorded_at or at)}
        op["id"] = content_hash({"kind": "clock", "at": op["at"]})
        return self._submit(op)

    def _active_events(self, operations: list[dict], at: str, recorded_at: str | None):
        eligible = [o for o in operations if o["at"] <= at and (recorded_at is None or o["recordedAt"] <= recorded_at)]
        snapshots, additive, flags, owners = {}, [], dict(self.initial_flags), {}
        for op in sorted(eligible, key=lambda o: (o["at"], o["id"])):
            if op["kind"] == "snapshot":
                row = op["snapshot"]
                key = (row["producer"].rsplit("@", 1)[0], row["unit"])
                if key not in snapshots or row["generation"] > snapshots[key]["generation"]:
                    snapshots[key] = row
            elif op["kind"] == "owner":
                owners[op["edge"]] = op
            elif op["kind"] == "event":
                event = op["event"]
                if event["eventType"] == "EVIDENCE":
                    additive.append(event)
                elif event["eventType"] == "CHANGE_EVENT" and event["change"]["kind"] == "flag_change":
                    flags[normalize(event["change"]["subject"])] = event["change"].get("to")
        return additive + [event for row in snapshots.values() for event in row["events"]], flags, owners

    def _flatten(self, event):
        edge = event["edge"]
        endpoints = {k: normalize(edge[k]["namespace"] + "/" + edge[k]["name"]) for k in ("from", "to")}
        condition = edge.get("condition")
        elements = edge.get("elements") or [None]
        for element in elements:
            body = {**endpoints, "type": edge["type"]}
            if element is not None:
                body.update({k: element[k] for k in ("class", "subtype")})
                body["masking"] = element.get("masking", False)
                if element["from"] is not None:
                    body["from"] = normalize(body["from"] + "#" + element["from"])
                if element["class"] == "DIRECT" and element["to"] is not None:
                    body["to"] = normalize(body["to"] + "#" + element["to"])
            yield content_hash({"edge": body, "condition": condition}), body, condition

    def _project(self, operations: list[dict], at: str, recorded_at: str | None = None) -> dict[str, EdgeState]:
        events, flags, owners = self._active_events(operations, at, recorded_at)
        buckets = {}
        for event in events:
            for (key, edge, condition), element in zip(self._flatten(event), event["edge"].get("elements") or [None]):
                bucket = buckets.setdefault(key, (edge, condition, [], set()))
                bucket[2].append(event)
                if element is not None and element.get("exprHash"):
                    bucket[3].add(element["exprHash"])
        result = {}
        weights = self.parameters["evidence"]["weights"]
        for key, (edge, condition, events, expression_hashes) in buckets.items():
            sources = tuple(sorted({e["evidence"]["source"] for e in events}))
            confidence = round(1 - math.prod(1 - weights[source] for source in sources), 12)
            runtime = [timestamp(e["evidence"]["observedAt"]) for e in events if e["evidence"]["runtime"]]
            last_runtime = max(runtime) if runtime else None
            state = "candidate"
            if confidence >= self.parameters["states"]["probable"]["min_confidence"]:
                state = "probable"
            if confidence >= self.parameters["states"]["confirmed"]["min_confidence"] and runtime:
                state = "confirmed"
            if last_runtime and datetime.fromisoformat(at.replace("Z", "+00:00")) - datetime.fromisoformat(last_runtime.replace("Z", "+00:00")) >= timedelta(days=self.parameters["states"]["dormant"]["after_days_without_runtime"]):
                state = "dormant"
            if "owner" in sources:
                state = "verified"
            owner = owners.get(key)
            if owner:
                if owner["action"] in {"dispute", "reject"}:
                    state = "candidate"
                elif owner["action"] == "confirm":
                    state = "verified"
            condition_state = None
            if condition:
                flag, operator, expected = condition.split(" ")
                actual = flags.get(normalize(flag))
                active = actual is not None and ((actual == expected) if operator == "==" else (actual != expected))
                condition_state = "active" if active else "latent"
            evidence = tuple({"rawRef": e["evidence"]["rawRef"], "producer": e["producer"], "source": e["evidence"]["source"],
                              "observedAt": timestamp(e["evidence"]["observedAt"]),
                              **({"unit": deepcopy(e["unit"])} if "unit" in e else {})} for e in sorted(events, key=canonical))
            # Duplicate source observations retain provenance but never add confidence.
            evidence = tuple({canonical(e): e for e in evidence}.values())
            result[key] = EdgeState(key, edge, confidence, state, condition, condition_state, sources,
                                    tuple(sorted({e["rawRef"] for e in evidence})), evidence,
                                    min(e["observedAt"] for e in evidence), last_runtime, None, tuple(sorted(expression_hashes)))
        return result

    def _histories(self, operations: list[dict], at: str, recorded_at: str | None = None):
        eligible = [o for o in operations if o["at"] <= at and (recorded_at is None or o["recordedAt"] <= recorded_at)]
        points = {o["at"] for o in eligible}
        days = self.parameters["states"]["dormant"]["after_days_without_runtime"]
        for op in eligible:
            if op["kind"] == "event" and op["event"]["eventType"] == "EVIDENCE" and op["event"]["evidence"]["runtime"]:
                expiry = timestamp((datetime.fromisoformat(op["at"].replace("Z", "+00:00")) + timedelta(days=days)).isoformat())
                if expiry <= at:
                    points.add(expiry)
        return histories_from_snapshots([(point, self._project(eligible, point, recorded_at)) for point in sorted(points)])

    def snapshot(self, valid_at: str | None = None, recorded_at: str | None = None) -> dict[str, EdgeState]:
        if not self._operations:
            return {}
        at = timestamp(valid_at) if valid_at else max(o["at"] for o in self._operations.values())
        recorded_at = timestamp(recorded_at) if recorded_at else None
        horizon = max(at, max(o["at"] for o in self._operations.values()))
        histories = self._histories(list(self._operations.values()), horizon, recorded_at)
        return {key: EdgeState.from_dict(row) for key, history in histories.items() for row in history
                if interval_start(row) <= at and (interval_end(row) is None or at < interval_end(row))}

    def graph_hash(self, valid_at: str | None = None, recorded_at: str | None = None) -> str:
        return content_hash({k: v.as_dict() for k, v in self.snapshot(valid_at, recorded_at).items()})

    def _causes(self, op):
        if "releaseCause" in op:
            return [op["releaseCause"]]
        if op["kind"] == "snapshot":
            refs = sorted({e["evidence"]["rawRef"] for e in op["snapshot"]["events"]})
            return [{"kind": "evidence", "ref": ref} for ref in refs] or [{"kind": "evidence", "ref": "candidate-unit-snapshot:" + op["snapshot"]["digest"]}]
        if op["kind"] == "owner":
            return [{"kind": "owner_action", "ref": op["actionId"]}]
        if op["kind"] == "clock":
            return [{"kind": "clock", "ref": "IN-8:30-days-without-runtime"}]
        event = op["event"]
        return [{"kind": "evidence", "ref": event["evidence"]["rawRef"]}] if event["eventType"] == "EVIDENCE" else [{"kind": "change_event", "ref": event.get("change", {}).get("ref") or op["id"]}]

    def _submit(self, op: dict) -> MergeResult:
        if op["id"] in self._operations:
            return MergeResult(op["id"], duplicate=True)
        pending = [*self._operations.values(), op]
        at = max(o["at"] for o in pending)
        before = self.snapshot()
        histories = self._histories(pending, at)
        after = {key: row for key, history in histories.items() for row in history if interval_end(row) is None}
        old_histories = self._histories(list(self._operations.values()), at)
        def view(history, point):
            return {key: row for key, rows in history.items() for row in rows
                    if interval_start(row) <= point and (interval_end(row) is None or point < interval_end(row))}
        points = sorted({interval_start(row) for rows in histories.values() for row in rows})
        if self._operations and op["at"] < max(o["at"] for o in self._operations.values()):
            # Late evidence can open an earlier interval even when today's score
            # is unchanged. Emit each changed historical material state once.
            points = sorted(set(points) | {interval_start(row) for rows in old_histories.values() for row in rows})
            changes, last_pairs = [], {}
            for point in points:
                previous, current = view(old_histories, point), view(histories, point)
                for key in sorted(set(previous) | set(current)):
                    pair = canonical([material(previous[key]) if key in previous else None,
                                      material(current[key]) if key in current else None])
                    if last_pairs.get(key) == pair:
                        continue
                    last_pairs[key] = pair
                    changes.extend(diff_snapshots({key: previous[key]} if key in previous else {},
                                                  {key: current[key]} if key in current else {},
                                                  op["recordedAt"], self._causes(op), valid_at=point))
        else:
            changes = diff_snapshots(before, after, op["recordedAt"], self._causes(op), valid_at=op["at"])
        if self.graph is not None:
            # Replaying an older transaction may refine every later knowledge
            # view. Append those corrections in one database transaction.
            from .graph import BitemporalGraph
            staged = BitemporalGraph()
            staged._assertions = list(self.graph.assertions)
            cutoffs = sorted({o["recordedAt"] for o in pending if o["recordedAt"] >= op["recordedAt"]})
            for cutoff in cutoffs:
                staged.replace_history(self._histories(pending, at, cutoff), cutoff, operation_id=op["id"])
            additions = list(staged.assertions[len(self.graph.assertions):])
            if self.graph.store is not None and additions:
                self.graph.store.append(additions)
            self.graph._assertions.extend(additions)
        self._operations[op["id"]] = deepcopy(op)
        return MergeResult(op["id"], tuple(changes))
