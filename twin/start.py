#!/usr/bin/env python3
"""Render and run an isolated, pinned OpenTelemetry demo and lineage platform."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
TWIN = ROOT / "twin"
DEMO_COMMIT = "dedc0178918e260823323b8d95005a8cb924b007"
PROJECT = "lineage-twin"


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def compose_args(state: Path):
    return ["docker", "compose", "--project-name", PROJECT, "-f", str(state / "compose.yaml")]


def prepare(demo: Path, state: Path):
    commit = command(["git", "-C", str(demo), "rev-parse", "HEAD"], capture_output=True).stdout.strip()
    if commit != DEMO_COMMIT:
        raise ValueError(f"Demo must be pinned to {DEMO_COMMIT}; got {commit}")
    for directory in ("capture", "flags", "sandbox"):
        (state / directory).mkdir(parents=True, exist_ok=True)
    (state / "capture").chmod(0o700)
    if not (state / "flags/demo.flagd.json").exists():
        shutil.copytree(demo / "src/flagd", state / "flags", dirs_exist_ok=True)
    (state / "flags").chmod(0o755)
    for path in (state / "flags").rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    command(["sh", str(ROOT / "fixtures/otel-demo-3.1.0/run/sandbox.sh"), str(demo), str(state / "sandbox")])
    env = dict(os.environ, DEMO_VERSION="3.1.0", IPV6_ENABLED="false", LOCUST_BROWSER_USER_WEIGHT="0",
               LOCUST_HTTP_USER_WEIGHT="1", LOCUST_USERS="5")
    rendered = command(["docker", "compose", "--project-name", PROJECT, "-f", str(demo / "compose.yaml"),
                        "-f", str(demo / "compose.full.yaml"), "config", "--format", "json"],
                       env=env, capture_output=True)
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
    lock_path = TWIN / "images.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        for service in config["services"].values():
            service["image"] = lock.get(service["image"], service["image"])
    (state / "compose.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    return config


def status(state):
    output = command(compose_args(state) + ["ps", "--all", "--format", "json"], capture_output=True).stdout.strip()
    rows = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines()]
    return [{"service": row["Service"], "state": row["State"], "health": row.get("Health", "")}
            for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "platform", "prepare", "status", "down"), nargs="?", default="up")
    parser.add_argument("--demo", type=Path, default=Path("/tmp/lineage-reference-otel-demo"))
    parser.add_argument("--state", type=Path, default=TWIN / ".state")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    state = args.state.resolve()
    if not state.is_relative_to(TWIN / ".state"):
        parser.error("state must be inside ignored twin/.state to protect synthetic capture")
    if args.action == "down":
        command(compose_args(state) + ["down"])
        return
    if args.action == "status":
        print(json.dumps(status(state), indent=2))
        return
    started = time.monotonic()
    config = prepare(args.demo.resolve(), state)
    if args.action == "prepare":
        print(state / "compose.yaml")
        return
    selected = ["lineage-kafka", "lineage-neo4j", "lineage-postgres"] if args.action == "platform" else []
    driver = command(["docker", "info", "--format", "{{.Driver}}"], capture_output=True).stdout.strip()
    if not selected and driver == "vfs" and shutil.disk_usage(state).free < 50 * 1024**3:
        raise SystemExit("Full demo blocked: Docker vfs requires at least 50 GiB free before pulling/creating this stack. "
                         "Use an overlay-backed Docker host or a larger disk; platform starts only with the 'platform' action.")
    command(compose_args(state) + ["up", "--detach", "--no-build", "--wait", "--wait-timeout", str(args.timeout)] + selected)
    rows = status(state)
    expected = len(selected) if selected else len(config["services"])
    if selected:
        rows = [row for row in rows if row["service"] in selected]
    result = {"demoCommit": DEMO_COMMIT, "elapsedSeconds": round(time.monotonic() - started, 3),
              "scope": "platform" if selected else "full-demo", "services": rows, "expectedServices": expected,
              "allRunning": len(rows) == expected and all(r["state"] == "running" for r in rows),
              "allContainersHealthy": len(rows) == expected and all(r["health"] == "healthy" for r in rows),
              "note": "Compose wait accepts running services without healthchecks; this is not the strict WP-03 health gate."}
    (state / "startup.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
