import copy
import json
import os
import uuid

import pytest

from lineage.archive import EventArchive
from lineage.config import repository_root
from lineage.graph import BoltGraphStore
from lineage.pipeline import RuntimePipeline, ReviewRequired


@pytest.fixture
def runtime_event():
    return json.loads((repository_root() / "factory/specs/evidence/examples/runtime-service-edge.json").read_text())


def test_restart_and_redelivery_keep_graph_and_change_stream_stable(tmp_path, runtime_event):
    archive = EventArchive(tmp_path)
    pipeline = RuntimePipeline(archive)
    changes = pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"])
    assert len(changes) == 1
    before = pipeline.engine.graph_hash(runtime_event["eventTime"])
    assert pipeline.process(runtime_event, recorded_at="2026-11-28T12:00:00Z") == []
    rebuilt = RuntimePipeline(archive)
    assert rebuilt.engine.graph_hash(runtime_event["eventTime"]) == before
    assert len(list(archive.pending_changes())) == 1
    assert len(archive.resolve(runtime_event["evidence"]["rawRef"])) == 1


def test_failed_delivery_retains_outbox_and_retry_sends_once(tmp_path, runtime_event):
    archive = EventArchive(tmp_path)
    pipeline = RuntimePipeline(archive)
    pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"])
    def unavailable(key, event):
        raise ConnectionError("broker down")
    with pytest.raises(ConnectionError):
        pipeline.flush(unavailable)
    sent = []
    assert RuntimePipeline(archive).flush(lambda key, event: sent.append(key)) == 1
    assert pipeline.flush(lambda key, event: sent.append(key)) == 0
    assert len(sent) == 1


def test_graph_failure_retains_durable_receipt_and_repairs_on_retry(tmp_path, runtime_event):
    class UnavailableStore:
        fail = True
        def append(self, assertions):
            if assertions and self.fail:
                raise ConnectionError("graph unavailable")
    store = UnavailableStore()
    archive = EventArchive(tmp_path)
    pipeline = RuntimePipeline(archive, store)
    with pytest.raises(ConnectionError):
        pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"])
    assert len(list(archive.receipts())) == 1
    assert len(list(archive.pending_changes())) == 1
    store.fail = False
    assert pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"]) == []
    assert len(list(archive.receipts())) == 1


def test_archive_commit_failure_never_publishes_an_unaccepted_graph_revision(tmp_path, runtime_event):
    class FailingAcceptance(EventArchive):
        fail = True
        def accept(self, digest, changes):
            if self.fail:
                raise OSError("simulated outbox disk error")
            super().accept(digest, changes)
    class RecordingStore:
        def __init__(self):
            self.assertions = {}
        def append(self, assertions):
            self.assertions.update({a["id"]: a for a in assertions})
    archive = FailingAcceptance(tmp_path)
    store = RecordingStore()
    pipeline = RuntimePipeline(archive, store)
    with pytest.raises(OSError, match="outbox disk"):
        pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"])
    assert list(archive.receipts()) == []
    assert not pipeline.engine.snapshot()
    assert store.assertions == {}
    archive.fail = False
    other = copy.deepcopy(runtime_event)
    other["edge"]["to"]["name"] = "other-service"
    other["evidence"]["rawRef"] = "archive://test/other"
    pipeline.process(other, recorded_at=runtime_event["eventTime"])
    rebuilt = RuntimePipeline(archive, store)
    assert len(rebuilt.engine.snapshot()) == 1
    assert len(store.assertions) == 1


def test_partial_unit_stream_cannot_replace_complete_evidence(tmp_path):
    event = json.loads((repository_root() / "factory/specs/evidence/examples/golden-field-edge.json").read_text())
    archive = EventArchive(tmp_path)
    pipeline = RuntimePipeline(archive)
    with pytest.raises(ValueError, match="complete unit snapshot"):
        pipeline.process(event, recorded_at=event["eventTime"])
    assert list(archive.receipts()) == []
    assert list(tmp_path.glob("*.parquet")) == []


def test_material_expression_change_is_accepted_with_approved_outbox_event(tmp_path):
    event = json.loads((repository_root() / "factory/specs/evidence/examples/golden-field-edge.json").read_text())
    event.pop("unit")
    event["evidence"].update(source="openlineage", weight=0.95, runtime=True, replaces="none")
    event["edge"]["elements"][0]["exprHash"] = "sha256:11111111"
    archive = EventArchive(tmp_path)
    pipeline = RuntimePipeline(archive)
    pipeline.process(event, recorded_at=event["eventTime"])
    changed = copy.deepcopy(event)
    changed["eventTime"] = changed["evidence"]["observedAt"] = "2026-11-28T12:00:00Z"
    changed["evidence"]["rawRef"] = "archive://expression/second"
    changed["edge"]["elements"][0]["exprHash"] = "sha256:22222222"
    changes = pipeline.process(changed, recorded_at=changed["eventTime"])
    assert changes[0]["change"] == "expression_changed"
    assert changes[0]["current"]["expressionHashes"] == ["sha256:11111111", "sha256:22222222"]
    assert len(list(archive.receipts())) == 2
    assert len(list(archive.receipts(accepted=False))) == 0
    assert len(list(archive.pending_changes())) == 2


@pytest.mark.integration
def test_live_neo4j_roundtrip_and_rebuild(tmp_path, runtime_event):
    uri = os.environ.get("LINEAGE_TEST_BOLT_URL")
    if not uri:
        pytest.skip("Set LINEAGE_TEST_BOLT_URL to the disposable local Neo4j")
    namespace = "pipeline-test-" + uuid.uuid4().hex
    store = BoltGraphStore(uri, ("neo4j", os.environ.get("LINEAGE_TEST_DB_PASSWORD", "lineage-local-only")), namespace=namespace)
    try:
        store.verify_connectivity()
        archive = EventArchive(tmp_path)
        pipeline = RuntimePipeline(archive, store)
        pipeline.process(runtime_event, recorded_at=runtime_event["eventTime"])
        expected = pipeline.engine.graph_hash(runtime_event["eventTime"])
        assert store.load()
        for _ in range(3):
            pipeline = RuntimePipeline(archive, store)
            assert pipeline.engine.graph_hash(runtime_event["eventTime"]) == expected
        assert len(store.load()) == 1
    finally:
        with store.driver.session() as session:
            session.run("MATCH (n {namespace: $namespace}) DETACH DELETE n", namespace=namespace).consume()
        store.close()
