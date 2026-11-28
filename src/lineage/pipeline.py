"""Single-writer runtime and complete-unit ingestion with one acceptance journal.

Runtime v2 events and separate unit completion manifests share a durable replay
order and merger. Individual static replacements remain prohibited. Proposed
routes require their own bound archive and graph namespace.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .archive import EventArchive, canonical
from .evidence import prepare_event
from .graph import BitemporalGraph, BoltGraphStore, timestamp
from .merge import MergeEngine, UnitSnapshot
from .snapshots import SnapshotPublisher, validate_route, validate_manifest, route_namespace


class ReviewRequired(RuntimeError):
    """A source receipt remains pending until its explicit hold is resolved."""


class RuntimePipeline:
    def __init__(self, archive: EventArchive, store=None, *, snapshot_root=None, route=None):
        self.archive, self.store = archive, store
        self.route = validate_route(route) if route is not None else {"repository": None, "stage": "merged", "pr": None}
        if self.route["stage"] == "proposed" and store is not None and getattr(store, "namespace", None) != route_namespace(self.route):
            raise ValueError("Proposed snapshots require their isolated graph namespace")
        archive.bind_route(self.route)
        self.snapshots = SnapshotPublisher(snapshot_root) if snapshot_root is not None else None
        self._restore()

    def _check_route(self, route):
        validate_route(route)
        if route["stage"] != self.route["stage"] or route["pr"] != self.route["pr"] or (self.route["repository"] is not None and route["repository"] != self.route["repository"]):
            raise ValueError("Snapshot completion belongs to another ingestion route")

    def _unit_operation(self, body, recorded_at):
        manifest = body["manifest"]
        self._check_route(manifest["route"])
        events = deepcopy(body["events"])
        if self.route["stage"] == "proposed":
            # The original PR route/revision is retained in the durable journal.
            # Only this isolated merger receives the neutralized projection.
            for event in events:
                event["unit"].pop("pr", None)
        return UnitSnapshot.build(manifest["unit"]["urn"], manifest["producer"], manifest["generation"],
                                  manifest["validAt"], recorded_at, events, manifest["deleted"])

    def _restore(self) -> None:
        graph = BitemporalGraph()
        engine = MergeEngine(graph=graph)
        self.highest_generations = {}
        for kind, digest, recorded_at, body in self.archive.operations():
            if kind == "event":
                result = engine.ingest(body, recorded_at=recorded_at)
            else:
                snapshot = self._unit_operation(body, recorded_at)
                release = self.archive.release_for(digest)
                if release is not None:
                    held = self.archive.snapshot_hold_for(digest)
                    if held is None:
                        raise ValueError("Accepted owner release has no original hold")
                    result = engine.apply_released_snapshot(snapshot, owner_action_id=release["owner_action_id"],
                                                            held_operation_id=held["operation_id"])
                else:
                    result = engine.replace_unit(snapshot)
                key = (snapshot.unit, snapshot.producer.rsplit("@", 1)[0])
                self.highest_generations[key] = max(self.highest_generations.get(key, 0), snapshot.generation)
            if result.held:
                raise ReviewRequired("Accepted operation cannot be replayed without review")
        if self.store is not None:
            self.store.append(list(graph.assertions))
        # The archive is the durable source of truth. Keep the staged graph
        # detached from Bolt: publishing before archive acceptance could leave
        # a phantom edge when the SQLite/outbox transaction fails.
        self.engine = engine

    def process(self, event: dict, *, recorded_at: str) -> list[dict]:
        event = prepare_event(event)
        if event.get("evidence", {}).get("replaces") == "unit":
            raise ValueError("Static evidence needs a complete unit snapshot; individual replacement events are rejected")
        recorded_at = timestamp(recorded_at)
        digest = self.archive.stage(event, recorded_at)
        if self.archive.is_accepted(digest):
            # An earlier call may have committed the archive and then failed
            # while projecting it to Bolt. Redelivery repairs that projection
            # before acknowledging the source, without producing a new change.
            self._restore()
            return []
        try:
            result = self.engine.ingest(event, recorded_at=self.archive.recorded_at(digest))
            if result.held:
                reason = (result.alert or {}).get("reason", "review_required")
                # Only a controlled category reaches worker logs, never a
                # source expression, metadata value, or arbitrary exception.
                category = reason if reason in {"unsupported_expression_change", "mass_close"} else "review_required"
                raise ReviewRequired(f"Lineage receipt held: {category}; source offset remains unacknowledged")
            changes = list(result.changes)
            self.archive.accept(digest, changes)
        except Exception:
            # No new Bolt assertion has been published at this point.
            self._restore()
            raise
        if self.store is not None:
            # Failures here leave a durable receipt and outbox, repairable by
            # restart/redelivery. The Kafka caller has not acknowledged yet.
            self.store.append(list(self.engine.graph.assertions))
        return changes

    def process_snapshot(self, manifest: dict, *, recorded_at: str) -> list[dict]:
        """Accept a fully archived completion, including late historical generations."""
        if self.snapshots is None:
            raise ValueError("Snapshot ingestion requires a shared snapshot archive")
        self._check_route(manifest.get("route", {}))
        snapshot = self.snapshots.load(manifest)
        recorded_at = timestamp(recorded_at)
        digest = self.archive.stage_snapshot(manifest, snapshot, recorded_at)
        if self.archive.is_accepted(digest):
            self._restore()
            return []
        try:
            body = self.archive.read(digest)
            operation = self._unit_operation(body, self.archive.recorded_at(digest))
            result = self.engine.replace_unit(operation)
            if result.held:
                self.archive.mark_snapshot_held(digest, result.operation_id, result.alert)
                raise ReviewRequired("Complete unit replacement held for review; source offset remains unacknowledged")
            changes = list(result.changes)
            self.archive.accept(digest, changes)
        except Exception:
            self._restore()
            raise
        key = (operation.unit, operation.producer.rsplit("@", 1)[0])
        self.highest_generations[key] = max(self.highest_generations.get(key, 0), operation.generation)
        if self.store is not None:
            self.store.append(list(self.engine.graph.assertions))
        return changes

    def pending_snapshot_holds(self) -> list[dict]:
        return self.archive.pending_snapshot_holds()

    def release_snapshot(self, receipt_digest: str, *, owner_action_id: str, actor: str, recorded_at: str) -> list[dict]:
        """Approve one pending hold through a trusted local caller.

        Actor/action are durable attribution, not an authentication mechanism.
        Source valid time stays unchanged; recorded time is the approval time.
        """
        for value in (owner_action_id, actor):
            if not isinstance(value, str) or not value.strip() or len(value) > 256 or any(ord(character) < 32 for character in value):
                raise ValueError("Release requires actor and owner action attribution")
        at = timestamp(recorded_at)
        existing = self.archive.release_for(receipt_digest)
        if self.archive.is_accepted(receipt_digest):
            if existing is None or existing["owner_action_id"] != owner_action_id or existing["actor"] != actor:
                raise ValueError("Accepted receipt does not match this owner release")
            self._restore()
            return []
        held = next((row for row in self.pending_snapshot_holds() if row["receipt_digest"] == receipt_digest), None)
        if held is None:
            raise ValueError("Release must identify a pending held snapshot")
        if datetime.fromisoformat(at.replace("Z", "+00:00")) < datetime.fromisoformat(self.archive.recorded_at(receipt_digest).replace("Z", "+00:00")):
            raise ValueError("Approval cannot precede the held receipt")
        latest = self.archive.latest_recorded_at()
        if latest is not None and at < latest:
            raise ValueError("Approval cannot precede already accepted knowledge")
        self._restore()
        try:
            operation = self._unit_operation(self.archive.read(receipt_digest), at)
            released = self.engine.apply_released_snapshot(operation, owner_action_id=owner_action_id,
                                                            held_operation_id=held["operation_id"])
            changes = list(released.changes)
            release = {"owner_action_id": owner_action_id, "actor": actor, "recorded_at": at}
            self.archive.accept(receipt_digest, changes, release=release)
        except Exception:
            self._restore()
            raise
        key = (operation.unit, operation.producer.rsplit("@", 1)[0])
        self.highest_generations[key] = max(self.highest_generations.get(key, 0), operation.generation)
        if self.store is not None:
            self.store.append(list(self.engine.graph.assertions))
        return changes

    def flush(self, send) -> int:
        sent = 0
        for change_id, event in self.archive.pending_changes():
            send(change_id, event)
            self.archive.mark_sent(change_id)
            sent += 1
        return sent


class KafkaChangeSink:
    def __init__(self, broker: str, topic: str = "lineage.changes"):
        from confluent_kafka import Producer
        self.topic = topic
        self.producer = Producer({"bootstrap.servers": broker, "enable.idempotence": True,
                                  "message.timeout.ms": 5000, "queue.buffering.max.messages": 1000})

    def __call__(self, change_id: str, event: dict) -> None:
        delivered = []
        self.producer.produce(self.topic, key=change_id, value=canonical(event),
                              on_delivery=lambda error, message: delivered.append(error))
        self.producer.flush(6)
        if not delivered or delivered[0] is not None:
            raise ConnectionError("Change stream delivery unavailable; durable outbox retained")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--events", type=Path, help="Replay a metadata-only v2 JSONL file locally")
    parser.add_argument("--broker", help="Consume lineage.evidence and publish lineage.changes")
    parser.add_argument("--bolt-url", default=os.environ.get("LINEAGE_BOLT_URL"))
    parser.add_argument("--namespace", default="lineage-runtime")
    parser.add_argument("--evidence-topic", default="lineage.evidence")
    parser.add_argument("--changes-topic", default="lineage.changes")
    parser.add_argument("--consumer-group", default="lineage-runtime-v1")
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--snapshots-topic", default="lineage.unit-snapshots")
    parser.add_argument("--repository")
    parser.add_argument("--stage", choices=["merged", "proposed"], default="merged")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--release-snapshot", help="Pending receipt digest to release through a trusted local caller")
    parser.add_argument("--owner-action-id")
    parser.add_argument("--actor", help="Attribution only; this local CLI does not authenticate the actor")
    parser.add_argument("--recorded-at")
    args = parser.parse_args(argv)
    if sum(bool(value) for value in (args.events, args.broker, args.release_snapshot)) != 1:
        parser.error("Provide exactly one of --events, --broker or --release-snapshot")
    route = {"repository": args.repository, "stage": args.stage, "pr": args.pr} if args.repository else None
    if args.stage == "proposed" and (route is None or args.snapshot_root is None):
        parser.error("Proposed ingestion requires repository, pr and snapshot-root")
    if route is not None:
        validate_route(route)
    if args.snapshots_topic == args.evidence_topic:
        parser.error("Snapshot completions require a separate topic")
    namespace = route_namespace(route) if args.stage == "proposed" else args.namespace
    store = BoltGraphStore(args.bolt_url,
                           (os.environ.get("LINEAGE_DB_USER", "neo4j"), os.environ.get("LINEAGE_DB_PASSWORD", "lineage-local-only")),
                           namespace=namespace) if args.bolt_url else None
    archive = EventArchive(args.archive)
    consumer = None
    try:
        pipeline = RuntimePipeline(archive, store, snapshot_root=args.snapshot_root, route=route)
        if args.release_snapshot:
            changes = pipeline.release_snapshot(args.release_snapshot, owner_action_id=args.owner_action_id,
                                                actor=args.actor, recorded_at=args.recorded_at)
            print(json.dumps({"status": "accepted", "material_changes": len(changes)}))
            return 0
        if args.events:
            count = changes = 0
            with args.events.open() as handle:
                for line in handle:
                    event = json.loads(line)
                    changes += len(pipeline.process(event, recorded_at=event["eventTime"]))
                    count += 1
            print(json.dumps({"events": count, "material_changes": changes, "archive": str(args.archive)}))
            return 0
        from confluent_kafka import Consumer
        group = args.consumer_group + "." + route_namespace(route) if route else args.consumer_group
        consumer = Consumer({"bootstrap.servers": args.broker, "group.id": group,
                             "enable.auto.commit": False, "auto.offset.reset": "earliest"})
        topics = [args.evidence_topic] if args.stage == "merged" else []
        if args.snapshot_root:
            topics.append(args.snapshots_topic)
        consumer.subscribe(topics)
        sink = KafkaChangeSink(args.broker, args.changes_topic)
        running = True
        def stop(signum, frame):
            nonlocal running
            running = False
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while running:
            # Outbox errors leave offsets/receipts intact and cause a restart.
            pipeline.flush(sink)
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                raise ConnectionError("Evidence broker returned an error")
            event = json.loads(message.value())
            at = datetime.now(timezone.utc).isoformat()
            if message.topic() == args.snapshots_topic:
                validate_manifest(event)
                incoming_route = event["route"]
                # Separate consumer groups inspect the same completion topic.
                # A valid manifest for another route is irrelevant to this worker.
                if incoming_route["stage"] != pipeline.route["stage"] or incoming_route["pr"] != pipeline.route["pr"] or (pipeline.route["repository"] is not None and incoming_route["repository"] != pipeline.route["repository"]):
                    consumer.commit(message=message, asynchronous=False)
                    continue
                pipeline.process_snapshot(event, recorded_at=at)
            else:
                pipeline.process(event, recorded_at=at)
            consumer.commit(message=message, asynchronous=False)
        return 0
    except Exception:
        print('{"status":"error","category":"ingestion_unavailable","source_acknowledged":false}', flush=True)
        return 1
    finally:
        if consumer is not None:
            consumer.close()
        archive.close()
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
