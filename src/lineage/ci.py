"""Fail-open static extraction with durable, complete-unit publication.

Evidence objects and completion manifests use separate durable storage and
transport. Individual replacement envelopes never enter the additive topic.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .config import schema
from .plugins import (ExtractContext, InputRef, PluginRegistry, RepoView, StubExtractor,
                      UnitRef, WorkerFailure, WorkerTimeout, canonical, checked_path,
                      digest, isolated, opaque_event, stub_fixture)

VERSION = "0.1.0"
REPO_SCHEMA = "factory/specs/build-collection/interfaces/lineage-repo.schema.json"
MANIFEST_SCHEMA = "factory/specs/build-collection/interfaces/unit-manifest.schema.json"


def _field(path) -> str:
    result = ""
    for part in path:
        result += f"[{part}]" if isinstance(part, int) else ("." if result else "") + part
    return result


def validate_config(value: object) -> list[str]:
    errors = []
    for error in sorted(Draft202012Validator(schema(REPO_SCHEMA)).iter_errors(value), key=lambda e: str(list(e.path))):
        field = _field(error.path)
        if error.validator == "required":
            missing = re.search(r"'([^']+)'", error.message)
            field = (field + "." if field else "") + (missing.group(1) if missing else "configuration")
        elif error.validator == "anyOf" and not field:
            field = "services, schemas or projects"
        # Schema messages name constraints; no input values or source fragments.
        fixes = {"required": "add this required field", "pattern": "use the documented naming format",
                 "enum": "choose a value listed in lineage-repo.schema.json", "const": "use version 1",
                 "maximum": "set this to 5 or less", "exclusiveMinimum": "use a number greater than zero",
                 "anyOf": "add at least one section", "type": "use the type required by lineage-repo.schema.json",
                 "additionalProperties": "remove unrecognized fields", "uniqueItems": "remove duplicate entries"}
        errors.append(f"{field or 'configuration'}: {fixes.get(error.validator, 'follow lineage-repo.schema.json')}")
    if not errors and isinstance(value, dict):
        for section in ("services", "schemas", "projects"):
            for index, item in enumerate(value.get(section, [])):
                for field in ("path", "artifact"):
                    if field in item:
                        try:
                            checked_path(item[field])
                        except ValueError:
                            errors.append(f"{section}[{index}].{field}: use a repository-relative path without '..'")
    return errors


def read_config(content: str | bytes) -> tuple[dict | None, list[str]]:
    try:
        value = yaml.safe_load(content)
    except (yaml.YAMLError, UnicodeError):
        return None, ["configuration: repair invalid YAML"]
    errors = validate_config(value)
    return (value if not errors else None), errors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".lineage-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _ancestor(directory: Path, before: str, after: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{40}", before):
        return False
    return subprocess.run(["git", "-C", str(directory), "merge-base", "--is-ancestor", before, after],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0


def _hash_files(repo: RepoView, paths: tuple[str, ...] | list[str]) -> str:
    # Hash length-delimited names and bytes, preserving filename and byte changes.
    import hashlib
    result = hashlib.sha256()
    for path in sorted(set(paths)):
        data = repo.read_bytes(path)
        name = path.encode()
        result.update(len(name).to_bytes(8, "big") + name + len(data).to_bytes(8, "big") + data)
    return "sha256:" + result.hexdigest()


def _unit_key(unit: dict) -> tuple:
    return tuple(unit[name] for name in ("extractor", "extractor_version", "content_hash", "input_schema_hash"))


def _cache_unit_valid(urn: str, prior: object, pr: int | None = None) -> bool:
    from .evidence import validate_event
    from .merge import snapshot_digest
    try:
        if not isinstance(prior, dict) or prior.get("complete") is not True:
            return False
        snapshot, row = prior["snapshot"], prior["manifest"]
        if snapshot["unit"] != urn or row["urn"] != urn or snapshot["complete"] is not True:
            return False
        if snapshot["digest"] != snapshot_digest(snapshot["events"]) or snapshot["deleted"]:
            return False
        for event in snapshot["events"]:
            validate_event(event)
            if event["unit"]["urn"] != urn or event["unit"].get("pr") != pr:
                return False
        _unit_key(row)
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _finalize_events(events, unit, repo, plugin, content_hash, input_hash, pr, *, replacing=True):
    from .evidence import prepare_event
    finalized = []
    for original in events:
        if original.get("eventType") != "EVIDENCE" or original.get("evidence", {}).get("source") != "ci_static":
            raise ValueError("static extractors may emit only ci_static evidence")
        event = json.loads(canonical(original))
        event["producer"] = f"lineage-extractors/{plugin.name}@{plugin.version}"
        event["unit"] = {"urn": unit.urn, "contentHash": content_hash,
                         "inputSchemaHash": input_hash, "commit": repo.commit}
        if pr is not None:
            event["unit"]["pr"] = pr
        event["evidence"]["replaces"] = "unit" if replacing else "none"
        finalized.append(prepare_event(event))
    return sorted({canonical(event): event for event in finalized}.values(), key=canonical)


def _snapshot(unit, plugin, events, repo, *, generation, recorded_at, deleted=False):
    from .merge import UnitSnapshot
    return UnitSnapshot.build(unit=unit.urn, producer=f"lineage-extractors/{plugin.name}@{plugin.version}",
                              generation=generation, valid_at=repo.timestamp, recorded_at=recorded_at,
                              events=events, deleted=deleted).as_dict()


def _unclaimed(item, section, config, repo):
    path = checked_path(item["path"])
    return UnitRef(f"unit://git/{config['repository']}/{path}", path, repo.files(path),
                   item.get("name", path), section, config["environment"])


def scan(*, repository_dir: str | Path, stage: str, commit: str, base: str | None = None,
         pr: int | None = None, config_path: str = ".lineage.yaml", out_dir: str | Path = ".lineage-out",
         state_dir: str | Path | None = None, transport: str = "local", stub: bool = False,
         registry: PluginRegistry | None = None, unit_seconds: float | None = None,
         clock: Callable[[], str] = _now, snapshot_root: str | Path | None = None,
         broker: str | None = None, snapshot_topic: str = "lineage.unit-snapshots",
         coordinator=None, publisher=None) -> dict:
    """Always return a structured result; own failures never become a failing CI exit.

    local means durable completion staging, not graph acceptance. kafka requires
    broker acknowledgment. Unavailable publication never advances merged cache.
    """
    directory, output = Path(repository_dir).resolve(), Path(out_dir).resolve()
    state = Path(state_dir).resolve() if state_dir else directory / ".lineage-state"
    snapshot_root = Path(snapshot_root).resolve() if snapshot_root else state / "snapshots"
    started, start_tick = clock(), time.monotonic()
    record = {"candidate": True, "transport": transport, "published": False, "publication_complete": False,
              "graph_accepted": False, "started": started,
              "errors": [], "alerts": [], "timings": {}, "conformance_rejected": {}}
    manifest = None
    lock = None
    extraction_ms = 0
    try:
        if stage not in ("proposed", "merged"):
            raise ValueError("stage: choose proposed or merged")
        if stage == "proposed" and (pr is None or pr < 1):
            raise ValueError("pr: proposed scans require a positive PR number")
        if stage == "merged" and pr is not None:
            raise ValueError("pr: merged scans must not carry a PR number")
        if transport not in ("local", "kafka", "unavailable"):
            raise ValueError("transport: choose local, kafka or unavailable")
        if transport == "kafka" and not broker and publisher is None:
            raise ValueError("transport: kafka requires --broker")
        repo = RepoView.from_git(directory, commit)
        config, errors = read_config(repo.read_bytes(checked_path(config_path)))
        if errors:
            record["errors"] = errors
            raise ValueError("configuration: scan unavailable until the named fields are fixed")
        repo = replace(repo, config=config, exclude=tuple(config.get("exclude", [])))
        if base:
            base = RepoView.from_git(directory, base).commit
        manifest = {"repository": config["repository"], "commit": repo.commit, "base": base,
                    "stage": stage, "pr": pr, "started": started, "finished": started,
                    "runner": "lineage-ci@" + VERSION, "units": [], "outcome": "unavailable"}
        budget = config.get("build", {}).get("max_minutes", 5) * 60
        deadline = start_tick + budget
        from .snapshots import KafkaSnapshotSink, SnapshotCoordinator, SnapshotPublisher
        route = {"repository": config["repository"], "stage": stage, "pr": pr}
        coordinator = coordinator or SnapshotCoordinator(snapshot_root)

        def make_publisher():
            # Kafka starts native threads. Construct it only after the final
            # extractor worker has exited; the dedicated CLI never forks it.
            sink = None
            if transport == "kafka":
                sink = KafkaSnapshotSink(broker, snapshot_topic, ack_timeout=min(5.0, max(0.1, deadline - time.monotonic())))
            elif transport == "unavailable":
                def sink(_key, _manifest):
                    raise ConnectionError("completion topic unavailable")
            return SnapshotPublisher(snapshot_root, sink=sink)
        registry = registry or PluginRegistry()
        if stub and not registry.get("stub"):
            registry.register(StubExtractor(), stub_fixture(), deadline)
        elif not registry.values():
            registry.discover(deadline)
        record["conformance_rejected"] = registry.rejected
        cache_path = state / config["repository"] / "candidate-merged.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        lock = (cache_path.parent / "scan.lock").open("a")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("state: another scan is active; retry without blocking the build") from error
        cached = _load(cache_path)
        if (stage == "merged" and cached and cached.get("commit") != repo.commit
                and _ancestor(directory, repo.commit, cached.get("commit", ""))):
            raise ValueError("state: stale merged scan cannot overwrite a newer merged baseline")
        cache_valid = bool(cached and cached.get("candidate") is True and cached.get("repository") == config["repository"]
                           and _ancestor(directory, cached.get("commit", ""), repo.commit)
                           and (not base or cached["commit"] == base))
        if cached and not cache_valid:
            record["errors"].append("state: stale merged cache ignored")
        previous = cached.get("units", {}) if cache_valid else {}
        if not isinstance(previous, dict):
            previous = {}
        previous = {urn: value for urn, value in previous.items() if _cache_unit_valid(urn, value)}
        overlay_path = state / "overlays" / config["repository"] / str(pr) / "completed-units.json"
        overlay_previous = {}
        if stage == "proposed":
            overlay_state = _load(overlay_path) or {}
            if overlay_state.get("repository") == config["repository"] and overlay_state.get("pr") == pr:
                overlay_previous = {urn: value for urn, value in overlay_state.get("units", {}).items()
                                    if _cache_unit_valid(urn, value, pr=pr)}
        intent_path = state / "publication-intents" / config["repository"] / (f"pr-{pr}.json" if pr is not None else "merged.json")
        intent_state = _load(intent_path) or {}
        intents = {urn: value for urn, value in intent_state.get("units", {}).items()
                   if _cache_unit_valid(urn, value, pr=pr)} if intent_state.get("route") == route else {}
        descriptors = [(section, item) for section in ("services", "schemas", "projects") for item in config.get(section, [])]
        found = []
        claimed = set()
        failed_paths = set()
        for plugin in registry.values():
            paths = [item["path"] for _, item in descriptors
                     if stub or not item.get("extractors") or plugin.name in item["extractors"]]
            if not paths:
                continue
            try:
                detected = isolated(lambda: plugin.detect(repo, paths), max(0, min(10, deadline - time.monotonic())))
                if not isinstance(detected, list):
                    raise ValueError("detect returned invalid units")
                for section, item in descriptors:
                    if plugin.name in item.get("extractors", []) and not any(
                            isinstance(unit, UnitRef) and (unit.path == item["path"] or unit.path.startswith(item["path"].rstrip("/") + "/"))
                            for unit in detected):
                        # An explicit assignment runs even when autodetection declines.
                        detected.append(_unclaimed(item, section, config, repo))
                accepted, claimed_here = [], set()
                for unit in detected:
                    if not isinstance(unit, UnitRef) or not any(unit.path == p or unit.path.startswith(p.rstrip("/") + "/") for p in paths):
                        raise ValueError("detect returned a unit outside configured paths")
                    expected_prefix = f"unit://git/{config['repository']}/"
                    if not unit.urn.startswith(expected_prefix) or unit.urn != expected_prefix + checked_path(unit.path):
                        raise ValueError("detect returned a foreign unit identity")
                    if not all(path in repo.files(unit.path) for path in unit.files):
                        raise ValueError("detect returned excluded or foreign files")
                    accepted.append((unit, plugin, None))
                    claimed_here.update(path for path in paths if unit.path == path or unit.path.startswith(path.rstrip("/") + "/"))
                found.extend(accepted)
                claimed.update(claimed_here)
            except (WorkerFailure, ValueError, KeyError, TypeError):
                failed_paths.update(paths)
                record["errors"].append(f"extractor {plugin.name}: detection failed or exceeded its deadline")
        for section, item in descriptors:
            if item["path"] not in claimed:
                unit = _unclaimed(item, section, config, repo)
                found.append((unit, StubExtractor(), "EXTRACTOR_ERROR" if item["path"] in failed_paths else "UNPARSED_LANGUAGE"))
                record["errors"].append(f"{item['path']}: claimed by no extractor")
        identities = [unit.urn for unit, _, _ in found]
        if len(identities) != len(set(identities)):
            raise ValueError("extractors: overlapping unit ownership is not supported")
        snapshots, next_units, diagnostics, completion_requests = [], {}, [], []
        partial = bool(failed_paths)
        found.sort(key=lambda entry: entry[0].urn)

        def reserve(unit, plugin, row, *, deleted=False):
            producer = f"lineage-extractors/{plugin.name}@{plugin.version}"
            revision = {"urn": unit.urn, "contentHash": row["content_hash"], "inputSchemaHash": row["input_schema_hash"],
                        "commit": repo.commit}
            if pr is not None:
                revision["pr"] = pr
            request_id = digest({"route": route, "revision": revision, "producer": producer, "deleted": deleted})
            generation = coordinator.reserve(route, unit.urn, producer, request_id)
            reservation = coordinator.reservation(route, unit.urn, producer, request_id)
            return generation, reservation["reserved_at"], request_id, revision

        for index, (unit, plugin, unresolved) in enumerate(found):
            began = time.monotonic()
            row = {"urn": unit.urn, "extractor": plugin.name if not unresolved else "unclaimed",
                   "extractor_version": plugin.version, "content_hash": _hash_files(repo, unit.files),
                   "input_schema_hash": digest([]), "status": "extracted"}
            events, reason, reservation = [], unresolved, None
            try:
                remaining = deadline - time.monotonic()
                allowance = min(unit_seconds if unit_seconds is not None else remaining / max(1, len(found) - index), remaining)
                refs = isolated(lambda: plugin.inputs(unit), allowance)
                if not all(isinstance(ref, InputRef) for ref in refs):
                    raise ValueError("invalid input reference")
                row["input_schema_hash"] = digest({"schemas": _hash_files(repo, [ref.path for ref in refs]),
                                                   "identity": {"name": unit.name, "kind": unit.kind, "environment": unit.environment}})
                prior = previous.get(unit.urn)
                if unresolved != "EXTRACTOR_ERROR" and prior and prior.get("complete") and _unit_key(prior["manifest"]) == _unit_key(row):
                    row.update(status="unchanged", events=0)
                    next_units[unit.urn] = prior
                    manifest["units"].append(row)
                    if stage == "proposed":
                        # Refresh unchanged overlay units too: a PR may revert a
                        # prior update, which must not leave its old overlay edge.
                        generation, recorded_at, request_id, revision = reserve(unit, plugin, row)
                        events = _finalize_events(prior["snapshot"]["events"], unit, repo, plugin,
                                                  row["content_hash"], row["input_schema_hash"], pr)
                        overlay_snapshot = _snapshot(unit, plugin, events, repo, generation=generation, recorded_at=recorded_at)
                        snapshots.append(overlay_snapshot)
                        completion_requests.append((request_id, revision))
                        next_units[unit.urn] = {"manifest": row, "complete": True, "snapshot": overlay_snapshot}
                    continue
                reservation = reserve(unit, plugin, row)
                if unresolved == "EXTRACTOR_ERROR":
                    row["status"], partial = "failed", True
                elif unresolved:
                    events = [opaque_event(unit, repo, unresolved, "lineage-extractors/stub@" + plugin.version)]
                    row["status"] = "opaque"
                else:
                    allowance = min(allowance - (time.monotonic() - began), deadline - time.monotonic())
                    events = isolated(lambda: list(plugin.extract(unit, ExtractContext(repo, time.monotonic() + allowance))), allowance)
                events = _finalize_events(events, unit, repo, plugin, row["content_hash"], row["input_schema_hash"], pr)
            except WorkerTimeout:
                row["status"], reason, partial = "over_budget", "EXTRACTOR_ERROR", True
            except (WorkerFailure, ValueError, KeyError, TypeError):
                row["status"], reason, partial = "failed", "EXTRACTOR_ERROR", True
            if row["status"] in ("over_budget", "failed"):
                diagnostics.extend(_finalize_events([opaque_event(unit, repo, reason, "lineage-extractors/stub@" + plugin.version)],
                                                    unit, repo, plugin, row["content_hash"], row["input_schema_hash"], pr, replacing=False))
                events = []
            if reason:
                row["reason"] = reason
            row["events"] = len(events)
            row["duration_ms"] = max(0, int((time.monotonic() - began) * 1000))
            extraction_ms += row["duration_ms"]
            manifest["units"].append(row)
            if row["status"] in ("over_budget", "failed"):
                continue
            generation, recorded_at, request_id, revision = reservation
            snapshot = _snapshot(unit, plugin, events, repo, generation=generation, recorded_at=recorded_at)
            snapshots.append(snapshot)
            completion_requests.append((request_id, revision))
            # Only complete extractions and explicit opaque gaps enter cache.
            if row["status"] in ("extracted", "opaque"):
                next_units[unit.urn] = {"manifest": row, "complete": True, "snapshot": snapshot}
        # A removed detected unit needs an explicit empty complete candidate set.
        deletion_baseline = {**previous, **overlay_previous, **intents}
        for urn, prior in sorted(deletion_baseline.items()) if not partial else []:
            if urn not in identities:
                old = prior["manifest"]
                unit = UnitRef(urn, urn.split(f"unit://git/{config['repository']}/", 1)[-1], ())
                old_producer = prior["snapshot"]["producer"].removeprefix("lineage-extractors/")
                old_name, old_version = old_producer.rsplit("@", 1)
                plugin = type("PriorExtractor", (), {"name": old_name, "version": old_version})()
                row = {**old, "content_hash": _hash_files(repo, []), "input_schema_hash": digest([])}
                generation, recorded_at, request_id, revision = reserve(unit, plugin, row, deleted=True)
                snapshots.append(_snapshot(unit, plugin, [], repo, generation=generation, recorded_at=recorded_at, deleted=True))
                completion_requests.append((request_id, revision))
        staging = {"candidate": True, "published": False, "route": route, "commit": repo.commit, "snapshots": snapshots}
        _write(output / "candidate-snapshots.json", staging)
        _write(output / "diagnostic-events.json", diagnostics)
        if transport == "unavailable" and not snapshots:
            raise ValueError("transport: completion topic unavailable")
        from .merge import UnitSnapshot
        publisher = publisher or make_publisher()
        completions = []
        _write(output / "completion-manifests.json", completions)
        manifest_rows = {row["urn"]: row for row in manifest["units"]}
        for snapshot in snapshots:
            if not snapshot["deleted"]:
                intents[snapshot["unit"]] = {"manifest": manifest_rows[snapshot["unit"]], "complete": True, "snapshot": snapshot}
        # This journal tracks possibly delivered complete sets, never cache
        # eligibility. It survives an ambiguous acknowledgment or partial scan
        # so a later removal can retire a PR-only unit safely.
        _write(intent_path, {"route": route, "units": intents})
        for snapshot, (request_id, revision) in zip(snapshots, completion_requests, strict=True):
            if time.monotonic() >= deadline:
                raise ValueError("transport: scan deadline reached before completion publication")
            if isinstance(getattr(publisher, "sink", None), KafkaSnapshotSink):
                publisher.sink.ack_timeout = min(publisher.sink.ack_timeout, deadline - time.monotonic())
            completions.append(publisher.publish(UnitSnapshot.from_dict(snapshot), route, request_id, unit_revision=revision))
            record["published"] = True
            record["completion_count"] = len(completions)
            _write(output / "completion-manifests.json", completions)
            if snapshot["deleted"]:
                intents.pop(snapshot["unit"], None)
                _write(intent_path, {"route": route, "units": intents})
        staging["published"] = bool(completions)
        _write(output / "candidate-snapshots.json", staging)
        destination = state / ("overlays" if stage == "proposed" else "merged") / config["repository"]
        if stage == "proposed":
            destination /= str(pr)
        _write(destination / repo.commit / "candidate-snapshots.json", staging)
        manifest["outcome"] = "emitted_partial" if partial else "emitted"
        record["local_candidate_accepted"] = transport == "local"
        record["published"] = bool(completions)
        record["publication_complete"] = True
        record["completion_count"] = len(completions)
        record["completion_topic"] = snapshot_topic if transport == "kafka" else None
        record["snapshot_root"] = str(snapshot_root)
        if partial:
            record["alerts"].append({"code": "LINEAGE_EXTRACTION_PARTIAL", "message": "one or more units were not replaced"})
        if stage == "merged" and not partial:
            # Never let a PR or a partial/unavailable scan advance merged state.
            _write(cache_path, {"candidate": True, "repository": config["repository"], "commit": repo.commit,
                                "units": next_units})
        elif stage == "proposed" and not partial:
            _write(overlay_path, {"repository": config["repository"], "pr": pr, "commit": repo.commit, "units": next_units})
    except Exception as error:
        # Deliberately omit arbitrary exception text: collectors can carry literals.
        if isinstance(error, ValueError) and str(error).startswith(("stage:", "pr:", "configuration:", "transport:", "state:", "extractors:")):
            record["errors"].append(str(error))
        else:
            record["errors"].append("runner: unavailable (" + type(error).__name__ + ")")
        if manifest:
            manifest["outcome"] = "unavailable"
        record["alerts"].append({"code": "LINEAGE_CHECK_UNAVAILABLE", "message": "lineage check unavailable"})
    finally:
        if lock:
            lock.close()
    finished = clock()
    record["finished"] = finished
    elapsed_ms = max(0, int((time.monotonic() - start_tick) * 1000))
    record["timings"] = {"total_ms": elapsed_ms, "unit_processing_ms": extraction_ms,
                         "runner_overhead_ms": elapsed_ms,
                         "runner_overhead_measurement": "conservative total-scan wall-time upper bound"}
    if manifest:
        manifest["finished"] = finished
        Draft202012Validator(schema(MANIFEST_SCHEMA), format_checker=FormatChecker()).validate(manifest)
        _write(output / "unit-manifest.json", manifest)
        content = {key: value for key, value in manifest.items() if key not in ("started", "finished")}
        content["units"] = [{key: value for key, value in unit.items() if key != "duration_ms"} for unit in manifest["units"]]
        _write(output / "scan-content.json", content)
    _write(output / "run-record.json", record)
    _write(output / "alerts.json", record["alerts"])
    if record["alerts"]:
        _write(output / "comment.json", {"posted": False, "message": "lineage check unavailable"})
    return {"manifest": manifest, "record": record}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lineage-ci")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--config", default=".lineage.yaml")
    scanner = commands.add_parser("scan")
    scanner.add_argument("--stage", choices=("proposed", "merged"), required=True)
    scanner.add_argument("--commit", required=True)
    scanner.add_argument("--base")
    scanner.add_argument("--pr", type=int)
    scanner.add_argument("--config", default=".lineage.yaml")
    scanner.add_argument("--out", default=".lineage-out")
    scanner.add_argument("--repo", default=".")
    scanner.add_argument("--state-dir")
    scanner.add_argument("--transport", choices=("local", "kafka", "unavailable"), default="local")
    scanner.add_argument("--snapshot-root", help="Shared durable snapshot archive and generation coordinator directory")
    scanner.add_argument("--broker", help="Kafka bootstrap servers for completion publication")
    scanner.add_argument("--snapshot-topic", default="lineage.unit-snapshots")
    scanner.add_argument("--stub", action="store_true", help="Explicit fixture mode, not real technology extraction")
    impact = commands.add_parser("impact")
    impact.add_argument("--pr", type=int, required=True)
    impact.add_argument("--comment", action="store_true")
    impact.add_argument("--out", default=".lineage-out")
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            _, errors = read_config(Path(args.config).read_bytes())
            print("\n".join(errors) if errors else "configuration valid")
        elif args.command == "scan":
            result = scan(repository_dir=args.repo, stage=args.stage, commit=args.commit, base=args.base,
                          pr=args.pr, config_path=args.config, out_dir=args.out, state_dir=args.state_dir,
                          transport=args.transport, stub=args.stub, snapshot_root=args.snapshot_root,
                          broker=args.broker, snapshot_topic=args.snapshot_topic)
            print(json.dumps({"outcome": result["manifest"]["outcome"] if result["manifest"] else "unavailable",
                              "candidate": True, "published": result["record"]["published"], "errors": result["record"]["errors"]}, sort_keys=True))
        else:
            # Impact and external comments belong to wave 3; never fabricate them.
            _write(Path(args.out) / "comment.json", {"pr": args.pr, "posted": False,
                                                    "message": "lineage check unavailable", "reason": "impact engine not implemented"})
            _write(Path(args.out) / "alerts.json", [{"code": "LINEAGE_CHECK_UNAVAILABLE", "pr": args.pr}])
            print("lineage check unavailable; impact engine not implemented; comment prepared, not posted")
    except SystemExit:
        # Even malformed arguments fail open; only a separate contract gate blocks.
        return 0
    except Exception as error:
        print("lineage check unavailable (" + type(error).__name__ + ")", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
