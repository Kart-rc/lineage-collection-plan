"""WP-15/16/17 aliases, ownership/classification and daily queue semantics."""
import json

import pytest

from lineage.catalog import Catalog
from lineage.config import repository_root
from lineage.reconcile import Reconciler
from lineage.resolve import Resolver
from lineage.urn import normalize

FIXTURES = repository_root() / "fixtures/otel-demo-3.1.0"


@pytest.mark.parametrize("value", ["172.18.0.4", "172.18.0.4:5050", "::1", "[2001:db8::1]:80", "http://172.18.0.4:80/x", "redis@172.18.0.4", "2001:db8::1", "172%2e18%2e0%2e4"])
def test_ip_is_not_an_alias_even_if_exact_table_is_poisoned(value):
    resolver = Resolver(aliases={"aliases": [{"kind": "service.name", "value": value, "urn": "svc://otel-demo/checkout"}]})
    assert resolver.resolve("service.name", value).status == "non_entity"


def test_login_never_attributes_access_even_with_a_poisoned_alias():
    resolver = Resolver(aliases={"aliases": [{"kind": "db.user", "value": "astronomy_user", "urn": "svc://otel-demo/accounting"}]})
    assert resolver("db.user", "astronomy_user") is None


def test_ip_cannot_be_hidden_in_a_service_urn_or_alias_target():
    resolver = Resolver(aliases={"aliases": [{"kind": "address", "value": "misleading:80", "urn": "svc://otel-demo/172.18.0.4"}]})
    assert resolver("address", "misleading:80") is None
    assert resolver("urn", "svc://otel-demo/172.18.0.4") is None


def test_exact_rows_precede_patterns_and_groups_keep_hyphens():
    resolver = Resolver()
    assert resolver("service.name", "otelcol-contrib") == "svc://otel-demo/otel-collector"
    assert resolver("kafka.client_id", "consumer-fraud-detection-12") == "svc://otel-demo/fraud-detection"
    assert resolver("kafka.client_id", "consumer-unlisted-service-1") is None
    assert resolver.resolve("envoy.cluster", "-").status == "non_entity"
    assert resolver.resolve("address", "unknown:80").status == "unresolved"


def test_nested_element_resolution_and_aliases_converge():
    resolver = Resolver()
    assert resolver("messaging.destination.name", "orders#items[].cost.units") == "kafka://otel-demo/orders#items[].cost.units"
    assert resolver.element("messaging.destination.name", "orders", "items[].cost.units") == "kafka://otel-demo/orders#items[].cost.units"
    assert resolver("db.table", 'accounting."order"#order_id') == resolver("db.table", "accounting.order#order_id")
    assert resolver("urn", "kafka://otel-demo/orders#items[].cost.units") == "kafka://otel-demo/orders#items[].cost.units"


def test_all_explicit_fixture_aliases_resolve_or_are_declared_nonentities():
    document = json.loads((FIXTURES / "aliases.json").read_text())
    resolver = Resolver()
    for row in document["aliases"]:
        if not row.get("pattern"):
            resolved = resolver.resolve(row["kind"], row["value"])
            assert resolved.status == ("resolved" if row.get("urn") else "non_entity")


def test_all_golden_endpoints_have_catalog_owner_and_tier():
    golden = json.loads((FIXTURES / "golden-graph.json").read_text())
    catalog = Catalog()
    count = 0
    for group in golden.values():
        if not isinstance(group, list):
            continue
        for edge in group:
            if not isinstance(edge, dict):
                continue
            for key in ("from", "to", "node", "reader"):
                urn = edge.get(key)
                if isinstance(urn, str) and "://" in urn:
                    attributes = catalog.attributes(urn)
                    assert attributes["owner"]
                    assert attributes["tier"] in {1, 2, 3}
                    count += 1
    assert count > 100


def test_service_tier_comes_from_criticality_and_personal_is_inherited():
    catalog = Catalog()
    assert catalog.attributes("api://otel-demo/checkout/PlaceOrder/request#address.zip_code")["tier"] == 1
    assert catalog.attributes("svc://otel-demo/accounting")["tier"] == 3
    assert catalog.attributes("kafka://otel-demo/orders#shipping_address.zip_code")["personal"]
    assert catalog.attributes("postgres://astronomy-db/astronomy_db.accounting.shipping#street_address")["personal"]
    assert not catalog.attributes("kafka://otel-demo/orders#order_id")["personal"]
    for event in catalog.ownership_events("2026-11-28T00:00:00Z"):
        assert event["evidence"]["source"] == "declared"
        assert event["evidence"]["weight"] == 0.50
    with pytest.raises(KeyError):
        catalog.attributes("svc://otel-demo/unknown")


def test_first_summary_routes_exact_eight_expected_items_with_owners():
    summary = json.loads((FIXTURES / "capture-2026-11-27/observed-edges.json").read_text())
    golden = json.loads((FIXTURES / "golden-graph.json").read_text())
    reconciler = Reconciler()
    items = reconciler.reconcile_summary(summary, golden["service_edges"], golden["flag_edges"], "2026-11-27")
    assert len(items) == 8
    assert {(i["from"], i["to"]) for i in items if i["reasons"] == ["static-only"]} == {
        ("svc://otel-demo/frontend", "svc://otel-demo/currency"),
        ("svc://otel-demo/frontend", "svc://otel-demo/shipping"),
    }
    assert sum(i["reasons"] == ["flag-reader-without-runtime"] for i in items) == 6
    assert all(i["owner"] for i in items)
    assert len(reconciler.reconcile_summary(summary, golden["service_edges"], golden["flag_edges"], "2026-11-27")) == 8


def test_queue_deduplicates_reasons_persists_and_routes_consumers(tmp_path):
    edge = {"from": "kafka://otel-demo/orders", "type": "CONSUMES", "to": "svc://otel-demo/accounting"}
    path = tmp_path / "queues.json"
    reconciler = Reconciler(state_path=path)
    reconciler.queue(edge, "2026-11-27", "runtime-only")
    reconciler.queue(edge, "2026-11-27", "disagreeing")
    restarted = Reconciler(state_path=path)
    restarted.queue(edge, "2026-11-27", "disagreeing")
    assert len(restarted.items) == 1
    assert restarted.items[0]["owner"] == "team-finance-data"
    assert restarted.items[0]["reasons"] == ["disagreeing", "runtime-only"]
    restarted.queue(edge, "2026-11-28", "runtime-only")
    assert len(restarted.items) == 2


def test_reconciles_all_four_issue_categories():
    static = {"from": "svc://otel-demo/frontend", "to": "svc://otel-demo/currency", "type": "CALLS"}
    runtime = {"from": "svc://otel-demo/checkout", "to": "svc://otel-demo/payment", "type": "CALLS"}
    items = Reconciler().reconcile([static], [runtime], "2026-11-28", declared_edges=[static], disputed_edges=[runtime])
    assert len(items) == 2
    assert {reason for item in items for reason in item["reasons"]} == {"static-only", "runtime-only", "declared-never-seen", "disagreeing"}
