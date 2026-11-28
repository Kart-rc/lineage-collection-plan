#!/usr/bin/env python3
"""Render and run an isolated, pinned OpenTelemetry demo and lineage platform."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
TWIN = ROOT / "twin"
DEMO_COMMIT = "dedc0178918e260823323b8d95005a8cb924b007"
PROJECT = "lineage-twin"
PLATFORM_SERVICES = ["lineage-kafka", "lineage-neo4j", "lineage-postgres"]
FULL_SERVICES = (
    "accounting", "ad", "astronomy-db", "cart", "checkout", "currency", "email", "flagd", "flagd-ui",
    "fraud-detection", "frontend", "frontend-proxy", "image-provider", "kafka", "load-generator",
    "otel-collector", "payment", "product-catalog", "quote", "recommendation", "shipping", "telemetry-docs", "valkey-cart",
    "lineage-kafka", "lineage-neo4j", "lineage-postgres", "lineage-worker", "lineage-collector",
)


def valid_timeout(value, *, platform=False):
    try:
        return type(value) in (int, float) and value > 0 and math.isfinite(value) and (platform or value <= 900)
    except OverflowError:
        return False


def validate_full_services(config):
    if set(config["services"]) != set(FULL_SERVICES) | {"lineage-topics"}:
        raise StartupFailure("configuration_service_set_mismatch")


class StartupFailure(Exception):
    def __init__(self, category):
        super().__init__(category)
        self.category = category


class Deadline:
    def __init__(self, seconds):
        self.started = time.monotonic()
        self.ends = self.started + seconds

    def remaining(self):
        remaining = self.ends - time.monotonic()
        if remaining <= 0:
            raise StartupFailure("deadline_exceeded")
        return remaining

    def elapsed(self):
        return time.monotonic() - self.started


def command(args, *, deadline=None, **kwargs):
    # Subprocess diagnostics can contain capture or configuration values. Keep
    # them transient; startup reports only controlled failure categories.
    kwargs.setdefault("capture_output", True)
    if deadline is not None:
        kwargs["timeout"] = deadline.remaining()
    return subprocess.run(args, check=True, text=True, **kwargs)


def compose_args(state: Path):
    return ["docker", "compose", "--project-name", PROJECT, "-f", str(state / "compose.yaml")]


def add_readiness(config, state):
    config["services"]["cart"]["healthcheck"] = {
        "test": ["CMD", "/bin/grpc_health_probe", "-addr=:7070"],
        "interval": "5s", "timeout": "6s", "start_period": "10s", "retries": 180,
    }
    probes = {
        "flagd": ["http", "--url", "http://127.0.0.1:8014/readyz"],
        "otel-collector": ["http", "--url", "http://127.0.0.1:13133/"],
        "accounting": ["kafka", "--broker", "kafka:9092", "--group", "accounting", "--topic", "orders"],
        "fraud-detection": ["kafka", "--broker", "kafka:9092", "--group", "fraud-detection", "--topic", "orders"],
    }
    for name, args in probes.items():
        service = config["services"][name]
        service["volumes"].append({"type": "bind", "source": str(state / "bin/lineage-healthcheck"),
                                   "target": "/lineage-healthcheck", "read_only": True,
                                   "bind": {"create_host_path": False}})
        service["healthcheck"] = {"test": ["CMD", "/lineage-healthcheck", *args],
                                  "interval": "5s", "timeout": "6s", "start_period": "10s", "retries": 180}


def private_file(path):
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    path.chmod(0o600)


def add_pipeline(config, state, worker_image):
    worker = yaml.safe_load((TWIN / "worker.compose.yaml").read_text())
    collector = yaml.safe_load((TWIN / "collector.compose.yaml").read_text())
    config["services"].update(worker["services"])
    config["services"].update(collector["services"])
    config["volumes"].update(worker.get("volumes", {}))
    config["services"]["lineage-topics"]["profiles"] = ["lineage-setup"]
    for name in ("lineage-worker", "lineage-collector"):
        service = config["services"][name]
        service.pop("build", None)
        service.pop("profiles", None)
        service["image"] = worker_image
        service["pull_policy"] = "never"
        service["depends_on"].pop("lineage-topics", None)
    bridge = config["services"]["lineage-collector"]
    bridge["user"] = f"{os.getuid()}:{os.getgid()}"
    for volume, source in zip(bridge["volumes"], (state / "capture", state / "changes.jsonl", state / "collector")):
        volume["source"] = str(source)
    for index, argument in enumerate(bridge["command"]):
        match = re.fullmatch(r"\$\{(LINEAGE_COLLECTOR_MAX_(?:INPUT_BYTES|EVENTS)):-([0-9]+)\}", argument)
        if match:
            value = os.environ.get(match[1], match[2])
            if not value.isdecimal() or int(value) < 1:
                raise StartupFailure("invalid_collector_limits")
            bridge["command"][index] = value
    (state / "collector").mkdir(exist_ok=True, mode=0o700)
    for name in ("traces.jsonl", "logs.jsonl", "metrics.jsonl"):
        private_file(state / "capture" / name)
    private_file(state / "changes.jsonl")


def prepare(demo: Path, state: Path, *, deadline=None, full=False, worker_image="lineage-platform:local"):
    commit = command(["git", "-C", str(demo), "rev-parse", "HEAD"], deadline=deadline).stdout.strip()
    if commit != DEMO_COMMIT:
        raise StartupFailure("demo_commit_mismatch")
    for directory in ("capture", "flags", "sandbox"):
        (state / directory).mkdir(parents=True, exist_ok=True)
    (state / "capture").chmod(0o700)
    if not (state / "flags/demo.flagd.json").exists():
        shutil.copytree(demo / "src/flagd", state / "flags", dirs_exist_ok=True)
    (state / "flags").chmod(0o755)
    for path in (state / "flags").rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    command(["sh", str(ROOT / "fixtures/otel-demo-3.1.0/run/sandbox.sh"), str(demo), str(state / "sandbox")], deadline=deadline)
    env = dict(os.environ, DEMO_VERSION="3.1.0", IPV6_ENABLED="false", LOCUST_BROWSER_USER_WEIGHT="0",
               LOCUST_HTTP_USER_WEIGHT="1", LOCUST_USERS="5", LOCUST_AUTOSTART="true", LOCUST_HEADLESS="false")
    rendered = command(["docker", "compose", "--project-name", PROJECT, "-f", str(demo / "compose.yaml"),
                        "-f", str(demo / "compose.full.yaml"), "config", "--format", "json"],
                       env=env, deadline=deadline)
    config = json.loads(rendered.stdout)
    config["name"] = PROJECT
    config["networks"] = {"demo": {"enable_ipv6": False}, "lineage": {"enable_ipv6": False}}
    config.pop("volumes", None)
    for name, service in config["services"].items():
        service.pop("build", None)
        service.pop("container_name", None)
        service.pop("ports", None)
        service["networks"] = ["demo"]
        service["logging"] = {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}}
        # No host filesystem or Docker socket reaches the demo collector.
        service["volumes"] = [v for v in service.get("volumes", [])
                              if v.get("target") not in ("/hostfs", "/var/run/docker.sock")]
    ports = {"frontend-proxy": (18080, 8080), "flagd-ui": (14000, 4000),
             "load-generator": (18089, 8089), "flagd": (18016, 8016)}
    for name, (host, target) in ports.items():
        config["services"][name]["ports"] = [f"127.0.0.1:{host}:{target}"]
    for name, target in (("flagd", "/etc/flagd"), ("flagd-ui", "/app/data")):
        config["services"][name]["volumes"] = [{"type": "bind", "source": str(state / "flags"), "target": target}]
    for name in ("image-provider", "telemetry-docs"):
        config["services"][name]["volumes"].append({"type": "bind", "source": str(state / f"sandbox/{name}.nginx.conf.template"),
                                                      "target": "/nginx.conf.template", "read_only": True})
    ui = config["services"]["flagd-ui"]
    ui["command"] = ["/app/bin/server"]
    ui["volumes"].append({"type": "bind", "source": str(state / "sandbox/flagd-ui.runtime.exs"),
                          "target": "/app/releases/0.1.1/runtime.exs", "read_only": True})
    collector = yaml.safe_load((demo / "src/otel-collector/otelcol-config.yml").read_text())
    collector["receivers"].pop("docker_stats", None)
    collector["receivers"].pop("host_metrics", None)
    collector["processors"]["resource_detection"]["detectors"] = ["env", "system"]
    collector["service"]["pipelines"]["metrics"]["receivers"] = [r for r in collector["service"]["pipelines"]["metrics"]["receivers"]
                                                                        if r not in ("docker_stats", "host_metrics")]
    collector.setdefault("extensions", {})["health_check"] = {"endpoint": "127.0.0.1:13133"}
    extensions = collector["service"].setdefault("extensions", [])
    if "health_check" not in extensions:
        extensions.append("health_check")
    (state / "otelcol-base.yaml").write_text(yaml.safe_dump(collector, sort_keys=False))
    addon = yaml.safe_load((ROOT / "fixtures/otel-demo-3.1.0/run/otelcol-capture.yml").read_text())
    # Synthetic-only OTLP capture is retained locally; debug never prints the raw records.
    for pipeline in addon["service"]["pipelines"].values():
        pipeline["exporters"] = [e for e in pipeline["exporters"] if e != "debug"]
    addon["service"]["telemetry"] = {"logs": {"level": "error"}}
    (state / "otelcol-capture.yaml").write_text(yaml.safe_dump(addon, sort_keys=False))
    for path in (state / "sandbox").iterdir():
        path.chmod(0o644)
    otel = config["services"]["otel-collector"]
    otel["volumes"] = [v for v in otel["volumes"] if v["target"] not in ("/etc/otelcol-config.yml", "/etc/otelcol-config-extras.yml")]
    otel["volumes"] += [
        {"type": "bind", "source": str(state / "otelcol-base.yaml"), "target": "/etc/otelcol-config.yml", "read_only": True},
        {"type": "bind", "source": str(state / "otelcol-capture.yaml"), "target": "/etc/otelcol-config-extras.yml", "read_only": True},
        {"type": "bind", "source": str(state / "capture"), "target": "/capture"},
    ]
    platform = yaml.safe_load((TWIN / "compose.yaml").read_text())
    shutil.copyfile(TWIN / "postgres-init.sql", state / "postgres-init.sql")
    (state / "postgres-init.sql").chmod(0o644)
    platform["services"]["lineage-postgres"]["volumes"][1] = f"{state / 'postgres-init.sql'}:/docker-entrypoint-initdb.d/lineage.sql:ro"
    config["services"].update(platform["services"])
    config["volumes"] = platform["volumes"]
    add_readiness(config, state)
    if full:
        add_pipeline(config, state, worker_image)
        validate_full_services(config)
    lock_path = TWIN / "images.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        for service in config["services"].values():
            service["image"] = lock.get(service["image"], service["image"])
    (state / "compose.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    return config


def status(state, *, deadline=None, services=None):
    output = command(compose_args(state) + ["ps", "--all", "--format", "json"] + (services or []), deadline=deadline).stdout.strip()
    rows = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines()]
    return [{"service": row["Service"], "state": row["State"], "health": row.get("Health", "")}
            for row in rows]


def readiness(rows, expected):
    names = [row["service"] for row in rows]
    exact = sorted(names) == sorted(expected)
    return exact, exact and all(row["state"] == "running" for row in rows), exact and all(
        row["state"] == "running" and row["health"] == "healthy" for row in rows)


def write_report(state, result):
    temporary = state / "startup.json.pending"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(state / "startup.json")


def startup(demo, state, *, platform=False, timeout=900, worker_image="lineage-platform:local"):
    accepted_timeout = valid_timeout(timeout, platform=platform)
    deadline = Deadline(timeout if accepted_timeout else 900)
    expected = PLATFORM_SERVICES if platform else sorted(FULL_SERVICES)
    result = {"demoCommit": DEMO_COMMIT, "scope": "platform" if platform else "full-demo",
              "status": "starting", "phase": "validate", "timeoutSeconds": timeout if accepted_timeout else None,
              "elapsedSeconds": 0, "expectedServices": len(expected), "expectedServiceNames": expected, "services": [],
              "exactServiceSet": False, "allRunning": False, "allContainersHealthy": False, "oneShotPrerequisites": []}
    exit_code = 1
    try:
        write_report(state, result)
        if not accepted_timeout:
            raise StartupFailure("invalid_timeout")
        result["phase"] = "prepare"
        config = prepare(Path(demo).resolve(), state, deadline=deadline, full=not platform, worker_image=worker_image)
        if not platform:
            validate_full_services(config)
        result["phase"] = "preflight"
        driver = command(["docker", "info", "--format", "{{.Driver}}"], deadline=deadline).stdout.strip()
        result["storageDriver"] = driver if driver in {"vfs", "overlay2", "overlayfs", "btrfs", "zfs", "fuse-overlayfs"} else "other"
        if not platform:
            if driver == "vfs" and shutil.disk_usage(state).free < 50 * 1024**3:
                raise StartupFailure("insufficient_vfs_capacity")
            probe = state / "bin/lineage-healthcheck"
            if not probe.is_file() or not os.access(probe, os.R_OK | os.X_OK):
                raise StartupFailure("probe_unavailable")
            result["probeSha256"] = hashlib.sha256(probe.read_bytes()).hexdigest()
            image = command(["docker", "image", "inspect", worker_image, "--format", "{{.Id}}"], deadline=deadline).stdout.strip()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                raise StartupFailure("worker_image_invalid")
            result["workerImageId"] = image
            for name in ("lineage-worker", "lineage-collector"):
                config["services"][name]["image"] = image
            (state / "compose.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        result["phase"] = "platform_start"
        command(compose_args(state) + ["up", "--detach", "--no-build", "--wait", "--wait-timeout",
                                      str(max(1, math.ceil(deadline.remaining()))), *PLATFORM_SERVICES], deadline=deadline)
        if not platform:
            result["phase"] = "topic_setup"
            prerequisite = {"service": "lineage-topics", "status": "running", "exitCode": None}
            result["oneShotPrerequisites"].append(prerequisite)
            setup = command(compose_args(state) + ["--profile", "lineage-setup", "run", "--rm", "--no-deps", "lineage-topics"], deadline=deadline)
            prerequisite.update(status="completed", exitCode=setup.returncode)
            result["phase"] = "full_start"
            command(compose_args(state) + ["up", "--detach", "--no-build", "--wait", "--wait-timeout",
                                          str(max(1, math.ceil(deadline.remaining())))], deadline=deadline)
        result["phase"] = "verify_readiness"
        rows = status(state, deadline=deadline, services=PLATFORM_SERVICES if platform else None)
        exact, running, healthy = readiness(rows, expected)
        result.update(exactServiceSet=exact, allRunning=running, allContainersHealthy=healthy)
        result["services"] = [{"service": row["service"],
                               "state": row["state"] if row["state"] in {"running", "exited", "created", "restarting", "paused", "dead"} else "unknown",
                               "health": row["health"] if row["health"] in {"healthy", "unhealthy", "starting", ""} else "unknown"}
                              for row in rows if row["service"] in expected]
        result["unexpectedServiceCount"] = sum(row["service"] not in expected for row in rows)
        deadline.remaining()
        if not exact:
            raise StartupFailure("service_set_mismatch")
        if not healthy:
            raise StartupFailure("services_not_healthy")
        result.update(status="passed", phase="complete")
        exit_code = 0
    except StartupFailure as error:
        result.update(status="failed", category=error.category)
    except subprocess.TimeoutExpired:
        result.update(status="failed", category="deadline_exceeded")
    except subprocess.CalledProcessError as error:
        if result["phase"] == "topic_setup" and result["oneShotPrerequisites"]:
            result["oneShotPrerequisites"][-1].update(status="failed", exitCode=error.returncode)
        result.update(status="failed", category="command_failed")
    except KeyboardInterrupt:
        result.update(status="failed", category="interrupted")
        exit_code = 130
    except Exception:
        result.update(status="failed", category="startup_unavailable")
    if result["status"] == "failed":
        for prerequisite in result["oneShotPrerequisites"]:
            if prerequisite["status"] == "running":
                prerequisite["status"] = "failed"
    result["elapsedSeconds"] = round(deadline.elapsed(), 6)
    try:
        write_report(state, result)
    except Exception:
        result.update(status="failed", category="report_unwritable")
        exit_code = 1
    print(json.dumps(result, indent=2))
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "platform", "prepare", "status", "down"), nargs="?", default="up")
    parser.add_argument("--demo", type=Path, default=Path("/tmp/lineage-reference-otel-demo"))
    parser.add_argument("--state", type=Path, default=TWIN / ".state")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--worker-image", default="lineage-platform:local")
    args = parser.parse_args(argv)
    if not valid_timeout(args.timeout, platform=args.action != "up"):
        parser.error("timeout must be positive and finite; full startup allows at most 900 seconds")
    state = args.state.resolve()
    if not state.is_relative_to(TWIN / ".state"):
        parser.error("state must be inside ignored twin/.state to protect synthetic capture")
    try:
        state.mkdir(parents=True, exist_ok=True)
    except Exception:
        print('{"status":"failed","category":"state_unavailable"}')
        return 1
    if args.action in {"up", "platform"}:
        return startup(args.demo, state, platform=args.action == "platform", timeout=args.timeout,
                       worker_image=args.worker_image)
    try:
        if args.action == "down":
            command(compose_args(state) + ["down"])
        elif args.action == "status":
            print(json.dumps(status(state), indent=2))
        else:
            prepare(args.demo.resolve(), state)
            print(state / "compose.yaml")
        return 0
    except (Exception, KeyboardInterrupt):
        result = {"status": "failed", "category": "command_failed", "phase": args.action}
        try:
            write_report(state, result)
        except Exception:
            result["category"] = "report_unwritable"
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
