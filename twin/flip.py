#!/usr/bin/env python3
"""Apply a twin fault and durably record a validated envelope-v2 change event."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import uuid

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "twin/.state"
SCHEMA = ROOT / "factory/specs/evidence/interfaces/envelope-v2.schema.json"
SERVICES = frozenset({"accounting", "ad", "cart", "checkout", "currency", "email", "fraud-detection", "frontend",
                      "frontend-proxy", "image-provider", "load-generator", "payment", "product-catalog", "quote",
                      "recommendation", "shipping", "kafka", "astronomy-db", "valkey-cart", "flagd", "flagd-ui"})


def update_flag(document, name, variant):
    """Match flagd-ui storage.ex: update the true branch of a three-part if."""
    updated = deepcopy(document)
    flag = updated["flags"][name]
    if variant not in flag["variants"]:
        raise ValueError(f"Unknown variant for {name}: {variant}")
    if "targeting" in flag:
        branch = flag["targeting"].get("if")
        if not isinstance(branch, list) or len(branch) != 3 or not isinstance(branch[1], str):
            raise ValueError("Unsupported targeting rule; refusing to change an ineffective default")
        old = branch[1]
        branch[1] = variant
    else:
        old = flag["defaultVariant"]
        flag["defaultVariant"] = variant
    return updated, old


def change_event(kind, subject, old, new):
    at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event = {"schemaVersion": "2", "eventType": "CHANGE_EVENT", "eventTime": at, "producer": "twin/flip@0.1.0",
             "change": {"kind": kind, "subject": subject, "at": at, "from": old, "to": new,
                        "actor": "twin/flip", "ref": f"twin:{uuid.uuid4()}"}}
    Draft202012Validator(json.loads(SCHEMA.read_text()), format_checker=FormatChecker()).validate(event)
    return event


def append_event(path, event):
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(event, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())


def apply(state, kind, subject, variant=None):
    state = Path(state).resolve()
    with (state / "flip.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if kind == "flag":
            path = state / "flags/demo.flagd.json"
            current = json.loads(path.read_text())
            updated, old = update_flag(current, subject, variant)
            event = change_event("flag_change", f"flag://otel-demo/{subject}", old, variant)
        else:
            if subject not in SERVICES or kind not in ("stop", "start"):
                raise ValueError("Only allowlisted demo services can be stopped or started")
            event = change_event(f"service_{kind}", f"svc://otel-demo/{subject}",
                                 "running" if kind == "stop" else "stopped", "stopped" if kind == "stop" else "running")
        # Intent survives a crash between the side effect and the committed event.
        # Only changes.jsonl is consumed as evidence; intents support recovery/audit.
        append_event(state / "change-intents.jsonl", event)
        if kind == "flag":
            pending = path.with_suffix(".pending")
            with pending.open("w", encoding="utf-8") as output:
                json.dump(updated, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            pending.replace(path)
            path.chmod(0o644)
        else:
            subprocess.run(["docker", "compose", "--project-name", "lineage-twin", "-f", str(state / "compose.yaml"), kind, subject],
                           check=True, capture_output=True, text=True)
        append_event(state / "changes.jsonl", event)
        return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("flag", "stop", "start"))
    parser.add_argument("subject")
    parser.add_argument("variant", nargs="?")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    if not args.state.resolve().is_relative_to(DEFAULT_STATE):
        parser.error("state must be inside twin/.state")
    if (args.action == "flag") != (args.variant is not None):
        parser.error("flag needs a variant; start/stop do not accept one")
    print(json.dumps(apply(args.state, args.action, args.subject, args.variant), indent=2))


if __name__ == "__main__":
    main()
