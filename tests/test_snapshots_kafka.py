"""Combined live twin transport; all input evidence is synthetic metadata."""
from copy import deepcopy
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
from lineage.graph import BoltGraphStore
from lineage.merge import UnitSnapshot
from lineage.pipeline import RuntimePipeline
from lineage.snapshots import KafkaSnapshotSink, SnapshotCoordinator, SnapshotPublisher


@pytest.mark.integration
def test_complete_static_and_runtime_topics_share_durable_recovery(tmp_path):
    broker, uri = os.environ.get("LINEAGE_TEST_BROKER"), os.environ.get("LINEAGE_TEST_BOLT_URL")
    if not broker or not uri:
        pytest.skip("Requires explicitly configured disposable Kafka and Neo4j")
    from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition
    from confluent_kafka.admin import AdminClient, NewTopic
    identity = "snapshots-" + uuid.uuid4().hex
    topics = [identity + suffix for suffix in (".evidence", ".unit-snapshots", ".changes")]
    admin = AdminClient({"bootstrap.servers": broker})
    for future in admin.create_topics([NewTopic(topic, 1, 1) for topic in topics]).values():
        future.result(timeout=15)
    store = BoltGraphStore(uri, ("neo4j", os.environ.get("LINEAGE_TEST_DB_PASSWORD", "lineage-local-only")), namespace=identity)
    root = tmp_path / "objects"
    route = {"repository": "opentelemetry-demo", "stage": "merged", "pr": None}
    event = json.loads((repository_root() / "factory/specs/evidence/examples/golden-field-edge.json").read_text())
    coordinator = SnapshotCoordinator(root)
    publisher = SnapshotPublisher(root, KafkaSnapshotSink(broker, topics[1]))
    def publish(request, at, rows, deleted=False):
        generation = coordinator.reserve(route, event["unit"]["urn"], event["producer"], request)
        snapshot = UnitSnapshot.build(event["unit"]["urn"], event["producer"], generation, at, at, rows, deleted)
        return publisher.publish(snapshot, route, request, unit_revision=event["unit"])
    arguments = ["-m", "lineage.pipeline", "--archive", str(tmp_path / "archive"),
               "--snapshot-root", str(root), "--broker", broker, "--bolt-url", uri, "--namespace", identity,
               "--evidence-topic", topics[0], "--snapshots-topic", topics[1], "--changes-topic", topics[2], "--consumer-group", identity]
    image = os.environ.get("LINEAGE_WORKER_IMAGE")
    container_name = identity + "-worker"
    command = (["docker", "run", "--rm", "--pull", "never", "--name", container_name, "--network", "host", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp", "--memory", "1g", "--pids-limit", "128",
                "--user", f"{os.getuid()}:{os.getgid()}", "--mount", f"type=bind,src={tmp_path},dst={tmp_path}",
                "--entrypoint", "python", image] if image else [sys.executable]) + arguments
    def stop_worker(process):
        if image:
            try:
                deadline = time.monotonic() + 15
                while process.poll() is None and time.monotonic() < deadline:
                    exists = subprocess.run(["docker", "container", "inspect", container_name], capture_output=True, timeout=5)
                    if exists.returncode == 0:
                        stopped = subprocess.run(["docker", "stop", "--time", "5", container_name], capture_output=True, timeout=10)
                        if stopped.returncode == 0:
                            break
                    time.sleep(.1)
            finally:
                # Also clean up startup failures and a stop/auto-remove race.
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                finally:
                    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)
        else:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    worker = None
    # OffsetFetch only: never subscribe or join the worker's consumer group.
    observer = Consumer({"bootstrap.servers": broker, "group.id": identity,
                         "enable.auto.commit": False, "log_level": 0})
    def wait_for_worker_commits(snapshot_offset):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            assert worker.poll() is None, "Ingestion worker stopped before committing source deliveries"
            try:
                offsets = observer.committed([TopicPartition(topics[0], 0), TopicPartition(topics[1], 0)], timeout=2)
            except KafkaException:
                time.sleep(.1)
                continue
            committed = {partition.topic: partition.offset for partition in offsets if not partition.error}
            if committed.get(topics[0], -1) >= 1 and committed.get(topics[1], -1) >= snapshot_offset:
                return
            time.sleep(.1)
        pytest.fail("Worker did not commit the expected runtime and snapshot deliveries")
    log = (tmp_path / "worker.log").open("w")
    try:
        worker = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        first = publish("first", event["eventTime"], [event])
        runtime = deepcopy(event)
        runtime.pop("unit")
        runtime["evidence"].update(source="openlineage", weight=.95, runtime=True, replaces="none")
        producer = Producer({"bootstrap.servers": broker})
        producer.produce(topics[0], value=json.dumps(runtime))
        assert producer.flush(10) == 0
        deletion = publish("delete", "2026-11-28T12:00:00Z", [], True)
        database = tmp_path / "archive/index.sqlite3"
        deadline = time.monotonic() + 30
        count = 0
        while time.monotonic() < deadline and count < 3:
            assert worker.poll() is None, "Ingestion worker stopped"
            if database.exists():
                with sqlite3.connect(database) as connection:
                    try:
                        count = connection.execute("SELECT COUNT(*) FROM acceptance_journal").fetchone()[0]
                    except sqlite3.OperationalError:
                        pass
            time.sleep(.1)
        assert count == 3
        wait_for_worker_commits(2)
        stop_worker(worker)
        worker = None
        archive = EventArchive(tmp_path / "archive")
        restored = RuntimePipeline(archive, snapshot_root=root)
        assert len(restored.engine.snapshot("2026-11-29T00:00:00Z")) == 1
        assert next(iter(restored.engine.snapshot("2026-11-29T00:00:00Z").values())).sources == ("openlineage",)
        expected = restored.engine.graph_hash("2026-11-29T00:00:00Z")
        archive.close()
        worker = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        publisher.resend(first)
        publisher.resend(deletion)
        # Old graph contents cannot prove that the restarted process consumed
        # either duplicate. Committed offsets advance only after projection.
        wait_for_worker_commits(4)
        assert store.load()
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT COUNT(*) FROM acceptance_journal").fetchone()[0] == 3
        archive = EventArchive(tmp_path / "archive")
        assert RuntimePipeline(archive, snapshot_root=root).engine.graph_hash("2026-11-29T00:00:00Z") == expected
        archive.close()
    finally:
        try:
            if worker is not None:
                stop_worker(worker)
        finally:
            observer.close()
            log.close()
            try:
                with store.driver.session() as session:
                    session.run("MATCH (n {namespace: $namespace}) DETACH DELETE n", namespace=identity).consume()
            finally:
                store.close()
                for future in admin.delete_topics(topics).values():
                    future.result(timeout=15)
