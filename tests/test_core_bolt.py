"""Actual DB tests, skipped explicitly unless a local Bolt instance is configured."""
import os
import uuid

import pytest

from lineage.graph import BitemporalGraph, BoltGraphStore
from lineage.merge import MergeEngine
from test_core_semantics import evidence, snap, T0, T1, T2, T3


@pytest.mark.integration
def test_neo4j_bitemporal_readback_immutable_relationships_and_rebuilds():
    uri = os.environ.get('LINEAGE_NEO4J_URI')
    if not uri:
        pytest.skip('A running local Neo4j is required; set LINEAGE_NEO4J_URI')
    auth = (os.environ.get('LINEAGE_NEO4J_USER', 'neo4j'), os.environ.get('LINEAGE_NEO4J_PASSWORD', 'lineage-local-only'))
    store = BoltGraphStore(uri, auth, namespace='core-test-' + uuid.uuid4().hex)
    store.verify_connectivity()
    graph = BitemporalGraph(store)
    engine = MergeEngine(graph=graph)
    first = evidence('otel_span', at=T2)
    engine.ingest(first, recorded_at=T3)
    prior = graph.assertions
    later = '2026-11-27T17:00:00Z'
    second = evidence(at=T0)
    engine.ingest(second, recorded_at=later)
    fresh = BitemporalGraph(store)
    assert fresh.assertions[:len(prior)] == prior
    assert not fresh.as_of(T1, T3)
    assert len(fresh.as_of(T1, later)) == 1
    assert not fresh.as_of(T2, '2026-11-27T15:00:00Z')
    assert fresh.graph_hash(T2) == graph.graph_hash(T2)
    with store._session() as session:
        count = session.run('MATCH (s:LineageNode {namespace: $namespace})-[r:LINEAGE_VERSION]->() RETURN count(r) AS count', namespace=store.namespace).single()['count']
    assert count == sum(len(a['timeline']) for a in graph.assertions)
    # All archived source records are replayed into three independent DB namespaces.
    for _ in range(3):
        replica_store = BoltGraphStore(uri, auth, namespace='core-rebuild-' + uuid.uuid4().hex)
        replica = MergeEngine(graph=BitemporalGraph(replica_store))
        replica.ingest(first, recorded_at=T3)
        replica.ingest(second, recorded_at=later)
        assert BitemporalGraph(replica_store).graph_hash(T2) == fresh.graph_hash(T2)
        replica_store.close()
    # Closing one unit appends relationships; the prior time remains queryable.
    unit_store = BoltGraphStore(uri, auth, namespace='core-close-' + uuid.uuid4().hex)
    units = MergeEngine(graph=BitemporalGraph(unit_store))
    units.replace_unit(snap([evidence(unit=True)]))
    units.replace_unit(snap([], 2, T1))
    closed = BitemporalGraph(unit_store)
    assert len(closed.as_of(T0)) == 1 and not closed.as_of(T1)
    assert len(closed.during(T0, T1)) == 1
    unit_store.close()
    store.close()


@pytest.mark.integration
def test_neo4j_generated_valid_and_recorded_views_match_independent_ledger():
    import random
    from datetime import datetime, timedelta, timezone
    from lineage.graph import timestamp
    uri = os.environ.get('LINEAGE_NEO4J_URI')
    if not uri:
        pytest.skip('Set LINEAGE_NEO4J_URI to run the actual Bolt as-of suite')
    auth = (os.environ.get('LINEAGE_NEO4J_USER', 'neo4j'), os.environ.get('LINEAGE_NEO4J_PASSWORD', 'lineage-local-only'))
    store = BoltGraphStore(uri, auth, namespace='core-property-' + uuid.uuid4().hex)
    merger = MergeEngine(graph=BitemporalGraph(store))
    origin = datetime(2026, 11, 27, 10, tzinfo=timezone.utc)
    def at(minutes): return (origin + timedelta(minutes=minutes)).isoformat()
    ledger = []
    for target in range(6):
        for n, source in enumerate(['ci_static', 'otel_span', 'otel_span']):
            valid = at(target + 4 * n)
            event = evidence(source, at=valid, target='target-' + str(target), ref=f'archive://ledger/{target}/{n}')
            ledger.append({'event': event, 'valid': timestamp(valid)})
    random.Random(130013).shuffle(ledger)
    for index, entry in enumerate(ledger):
        entry['recorded'] = timestamp(at(120 + index))
        merger.ingest(entry['event'], recorded_at=entry['recorded'])
    readback = BitemporalGraph(store)
    for valid_minute in range(0, 16, 2):
        for record_minute in [119, 120, 124, 129, 133, 137, 140]:
            valid_at, recorded_at = timestamp(at(valid_minute)), timestamp(at(record_minute))
            expected = {}
            for entry in ledger:
                if entry['valid'] <= valid_at and entry['recorded'] <= recorded_at:
                    event = entry['event']
                    expected.setdefault('svc://otel-demo/' + event['edge']['to']['name'], []).append(event)
            actual = {row['edge']['to']: row for row in readback.as_of(valid_at, recorded_at).values()}
            assert set(actual) == set(expected)
            for target, events in expected.items():
                sources = {e['evidence']['source'] for e in events}
                assert set(actual[target]['sources']) == sources
                assert set(actual[target]['evidenceRefs']) == {e['evidence']['rawRef'] for e in events}
                score = 0.96 if len(sources) == 2 else (0.9 if 'otel_span' in sources else 0.6)
                assert actual[target]['confidence'] == pytest.approx(score)
                assert actual[target]['state'] == ('confirmed' if 'otel_span' in sources else 'probable')
            assert readback.graph_hash(valid_at, recorded_at) == merger.graph_hash(valid_at, recorded_at)
    store.close()


@pytest.mark.integration
def test_neo4j_out_of_order_recorded_provenance_regression():
    uri = os.environ.get('LINEAGE_NEO4J_URI')
    if not uri:
        pytest.skip('Set LINEAGE_NEO4J_URI for recorded-time replay correction')
    auth = (os.environ.get('LINEAGE_NEO4J_USER', 'neo4j'), os.environ.get('LINEAGE_NEO4J_PASSWORD', 'lineage-local-only'))
    store = BoltGraphStore(uri, auth, namespace='core-recorded-' + uuid.uuid4().hex)
    merger = MergeEngine(graph=BitemporalGraph(store))
    merger.ingest(evidence('otel_span', at=T1, ref='archive://second'), recorded_at=T1)
    immutable = merger.graph.assertions
    merger.ingest(evidence('otel_span', at=T0, ref='archive://first'), recorded_at=T0)
    readback = BitemporalGraph(store)
    assert all(assertion in readback.assertions for assertion in immutable)
    assert readback.graph_hash(T0, T0) == merger.graph_hash(T0, T0)
    assert readback.graph_hash(T1, T1) == merger.graph_hash(T1, T1)
    assert next(iter(readback.as_of(T0).values()))['evidenceRefs'] == ['archive://first']
    store.close()


@pytest.mark.integration
def test_neo4j_expression_transitions_own_contributions_and_rebuild_three_times():
    from lineage.diff import event_id
    from lineage.merge import UnitSnapshot
    from test_core_semantics import (
        UNIT, PRODUCER, HASH_A, HASH_B, HASH_C, HASH_RUNTIME,
        expression_evidence, assert_change_schema,
    )
    uri = os.environ.get('LINEAGE_NEO4J_URI')
    if not uri:
        pytest.skip('Set LINEAGE_NEO4J_URI to exercise expression changes on the actual graph store')
    auth = (os.environ.get('LINEAGE_NEO4J_USER', 'neo4j'), os.environ.get('LINEAGE_NEO4J_PASSWORD', 'lineage-local-only'))
    other_unit = 'unit://git/demo/other-expression.sql'
    final_recorded = '2026-11-27T17:00:00Z'
    records = [
        ('snapshot', snap([expression_evidence()]).as_dict()),
        ('snapshot', snap([expression_evidence(HASH_B, unit=other_unit)], unit=other_unit).as_dict()),
        ('event', expression_evidence(HASH_RUNTIME, source='otel_span', ref='archive://runtime/expression')),
        ('snapshot', UnitSnapshot.build(UNIT, PRODUCER, 2, T1, T2,
                                        [expression_evidence(HASH_C, at=T1)]).as_dict()),
        ('snapshot', UnitSnapshot.build(UNIT, PRODUCER, 3, T2, T3,
                                        [expression_evidence(None, at=T2)]).as_dict()),
        ('snapshot', UnitSnapshot.build(other_unit, PRODUCER, 2, T3, final_recorded, [], deleted=True).as_dict()),
    ]
    store = BoltGraphStore(uri, auth, namespace='core-expression-' + uuid.uuid4().hex)
    live = MergeEngine(graph=BitemporalGraph(store))
    events = []
    for kind, payload in records:
        result = live.replace_unit(UnitSnapshot.from_dict(payload)) if kind == 'snapshot' else live.ingest(payload)
        assert not result.held
        events.extend(result.changes)
    assert_change_schema(events)
    assert all(event['schemaVersion'] == '2' for event in events)
    assert [event['change'] for event in events] == ['opened'] + ['expression_changed'] * 5
    persisted = BitemporalGraph(store)
    cases = [
        (T0, T0, [HASH_A, HASH_B, HASH_RUNTIME]),
        (T1, T1, [HASH_A, HASH_B, HASH_RUNTIME]),
        (T1, T2, [HASH_B, HASH_C, HASH_RUNTIME]),
        (T2, T2, [HASH_B, HASH_C, HASH_RUNTIME]),
        (T2, T3, [HASH_B, HASH_RUNTIME]),
        (T3, final_recorded, [HASH_RUNTIME]),
    ]
    for valid_at, recorded_at, expected in cases:
        rows = persisted.as_of(valid_at, recorded_at)
        assert len(rows) == 1
        assert next(iter(rows.values()))['expressionHashes'] == expected
        assert persisted.graph_hash(valid_at, recorded_at) == live.graph_hash(valid_at, recorded_at)
    original_assertions = live.graph.assertions
    for _ in range(3):
        replica_store = BoltGraphStore(uri, auth, namespace='core-expression-rebuild-' + uuid.uuid4().hex)
        replica = MergeEngine(graph=BitemporalGraph(replica_store))
        replay_events = []
        for kind, payload in records:
            result = replica.replace_unit(UnitSnapshot.from_dict(payload)) if kind == 'snapshot' else replica.ingest(payload)
            replay_events.extend(result.changes)
        assert [event_id(e) for e in replay_events] == [event_id(e) for e in events]
        reloaded = BitemporalGraph(replica_store)
        for valid_at, recorded_at, _ in cases:
            assert reloaded.graph_hash(valid_at, recorded_at) == persisted.graph_hash(valid_at, recorded_at)
        replica_store.close()
    assert live.graph.assertions == original_assertions
    with store._session() as session:
        count = session.run('MATCH (s:LineageNode {namespace: $namespace})-[r:LINEAGE_VERSION]->() RETURN count(r) AS count',
                            namespace=store.namespace).single()['count']
    assert count == sum(len(assertion['timeline']) for assertion in original_assertions)
    store.close()
