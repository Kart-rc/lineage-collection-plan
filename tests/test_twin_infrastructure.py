"""Static safety checks and opt-in live checks of the separately running platform."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_platform_never_joins_demo_network_and_has_distinct_storage():
    config = yaml.safe_load((ROOT / "twin/compose.yaml").read_text())
    assert set(config["services"]) == {"lineage-kafka", "lineage-neo4j", "lineage-postgres"}
    for service in config["services"].values():
        assert service["networks"] == ["lineage"]
        assert all(p.startswith("127.0.0.1:") for p in service["ports"])
        assert all(not p.startswith("astronomy") for p in service["volumes"])
        assert ":latest" not in service["image"]
    assert "lineage-archive" in config["volumes"]


def test_platform_images_are_digest_locked():
    config = yaml.safe_load((ROOT / "twin/compose.yaml").read_text())
    lock = json.loads((ROOT / "twin/images.lock.json").read_text())
    for service in config["services"].values():
        assert "@sha256:" in lock[service["image"]]


live = pytest.mark.skipif(os.environ.get("LINEAGE_TWIN_LIVE") != "1", reason="set LINEAGE_TWIN_LIVE=1 with platform running")


@pytest.mark.integration
@live
def test_live_neo4j_roundtrip():
    from neo4j import GraphDatabase
    token = "twin-health-" + uuid.uuid4().hex
    with GraphDatabase.driver("bolt://127.0.0.1:17687", auth=("neo4j", "lineage-local-only")) as driver:
        driver.verify_connectivity()
        with driver.session() as session:
            try:
                record = session.run("CREATE (n:TwinHealth {id: $id}) RETURN n.id AS id", id=token).single()
                assert record["id"] == token
            finally:
                session.run("MATCH (n:TwinHealth {id: $id}) DELETE n", id=token).consume()


@pytest.mark.integration
@live
def test_live_lineage_kafka_envelope_roundtrip():
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.admin import AdminClient, NewTopic
    from jsonschema import Draft202012Validator, FormatChecker
    topic = "lineage.twin-health-" + uuid.uuid4().hex
    config = {"bootstrap.servers": "127.0.0.1:19092"}
    admin = AdminClient(config)
    for future in admin.create_topics([NewTopic(topic, 1, 1)]).values():
        future.result(timeout=20)
    event = json.loads((ROOT / "factory/specs/evidence/examples/change-event.json").read_text())
    producer = Producer(config)
    consumer = Consumer(dict(config, **{"group.id": topic, "auto.offset.reset": "earliest", "enable.auto.commit": False}))
    try:
        producer.produce(topic, json.dumps(event).encode())
        assert producer.flush(10) == 0
        consumer.subscribe([topic])
        msg = consumer.poll(20)
        assert msg is not None and not msg.error()
        received = json.loads(msg.value())
        assert received == event
        schema = json.loads((ROOT / "factory/specs/evidence/interfaces/envelope-v2.schema.json").read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(received)
    finally:
        consumer.close()
        for future in admin.delete_topics([topic]).values():
            future.result(timeout=20)


@pytest.mark.integration
@live
def test_live_postgres_alias_and_queue_schema():
    result = subprocess.run(["docker", "exec", "lineage-twin-lineage-postgres-1", "psql", "-U", "lineage", "-d", "lineage",
                             "-Atc", "SELECT to_regclass('aliases'), to_regclass('reconciliation_queue')"],
                            check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "aliases|reconciliation_queue"
