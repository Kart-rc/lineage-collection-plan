"""Real local infrastructure test; the input is a labeled metadata fixture."""
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid

import pytest

from lineage.config import repository_root
from lineage.graph import BoltGraphStore


@pytest.mark.integration
def test_kafka_to_archive_to_neo4j_to_change_stream(tmp_path):
    broker, uri = os.environ.get("LINEAGE_TEST_BROKER"), os.environ.get("LINEAGE_TEST_BOLT_URL")
    if not broker or not uri:
        pytest.skip("Requires explicitly configured disposable Kafka and Neo4j")
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.admin import AdminClient, NewTopic

    identity = "plumbing-" + uuid.uuid4().hex
    topics = [identity + ".evidence", identity + ".changes"]
    admin = AdminClient({"bootstrap.servers": broker})
    for future in admin.create_topics([NewTopic(name, 1, 1) for name in topics]).values():
        future.result(timeout=15)
    store = BoltGraphStore(uri, ("neo4j", os.environ.get("LINEAGE_TEST_DB_PASSWORD", "lineage-local-only")), namespace=identity)
    event = json.loads((repository_root() / "factory/specs/evidence/examples/runtime-service-edge.json").read_text())
    consumer = Consumer({"bootstrap.servers": broker, "group.id": identity + "-observer", "auto.offset.reset": "earliest"})
    consumer.subscribe([topics[1]])
    with (tmp_path / "worker.log").open("w") as log:
        worker = subprocess.Popen([sys.executable, "-m", "lineage.pipeline", "--archive", str(tmp_path / "archive"),
                                   "--broker", broker, "--bolt-url", uri, "--namespace", identity,
                                   "--evidence-topic", topics[0], "--changes-topic", topics[1], "--consumer-group", identity],
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            producer = Producer({"bootstrap.servers": broker})
            # Same delivery twice must create one logical change.
            for _ in range(2):
                producer.produce(topics[0], value=json.dumps(event))
            assert producer.flush(10) == 0
            changes = []
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not changes:
                assert worker.poll() is None, (tmp_path / "worker.log").read_text()
                message = consumer.poll(0.5)
                if message is not None and not message.error():
                    changes.append(json.loads(message.value()))
            assert len(changes) == 1
            assert changes[0]["eventType"] == "EDGE_CHANGE"
            assert changes[0]["change"] == "opened"
            assert len(store.load()) == 1
            db = sqlite3.connect(tmp_path / "archive/index.sqlite3")
            assert db.execute("SELECT count(*) FROM receipts WHERE accepted=1").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
            db.close()
            assert len(list((tmp_path / "archive").glob("*.parquet"))) == 1
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
