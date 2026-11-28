#!/usr/bin/env python3
"""One fresh, metadata-only readiness/feasibility pilot; never release acceptance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TWIN = ROOT / "twin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from twin import start, smoke

PROJECT = start.PROJECT
STARTUP_LIMIT = 900
LOAD_MINIMUM = 600
SAMPLE_INTERVAL = 30
LOAD_USERS = 5
LOAD_PROGRESS_WINDOW = 2 * SAMPLE_INTERVAL
GIB = 1024 ** 3
DISK_STOP_BYTES = GIB
MEMORY_STOP_BYTES = 256 * 1024 ** 2
VFS_MIN_BYTES = 50 * GIB
EXPECTED = frozenset({
    "accounting", "ad", "astronomy-db", "cart", "checkout", "currency", "email", "flagd", "flagd-ui",
    "fraud-detection", "frontend", "frontend-proxy", "image-provider", "kafka", "load-generator",
    "otel-collector", "payment", "product-catalog", "quote", "recommendation", "shipping", "telemetry-docs",
    "valkey-cart", "lineage-kafka", "lineage-neo4j", "lineage-postgres", "lineage-worker", "lineage-collector",
})
STATES = {"running", "exited", "created", "restarting", "paused", "dead", "removing"}
HEALTH = {"healthy", "unhealthy", "starting", ""}
DRIVERS = {"vfs", "overlay2", "overlayfs", "btrfs", "zfs", "fuse-overlayfs"}
PHASES = {"validate", "prepare", "preflight", "platform_start", "topic_setup", "full_start", "verify_readiness", "complete"}
STARTUP_FAILURES = {
    "deadline_exceeded", "demo_commit_mismatch", "invalid_collector_limits", "insufficient_vfs_capacity",
    "probe_unavailable", "worker_image_invalid", "service_set_mismatch", "services_not_healthy",
    "command_failed", "interrupted", "startup_unavailable", "report_unwritable", "state_unavailable",
    "invalid_timeout", "configuration_service_set_mismatch",
}
LOCUST_STATES = {"ready", "spawning", "running", "cleanup", "stopping", "stopped", "missing", "unknown"}
# Shape checked against locust==2.44.4: web.py request_stats appends the total
# StatsEntry; stats.py names that row Aggregated with method None (or "" after
# clear_all). No endpoint rows, errors, URLs or request values leave this child.
LOCUST_SCRIPT = """
import json, signal, urllib.request
signal.alarm(8)
result={'available':False}
try:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open('http://127.0.0.1:8089/stats/requests',timeout=5) as response:
        if response.status != 200:
            raise ValueError()
        encoded=response.read(1048577)
    if len(encoded)>1048576:
        raise ValueError()
    document=json.loads(encoded)
    rows=document['stats']
    if not isinstance(rows,list) or len(rows)>501:
        raise ValueError()
    aggregate=[row for row in rows if isinstance(row,dict) and row.get('name')=='Aggregated' and row.get('method') in (None,'')]
    if len(aggregate)!=1:
        raise ValueError()
    users,requests=document['user_count'],aggregate[0]['num_requests']
    if type(users) is not int or not 0<=users<=1000000 or type(requests) is not int or not 0<=requests<2**63:
        raise ValueError()
    state=document.get('state')
    if state not in ('ready','spawning','running','cleanup','stopping','stopped','missing'):
        state='unknown'
    result={'available':True,'state':state,'user_count':users,'num_requests':requests}
except Exception:
    pass
signal.alarm(0)
print(json.dumps(result,sort_keys=True))
"""
FLOW_FIELDS = ("accepted_receipts", "outbox_total", "outbox_sent", "graph_revisions", "graph_nodes", "graph_versions")
COLLECTOR_CATEGORIES = frozenset({
    "sending", "complete", "more_pending", "delivery_pending", "delivery_unavailable", "state_limit",
    "checkpoint_unavailable", "parse_unavailable", "parse_timeout", "metadata_limit", "source_changed",
    "input_limit", "line_limit", "input_invalid", "change_type_rejected", "input_missing", "event_limit",
    "static_protocol_rejected", "invalid_configuration", "not_started", "stale", "state_unavailable",
})
FLOW_SCRIPT = """
import json, os, sqlite3
from neo4j import GraphDatabase, Query
with sqlite3.connect('file:/archive/index.sqlite3?mode=ro', uri=True, timeout=5) as db:
    result={'accepted_receipts':db.execute('SELECT count(*) FROM receipts WHERE accepted=1').fetchone()[0],
            'outbox_total':db.execute('SELECT count(*) FROM outbox').fetchone()[0],
            'outbox_sent':db.execute('SELECT count(*) FROM outbox WHERE sent=1').fetchone()[0]}
driver=GraphDatabase.driver('bolt://lineage-neo4j:7687',
    auth=(os.environ.get('LINEAGE_DB_USER','neo4j'),os.environ.get('LINEAGE_DB_PASSWORD','lineage-local-only')),
    connection_timeout=5, max_connection_pool_size=1)
try:
    with driver.session() as session:
        for key,query in (
            ('graph_revisions','MATCH (n:LineageRevision {namespace: $namespace}) RETURN count(n) AS count'),
            ('graph_nodes','MATCH (n:LineageNode {namespace: $namespace}) RETURN count(n) AS count'),
            ('graph_versions','MATCH (n:LineageNode {namespace: $namespace})-[r:LINEAGE_VERSION]->() RETURN count(r) AS count')):
            result[key]=session.run(Query(query,timeout=5),namespace='lineage-runtime').single()['count']
finally:
    driver.close()
print(json.dumps(result,sort_keys=True))
"""


class PilotFailure(Exception):
    def __init__(self, category):
        self.category = category


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    @staticmethod
    def utc():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pilot-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Commands:
    """Raw subprocess streams stay exclusively inside the ignored state tree."""
    def __init__(self, state):
        self.folder = state / "pilot-logs" / uuid.uuid4().hex
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.count = 0

    def __call__(self, args, *, timeout=30, capture=True):
        self.count += 1
        paths = [self.folder / f"{self.count:04d}.{suffix}" for suffix in ("stdout", "stderr")]
        descriptors = [os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600) for path in paths]
        with os.fdopen(descriptors[0], "wb") as stdout, os.fdopen(descriptors[1], "wb") as stderr:
            process = subprocess.Popen(args, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
        result = ""
        if capture:
            with paths[0].open("rb") as stream:
                encoded = stream.read(1024 * 1024 + 1)
            if len(encoded) > 1024 * 1024:
                raise PilotFailure("probe_output_limit")
            result = encoded.decode("utf-8", errors="strict")
        return subprocess.CompletedProcess(args, code, result, "")


def checked(run, args, *, timeout=30):
    result = run(args, timeout=timeout)
    if result.returncode:
        raise PilotFailure("probe_failed")
    return result.stdout.strip()


def integer(value, *, maximum=2 ** 63 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError()
    return value


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError()
    return value


def memory_info():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        name, _, rest = line.partition(":")
        if name in {"MemTotal", "MemAvailable"}:
            values[name] = int(rest.split()[0]) * 1024
    return {"total_bytes": integer(values["MemTotal"]), "available_bytes": integer(values["MemAvailable"])}


def docker_disk(root: Path, run):
    """Measure DockerRootDir itself; never substitute the checkout filesystem."""
    try:
        info = os.statvfs(root)
        return {"free_bytes": info.f_bavail * info.f_frsize, "total_bytes": info.f_blocks * info.f_frsize,
                "method": "statvfs"}
    except PermissionError:
        result = checked(run, ["sudo", "-n", "stat", "-f", "--format=%S:%a:%b", "--", str(root)], timeout=10)
        if not re.fullmatch(r"[0-9]+:[0-9]+:[0-9]+", result):
            raise PilotFailure("docker_root_unavailable")
        size, available, total = map(int, result.split(":"))
        return {"free_bytes": size * available, "total_bytes": size * total, "method": "sudo_stat_read_only"}


def resource_summary(memory, disk):
    memory = {key: integer(memory[key]) for key in ("total_bytes", "available_bytes")}
    disk = {**{key: integer(disk[key]) for key in ("total_bytes", "free_bytes")},
            "method": disk["method"] if disk["method"] in {"statvfs", "sudo_stat_read_only"} else "unknown"}
    if not memory["total_bytes"] or not disk["total_bytes"] or memory["available_bytes"] > memory["total_bytes"] or disk["free_bytes"] > disk["total_bytes"]:
        raise ValueError()
    return memory, disk


def compose(state):
    return ["docker", "compose", "--project-name", PROJECT, "-f", str(state / "compose.yaml")]


def service_health(run, state):
    encoded = checked(run, compose(state) + ["ps", "--all", "--format", "json"], timeout=20)
    rows = json.loads(encoded) if encoded.startswith("[") else [json.loads(line) for line in encoded.splitlines()]
    return sanitize_services(rows, docker=True)


def sanitize_services(rows, *, docker=False):
    if not isinstance(rows, list) or len(rows) > 256:
        raise ValueError()
    result, unknown = [], 0
    for row in rows:
        name = row.get("Service" if docker else "service")
        if name not in EXPECTED:
            unknown += 1
            continue
        state = row.get("State" if docker else "state")
        health = row.get("Health" if docker else "health", "")
        result.append({"service": name, "state": state if state in STATES else "unknown",
                       "health": health if health in HEALTH else "unknown"})
    names = [row["service"] for row in result]
    exact = sorted(names) == sorted(EXPECTED) and unknown == 0
    return {"services": sorted(result, key=lambda row: row["service"]), "unexpected_count": unknown,
            "exact_service_set": exact, "all_healthy": exact and all(row["state"] == "running" and row["health"] == "healthy" for row in result)}


def read_json(path, limit=1024 * 1024):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError()
    return json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))


def collector_capacity_summary(value):
    keys = {"name", "scope", "limits", "container_memory_bytes", "parent_headroom_bytes"}
    if (type(value) is not dict or set(value) != keys
            or value["name"] != start.REFERENCE_COLLECTOR_PROFILE or value["scope"] != "ten-minute-reference-twin"
            or type(value["limits"]) is not dict or set(value["limits"]) != set(start.REFERENCE_COLLECTOR_LIMITS)):
        raise ValueError()
    limits = {}
    for key, ceiling in start.REFERENCE_COLLECTOR_LIMITS.items():
        limit = value["limits"][key]
        limit = integer(limit, maximum=ceiling) if type(ceiling) is int else finite(limit)
        if not 0 < limit <= ceiling:
            raise ValueError()
        limits[key] = limit
    memory = integer(value["container_memory_bytes"])
    headroom = integer(value["parent_headroom_bytes"])
    if (memory != start.REFERENCE_COLLECTOR_MEMORY_BYTES or headroom != start.REFERENCE_COLLECTOR_PARENT_HEADROOM_BYTES
            or limits["max_line_bytes"] > limits["max_input_bytes"]
            or limits["max_memory_bytes"] <= limits["max_input_bytes"] + limits["max_metadata_bytes"]
            or limits["max_memory_bytes"] + headroom > memory):
        raise ValueError()
    return {"name": start.REFERENCE_COLLECTOR_PROFILE, "scope": "ten-minute-reference-twin", "limits": limits,
            "container_memory_bytes": memory, "parent_headroom_bytes": headroom}


def startup_report(path):
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("demoCommit") != start.DEMO_COMMIT or raw.get("scope") != "full-demo":
        raise ValueError()
    if raw.get("status") not in {"starting", "failed", "passed"} or raw.get("phase") not in PHASES:
        raise ValueError()
    report = {"demoCommit": start.DEMO_COMMIT, "scope": "full-demo", "status": raw["status"], "phase": raw["phase"],
              "elapsedSeconds": finite(raw["elapsedSeconds"]),
              "timeoutSeconds": None if raw.get("timeoutSeconds") is None and raw.get("status") == "failed" and raw.get("category") == "invalid_timeout" else integer(raw["timeoutSeconds"]),
              "expectedServices": integer(raw["expectedServices"], maximum=256)}
    names = raw.get("expectedServiceNames", [])
    if not isinstance(names, list) or any(name not in EXPECTED for name in names) or len(names) != len(set(names)):
        raise ValueError()
    report["expectedServiceNames"] = sorted(names)
    services = sanitize_services(raw.get("services", []))
    if raw["status"] == "passed" and not services["all_healthy"]:
        raise ValueError()
    report["services"] = services["services"]
    for key in ("allRunning", "allContainersHealthy", "exactServiceSet"):
        if key in raw:
            if type(raw[key]) is not bool:
                raise ValueError()
            report[key] = raw[key]
    if "category" in raw:
        report["category"] = raw["category"] if raw["category"] in STARTUP_FAILURES else "startup_unavailable"
    if "storageDriver" in raw:
        report["storageDriver"] = raw["storageDriver"] if raw["storageDriver"] in DRIVERS else "other"
    for key, pattern in (("probeSha256", r"[0-9a-f]{64}"), ("workerImageId", r"sha256:[0-9a-f]{64}")):
        if key in raw:
            if not isinstance(raw[key], str) or not re.fullmatch(pattern, raw[key]):
                raise ValueError()
            report[key] = raw[key]
    prerequisites = []
    for item in raw.get("oneShotPrerequisites", []):
        if item.get("service") != "lineage-topics" or item.get("status") not in {"running", "completed", "failed"}:
            raise ValueError()
        code = item.get("exitCode")
        if code is not None and (type(code) is not int or not -255 <= code <= 255):
            raise ValueError()
        prerequisites.append({"service": "lineage-topics", "status": item["status"], "exitCode": code})
    report["oneShotPrerequisites"] = prerequisites
    if "collectorCapacityProfile" in raw:
        report["collectorCapacityProfile"] = collector_capacity_summary(raw["collectorCapacityProfile"])
    return report


def flow_proof(run, state):
    value = json.loads(checked(run, compose(state) + ["exec", "-T", "lineage-worker", "python", "-c", FLOW_SCRIPT], timeout=30))
    return {key: integer(value[key]) for key in FLOW_FIELDS}


def collector_health(state):
    """Read the last collector health only; never expose source guards or paths."""
    path = Path(state).absolute() / "collector/progress.sqlite"
    try:
        if path.is_symlink() or path.parent.is_symlink():
            return {"available": False, "reason": "invalid_state"}
        if not path.is_file():
            return {"available": False, "reason": "missing_state"}
        deadline = time.monotonic() + 0.5
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 4096)
            connection.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            row = connection.execute("SELECT value FROM health WHERE id=1 LIMIT 1").fetchone()
        finally:
            connection.close()
        if not row:
            return {"available": False, "reason": "missing_health"}
        if not isinstance(row[0], str) or len(row[0].encode("utf-8")) > 4096:
            return {"available": False, "reason": "invalid_record"}
        value = json.loads(row[0], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict) or value.get("status") not in {"ok", "error"} or value.get("category") not in COLLECTOR_CATEGORIES:
            raise ValueError()
        updated = finite(value["updated_at"])
        if updated > 253402300799:
            raise ValueError()
        result = {"available": True, "status": value["status"], "category": value["category"], "updated_at": updated}
        for key in ("sent", "pending", "input_bytes", "partial_lines"):
            if key in value:
                result[key] = integer(value[key])
        return result
    except sqlite3.DataError:
        return {"available": False, "reason": "record_too_large"}
    except (ValueError, TypeError, KeyError, UnicodeError):
        return {"available": False, "reason": "invalid_record"}
    except Exception:
        return {"available": False, "reason": "read_unavailable"}


def locust_proof(run, state):
    value = json.loads(checked(run, compose(state) + ["exec", "-T", "load-generator", "python", "-c", LOCUST_SCRIPT], timeout=10))
    if value.get("available") is not True or value.get("state") not in LOCUST_STATES:
        raise ValueError()
    return {"available": True, "state": value["state"], "user_count": integer(value["user_count"], maximum=1000000),
            "num_requests": integer(value["num_requests"])}


def raw_summary(value):
    result = {"raw_files": {}, "failure_categories": []}
    for name in smoke.RAW_FILES:
        row = value.get("raw_files", {}).get(name, {})
        clean = {}
        for key in ("present", "jsonl_validated", "processed"):
            if key in row and type(row[key]) is bool:
                clean[key] = row[key]
        for key in ("size_bytes", "complete_jsonl_lines", "max_complete_jsonl_line_bytes", "trailing_bytes"):
            if key in row:
                clean[key] = None if row[key] is None else integer(row[key])
        if "sha256" in row:
            digest = row["sha256"]
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ValueError()
            clean["sha256"] = digest
        result["raw_files"][name] = clean
    result["failure_categories"] = sorted({item for item in value.get("failure_categories", []) if item in smoke.FAILURES})
    return result


def smoke_summary(value):
    """Only counts, exact precision and fixed categories leave the raw-data host."""
    if value.get("status") not in {"pass", "blocked"}:
        raise ValueError()
    result = {"status": value["status"], "scope": "WP-03 service-edge smoke only", **raw_summary(value),
              "raw_capture_replayed": value.get("raw_capture_replayed") is True,
              "counts": {}, "diagnostics": {}, "precision": None, "structural_failure": None,
              "claims": {"full_wp03_accepted": False, "timings_measured": False, "holdout_measured": False}}
    detail = value.get("structural_failure")
    if (type(detail) is dict and set(detail) == {"filename", "line", "field_path", "category"}
            and all(type(detail[key]) is str for key in ("filename", "field_path", "category"))
            and detail["filename"] in smoke.RAW_FILES
            and detail["field_path"] in smoke.STRUCTURAL_PATHS
            and detail["category"] in smoke.STRUCTURAL_CATEGORIES
            and type(detail["line"]) is int and 0 < detail["line"] <= 2 ** 63 - 1):
        result["structural_failure"] = {key: detail[key] for key in ("filename", "line", "field_path", "category")}
    for key in ("data_edges", "control_edges", "collector_events", "redacted_endpoints"):
        count = value.get("counts", {}).get(key)
        result["counts"][key] = None if count is None else integer(count)
    for key, count in value.get("diagnostics", {}).items():
        if key in smoke.DIAGNOSTICS:
            result["diagnostics"][key] = integer(count)
    if value.get("precision") is not None:
        precision = value["precision"]
        if precision.get("bar") != 0.95:
            raise ValueError()
        result["precision"] = smoke.precision_check(integer(precision["hit"]), integer(precision["observed"]),
                                                     integer(precision["expected"]), "0.95")
    if result["status"] == "pass" and (not result["precision"] or not result["precision"]["holds"]
                                          or not result["raw_capture_replayed"] or result["failure_categories"]):
        raise ValueError()
    return result


def run_pilot(demo, state, output, *, worker_image="lineage-platform:pilot", run=None, clock=None,
              memory_probe=memory_info, disk_probe=docker_disk, score=smoke.score_capture, stats=smoke.capture_stats,
              invocation_id=None):
    clock = clock or Clock()
    output, state, demo = Path(output), Path(state), Path(demo)
    run_id = uuid.uuid4().hex if invocation_id is None else invocation_id
    valid_invocation = isinstance(run_id, str) and re.fullmatch(r"[0-9a-f]{32}", run_id) is not None
    report = {"schema_version": 1, "purpose": "readiness_feasibility_pilot", "status": "blocked", "failure_categories": [],
              "run_id": run_id if valid_invocation else None, "ownership": {"project": PROJECT, "acquired": False},
              "startup_scope": {"image_preparation_included": False, "probe_preparation_included": False,
                                "description": "One readiness trial using previously built images and probe"},
              "limits": {"startup_seconds": STARTUP_LIMIT, "minimum_load_seconds": LOAD_MINIMUM,
                         "sample_interval_seconds": SAMPLE_INTERVAL, "minimum_disk_free_bytes": DISK_STOP_BYTES,
                         "emergency_memory_available_bytes": MEMORY_STOP_BYTES,
                         "score_timeout_seconds": 180, "score_memory_limit_mb": 8192, "max_raw_bytes": 4 * GIB},
              "identities": {}, "resources": {"initial": None, "samples": []}, "startup": None,
              "load": {"samples": [], "all_healthy": False, "traffic": {"holds": False, "samples": [],
                       "policy": {"expected_users": LOAD_USERS, "sample_interval_seconds": SAMPLE_INTERVAL,
                                  "progress_window_seconds": LOAD_PROGRESS_WINDOW,
                                  "evidence": "aggregate_request_count_increase"}}},
              "run_window": None, "flow": {"holds": False},
              "shutdown": {"attempted": False, "stopped": False}, "capture": None, "smoke": None,
              "collector_health": {"available": False, "reason": "not_owned"},
              "claims": {"full_wp03_accepted": False, "three_cold_starts": False, "holdout_measured": False,
                         "full_in10_p95_measured": False, "g4_approved": False}}
    owned = False
    completed_window = False

    def fail(category):
        if category not in report["failure_categories"]:
            report["failure_categories"].append(category)
        report.setdefault("first_failure", category)
        report.setdefault("first_failure_at", clock.utc())

    def health():
        try:
            return service_health(run, state)
        except Exception:
            fail("health_probe_unavailable")
            return {"services": [], "exact_service_set": False, "all_healthy": False, "unexpected_count": 0}

    def traffic():
        try:
            value = locust_proof(run, state)
            if value["state"] != "running":
                fail("load_generator_inactive")
            if value["user_count"] != LOAD_USERS:
                fail("load_user_count_mismatch")
            return value
        except Exception:
            fail("load_generator_probe_unavailable")
            return {"available": False}

    try:
        output, state, demo = output.resolve(), state.resolve(), demo.resolve()
        if not valid_invocation:
            raise PilotFailure("invalid_invocation_id")
        if not state.is_relative_to((TWIN / ".state").resolve()) or output.is_relative_to(state):
            raise PilotFailure("unsafe_artifact_location")
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        run = run or Commands(state)
        write_json(output / "pilot.json", report)
        existing = checked(run, ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"])
        volumes = checked(run, ["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}"])
        if existing or volumes:
            raise PilotFailure("project_not_fresh")
        if any((state / name).exists() for name in ("startup.json", "compose.yaml", "capture", "flags", "collector", "changes.jsonl", "pilot-attempt.json")):
            raise PilotFailure("state_not_fresh")
        docker = json.loads(checked(run, ["docker", "info", "--format", '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}}}']))
        root = Path(docker["root"])
        if not root.is_absolute() or "\x00" in str(root):
            raise PilotFailure("docker_root_unavailable")
        driver = docker["driver"] if docker["driver"] in DRIVERS else "other"
        memory, disk = resource_summary(memory_probe(), disk_probe(root, run))
        initial = {"architecture": platform.machine() if platform.machine() in {"x86_64", "aarch64", "arm64"} else "other",
                   "cpu_count": integer(os.cpu_count() or 1), "memory": memory, "docker_storage_driver": driver,
                   "docker_root_disk": disk}
        report["resources"]["initial"] = initial
        if driver == "vfs" and disk["free_bytes"] < VFS_MIN_BYTES:
            raise PilotFailure("insufficient_vfs_capacity")
        if disk["free_bytes"] < DISK_STOP_BYTES or memory["available_bytes"] < MEMORY_STOP_BYTES:
            raise PilotFailure("host_resource_unsafe")
        source_commit = checked(run, ["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        demo_commit = checked(run, ["git", "-C", str(demo), "rev-parse", "HEAD"])
        image = checked(run, ["docker", "image", "inspect", worker_image, "--format", "{{.Id}}"])
        if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or demo_commit != start.DEMO_COMMIT or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise PilotFailure("identity_unavailable")
        probe = state / "bin/lineage-healthcheck"
        if not probe.is_file() or not os.access(probe, os.R_OK | os.X_OK):
            raise PilotFailure("probe_unavailable")
        report["identities"] = {"source_commit": source_commit, "demo_commit": demo_commit, "worker_image_id": image,
                                "probe_sha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
                                "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                                  for name in ("twin/pilot.py", "twin/start.py", "twin/smoke.py", "twin/images.lock.json", "twin/probe-toolchain.json", "twin/collector.compose.yaml")}}
        write_json(state / "pilot-attempt.json", {"schema_version": 1, "project": PROJECT, "run_id": report["run_id"],
                                                  "fresh_project_acquired": True})
        report["ownership"]["acquired"] = True
        owned = True
        # Persist the token-bound ownership before a long subprocess can be
        # interrupted, so the workflow's finally block has current evidence.
        write_json(output / "pilot.json", report)
        began = clock.monotonic()
        starter_code = None
        try:
            result = run([sys.executable, str(TWIN / "start.py"), "up", "--demo", str(demo), "--state", str(state),
                          "--timeout", str(STARTUP_LIMIT), "--worker-image", worker_image], timeout=STARTUP_LIMIT, capture=False)
            starter_code = result.returncode
        except subprocess.TimeoutExpired:
            fail("startup_deadline_exceeded")
        except Exception:
            fail("starter_unavailable")
        elapsed = clock.monotonic() - began
        report["startup_observed_seconds"] = round(elapsed, 6)
        try:
            startup = startup_report(state / "startup.json")
            report["startup"] = startup
            write_json(output / "startup.json", startup)
        except Exception:
            fail("startup_report_invalid")
            startup = None
        observed = health()
        report["startup_observation"] = observed
        if elapsed > STARTUP_LIMIT or (startup and (startup["elapsedSeconds"] > STARTUP_LIMIT or startup["timeoutSeconds"] != STARTUP_LIMIT)):
            fail("startup_deadline_exceeded")
        if (starter_code != 0 or not startup or startup["status"] != "passed" or not startup.get("allContainersHealthy")
                or not startup.get("allRunning") or not startup.get("exactServiceSet") or startup["expectedServiceNames"] != sorted(EXPECTED)
                or startup["expectedServices"] != len(EXPECTED) or not observed["all_healthy"]
                or startup.get("workerImageId") != image or startup.get("probeSha256") != report["identities"]["probe_sha256"]
                or startup.get("oneShotPrerequisites") != [{"service": "lineage-topics", "status": "completed", "exitCode": 0}]):
            fail("startup_not_ready")
        if report["failure_categories"]:
            raise PilotFailure(report["failure_categories"][0])
        try:
            report["flow"]["baseline"] = flow_proof(run, state)
        except Exception:
            fail("flow_probe_unavailable")
        baseline_traffic = traffic()
        report["load"]["traffic"]["baseline"] = baseline_traffic
        load_started, load_at = clock.monotonic(), clock.utc()
        next_sample = load_started
        all_healthy = True
        all_active = baseline_traffic.get("state") == "running" and baseline_traffic.get("user_count") == LOAD_USERS
        previous_requests = baseline_traffic.get("num_requests")
        counters_monotonic = True
        last_progress_at = max_no_progress_interval = 0.0
        progress_proven = True
        try:
            while True:
                elapsed = clock.monotonic() - load_started
                observed = health()
                all_healthy = all_healthy and observed["all_healthy"]
                report["load"]["samples"].append({"elapsed_seconds": round(elapsed, 6), **observed})
                if not observed["all_healthy"]:
                    fail("load_services_not_healthy")
                current_traffic = traffic()
                sample_at = clock.monotonic() - load_started
                report["load"]["traffic"]["samples"].append({"elapsed_seconds": sample_at, **current_traffic})
                all_active = all_active and current_traffic.get("state") == "running" and current_traffic.get("user_count") == LOAD_USERS
                current_requests = current_traffic.get("num_requests")
                progressed = current_requests is not None and previous_requests is not None and current_requests > previous_requests
                interval = sample_at - last_progress_at
                max_no_progress_interval = max(max_no_progress_interval, interval)
                # A flat completion count may mean requests are still in flight.
                # Withhold the activity claim when this observation is too old;
                # later progress cannot repair an earlier unproven interval.
                if interval > LOAD_PROGRESS_WINDOW or (interval >= LOAD_PROGRESS_WINDOW and not progressed):
                    progress_proven = False
                    fail("load_progress_unproven")
                if progressed:
                    last_progress_at = sample_at
                if current_requests is not None:
                    if previous_requests is not None and current_requests < previous_requests:
                        counters_monotonic = False
                        fail("load_request_counter_reset")
                    previous_requests = current_requests
                try:
                    memory, disk = resource_summary(memory_probe(), disk_probe(root, run))
                    report["resources"]["samples"].append({"elapsed_seconds": round(elapsed, 6), "memory": memory, "docker_root_disk": disk})
                    if disk["free_bytes"] < DISK_STOP_BYTES or memory["available_bytes"] < MEMORY_STOP_BYTES:
                        fail("host_resource_unsafe")
                        break
                except Exception:
                    fail("resource_probe_unavailable")
                if clock.monotonic() - load_started >= LOAD_MINIMUM:
                    completed_window = True
                    break
                next_sample += SAMPLE_INTERVAL
                clock.sleep(max(0.0, min(next_sample, load_started + LOAD_MINIMUM) - clock.monotonic()))
        finally:
            report["run_window"] = {"started_at": load_at, "ended_at": clock.utc(), "duration_seconds": clock.monotonic() - load_started}
            report["load"]["all_healthy"] = all_healthy
            tail = report["run_window"]["duration_seconds"] - last_progress_at
            max_no_progress_interval = max(max_no_progress_interval, tail)
            progress_proven = progress_proven and tail < LOAD_PROGRESS_WINDOW
            initial_requests = baseline_traffic.get("num_requests")
            increased = initial_requests is not None and previous_requests is not None and previous_requests > initial_requests
            progress_proven = progress_proven and increased
            report["load"]["traffic"].update(all_active=all_active, counters_monotonic=counters_monotonic,
                                                  request_count_increased=increased,
                                                  request_count_delta=previous_requests - initial_requests if initial_requests is not None and previous_requests is not None else None,
                                                  max_no_progress_interval_seconds=max_no_progress_interval,
                                                  progress_proven=progress_proven,
                                                  holds=completed_window and all_active and counters_monotonic and progress_proven)
            if not progress_proven:
                fail("load_progress_unproven")
        try:
            final = report["flow"]["final"] = flow_proof(run, state)
            baseline = report["flow"].get("baseline", {})
            holds = all(key in baseline and final[key] >= baseline[key] and final[key] > 0 for key in FLOW_FIELDS)
            holds = holds and final["accepted_receipts"] > baseline.get("accepted_receipts", final["accepted_receipts"])
            report["flow"]["holds"] = holds and all_healthy
            if not report["flow"]["holds"]:
                fail("forwarding_proof_failed")
        except Exception:
            fail("flow_probe_unavailable")
    except PilotFailure as error:
        fail(error.category)
    except KeyboardInterrupt:
        fail("interrupted")
    except Exception:
        fail("pilot_unavailable")
    finally:
        if owned:
            report["shutdown"]["attempted"] = True
            try:
                identifiers = checked(run, ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"]).split()
                if any(not re.fullmatch(r"[0-9a-f]{12,64}", identifier) for identifier in identifiers):
                    raise ValueError()
                if identifiers:
                    checked(run, ["docker", "stop", "--time", "30", *identifiers], timeout=45)
                running = checked(run, ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}"])
                if running:
                    raise ValueError()
                report["shutdown"]["stopped"] = True
            except Exception:
                fail("shutdown_failed")
            report["collector_health"] = collector_health(state) if report["shutdown"]["stopped"] else {
                "available": False, "reason": "shutdown_incomplete"}
        try:
            report["capture"] = raw_summary(stats(state / "capture", max_capture_bytes=4 * GIB, max_line_bytes=128 * 1024 ** 2))
        except Exception:
            fail("capture_stats_unavailable")
        if owned and report["shutdown"]["stopped"] and completed_window:
            try:
                report["smoke"] = smoke_summary(score(state / "capture", report["run_window"], timeout_seconds=180,
                                                       memory_limit_mb=8192, max_capture_bytes=4 * GIB, max_line_bytes=128 * 1024 ** 2))
                write_json(output / "smoke.json", report["smoke"])
                if report["smoke"]["status"] != "pass":
                    fail("smoke_failed")
            except Exception:
                fail("smoke_unavailable")
        if not completed_window and owned and report["startup"] and report["startup"]["status"] == "passed":
            fail("load_window_incomplete")
        report["status"] = "passed" if not report["failure_categories"] and completed_window and report["load"]["traffic"]["holds"] and report["flow"]["holds"] and report["smoke"] and report["smoke"]["status"] == "pass" else "blocked"
        try:
            write_json(output / "pilot.json", report)
        except Exception:
            report["status"] = "blocked"
            fail("report_unwritable")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=TWIN / ".state")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-image", default="lineage-platform:pilot")
    parser.add_argument("--invocation-id", help="Fresh workflow cleanup token, exactly 32 lowercase hexadecimal characters")
    args = parser.parse_args(argv)
    report = run_pilot(args.demo, args.state, args.output, worker_image=args.worker_image, invocation_id=args.invocation_id)
    print(json.dumps({"purpose": report["purpose"], "status": report["status"], "failure_categories": report["failure_categories"]}, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
