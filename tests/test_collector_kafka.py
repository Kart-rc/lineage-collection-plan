"""Synthetic raw exports through the container collector and actual platform."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid

import pytest

from lineage.archive import EventArchive
from lineage.config import repository_root
from lineage.evidence import validate_event
from lineage.graph import BoltGraphStore


def attributes(**values):
    return [{"key": key.replace("__", "."), "value": {"stringValue": value}} for key, value in values.items()]


def document(identity="first", minute=0):
    start = str(1795789020000000000 + minute * 60_000_000_000)
    resources = [{"resource": {"attributes": attributes(service__name="checkout")},
                  "scopeSpans": [{"spans": [{"traceId": identity, "spanId": identity, "kind": 4,
                                               "startTimeUnixNano": start,
                                               "attributes": attributes(messaging__system="kafka", messaging__destination__name="orders")}]}]}]
    if minute == 0:
        resources.append({"resource": {"attributes": attributes(service__name="accounting")},
                          "scopeSpans": [{"spans": [{"traceId": "sql", "spanId": "sql", "kind": 3,
                                                       "startTimeUnixNano": start,
                                                       "attributes": attributes(db__system__name="postgresql", db__query__text="INSERT INTO accounting.shipping (order_id) VALUES ('SYNTHETIC_PRIVATE_VALUE')")}]}]})
    return {"resourceSpans": resources}


@pytest.mark.integration
def test_container_collects_raw_exports_and_faults_with_restart_progress(tmp_path):
    image = os.environ.get("LINEAGE_COLLECTOR_IMAGE")
    broker, uri = os.environ.get("LINEAGE_TEST_BROKER"), os.environ.get("LINEAGE_TEST_BOLT_URL")
    if not all((image, broker, uri)):
        pytest.skip("Requires configured disposable Kafka, Neo4j and built collector image")
    from confluent_kafka import Consumer
    from confluent_kafka.admin import AdminClient, NewTopic

    identity = "collector-" + uuid.uuid4().hex
    topics = [identity + ".evidence", identity + ".changes"]
    admin = AdminClient({"bootstrap.servers": broker})
    for future in admin.create_topics([NewTopic(name, 1, 1) for name in topics]).values():
        future.result(timeout=15)
    store = BoltGraphStore(uri, ("neo4j", os.environ.get("LINEAGE_TEST_DB_PASSWORD", "lineage-local-only")), namespace=identity)
    capture, state = tmp_path / "capture", tmp_path / "collector-state"
    capture.mkdir()
    state.mkdir()
    raw = capture / "traces.jsonl"
    raw.write_text(json.dumps(document()) + "\n")
    fault = json.loads((repository_root() / "factory/specs/evidence/examples/change-event.json").read_text())
    faults = tmp_path / "changes.jsonl"
    faults.write_text(json.dumps(fault) + "\n")
    original = hashlib.sha256(raw.read_bytes()).hexdigest()
    command = ["docker", "run", "--rm", "--network", "host", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp", "--memory", "512m", "--pids-limit", "64",
               "--user", f"{os.getuid()}:{os.getgid()}",
               "--mount", f"type=bind,src={capture},dst=/capture,readonly",
               "--mount", f"type=bind,src={faults},dst=/changes.jsonl,readonly",
               "--mount", f"type=bind,src={state},dst=/collector-state",
               "--entrypoint", "python", image, "-m", "lineage.collector",
               "--capture-dir", "/capture", "--changes", "/changes.jsonl", "--state", "/collector-state",
               "--broker", broker, "--topic", topics[0], "--once"]
    consumer = Consumer({"bootstrap.servers": broker, "group.id": identity, "auto.offset.reset": "earliest"})
    consumer.subscribe([topics[0]])
    archive_dir = tmp_path / "archive"

    def collect():
        result = subprocess.run(command, capture_output=True, text=True, timeout=35)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "SYNTHETIC_PRIVATE_VALUE" not in result.stdout + result.stderr

    def wait_for_receipts(expected):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            assert worker.poll() is None, log_path.read_text()
            if (archive_dir / "index.sqlite3").exists():
                with sqlite3.connect(archive_dir / "index.sqlite3") as database:
                    count = database.execute("SELECT count(*) FROM receipts WHERE accepted=1").fetchone()[0]
                if count == expected:
                    return
            time.sleep(0.1)
        pytest.fail("Expected archived collector receipts were not accepted")

    log_path = tmp_path / "worker.log"
    with log_path.open("w") as log:
        worker = subprocess.Popen([sys.executable, "-m", "lineage.pipeline", "--archive", str(archive_dir),
                                   "--broker", broker, "--bolt-url", uri, "--namespace", identity,
                                   "--evidence-topic", topics[0], "--changes-topic", topics[1], "--consumer-group", identity + "-worker"],
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            # Isolate only this collector from the network; shared Kafka and
            # Neo4j remain running. Recovery uses the same source and state.
            offline = list(command)
            offline[offline.index("--network") + 1] = "none"
            result = subprocess.run(offline + ["--send-timeout", "0.25"], capture_output=True, text=True, timeout=20)
            assert result.returncode != 0
            assert "SYNTHETIC_PRIVATE_VALUE" not in result.stdout + result.stderr
            with sqlite3.connect(state / "progress.sqlite") as progress:
                assert progress.execute("SELECT count(*) FROM acknowledged").fetchone()[0] == 0
            collect()
            wait_for_receipts(3)
            assert hashlib.sha256(raw.read_bytes()).hexdigest() == original
            observed = []
            deadline = time.monotonic() + 15
            while len(observed) < 3 and time.monotonic() < deadline:
                message = consumer.poll(0.5)
                if message is not None and not message.error():
                    event = json.loads(message.value())
                    validate_event(event)
                    observed.append(event)
            assert len(observed) == 3
            assert {e["eventType"] for e in observed} == {"EVIDENCE", "CHANGE_EVENT"}
            assert "SYNTHETIC_PRIVATE_VALUE" not in json.dumps(observed)
            assert len(store.load()) == 2

            # A fresh collector process with the same durable state sends nothing.
            collect()
            assert consumer.poll(1) is None
            with raw.open("a") as output:
                output.write(json.dumps(document("second", minute=1)) + "\n")
            collect()
            wait_for_receipts(4)
            archive = EventArchive(archive_dir)
            try:
                receipts = list(archive.receipts())
                assert len(receipts) == 4
                assert "SYNTHETIC_PRIVATE_VALUE" not in json.dumps(receipts)
            finally:
                archive.close()
            assert all(b"SYNTHETIC_PRIVATE_VALUE" not in p.read_bytes() for p in state.iterdir() if p.is_file())
            assert "SYNTHETIC_PRIVATE_VALUE" not in log_path.read_text()
        finally:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
            consumer.close()
            with store.driver.session() as session:
                session.run("MATCH (n {namespace: $namespace}) DETACH DELETE n", namespace=identity).consume()
            store.close()
            for future in admin.delete_topics(topics).values():
                future.result(timeout=15)
