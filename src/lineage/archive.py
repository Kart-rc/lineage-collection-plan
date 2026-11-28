"""Immutable Parquet receipts with a transactional replay and change-outbox index.

The archive accepts validated metadata, not raw OTLP payloads. A receipt becomes
accepted only with its change outbox; an interrupted receipt can be retried.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class EventArchive:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.directory / "index.sqlite3")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
          CREATE TABLE IF NOT EXISTS receipts (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            digest TEXT NOT NULL UNIQUE,
            recorded_at TEXT NOT NULL,
            raw_ref TEXT,
            accepted INTEGER NOT NULL DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS outbox (
            digest TEXT PRIMARY KEY,
            body TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS acceptance_journal (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            digest TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            recorded_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS archive_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS snapshot_holds (
            digest TEXT PRIMARY KEY, operation_id TEXT NOT NULL, alert TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS snapshot_releases (
            digest TEXT PRIMARY KEY, owner_action_id TEXT NOT NULL UNIQUE,
            actor TEXT NOT NULL, recorded_at TEXT NOT NULL
          );
        """)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(receipts)")}
        if "kind" not in columns:
            self.connection.execute("ALTER TABLE receipts ADD COLUMN kind TEXT NOT NULL DEFAULT 'event'")
        # Upgrade the earlier runtime-only twin archive without dropping receipts.
        with self.connection:
            self.connection.execute("""INSERT OR IGNORE INTO acceptance_journal(digest,kind,recorded_at)
                SELECT digest,kind,recorded_at FROM receipts WHERE accepted=1 ORDER BY sequence""")

    def bind_route(self, route: dict) -> None:
        value = canonical(route)
        with self.connection:
            row = self.connection.execute("SELECT value FROM archive_settings WHERE key='route'").fetchone()
            if row and row[0] != value:
                raise ValueError("Archive belongs to a different ingestion route")
            self.connection.execute("INSERT OR IGNORE INTO archive_settings VALUES('route',?)", (value,))

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid archive digest")
        return self.directory / f"{digest}.parquet"

    def stage(self, event: dict, recorded_at: str) -> str:
        """Validate and durably stage a receipt without declaring it applied."""
        from .evidence import prepare_event

        event = prepare_event(event)
        return self._stage(event, recorded_at, "event")

    def stage_snapshot(self, manifest, snapshot, recorded_at):
        """Retain the complete validated event set for independent recovery."""
        from .snapshots import validate_manifest
        from .evidence import validate_event, prepare_event
        from .merge import snapshot_digest

        validate_manifest(manifest)
        if snapshot.unit != manifest["unit"]["urn"] or snapshot.producer != manifest["producer"] or snapshot.generation != manifest["generation"] or snapshot.complete is not True or snapshot.deleted != manifest["deleted"]:
            raise ValueError("Snapshot archive disagrees with completion metadata")
        if snapshot.digest != manifest["eventsHash"] or snapshot_digest(snapshot.events) != snapshot.digest or len(snapshot.events) != manifest["eventCount"]:
            raise ValueError("Snapshot archive count or hash mismatch")
        for event in snapshot.events:
            validate_event(event)
            if prepare_event(event) != event or event["eventType"] != "EVIDENCE" or event["evidence"]["runtime"] or event["evidence"].get("replaces") != "unit":
                raise ValueError("Invalid static snapshot evidence")
            if event.get("unit") != manifest["unit"] or event["producer"] != manifest["producer"]:
                raise ValueError("Snapshot archive contains inconsistent revision metadata")
        return self._stage({"manifest": manifest, "events": list(snapshot.events)}, recorded_at, "snapshot")

    def _stage(self, event, recorded_at, kind):
        body = canonical(event)
        digest = hashlib.sha256(body.encode()).hexdigest()
        destination = self._path(digest)
        if not destination.exists():
            descriptor, temporary = tempfile.mkstemp(prefix=".receipt-", dir=self.directory)
            os.close(descriptor)
            try:
                pq.write_table(pa.table({"sha256": [digest], "event_json": [body]}), temporary, compression="zstd")
                with open(temporary, "rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temporary, destination)
                directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        else:
            self.read(digest)  # A corrupt receipt must never be silently accepted.
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO receipts(digest,recorded_at,raw_ref,kind) VALUES(?,?,?,?)",
                (digest, recorded_at, event.get("evidence", {}).get("rawRef"), kind),
            )
        return digest

    def read(self, digest: str) -> dict:
        rows = pq.read_table(self._path(digest)).to_pylist()
        if len(rows) != 1:
            raise ValueError("Archive receipt contains an unexpected row count")
        row = rows[0]
        if row["sha256"] != digest or hashlib.sha256(row["event_json"].encode()).hexdigest() != digest:
            raise ValueError("Archive receipt integrity check failed")
        return json.loads(row["event_json"])

    def mark_snapshot_held(self, digest: str, operation_id: str, alert: dict) -> None:
        if alert.get("reason") != "mass_close_hold" or alert.get("operationId") != operation_id:
            raise ValueError("Invalid snapshot hold metadata")
        with self.connection:
            row = self.connection.execute("SELECT kind,accepted FROM receipts WHERE digest=?", (digest,)).fetchone()
            if row != ("snapshot", 0):
                raise ValueError("Only pending snapshots can be held")
            self.connection.execute("INSERT OR REPLACE INTO snapshot_holds VALUES(?,?,?)", (digest, operation_id, canonical(alert)))

    def pending_snapshot_holds(self):
        return [{"receipt_digest": digest, "operation_id": operation_id, "alert": json.loads(alert)}
                for digest, operation_id, alert in self.connection.execute("""SELECT h.digest,h.operation_id,h.alert
                FROM snapshot_holds h JOIN receipts r ON r.digest=h.digest WHERE r.accepted=0 ORDER BY r.sequence""").fetchall()]

    def snapshot_hold_for(self, digest):
        row = self.connection.execute("SELECT operation_id,alert FROM snapshot_holds WHERE digest=?", (digest,)).fetchone()
        return {"receipt_digest": digest, "operation_id": row[0], "alert": json.loads(row[1])} if row else None

    def release_for(self, digest):
        row = self.connection.execute("SELECT owner_action_id,actor,recorded_at FROM snapshot_releases WHERE digest=?", (digest,)).fetchone()
        return {"owner_action_id": row[0], "actor": row[1], "recorded_at": row[2]} if row else None

    def accept(self, digest: str, changes: list[dict] | tuple[dict, ...], *, release: dict | None = None) -> None:
        """Atomically mark a receipt applied and enqueue logical material changes."""
        from .config import schema
        from jsonschema import Draft202012Validator, FormatChecker

        validator = Draft202012Validator(schema("factory/specs/changes/interfaces/lineage-changes.schema.json"), format_checker=FormatChecker())
        for event in changes:
            if next(validator.iter_errors(event), None) is not None:
                raise ValueError("Invalid lineage change event")
        with self.connection:
            row = self.connection.execute("SELECT accepted FROM receipts WHERE digest=?", (digest,)).fetchone()
            if row is None:
                raise ValueError("Unknown archive receipt")
            if row[0]:
                return
            held = self.connection.execute("SELECT 1 FROM snapshot_holds WHERE digest=?", (digest,)).fetchone()
            if held and release is None:
                raise ValueError("Held snapshot requires an explicit attributable release")
            if release is not None:
                if not held or set(release) != {"owner_action_id", "actor", "recorded_at"}:
                    raise ValueError("Release must refer to a held snapshot")
                for key in ("owner_action_id", "actor"):
                    if not isinstance(release[key], str) or not release[key].strip() or len(release[key]) > 256:
                        raise ValueError("Release requires actor and owner action attribution")
                from .graph import timestamp
                at = timestamp(release["recorded_at"])
                self.connection.execute("INSERT INTO snapshot_releases VALUES(?,?,?,?)", (digest, release["owner_action_id"], release["actor"], at))
            for event in changes:
                body = canonical(event)
                change_id = hashlib.sha256(body.encode()).hexdigest()
                self.connection.execute("INSERT OR IGNORE INTO outbox(digest,body) VALUES(?,?)", (change_id, body))
            self.connection.execute("UPDATE receipts SET accepted=1 WHERE digest=?", (digest,))
            if release is None:
                self.connection.execute("""INSERT INTO acceptance_journal(digest,kind,recorded_at)
                    SELECT digest,kind,recorded_at FROM receipts WHERE digest=?""", (digest,))
            else:
                self.connection.execute("""INSERT INTO acceptance_journal(digest,kind,recorded_at)
                    SELECT digest,kind,? FROM receipts WHERE digest=?""", (at, digest))

    def operations(self):
        """One durable acceptance order for runtime and complete-unit operations."""
        for digest, kind, recorded_at in self.connection.execute(
            "SELECT digest,kind,recorded_at FROM acceptance_journal ORDER BY sequence").fetchall():
            yield kind, digest, recorded_at, self.read(digest)

    def receipts(self, *, accepted: bool = True) -> Iterator[tuple[str, str, dict]]:
        rows = self.connection.execute(
            "SELECT digest,recorded_at FROM receipts WHERE accepted=? ORDER BY sequence", (int(accepted),)
        ).fetchall()
        for digest, recorded_at in rows:
            yield digest, recorded_at, self.read(digest)

    def is_accepted(self, digest: str) -> bool:
        row = self.connection.execute("SELECT accepted FROM receipts WHERE digest=?", (digest,)).fetchone()
        return bool(row and row[0])

    def recorded_at(self, digest: str) -> str:
        row = self.connection.execute("SELECT recorded_at FROM receipts WHERE digest=?", (digest,)).fetchone()
        if row is None:
            raise ValueError("Unknown archive receipt")
        return row[0]

    def latest_recorded_at(self):
        from .graph import timestamp
        times = [timestamp(row[0]) for row in self.connection.execute("SELECT recorded_at FROM acceptance_journal")]
        return max(times) if times else None

    def resolve(self, raw_ref: str) -> list[dict]:
        result = [self.read(row[0]) for row in self.connection.execute(
            "SELECT digest FROM receipts WHERE raw_ref=? AND accepted=1 ORDER BY sequence", (raw_ref,)
        ).fetchall()]
        for kind, _, _, body in self.operations():
            if kind == "snapshot":
                result.extend(event for event in body["events"] if event["evidence"]["rawRef"] == raw_ref)
        return result

    def pending_changes(self) -> Iterator[tuple[str, dict]]:
        for digest, body in self.connection.execute("SELECT digest,body FROM outbox WHERE sent=0 ORDER BY rowid").fetchall():
            yield digest, json.loads(body)

    def mark_sent(self, digest: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE outbox SET sent=1 WHERE digest=?", (digest,))

    def close(self) -> None:
        self.connection.close()
