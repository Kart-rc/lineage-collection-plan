import copy
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from lineage.archive import EventArchive
from lineage.config import repository_root


@pytest.fixture
def event():
    return json.loads((repository_root() / "factory/specs/evidence/examples/runtime-service-edge.json").read_text())


def test_receipt_is_invisible_until_atomic_acceptance_and_survives_restart(tmp_path, event):
    archive = EventArchive(tmp_path)
    digest = archive.stage(event, event["eventTime"])
    assert list(archive.receipts()) == []
    assert len(list(archive.receipts(accepted=False))) == 1
    archive.close()
    archive = EventArchive(tmp_path)
    assert archive.read(digest) == event
    archive.accept(digest, [])
    archive.close()
    archive = EventArchive(tmp_path)
    assert len(list(archive.receipts())) == 1
    assert archive.resolve(event["evidence"]["rawRef"]) == [event]


def test_redelivery_is_one_parquet_receipt_and_one_logical_change(tmp_path, event):
    archive = EventArchive(tmp_path)
    change = json.loads((repository_root() / "factory/specs/changes/example-condition-activated.json").read_text())
    digest = archive.stage(event, event["eventTime"])
    archive.accept(digest, [change])
    assert archive.stage(event, "2026-11-28T12:00:00Z") == digest
    archive.accept(digest, [change])
    assert len(list(tmp_path.glob("*.parquet"))) == 1
    pending = list(archive.pending_changes())
    assert len(pending) == 1
    archive.mark_sent(pending[0][0])
    archive.close()
    archive = EventArchive(tmp_path)
    assert list(archive.pending_changes()) == []
    assert len(list(archive.receipts())) == 1


def test_invalid_change_never_commits_receipt(tmp_path, event):
    archive = EventArchive(tmp_path)
    digest = archive.stage(event, event["eventTime"])
    with pytest.raises(Exception):
        archive.accept(digest, [{"unexpected": "invalid"}])
    assert not archive.is_accepted(digest)
    assert list(archive.pending_changes()) == []


def test_unknown_payload_is_rejected_before_storage(tmp_path, event):
    archive = EventArchive(tmp_path)
    bad = copy.deepcopy(event)
    bad["payload"] = "must never be written"
    with pytest.raises(ValueError):
        archive.stage(bad, event["eventTime"])
    assert list(tmp_path.glob("*.parquet")) == []


def test_corrupt_receipt_is_detected_on_read_and_redelivery(tmp_path, event):
    archive = EventArchive(tmp_path)
    digest = archive.stage(event, event["eventTime"])
    pq.write_table(pa.table({"sha256": [digest], "event_json": ["{}"]}), tmp_path / f"{digest}.parquet")
    with pytest.raises(ValueError, match="integrity"):
        archive.read(digest)
    with pytest.raises(ValueError, match="integrity"):
        archive.stage(event, event["eventTime"])


def test_replay_journal_follows_acceptance_not_initial_staging_order(tmp_path, event):
    archive = EventArchive(tmp_path)
    first = archive.stage(event, event["eventTime"])
    later = copy.deepcopy(event)
    later["edge"]["to"]["name"] = "second-service"
    second = archive.stage(later, "2026-11-28T12:00:00Z")
    archive.accept(second, [])
    archive.accept(first, [])
    assert [digest for _, digest, _, _ in archive.operations()] == [second, first]
    archive.close()
    restored = EventArchive(tmp_path)
    assert [digest for _, digest, _, _ in restored.operations()] == [second, first]
    restored.close()
