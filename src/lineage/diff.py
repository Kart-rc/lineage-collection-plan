"""Material graph differences and approved lineage.changes events (IN-6)."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from .config import schema
from .urn import parse


def _data(value: Any) -> dict:
    return value.as_dict() if hasattr(value, "as_dict") else deepcopy(value)


def material(value: Any) -> dict:
    row = _data(value)
    return {**{k: row.get(k) for k in ("edge", "state", "confidence", "condition", "conditionState")},
            "expressionHashes": sorted(set(row.get("expressionHashes", [])))}


def _version(value: Any, at: str, closed: bool = False, *, include_expressions: bool = False) -> dict:
    row = _data(value)
    version = {
        "state": row["state"], "confidence": row["confidence"],
        "condition": row.get("condition"), "conditionState": row.get("conditionState"),
        "validFrom": row.get("validFrom", at), "validTo": at if closed else row.get("validTo"),
        "sources": sorted(row.get("sources", [])),
    }
    if include_expressions:
        version["expressionHashes"] = sorted(set(row.get("expressionHashes", [])))
    return version


def event_id(event: dict) -> str:
    return hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def diff_snapshots(before: Mapping, after: Mapping, recorded_at: str, causes: list[dict] | tuple[dict, ...], *, valid_at: str | None = None) -> list[dict]:
    """Emit once per material change; updated citations alone are not lineage changes."""
    at = valid_at or recorded_at
    if not causes:
        raise ValueError("Material changes require a traceable cause")
    validator = Draft202012Validator(schema("factory/specs/changes/interfaces/lineage-changes.schema.json"), format_checker=FormatChecker())
    events = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old is not None and new is not None and material(old) == material(new):
            continue
        row = _data(new if new is not None else old)
        if old is None:
            kind = "opened"
        elif new is None:
            kind = "closed"
        elif material(old)["expressionHashes"] != material(new)["expressionHashes"]:
            kind = "expression_changed"
        elif _data(old).get("conditionState") != row.get("conditionState"):
            kind = "condition_activated" if row.get("conditionState") == "active" else "condition_deactivated"
        elif row["state"] == "candidate" and any(c["kind"] == "owner_action" for c in causes):
            kind = "disputed"
        elif _data(old)["state"] != row["state"]:
            kind = "state_changed"
        else:
            kind = "confidence_changed"
        include_expressions = kind == "expression_changed" or any(
            material(value)["expressionHashes"] for value in (old, new) if value is not None)
        current = _version(new if new is not None else old, at, closed=new is None,
                           include_expressions=include_expressions)
        if new is None:
            current["state"] = "retired"
        event = {
            "schemaVersion": "2" if include_expressions else "1", "eventType": "EDGE_CHANGE", "recordedAt": recorded_at,
            "edgeKey": row["edgeKey"], "edge": row["edge"], "change": kind,
            "current": current, "causes": [dict(c) for c in causes],
        }
        if old is not None:
            event["previous"] = _version(old, at, closed=True, include_expressions=include_expressions)
        validator.validate(event)
        events.append(event)
    return events


class LineageDiff:
    """Read-only diffs between graph times or explicitly registered commit times."""

    def __init__(self, graph):
        self.graph = graph
        self.commits: dict[str, str] = {}

    def register_commit(self, commit: str, valid_at: str) -> None:
        if commit in self.commits and self.commits[commit] != valid_at:
            raise ValueError("A commit cannot be reassigned to another time")
        self.commits[commit] = valid_at

    def between(self, base: str, head: str, *, recorded_at: str, causes: list[dict], scope: str | None = None) -> dict:
        base_time, head_time = self.commits.get(base, base), self.commits.get(head, head)
        before, after = self.graph.as_of(base_time, recorded_at), self.graph.as_of(head_time, recorded_at)
        events = diff_snapshots(before, after, recorded_at, causes, valid_at=head_time)
        if scope:
            events = [e for e in events if e["edge"]["from"].startswith(scope) or e["edge"]["to"].startswith(scope)]
        def nodes(rows):
            endpoints = {r["edge"][side] for r in map(_data, rows.values()) for side in ("from", "to")}
            result = endpoints | {parse(urn).dataset for urn in endpoints}
            return {urn for urn in result if scope is None or urn.startswith(scope)}
        added, removed = nodes(after) - nodes(before), nodes(before) - nodes(after)
        return {"events": events, "added": sorted(added), "removed": sorted(removed), "changed": sorted({e["edgeKey"] for e in events if e["change"] not in {"opened", "closed"}})}
