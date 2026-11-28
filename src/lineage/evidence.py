"""Strict v2 metadata envelopes and bounded, fail-open emission (WP-11).

Validation errors deliberately omit instance values: malformed evidence must not
copy a payload into logs or exception messages.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from .config import parameters, schema


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(
        schema("factory/specs/evidence/interfaces/envelope-v2.schema.json"),
        format_checker=FormatChecker(),
    )


@lru_cache(maxsize=1)
def _rules() -> dict:
    return parameters()["evidence"]


def validate_event(event: dict) -> None:
    """Validate a complete v2 event; raise ValueError without leaking its values."""
    if next(_validator().iter_errors(event), None) is not None:
        raise ValueError("Invalid evidence envelope: schema validation failed")
    body = {"EVIDENCE": "edge", "QUALITY_ASSERTION": "assertion", "CHANGE_EVENT": "change"}[event["eventType"]]
    if any(key in event for key in {"edge", "assertion", "change"} - {body}):
        raise ValueError("Envelope contains a body for a different event type")


def prepare_event(event: dict) -> dict:
    """Copy v2 input and set the library-owned weight before strict validation.

An explicit runtime value is validated rather than silently corrected. Legacy
input must use upgrade_v1 first, so unsupported fields cannot disappear.
"""
    result = deepcopy(event)
    if result.get("eventType") == "EVIDENCE" and isinstance(result.get("evidence"), dict):
        evidence = result["evidence"]
        source = evidence.get("source")
        if source not in _rules()["weights"]:
            raise ValueError("Unknown evidence source")
        evidence["weight"] = _rules()["weights"][source]
        evidence.setdefault("runtime", source in _rules()["runtime_sources"])
    validate_event(result)
    return result


def upgrade_v1(event: dict) -> dict:
    """Explicit adapter for the complete v1 envelope printed in doc 03.

Legacy identity column mappings become DIRECT/IDENTITY elements. Null pr/commit
are representable by absence in v2; non-null legacy unit fields cannot be
recovered without a unit identity and are rejected rather than discarded.
"""
    result = deepcopy(event)
    if result.get("schemaVersion") not in (None, "1"):
        raise ValueError("Expected a v1 envelope")
    result["schemaVersion"] = "2"
    edge = result.get("edge", {})
    mappings = edge.get("columns")
    if edge.get("type") == "DERIVES" and isinstance(mappings, list):
        if not mappings or not all(isinstance(m, dict) and set(m) == {"from", "to"} for m in mappings):
            raise ValueError("Unsupported legacy column mapping")
        if "elements" in edge:
            raise ValueError("Ambiguous legacy mappings")
        edge["elements"] = [dict(m, **{"class": "DIRECT", "subtype": "IDENTITY"}) for m in mappings]
        del edge["columns"]
    for key in ("pr", "commit"):
        evidence = result.get("evidence", {})
        if key in evidence:
            if evidence[key] is not None:
                raise ValueError("Non-null legacy unit metadata needs an explicit unit migration")
            del evidence[key]
    return prepare_event(result)


def downgrade_v1(event: dict) -> dict:
    """Round-trip the doc 03 v1 identity envelope; reject lossy conversions."""
    validate_event(event)
    result = deepcopy(event)
    if result["eventType"] != "EVIDENCE" or "unit" in result:
        raise ValueError("This envelope has no lossless v1 representation")
    edge = result["edge"]
    if "elements" in edge:
        for mapping in edge["elements"]:
            if set(mapping) != {"from", "to", "class", "subtype"} or mapping["class"] != "DIRECT" or mapping["subtype"] != "IDENTITY":
                raise ValueError("This mapping has no lossless v1 representation")
        edge["columns"] = [{"from": m["from"], "to": m["to"]} for m in edge.pop("elements")]
    del result["schemaVersion"]
    result["evidence"].update(pr=None, commit=None)
    return result


class EvidenceEmitter:
    """Best-effort queue; transport and validation run only on its daemon worker.

``transport`` is callable(event) or exposes send(event). A blocked transport
occupies one daemon worker; the bounded queue fills and subsequent emits drop.
No retry or synchronous fallback is performed on the producer path.
"""

    def __init__(self, transport: Callable[[dict], Any] | Any, max_queue: int = 1024):
        if max_queue < 1:
            raise ValueError("max_queue must be positive")
        self._send = transport if callable(transport) else transport.send
        self._queue: Queue = Queue(maxsize=max_queue)
        self._stop = Event()
        self.accepted = self.sent = self.dropped = self.invalid = self.failed = 0
        self._worker = Thread(target=self._run, name="lineage-evidence", daemon=True)
        self._worker.start()

    def emit(self, event: dict) -> bool:
        """Queue a snapshot without waiting for capacity; never raise to producer."""
        try:
            if self._stop.is_set():
                self.dropped += 1
                return False
            self._queue.put_nowait(deepcopy(event))
            self.accepted += 1
            return True
        except Exception:
            self.dropped += 1
            return False

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.05)
            except Empty:
                continue
            try:
                prepared = prepare_event(event)
            except Exception:
                self.invalid += 1
            else:
                try:
                    self._send(prepared)
                    self.sent += 1
                except Exception:
                    self.failed += 1
            finally:
                self._queue.task_done()

    def close(self, timeout: float = 0.1) -> None:
        """Stop accepting new events; wait at most timeout for the daemon."""
        self._stop.set()
        self._worker.join(timeout=max(0.0, timeout))

    @property
    def pending(self) -> int:
        return self._queue.qsize()
