"""Durable complete-unit publication and combined acceptance/recovery semantics."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from lineage.archive import EventArchive
from lineage.config import repository_root
from lineage.merge import UnitSnapshot
from lineage.pipeline import RuntimePipeline, ReviewRequired
from lineage.snapshots import SnapshotCoordinator, SnapshotPublisher, canonical, route_namespace

T1 = "2026-11-27T12:00:00Z"
T2 = "2026-11-28T12:00:00Z"
T3 = "2026-11-29T12:00:00Z"
ROUTE = {"repository": "opentelemetry-demo", "stage": "merged", "pr": None}


def event():
    return json.loads((repository_root() / "factory/specs/evidence/examples/golden-field-edge.json").read_text())


def publication(root, request="first", at=T1, *, rows=None, deleted=False, route=None, producer=None):
    route = deepcopy(route or ROUTE)
    revision = event()["unit"]
    if route["pr"] is not None:
        revision["pr"] = route["pr"]
    rows = deepcopy(rows if rows is not None else [event()])
    producer = producer or event()["producer"]
    for row in rows:
        row["unit"] = deepcopy(revision)
        row["producer"] = producer
        row["eventTime"] = row["evidence"]["observedAt"] = at
    coordinator = SnapshotCoordinator(root)
    generation = coordinator.reserve(route, revision["urn"], producer, request)
    snapshot = UnitSnapshot.build(revision["urn"], producer, generation, at, at, rows, deleted)
    return SnapshotPublisher(root).publish(snapshot, route, request, unit_revision=revision)


def test_reservation_is_durable_idempotent_serialized_and_version_independent(tmp_path):
    unit = event()["unit"]["urn"]
    producer = event()["producer"]
    def reserve(index):
        return SnapshotCoordinator(tmp_path).reserve(ROUTE, unit, producer, f"r{index}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        generations = list(pool.map(reserve, range(10)))
    assert sorted(generations) == list(range(1, 11))
    coordinator = SnapshotCoordinator(tmp_path)
    assert coordinator.reserve(ROUTE, unit, producer, "r0") == generations[0]
    assert coordinator.reserve(ROUTE, unit, producer.replace("0.1.0", "0.2.0"), "version-bump") == 11
    assert coordinator.reservation(ROUTE, unit, producer, "r0")["reserved_at"]
    with pytest.raises(ValueError):
        coordinator.reserve(ROUTE, unit, producer.replace("0.1.0", "0.2.0"), "r0")


def test_completion_is_last_and_failed_send_has_a_durable_retry(tmp_path):
    manifest = publication(tmp_path)
    sent = []
    def unavailable(key, completion):
        assert SnapshotPublisher(tmp_path).load(completion).digest == completion["eventsHash"]
        sent.append(key)
        raise OSError("unavailable")
    publisher = SnapshotPublisher(tmp_path, unavailable)
    with pytest.raises(ConnectionError):
        publisher.resend(manifest)
    assert publisher.completed(ROUTE, manifest["unit"]["urn"], manifest["producer"], "first") == manifest
    successful = []
    SnapshotPublisher(tmp_path, lambda key, completion: successful.append(key)).resend(manifest)
    assert sent == successful


def test_same_request_changed_content_never_overwrites_completion(tmp_path):
    manifest = publication(tmp_path)
    changed = event()
    changed["edge"]["elements"][0]["exprHash"] = "sha256:12345678"
    with pytest.raises(ValueError, match="Immutable"):
        publication(tmp_path, rows=[changed])
    assert SnapshotPublisher(tmp_path).completed(ROUTE, manifest["unit"]["urn"], manifest["producer"], "first") == manifest


@pytest.mark.parametrize("field,value", [("eventCount", 2), ("eventsHash", "sha256:" + "f" * 64), ("generation", 99), ("complete", False)])
def test_incomplete_or_corrupt_completion_is_rejected(tmp_path, field, value):
    manifest = publication(tmp_path)
    bad = deepcopy(manifest)
    bad[field] = value
    with pytest.raises(ValueError):
        SnapshotPublisher(tmp_path).load(bad)


def test_archive_rejects_path_escape_symlinks_and_foreign_repository(tmp_path):
    manifest = publication(tmp_path / "root")
    bad = deepcopy(manifest)
    bad["objectRef"] = "snapshot://sha256/../../outside"
    with pytest.raises(ValueError):
        SnapshotPublisher(tmp_path / "root").load(bad)
    digest = manifest["objectRef"].rsplit("/", 1)[1]
    path = tmp_path / "root" / (digest + ".json")
    external = tmp_path / "external"
    path.replace(external)
    path.symlink_to(external)
    with pytest.raises(ValueError, match="escaped"):
        SnapshotPublisher(tmp_path / "root").load(manifest)
    with pytest.raises(ValueError, match="repository"):
        SnapshotCoordinator(tmp_path / "other").reserve(ROUTE, "unit://git/foreign/unit", event()["producer"], "bad")


def test_missing_object_empty_revision_and_mixed_revision_rejected(tmp_path):
    manifest = publication(tmp_path)
    digest = manifest["objectRef"].rsplit("/", 1)[1]
    (tmp_path / (digest + ".json")).unlink()
    with pytest.raises(FileNotFoundError):
        SnapshotPublisher(tmp_path).load(manifest)
    first = event()
    coordinator = SnapshotCoordinator(tmp_path)
    generation = coordinator.reserve(ROUTE, first["unit"]["urn"], first["producer"], "empty")
    snapshot = UnitSnapshot.build(first["unit"]["urn"], first["producer"], generation, T2, T2, [])
    with pytest.raises(ValueError, match="revision"):
        SnapshotPublisher(tmp_path).publish(snapshot, ROUTE, "empty")
    changed = deepcopy(first)
    changed["unit"]["commit"] = "abcdef123"
    generation = coordinator.reserve(ROUTE, first["unit"]["urn"], first["producer"], "mixed")
    snapshot = UnitSnapshot.build(first["unit"]["urn"], first["producer"], generation, T2, T2, [first, changed])
    with pytest.raises(ValueError, match="mixed"):
        SnapshotPublisher(tmp_path).publish(snapshot, ROUTE, "mixed")


def test_changed_object_bytes_and_swapped_completion_are_detected(tmp_path):
    first = publication(tmp_path)
    second = publication(tmp_path, "second", T2)
    publisher = SnapshotPublisher(tmp_path)
    completion = tmp_path / publisher._completion_name(ROUTE, first["unit"]["urn"], first["producer"], "first")
    completion.write_text(canonical(second))
    with pytest.raises(ValueError, match="reserved request"):
        publisher.completed(ROUTE, first["unit"]["urn"], first["producer"], "first")
    object_path = tmp_path / (first["objectRef"].rsplit("/", 1)[1] + ".json")
    object_path.write_bytes(object_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        publisher.load(first)


def test_runtime_and_static_replay_share_acceptance_order_and_runtime_survives_delete(tmp_path):
    root = tmp_path / "snapshots"
    manifest = publication(root)
    archive = EventArchive(tmp_path / "archive")
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    pipeline.process_snapshot(manifest, recorded_at=T1)
    runtime = event()
    runtime.pop("unit")
    runtime["evidence"].update(source="openlineage", weight=.95, runtime=True, replaces="none")
    pipeline.process(runtime, recorded_at=T2)
    deleted = publication(root, "deleted", T2, rows=[], deleted=True)
    pipeline.process_snapshot(deleted, recorded_at=T3)
    assert len(pipeline.engine.snapshot(T3)) == 1
    assert next(iter(pipeline.engine.snapshot(T3).values())).sources == ("openlineage",)
    expected = pipeline.engine.graph_hash(T3)
    assert [op[0] for op in archive.operations()] == ["snapshot", "event", "snapshot"]
    assert RuntimePipeline(archive, snapshot_root=root).engine.graph_hash(T3) == expected
    assert pipeline.process_snapshot(deleted, recorded_at=T3) == []


def test_late_old_generation_fills_history_without_resurrecting_deleted_current(tmp_path):
    root = tmp_path / "snapshots"
    old = publication(root)
    newer = publication(root, "deleted", T2, rows=[], deleted=True)
    archive = EventArchive(tmp_path / "archive")
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    pipeline.process_snapshot(newer, recorded_at=T2)
    pipeline.process_snapshot(old, recorded_at=T3)
    assert len(pipeline.engine.snapshot(T1)) == 1
    assert not pipeline.engine.snapshot(T3)
    assert max(pipeline.highest_generations.values()) == 2
    rebuilt = RuntimePipeline(archive, snapshot_root=root)
    assert len(rebuilt.engine.snapshot(T1)) == 1
    assert not rebuilt.engine.snapshot(T3)


def test_proposed_route_isolated_from_merged_archive_namespace_and_engine(tmp_path):
    root = tmp_path / "snapshots"
    route = {**ROUTE, "stage": "proposed", "pr": 42}
    proposed = publication(root, route=route)
    archive = EventArchive(tmp_path / "merged")
    merged = RuntimePipeline(archive, snapshot_root=root)
    with pytest.raises(ValueError, match="route"):
        merged.process_snapshot(proposed, recorded_at=T1)
    with pytest.raises(ValueError, match="route"):
        RuntimePipeline(archive, snapshot_root=root, route=route)
    class WrongStore:
        namespace = "lineage-runtime"
    with pytest.raises(ValueError, match="namespace"):
        RuntimePipeline(EventArchive(tmp_path / "wrong"), WrongStore(), snapshot_root=root, route=route)
    overlay_archive = EventArchive(tmp_path / "proposed")
    overlay = RuntimePipeline(overlay_archive, snapshot_root=root, route=route)
    assert overlay.process_snapshot(proposed, recorded_at=T1)
    assert len(overlay.engine.snapshot()) == 1 and not merged.engine.snapshot()
    assert len(RuntimePipeline(overlay_archive, snapshot_root=root, route=route).engine.snapshot()) == 1


def test_static_projection_failure_is_durable_and_redelivery_repairs(tmp_path):
    root = tmp_path / "snapshots"
    manifest = publication(root)
    class Store:
        fail = True
        def append(self, assertions):
            if assertions and self.fail:
                raise OSError("graph unavailable")
    store = Store()
    archive = EventArchive(tmp_path / "archive")
    pipeline = RuntimePipeline(archive, store, snapshot_root=root)
    with pytest.raises(OSError):
        pipeline.process_snapshot(manifest, recorded_at=T1)
    assert len(list(archive.operations())) == 1
    store.fail = False
    assert pipeline.process_snapshot(manifest, recorded_at=T2) == []
    assert len(list(archive.pending_changes())) == 1


def test_snapshot_outbox_failure_never_projects_or_erases_preexisting_runtime(tmp_path):
    root = tmp_path / "snapshots"
    manifest = publication(root)
    class Archive(EventArchive):
        fail = False
        def accept(self, digest, changes):
            if self.fail:
                raise OSError("simulated atomic acceptance failure")
            return super().accept(digest, changes)
    class Store:
        def __init__(self):
            self.assertions = {}
        def append(self, assertions):
            self.assertions.update({row["id"]: row for row in assertions})
    archive, store = Archive(tmp_path / "archive"), Store()
    pipeline = RuntimePipeline(archive, store, snapshot_root=root)
    runtime = json.loads((repository_root() / "factory/specs/evidence/examples/runtime-service-edge.json").read_text())
    pipeline.process(runtime, recorded_at=T1)
    expected_graph = pipeline.engine.graph_hash(T3)
    expected_projection = deepcopy(store.assertions)
    archive.fail = True
    with pytest.raises(OSError):
        pipeline.process_snapshot(manifest, recorded_at=T2)
    assert pipeline.engine.graph_hash(T3) == expected_graph
    assert store.assertions == expected_projection
    assert [operation[0] for operation in archive.operations()] == ["event"]
    archive.fail = False
    pipeline.process_snapshot(manifest, recorded_at=T2)
    assert [operation[0] for operation in archive.operations()] == ["event", "snapshot"]


def held_deletion(root, archive):
    rows = []
    for index in range(10):
        row = event()
        row["edge"]["elements"][0].update({"from": f"field{index}", "to": f"field{index}"})
        rows.append(row)
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    pipeline.process_snapshot(publication(root, rows=rows), recorded_at=T1)
    deletion = publication(root, "delete-held", T2, rows=[], deleted=True)
    with pytest.raises(ReviewRequired):
        pipeline.process_snapshot(deletion, recorded_at=T2)
    return pipeline.pending_snapshot_holds()[0]["receipt_digest"], deletion


def test_mass_close_hold_restart_attributable_release_and_recorded_time_replay(tmp_path):
    root = tmp_path / "snapshots"
    archive = EventArchive(tmp_path / "archive")
    receipt, deletion = held_deletion(root, archive)
    archive.close()
    archive = EventArchive(tmp_path / "archive")
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    original_operation_id = pipeline.pending_snapshot_holds()[0]["operation_id"]
    assert len(pipeline.engine.snapshot(T3)) == 10
    changes = pipeline.release_snapshot(receipt, owner_action_id="review-42", actor="team-payments/alice", recorded_at=T3)
    assert len(changes) == 10
    assert all({"kind": "owner_action", "ref": "review-42"} in change["causes"] for change in changes)
    assert not pipeline.pending_snapshot_holds()
    assert not pipeline.engine.snapshot(T3)
    assert len(pipeline.engine.snapshot(T3, recorded_at=T2)) == 10
    assert not pipeline.engine.snapshot(T3, recorded_at=T3)
    accepted = list(archive.operations())[-1]
    assert accepted[2].startswith("2026-11-29T12:00:00")
    assert archive.release_for(receipt)["actor"] == "team-payments/alice"
    assert original_operation_id in pipeline.engine._operations
    count = len(list(archive.pending_changes()))
    assert pipeline.release_snapshot(receipt, owner_action_id="review-42", actor="team-payments/alice", recorded_at=T3) == []
    assert pipeline.process_snapshot(deletion, recorded_at=T3) == []
    assert len(list(archive.pending_changes())) == count
    archive.close()
    archive = EventArchive(tmp_path / "archive")
    rebuilt = RuntimePipeline(archive, snapshot_root=root)
    assert not rebuilt.engine.snapshot(T3)
    assert len(rebuilt.engine.snapshot(T3, recorded_at=T2)) == 10


def test_invalid_releases_and_release_commit_failure_preserve_original_hold(tmp_path):
    class Archive(EventArchive):
        fail_release = False
        def accept(self, digest, changes, *, release=None):
            if self.fail_release and release is not None:
                raise OSError("simulated release commit failure")
            return super().accept(digest, changes, release=release)
    root = tmp_path / "snapshots"
    archive = Archive(tmp_path / "archive")
    receipt, _ = held_deletion(root, archive)
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    invalid = [
        {"receipt_digest": "f" * 64, "owner_action_id": "review", "actor": "alice", "recorded_at": T3},
        {"receipt_digest": receipt, "owner_action_id": "", "actor": "alice", "recorded_at": T3},
        {"receipt_digest": receipt, "owner_action_id": "review", "actor": " ", "recorded_at": T3},
        {"receipt_digest": receipt, "owner_action_id": "review", "actor": "alice", "recorded_at": T1},
    ]
    for arguments in invalid:
        with pytest.raises(ValueError):
            pipeline.release_snapshot(**arguments)
        assert len(pipeline.engine.snapshot(T3)) == 10
        assert len(list(archive.operations())) == 1
    archive.fail_release = True
    with pytest.raises(OSError):
        pipeline.release_snapshot(receipt, owner_action_id="review", actor="alice", recorded_at=T3)
    assert len(pipeline.engine.snapshot(T3)) == 10
    assert archive.release_for(receipt) is None
    assert len(pipeline.pending_snapshot_holds()) == 1
    archive.fail_release = False
    pipeline.release_snapshot(receipt, owner_action_id="review", actor="alice", recorded_at=T3)
    with pytest.raises(ValueError):
        pipeline.release_snapshot(receipt, owner_action_id="different-action", actor="alice", recorded_at=T3)


def test_owner_release_survives_runtime_support_removing_current_mass_close_reason(tmp_path):
    root = tmp_path / "snapshots"
    archive = EventArchive(tmp_path / "archive")
    receipt, _ = held_deletion(root, archive)
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    for index in range(10):
        runtime = event()
        runtime.pop("unit")
        runtime["edge"]["elements"][0].update({"from": f"field{index}", "to": f"field{index}"})
        runtime["eventTime"] = T2
        runtime["evidence"].update(source="openlineage", weight=.95, runtime=True, replaces="none", observedAt=T2)
        pipeline.process(runtime, recorded_at=T2)
    changes = pipeline.release_snapshot(receipt, owner_action_id="review-after-runtime", actor="alice", recorded_at=T3)
    assert changes and all({"kind": "owner_action", "ref": "review-after-runtime"} in change["causes"] for change in changes)
    assert len(pipeline.engine.snapshot(T3)) == 10
    assert all(row.sources == ("openlineage",) for row in pipeline.engine.snapshot(T3).values())
    assert all("ci_static" in row.sources for row in pipeline.engine.snapshot(T3, recorded_at=T2).values())
    rebuilt = RuntimePipeline(archive, snapshot_root=root)
    assert not rebuilt.pending_snapshot_holds()
    assert all(row.sources == ("openlineage",) for row in rebuilt.engine.snapshot(T3).values())


def test_release_cannot_backdate_newer_accepted_knowledge(tmp_path):
    root = tmp_path / "snapshots"
    archive = EventArchive(tmp_path / "archive")
    receipt, _ = held_deletion(root, archive)
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    runtime = event()
    runtime.pop("unit")
    runtime["edge"]["elements"][0].update({"from": "field0", "to": "field0"})
    runtime["evidence"].update(source="openlineage", weight=.95, runtime=True, replaces="none")
    pipeline.process(runtime, recorded_at="2026-11-30T12:00:00Z")
    with pytest.raises(ValueError, match="accepted knowledge"):
        pipeline.release_snapshot(receipt, owner_action_id="backdated-review", actor="alice", recorded_at=T3)
    assert len(pipeline.pending_snapshot_holds()) == 1
    assert archive.release_for(receipt) is None


def test_release_journal_insert_failure_rolls_back_attribution_receipt_and_outbox(tmp_path):
    root = tmp_path / "snapshots"
    archive = EventArchive(tmp_path / "archive")
    receipt, _ = held_deletion(root, archive)
    pipeline = RuntimePipeline(archive, snapshot_root=root)
    before_outbox = list(archive.pending_changes())
    archive.connection.execute("""CREATE TRIGGER fail_acceptance BEFORE INSERT ON acceptance_journal
        BEGIN SELECT RAISE(ABORT, 'injected journal failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        pipeline.release_snapshot(receipt, owner_action_id="review-atomic", actor="alice", recorded_at=T3)
    assert archive.release_for(receipt) is None
    assert not archive.is_accepted(receipt)
    assert list(archive.pending_changes()) == before_outbox
    assert len(pipeline.engine.snapshot(T3)) == 10
    archive.connection.execute("DROP TRIGGER fail_acceptance")
    pipeline.release_snapshot(receipt, owner_action_id="review-atomic", actor="alice", recorded_at=T3)
    assert not RuntimePipeline(archive, snapshot_root=root).engine.snapshot(T3)
