"""Daily deduplicated owner queues for conflicting or one-sided evidence (WP-16)."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from .catalog import Catalog
from .urn import normalize


def edge_key(edge: dict) -> tuple[str, str, str]:
    def endpoint(value):
        return normalize(value if isinstance(value, str) else value["namespace"] + "/" + value["name"])
    return endpoint(edge["from"]), edge["type"], endpoint(edge["to"])


class Reconciler:
    """Queue identity is (UTC day, from URN, edge type, to URN).

Provide state_path for atomic local persistence across daily runner restarts.
Multiple reasons merge into one item. This candidate is a single-writer store.
"""

    def __init__(self, catalog: Catalog | None = None, state_path: str | Path | None = None):
        self.catalog = catalog or Catalog()
        self.state_path = Path(state_path) if state_path else None
        self._items = {}
        if self.state_path and self.state_path.exists():
            for item in json.loads(self.state_path.read_text()):
                self._items[(item["day"], *edge_key(item))] = item

    @property
    def items(self) -> list[dict]:
        return [dict(item, reasons=list(item["reasons"])) for _, item in sorted(self._items.items())]

    def queue(self, edge: dict, day: str, reason: str, *, owner_node: str | None = None) -> dict:
        day = date.fromisoformat(day).isoformat()
        source, edge_type, target = edge_key(edge)
        key = (day, source, edge_type, target)
        if key not in self._items:
            # Consumer/configuration issues belong to the affected reader.
            responsible = owner_node or (target if edge_type in {"CONSUMES", "CONFIGURES"} else source)
            self._items[key] = {"day": day, "from": source, "type": edge_type, "to": target,
                                "owner": self.catalog.owner_for(responsible), "reasons": []}
        if reason not in self._items[key]["reasons"]:
            self._items[key]["reasons"].append(reason)
            self._items[key]["reasons"].sort()
            self._save()
        return dict(self._items[key], reasons=list(self._items[key]["reasons"]))

    def _save(self) -> None:
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temporary.write_text(json.dumps(self.items, sort_keys=True))
            temporary.replace(self.state_path)

    def reconcile(self, static_edges: list[dict], runtime_edges: list[dict], day: str,
                  *, declared_edges: list[dict] = (), disputed_edges: list[dict] = ()) -> list[dict]:
        static = {edge_key(e): e for e in static_edges}
        runtime = {edge_key(e): e for e in runtime_edges}
        for key in static.keys() - runtime.keys():
            self.queue(static[key], day, "static-only")
        for key in runtime.keys() - static.keys():
            self.queue(runtime[key], day, "runtime-only")
        for edge in declared_edges:
            if edge_key(edge) not in runtime:
                self.queue(edge, day, "declared-never-seen")
        for edge in disputed_edges:
            self.queue(edge, day, "disagreeing")
        return self.items

    def reconcile_summary(self, summary: dict, static_edges: list[dict], flag_edges: list[dict], day: str) -> list[dict]:
        """Compare summary edge metadata; this does not replay missing raw captures."""
        types = {"CALLS", "PRODUCES", "CONSUMES"}
        static = [e for e in static_edges if e["type"] in types]
        runtime = [e for e in summary["edges"] if e["type"] in types and e["to"] != "svc://otel-demo/flagd"]
        self.reconcile(static, runtime, day)
        readers = {normalize(e["to"]) for e in flag_edges}
        seen = {normalize(e["from"]) for e in summary["edges"] if e["to"] == "svc://otel-demo/flagd"}
        # One missing control-read edge per service, regardless of flag count.
        for reader in sorted(readers - seen):
            self.queue({"from": reader, "type": "CALLS", "to": "svc://otel-demo/flagd"}, day, "flag-reader-without-runtime")
        return self.items
