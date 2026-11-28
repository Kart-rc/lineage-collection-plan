"""Catalog-derived ownership, tiers and inherited personal classifications (WP-17)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterable

import yaml

from .config import repository_root
from .evidence import prepare_event
from .urn import normalize, parse

CRITICALITY_TIERS = {"critical": 1, "high": 2, "medium": 3, "low": 3}


def dataset_ref(urn: str) -> dict:
    parsed = parse(urn)
    if parsed.field:
        raise ValueError("Expected dataset URN, not field")
    return {"namespace": parsed.namespace, "name": parsed.name}


class Catalog:
    def __init__(self, path: str | Path | None = None, contracts: str | Path | None = None, *, document: dict | None = None):
        root = repository_root() / "fixtures/otel-demo-3.1.0"
        self.document = deepcopy(document) if document is not None else yaml.safe_load(Path(path or root / "catalog.yaml").read_text())
        self.nodes: dict[str, dict] = {}
        self.personal: set[str] = set()
        for name, row in self.document.get("services", {}).items():
            tier = CRITICALITY_TIERS.get(row["criticality"], row.get("tier"))
            self._add(f"svc://otel-demo/{name}", row["owner"], tier)
        for group in ("datasets", "flags"):
            for urn, row in self.document.get(group, {}).items():
                self._add(urn, row["owner"], row["tier"])
        for contract_path in sorted(Path(contracts or root / "contracts").glob("*.yaml")):
            self._contract(yaml.safe_load(contract_path.read_text()))

    def _add(self, urn: str, owner: str, tier: int) -> None:
        if not owner or tier not in (1, 2, 3):
            raise ValueError("Catalog node requires owner and tier 1, 2 or 3")
        self.nodes[normalize(urn)] = {"owner": owner, "tier": tier}

    def _contract(self, contract: dict) -> None:
        server = contract["server"]
        if server["type"] == "kafka":
            datasets = [u for u in self.nodes if u.startswith("kafka://") and parse(u).name == server["topic"]]
            if len(datasets) != 1:
                raise ValueError("Contract topic is not unambiguously catalogued")
            for record in contract.get("schema", []):
                self._properties(datasets[0], record.get("properties", []))
        elif server["type"] == "postgres":
            for record in contract.get("schema", []):
                dataset = normalize(f"postgres://{server['host']}/{server['database']}.{record['physicalName']}")
                self._properties(dataset, record.get("properties", []))

    def _properties(self, dataset: str, properties: list, prefix: str = "", inherited_personal: bool = False) -> None:
        for prop in properties:
            field = prefix + prop["name"]
            personal = inherited_personal or prop.get("classification") == "personal"
            if prop.get("logicalType") == "array":
                field += "[]"
            if personal:
                self.personal.add(normalize(dataset + "#" + field))
            self._properties(dataset, prop.get("properties", []), field + ".", personal)
            self._properties(dataset, prop.get("items", {}).get("properties", []), field + ".", personal)

    def attributes(self, urn: str) -> dict:
        urn = normalize(urn)
        parsed = parse(urn)
        dataset = str(parsed.dataset) if not isinstance(parsed.dataset, str) else parsed.dataset
        row = self.nodes.get(dataset)
        if row is None and parsed.scheme in {"svc", "api", "otel", "logs"}:
            service = parsed.name.split("/", 1)[0]
            row = self.nodes.get(f"svc://{parsed.authority}/{service}")
        if row is None:
            raise KeyError("No catalog ownership for node")
        result = dict(row)
        result["personal"] = urn in self.personal or any(urn.startswith(p + ".") for p in self.personal)
        return result

    def overlay(self, urns: Iterable[str]) -> dict[str, dict]:
        return {normalize(urn): self.attributes(urn) for urn in urns}

    def owner_for(self, urn: str) -> str:
        return self.attributes(urn)["owner"]

    def ownership_events(self, event_time: str, *, raw_ref: str = "fixture://catalog.yaml") -> list[dict]:
        events = []
        for urn, row in sorted(self.nodes.items()):
            events.append(prepare_event({
                "schemaVersion": "2", "eventType": "EVIDENCE", "eventTime": event_time,
                "producer": "lineage-collectors/catalog@0.1.0",
                "edge": {"type": "OWNS", "from": {"namespace": "team://catalog", "name": row["owner"]}, "to": dataset_ref(urn)},
                "evidence": {"source": "declared", "observedAt": event_time, "rawRef": raw_ref},
            }))
        return events
