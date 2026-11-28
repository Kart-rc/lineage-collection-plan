"""WP-11 schema, metadata exclusion, explicit legacy compatibility and faults."""
from copy import deepcopy
import json
from pathlib import Path
import re
from threading import Event
import time

import pytest

from lineage.config import repository_root
from lineage.evidence import EvidenceEmitter, downgrade_v1, prepare_event, upgrade_v1, validate_event

ROOT = repository_root()
EXAMPLES = ROOT / "factory/specs/evidence/examples"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.stem)
def test_all_approved_examples_validate(path):
    validate_event(json.loads(path.read_text()))


@pytest.mark.parametrize("path", sorted((EXAMPLES / "invalid").glob("*.json")), ids=lambda p: p.stem)
def test_all_invalid_examples_rejected(path):
    with pytest.raises(ValueError):
        validate_event(json.loads(path.read_text()))


def event():
    return json.loads((EXAMPLES / "runtime-service-edge.json").read_text())


def test_weight_is_library_owned_and_input_not_mutated():
    item = event()
    item["evidence"]["weight"] = 0.01
    result = prepare_event(item)
    assert result["evidence"]["weight"] == 0.90
    assert item["evidence"]["weight"] == 0.01
    item["evidence"]["weight"] = 100
    assert prepare_event(item)["evidence"]["weight"] == 0.90


@pytest.mark.parametrize("location", ["root", "edge", "evidence", "dataset"])
def test_unknown_payload_fields_rejected_without_error_value_leak(location):
    item = event()
    target = {"root": item, "edge": item["edge"], "evidence": item["evidence"], "dataset": item["edge"]["from"]}[location]
    target["payload"] = "SECRET_SENTINEL"
    with pytest.raises(ValueError) as error:
        prepare_event(item)
    assert "SECRET_SENTINEL" not in str(error.value)


def test_invalid_time_and_mixed_event_bodies_rejected():
    item = event()
    item["eventTime"] = "not-a-time"
    with pytest.raises(ValueError):
        prepare_event(item)
    item = event()
    item["change"] = json.loads((EXAMPLES / "change-event.json").read_text())["change"]
    with pytest.raises(ValueError):
        prepare_event(item)


def test_actual_doc03_v1_fixture_round_trip_without_field_loss():
    document = (ROOT / "docs/03-collection-and-build-guide.md").read_text()
    v1 = json.loads(re.search(r"```json\n(.*?)\n```", document, re.S)[1])
    upgraded = upgrade_v1(v1)
    validate_event(upgraded)
    assert upgraded["edge"]["elements"][0]["subtype"] == "IDENTITY"
    assert downgrade_v1(upgraded) == v1
    assert "schemaVersion" not in v1
    with pytest.raises(ValueError):
        prepare_event(v1)


def test_unrepresentable_legacy_metadata_rejected_rather_than_lost():
    item = event()
    item.pop("schemaVersion")
    item["evidence"]["commit"] = "abcdef123"
    with pytest.raises(ValueError, match="explicit unit migration"):
        upgrade_v1(item)


def test_transport_failure_and_invalid_events_are_dropped_off_producer_thread():
    sent = Event()
    def broken_transport(item):
        sent.set()
        raise ConnectionError("broker unavailable")
    emitter = EvidenceEmitter(broken_transport)
    assert emitter.emit(event())
    assert sent.wait(2)
    assert emitter.emit({"payload": "SECRET_SENTINEL"})
    emitter.close(2)
    assert emitter.failed == 1
    assert emitter.invalid == 1


def test_hung_transport_queue_is_bounded_and_producer_path_never_waits():
    entered, release = Event(), Event()
    def stalled_transport(item):
        entered.set()
        release.wait(5)
    emitter = EvidenceEmitter(stalled_transport, max_queue=2)
    try:
        assert emitter.emit(event())
        assert entered.wait(2)
        durations = []
        item = event()
        for _ in range(2000):
            start = time.perf_counter_ns()
            emitter.emit(item)
            durations.append(time.perf_counter_ns() - start)
        assert emitter.pending == 2
        assert emitter.dropped == 1998
        p99_ns = sorted(durations)[int(len(durations) * .99)]
        # Local emit microbenchmark only; it does not establish checkout p99.
        assert p99_ns < 1_000_000
    finally:
        release.set()
        emitter.close(2)
    assert emitter.emit(event()) is False


def test_producer_copy_failure_never_escapes():
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise RuntimeError("bad object")
    emitter = EvidenceEmitter(lambda item: None)
    try:
        assert emitter.emit(Uncopyable()) is False
    finally:
        emitter.close()
