"""Alias-table identity resolution, with explicit non-entity outcomes (WP-15)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import fnmatch
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .config import repository_root
from .urn import normalize, parse


def is_ip(value: str) -> bool:
    """Recognize IP literals, host:port, bracketed IPv6 and URL authorities."""
    value = unquote(str(value)).strip()
    if "://" in value:
        try:
            value = urlsplit(value).hostname or ""
        except ValueError:
            return True
    if "@" in value:
        value = value.rsplit("@", 1)[-1]
    candidates = [value, value.split("%", 1)[0]]
    if value.startswith("["):
        candidates.append(value[1:].split("]", 1)[0].split("%", 1)[0])
    elif value.count(":") == 1:
        candidates.append(value.rsplit(":", 1)[0])
    for candidate in candidates:
        try:
            ipaddress.ip_address(candidate)
            return True
        except ValueError:
            pass
    return False


@dataclass(frozen=True)
class Resolution:
    status: str
    urn: str | None
    reason: str | None = None


class Resolver:
    def __init__(self, path: str | Path | None = None, *, aliases: dict | None = None):
        document = aliases if aliases is not None else json.loads(Path(path or repository_root() / "fixtures/otel-demo-3.1.0/aliases.json").read_text())
        self.exact = {}
        self.patterns = []
        self.misses: Counter = Counter()
        for row in document["aliases"]:
            if row.get("pattern"):
                self.patterns.append(row)
            else:
                self.exact[(row["kind"], row["value"])] = row

    def resolve(self, kind: str, value: str) -> Resolution:
        if not isinstance(value, str) or not value:
            return Resolution("unresolved", None, "missing-name")
        base, separator, field = value.partition("#")
        if is_ip(base):
            return Resolution("non_entity", None, "ip-address")
        if kind in {"db.user", "db.username", "db.login", "user.name"}:
            return Resolution("non_entity", None, "login-is-not-identity")
        if "://" in base:
            try:
                if is_ip(parse(value).name.split("/", 1)[0]):
                    return Resolution("non_entity", None, "ip-address")
                return Resolution("resolved", normalize(value))
            except ValueError:
                return Resolution("unresolved", None, "invalid-urn")
        row = self.exact.get((kind, base))
        if row is None:
            row = next((p for p in self.patterns if p["kind"] == kind and fnmatch.fnmatchcase(base, p["value"])), None)
        if row is None:
            self.misses[(kind, value)] += 1
            return Resolution("unresolved", None, "unknown-alias")
        if not row.get("urn"):
            return Resolution("non_entity", None, "declared-non-entity")
        target = row["urn"].replace("{value}", base)
        if "{group}" in target:
            match = re.fullmatch(r"consumer-(.+)-[0-9]+", base)
            if match is None:
                return Resolution("unresolved", None, "unknown-consumer-group")
            group = self.resolve("kafka.consumer_group", match.group(1))
            if group.urn is None:
                return Resolution("unresolved", None, "unknown-consumer-group")
            target = group.urn
        try:
            if is_ip(target) or is_ip(parse(target).name.split("/", 1)[0]):
                return Resolution("non_entity", None, "ip-address")
            target = normalize(target + ("#" + field if separator else ""))
            return Resolution("resolved", target)
        except ValueError:
            return Resolution("unresolved", None, "invalid-urn")

    def __call__(self, kind: str, value: str) -> str | None:
        return self.resolve(kind, value).urn

    def element(self, kind: str, value: str, field: str) -> str | None:
        base = self(kind, value)
        return normalize(base + "#" + field) if base else None
