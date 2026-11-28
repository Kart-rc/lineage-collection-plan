"""Visible core acceptance checks; these are not the inaccessible holdout."""
import copy
import json
import hashlib
import math
import random
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from lineage.config import parameters, repository_root, schema
from lineage.diff import LineageDiff, diff_snapshots
from lineage.graph import BitemporalGraph, timestamp
from lineage.merge import MergeEngine, UnitSnapshot
from lineage.urn import format, normalize, parse

ROOT = repository_root()
PARAMS = parameters()
T0 = '2026-11-27T12:00:00Z'
T1 = '2026-11-27T13:00:00Z'
T2 = '2026-11-27T14:00:00Z'
T3 = '2026-11-27T16:00:00Z'
UNIT = 'unit://git/demo/model.sql'
PRODUCER = 'lineage-test/core@1.0.0'


def evidence(source='ci_static', *, at=T0, ref='archive://test/input', target='shipping', unit=False, elements=None):
    event = {'schemaVersion': '2', 'eventType': 'EVIDENCE', 'eventTime': at, 'producer': PRODUCER,
             'edge': {'type': 'CALLS', 'from': {'namespace': 'svc://otel-demo', 'name': 'frontend'},
                      'to': {'namespace': 'svc://otel-demo', 'name': target}},
             'evidence': {'source': source, 'weight': PARAMS['evidence']['weights'][source],
                          'runtime': source in PARAMS['evidence']['runtime_sources'], 'observedAt': at,
                          'rawRef': ref, 'replaces': 'unit' if unit else 'none'}}
    if elements is not None:
        event['edge']['type'] = 'DERIVES'
        event['edge']['elements'] = elements
    if unit:
        event['unit'] = {'urn': UNIT, 'contentHash': 'sha256:12345678', 'commit': '1234567'}
    return event


def snap(events, generation=1, at=T0, unit=UNIT, producer=PRODUCER):
    return UnitSnapshot.build(unit, producer, generation, at, at, events)


def fields(n):
    return [{'from': 'f' + str(i), 'to': 'f' + str(i), 'class': 'DIRECT', 'subtype': 'IDENTITY'} for i in range(n)]


def fixture_event(edge, *, at=T0, unit=False):
    source, target = parse(edge['from']), parse(edge['to'])
    event = evidence(at=at, ref='archive://fixture/' + hashlib.sha256(json.dumps(edge, sort_keys=True).encode()).hexdigest(), unit=unit)
    event['edge'] = {'type': edge.get('type', 'DERIVES'),
                     'from': {'namespace': source.namespace, 'name': source.name},
                     'to': {'namespace': target.namespace, 'name': target.name}}
    if 'class' in edge:
        event['edge']['elements'] = [{'from': source.field, 'to': target.field,
                                      'class': edge['class'], 'subtype': edge['subtype'], 'masking': edge.get('masking', False)}]
    if edge.get('condition'):
        event['edge']['condition'] = edge['condition']
    return event


def test_10000_generated_urn_round_trips():
    rng = random.Random(101)
    for i in range(10000):
        kind = rng.choice(['svc', 'api', 'kafka', 'postgres', 'bi', 'flag', 'otel', 'unit', 'valkey', 'snowflake', 's3'])
        fields_ = '.'.join('field_' + str(rng.randrange(999)) + rng.choice(['', '[]']) for _ in range(rng.randrange(1, 5)))
        text = f'{kind}://tenant-{i % 97}/case_{i}/Name' + ('#' + fields_ if i % 3 else '')
        assert format(parse(text)) == text
        assert normalize(normalize(text)) == text


def test_every_pinned_fixture_urn_parses():
    found = []
    def walk(value):
        if isinstance(value, dict):
            for v in value.values(): walk(v)
        elif isinstance(value, list):
            for v in value: walk(v)
        elif isinstance(value, str) and '://' in value and value.split('://', 1)[0] in {'svc', 'api', 'kafka', 'postgres', 'bi', 'flag', 'otel', 'unit', 'valkey'}:
            if not any(fragment in value for fragment in [' -> ', '{', '<', ' ', '\n']) or value.startswith('api://otel-demo/shipping/POST '):
                found.append(value)
    for name in ['golden-graph.json', 'dbt/golden-dbt.json', 'aliases.json']:
        walk(json.loads((ROOT / 'fixtures/otel-demo-3.1.0' / name).read_text()))
    assert len(found) > 200
    for urn in found:
        assert format(parse(urn)) == normalize(urn)
    assert normalize('postgres://db/db.accounting."order"#"id"') == 'postgres://db/db.accounting.order#id'
    assert normalize('api://demo/shipping/POST /ship-order/response') == 'api://demo/shipping/POST%20/ship-order/response'


@pytest.mark.parametrize('bad', ['x', 'svc:///name', 'svc://demo/', 'svc://demo/a#', 'svc://demo/a#a..b', 'svc://demo/a#items[0]', 'svc://demo/a%Q0', 'svc://demo/a\n'])
def test_invalid_urns_rejected(bad):
    with pytest.raises(ValueError): parse(bad)


def test_1000_generated_event_sequences_are_idempotent_order_independent_and_monotonic():
    rng = random.Random(12412)
    weights = PARAMS['evidence']['weights']
    for sequence in range(1000):
        sources = rng.sample(['ci_static', 'declared', 'iam', 'otel_span', 'openlineage', 'gateway_log', 'db_span'], rng.randrange(2, 6))
        events = [evidence(source, ref=f'archive://seq/{sequence}/{source}') for source in sources]
        first, shuffled = MergeEngine(), MergeEngine()
        previous = 0
        for event in events:
            first.ingest(event)
            score = next(iter(first.snapshot().values())).confidence
            assert score >= previous
            previous = score
        expected = 1 - math.prod(1 - weights[s] for s in sources)
        assert score == pytest.approx(expected)
        rng.shuffle(events)
        for event in events + events:
            shuffled.ingest(event)
        assert first.graph_hash() == shuffled.graph_hash()
        old_hash = first.graph_hash()
        for event in reversed(events):
            result = first.ingest(event)
            assert result.duplicate and not result.changes
        assert first.graph_hash() == old_hash


def test_repeated_same_source_does_not_amplify_score_and_retains_provenance():
    engine = MergeEngine()
    for i in range(30): engine.ingest(evidence(ref=f'archive://input/{i}'))
    edge = next(iter(engine.snapshot().values()))
    assert edge.confidence == 0.6 and edge.sources == ('ci_static',)
    assert len(edge.evidence_refs) == 30
    assert all(e['producer'] == PRODUCER for e in edge.evidence)


def test_unit_replacement_is_atomic_and_unchanged_versions_stay_open():
    engine = MergeEngine(graph=BitemporalGraph())
    engine.replace_unit(snap([evidence(unit=True, elements=fields(9))]))
    old = {e.from_urn: e for e in engine.snapshot().values()}
    result = engine.replace_unit(snap([evidence(unit=True, elements=fields(6), at=T1)], generation=2, at=T1))
    assert [event['change'] for event in result.changes] == ['closed'] * 3
    assert len(engine.snapshot()) == 6
    assert all(e.valid_from == old[e.from_urn].valid_from for e in engine.snapshot().values())
    assert len(engine.graph.as_of(T0)) == 9 and len(engine.graph.as_of(T1)) == 6


@pytest.mark.parametrize('total,closed,held', [(17, 12, True), (50, 10, False), (49, 10, True), (20, 9, False)])
def test_exact_mass_close_boundaries(total, closed, held):
    engine = MergeEngine()
    engine.replace_unit(snap([evidence(unit=True, elements=fields(total))]))
    before = engine.graph_hash()
    result = engine.replace_unit(snap([evidence(unit=True, elements=fields(total - closed), at=T1)], 2, T1))
    assert result.held is held
    if held:
        assert engine.graph_hash() == before
        assert result.alert['closingEdges'] == closed and result.alert['producer'] == PRODUCER and result.alert['unit'] == UNIT
    else:
        assert len(engine.snapshot()) == total - closed


def test_empty_deleted_corrupt_incomplete_and_old_generations():
    engine = MergeEngine()
    initial = snap([evidence(unit=True)])
    engine.replace_unit(initial)
    before = engine.graph_hash()
    for broken in [replace(initial, complete=False), replace(initial, generation=2, digest='sha256:' + '0' * 64)]:
        with pytest.raises(ValueError): engine.replace_unit(broken)
        assert engine.graph_hash() == before
    engine.replace_unit(UnitSnapshot.build(UNIT, PRODUCER, 3, T2, T2, [], deleted=True))
    assert not engine.snapshot()
    engine.replace_unit(snap([evidence(unit=True, target='cart', at=T1)], 2, T1))
    assert not engine.snapshot()
    assert next(iter(engine.snapshot(T1).values())).to_urn.endswith('/cart')
    with pytest.raises(ValueError): engine.replace_unit(snap([evidence(unit=True, target='different')]))


def test_unit_snapshot_digest_and_identity_ignore_event_order_and_duplicates():
    events = [evidence(unit=True, target='a'), evidence(unit=True, target='b')]
    engine = MergeEngine()
    a = snap(events)
    b = snap([events[1], events[0], events[0]])
    assert a.digest == b.digest
    engine.replace_unit(a)
    assert engine.replace_unit(b).duplicate


def test_bare_unit_event_runtime_replace_and_pr_do_not_enter_graph():
    engine = MergeEngine()
    for event in [evidence(unit=True), evidence('otel_span', unit=True)]:
        with pytest.raises(ValueError): engine.ingest(event)
    pr = evidence()
    pr['unit'] = {'urn': UNIT, 'contentHash': 'sha256:12345678', 'commit': '1234567', 'pr': 10}
    with pytest.raises(ValueError): engine.ingest(pr)
    assert not engine.snapshot()


def test_runtime_survives_empty_static_replacement():
    engine = MergeEngine()
    engine.replace_unit(snap([evidence(unit=True)]))
    engine.ingest(evidence('otel_span'))
    engine.replace_unit(snap([], 2, T1))
    edge = next(iter(engine.snapshot().values()))
    assert edge.sources == ('otel_span',) and edge.state == 'confirmed'


def test_fixture_bl5_exactly_five_indirect_edges_no_target_columns():
    data = json.loads((ROOT / 'fixtures/otel-demo-3.1.0/dbt/golden-dbt.json').read_text())
    engine = MergeEngine()
    for edge in data['field_edges']:
        engine.ingest(fixture_event(edge))
    indirect = [e for e in engine.snapshot().values() if e.class_ == 'INDIRECT']
    assert len(indirect) == data['bl5_size_check']['indirect_edges_expected'] == 5
    assert sum(e.to_urn.endswith('fct_order_value') for e in indirect) == 4
    assert all('#' not in e.to_urn for e in indirect)
    # A producer's erroneous fanout still collapses to dataset+source+subtype.
    edge = next(e for e in data['field_edges'] if e['class'] == 'INDIRECT')
    for n in range(7): engine.ingest(fixture_event({**edge, 'to': edge['to'] + '#column_' + str(n)}))
    assert len([e for e in engine.snapshot().values() if e.class_ == 'INDIRECT']) == 5


def test_flag_C7_activates_five_and_reverts_with_schema_valid_causes():
    golden = json.loads((ROOT / 'fixtures/otel-demo-3.1.0/golden-graph.json').read_text())
    engine = MergeEngine(initial_flags={'flag://otel-demo/emitRawPii': 'off'})
    for edge in golden['gated_field_edges']: engine.ingest(fixture_event(edge))
    assert sum(e.condition_state == 'latent' for e in engine.snapshot().values()) == 5
    validator = Draft202012Validator(schema('factory/specs/changes/interfaces/lineage-changes.schema.json'), format_checker=FormatChecker())
    for at, target, expected in [(T1, 'on', 'condition_activated'), (T2, 'off', 'condition_deactivated')]:
        result = engine.ingest({'schemaVersion': '2', 'eventType': 'CHANGE_EVENT', 'eventTime': at, 'producer': PRODUCER,
                               'change': {'kind': 'flag_change', 'subject': 'flag://otel-demo/emitRawPii', 'at': at, 'to': target, 'ref': 'C7-' + target}})
        assert len(result.changes) == 5
        for event in result.changes:
            validator.validate(event)
            assert event['change'] == expected and event['causes'] == [{'kind': 'change_event', 'ref': 'C7-' + target}]
    assert sum(e.condition_state == 'latent' for e in engine.snapshot().values()) == 5


def test_dispute_owner_review_and_dormancy_at_30_days():
    engine = MergeEngine()
    engine.ingest(evidence())
    engine.ingest(evidence('otel_span'))
    edge_id = next(iter(engine.snapshot()))
    engine.owner_action(edge_id, 'dispute', 'owner/dispute-1', T1)
    assert engine.snapshot()[edge_id].state == 'candidate'
    engine.owner_action(edge_id, 'confirm', 'owner/confirm-1', T2)
    assert engine.snapshot()[edge_id].state == 'verified'
    engine.owner_action(edge_id, 'review', 'owner/review-1', T3)
    assert engine.snapshot()[edge_id].state == 'confirmed'
    engine.advance_clock('2026-12-27T11:59:59Z')
    assert engine.snapshot()[edge_id].state == 'confirmed'
    result = engine.advance_clock('2026-12-27T12:00:00Z')
    assert engine.snapshot()[edge_id].state == 'dormant'
    assert len(result.changes) == 1 and result.changes[0]['causes'][0]['kind'] == 'clock'


def test_late_runtime_valid_and_recorded_views_and_three_archive_rebuilds():
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    first = evidence('otel_span', at=T2)
    engine.ingest(first, recorded_at=T3)
    assert not graph.as_of('2026-11-27T14:30:00Z', '2026-11-27T15:00:00Z')
    assert len(graph.as_of('2026-11-27T14:30:00Z')) == 1
    original_assertions = graph.assertions
    second = evidence('ci_static', at=T0)
    engine.ingest(second, recorded_at='2026-11-27T17:00:00Z')
    assert graph.assertions[:len(original_assertions)] == original_assertions
    assert not graph.as_of(T1, T3)
    assert len(graph.as_of(T1)) == 1
    live = graph.graph_hash(T2)
    for _ in range(3):
        rebuilt = BitemporalGraph()
        replay = MergeEngine(graph=rebuilt)
        replay.ingest(first, recorded_at=T3)
        replay.ingest(second, recorded_at='2026-11-27T17:00:00Z')
        assert rebuilt.graph_hash(T2) == live


def test_failed_graph_transaction_preserves_cache_and_can_retry():
    class Unavailable:
        def load(self): return []
        def append(self, assertions): raise ConnectionError('graph unavailable')
    engine = MergeEngine(graph=BitemporalGraph(Unavailable()))
    with pytest.raises(ConnectionError): engine.ingest(evidence())
    assert not engine.snapshot() and not engine.graph.assertions
    engine.graph.store = None
    assert len(engine.ingest(evidence()).changes) == 1


def test_C6_rewrite_only_changes_citations_not_lineage():
    engine = MergeEngine()
    first = evidence(unit=True, target='product-catalog', ref='archive://python/source')
    engine.replace_unit(snap([first]))
    rewritten = evidence(unit=True, target='product-catalog', ref='archive://java/source', at=T1)
    result = engine.replace_unit(snap([rewritten], 2, T1))
    assert not result.changes
    assert next(iter(engine.snapshot().values())).evidence_refs == ('archive://java/source',)


def test_C3_C4_exact_orm_edges_and_C5_retirement_retain_history():
    golden = json.loads((ROOT / 'fixtures/otel-demo-3.1.0/golden-graph.json').read_text())
    orm = [e for e in golden['field_edges'] if e['to'].startswith('postgres://')]
    assert len(orm) == 17
    old_edges = [{**e, 'to': e['to'].replace('.accounting.', '.public.')} for e in orm]
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    opened = engine.replace_unit(snap([fixture_event(e, unit=True) for e in old_edges]))
    assert len(opened.changes) == 17 and all(e['change'] == 'opened' for e in opened.changes)
    assert {parse(e['edge']['to']).dataset for e in opened.changes} == {
        'postgres://astronomy-db/astronomy_db.public.' + name for name in ['order', 'orderitem', 'shipping']}
    moved = engine.replace_unit(snap([fixture_event(e, unit=True, at=T1) for e in orm], 2, T1))
    assert moved.held
    moved = engine.release_hold(moved.operation_id, owner_action_id='C4-approved-schema-move')
    assert sum(e['change'] == 'opened' for e in moved.changes) == 17
    assert sum(e['change'] == 'closed' for e in moved.changes) == 17
    added = LineageDiff(graph).between('2026-11-27T11:00:00Z', T0, recorded_at=T2,
                                      causes=[{'kind': 'change_event', 'ref': 'C3'}], scope='postgres://')['added']
    assert len([urn for urn in added if '#' not in urn]) == 3
    assert len([urn for urn in added if '#' in urn]) == 17
    assert all('.public.' in row['edge']['to'] for row in graph.as_of(T0).values())
    assert all('.accounting.' in row['edge']['to'] for row in graph.as_of(T1).values())
    assert len(graph.during(T0, T1)) == 34
    reviews = MergeEngine(graph=BitemporalGraph())
    reviews.replace_unit(snap([evidence(unit=True, target='product-reviews')]))
    retirement = reviews.replace_unit(snap([], 2, T1))
    assert retirement.changes[0]['change'] == 'closed'
    assert retirement.changes[0]['current']['state'] == 'retired'
    assert len(reviews.graph.as_of(T0)) == 1 and not reviews.graph.as_of(T1)
    diff = LineageDiff(reviews.graph)
    diff.register_commit('before-C5', T0)
    diff.register_commit('C5', T1)
    assert diff.between('before-C5', 'C5', recorded_at=T2, causes=[{'kind': 'change_event', 'ref': 'C5'}])['events'][0]['change'] == 'closed'


def test_repeated_runtime_observation_does_not_leak_into_valid_past():
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    engine.ingest(evidence('otel_span', at=T0, ref='archive://first'), recorded_at=T0)
    engine.ingest(evidence('otel_span', at=T1, ref='archive://second'), recorded_at=T1)
    assert next(iter(graph.as_of(T0).values()))['evidenceRefs'] == ['archive://first']
    assert engine.graph_hash(T0) == graph.graph_hash(T0)
    assert engine.graph_hash(T1) == graph.graph_hash(T1)
    assert next(iter(graph.as_of(T1).values()))['validFrom'] == timestamp(T0)


def test_out_of_order_recorded_times_correct_later_knowledge_atomically():
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    engine.ingest(evidence('otel_span', at=T1, ref='archive://second'), recorded_at=T1)
    immutable = graph.assertions
    engine.ingest(evidence('otel_span', at=T0, ref='archive://first'), recorded_at=T0)
    assert graph.assertions[:len(immutable)] == immutable
    assert engine.graph_hash(T0, T0) == graph.graph_hash(T0, T0)
    assert engine.graph_hash(T1, T1) == graph.graph_hash(T1, T1)
    assert next(iter(graph.as_of(T1).values()))['evidenceRefs'] == ['archive://first', 'archive://second']


def test_late_same_source_opens_earlier_interval_and_emits_material_change():
    engine = MergeEngine(graph=BitemporalGraph())
    engine.ingest(evidence('otel_span', at=T1, ref='archive://second'), recorded_at=T1)
    earlier = engine.ingest(evidence('otel_span', at=T0, ref='archive://first'), recorded_at=T2)
    assert len(earlier.changes) == 1
    assert earlier.changes[0]['change'] == 'opened'
    assert earlier.changes[0]['current']['validFrom'] == timestamp(T0)
    assert engine.graph_hash(T0) == engine.graph.graph_hash(T0)


HASH_A = 'sha256:11111111'
HASH_B = 'sha256:22222222'
HASH_C = 'sha256:33333333'
HASH_RUNTIME = 'sha256:44444444'


def expression_evidence(expression_hash=HASH_A, *, at=T0, unit=UNIT, producer=PRODUCER,
                        source='ci_static', ref=None):
    element = {'from': 'amount', 'to': 'amount', 'class': 'DIRECT', 'subtype': 'TRANSFORMATION'}
    if expression_hash is not None:
        element['exprHash'] = expression_hash
    event = evidence(source, at=at, unit=source not in PARAMS['evidence']['runtime_sources'], elements=[element],
                     ref=ref or f'archive://expressions/{expression_hash}/{at}/{unit}/{producer}')
    event['producer'] = producer
    if 'unit' in event:
        event['unit']['urn'] = unit
    return event


def assert_change_schema(events):
    validator = Draft202012Validator(schema('factory/specs/changes/interfaces/lineage-changes.schema.json'),
                                    format_checker=FormatChecker())
    for event in events:
        validator.validate(event)


def test_expression_replacement_emits_one_change_and_keeps_immutable_bitemporal_history():
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    original = snap([expression_evidence()])
    opened = engine.replace_unit(original)
    old_assertions = graph.assertions
    rewritten = UnitSnapshot.build(UNIT, PRODUCER, 2, T1, T2,
                                   [expression_evidence(HASH_B, at=T1, ref='archive://rewrite')])
    result = engine.replace_unit(rewritten)
    assert not result.held and len(result.changes) == 1
    change = result.changes[0]
    assert change['change'] == 'expression_changed'
    assert change['previous']['expressionHashes'] == [HASH_A]
    assert change['current']['expressionHashes'] == [HASH_B]
    assert change['previous']['confidence'] == change['current']['confidence'] == 0.6
    assert change['previous']['state'] == change['current']['state'] == 'probable'
    assert change['previous']['validTo'] == change['current']['validFrom'] == timestamp(T1)
    assert change['causes'] == [{'kind': 'evidence', 'ref': 'archive://rewrite'}]
    assert graph.assertions[:len(old_assertions)] == old_assertions
    assert next(iter(graph.as_of(T0, T2).values()))['expressionHashes'] == [HASH_A]
    assert next(iter(graph.as_of(T1, T1).values()))['expressionHashes'] == [HASH_A]
    assert next(iter(graph.as_of(T1, T2).values()))['expressionHashes'] == [HASH_B]
    assert len(engine.snapshot()) == 1
    assert_change_schema([*opened.changes, *result.changes])
    for snapshot in (original, rewritten, original):
        duplicate = engine.replace_unit(snapshot)
        assert duplicate.duplicate and not duplicate.changes
    diff = LineageDiff(graph).between(T0, T1, recorded_at=T2,
                                      causes=[{'kind': 'evidence', 'ref': 'archive://rewrite'}])
    assert len(diff['events']) == 1 and diff['events'][0]['change'] == 'expression_changed'


@pytest.mark.parametrize('first,second', [(HASH_A, None), (None, HASH_B)])
def test_expression_hash_loss_and_first_known_hash_are_material(first, second):
    engine = MergeEngine(graph=BitemporalGraph())
    engine.replace_unit(snap([expression_evidence(first)]))
    result = engine.replace_unit(snap([expression_evidence(second, at=T1)], 2, T1))
    assert not result.held and len(result.changes) == 1
    change = result.changes[0]
    assert change['change'] == 'expression_changed'
    assert change['previous']['expressionHashes'] == ([first] if first else [])
    assert change['current']['expressionHashes'] == ([second] if second else [])
    assert len(engine.snapshot()) == 1
    assert_change_schema(result.changes)


@pytest.mark.parametrize('independent_unit,independent_producer', [
    ('unit://git/demo/other.sql', PRODUCER),
    (UNIT, 'lineage-test/independent@1.0.0'),
])
def test_expression_alternatives_remain_owned_by_independent_units_and_extractors(independent_unit, independent_producer):
    engine = MergeEngine(graph=BitemporalGraph())
    original = snap([expression_evidence()])
    independent = snap([expression_evidence(HASH_B, unit=independent_unit, producer=independent_producer)],
                       unit=independent_unit, producer=independent_producer)
    engine.replace_unit(original)
    engine.replace_unit(independent)
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_A, HASH_B)
    # Extractor version changes keep the same ownership key and remove its old hash.
    upgraded = 'lineage-test/core@2.0.0'
    result = engine.replace_unit(snap([expression_evidence(HASH_C, at=T1, producer=upgraded)],
                                     2, T1, producer=upgraded))
    assert len(result.changes) == 1 and result.changes[0]['change'] == 'expression_changed'
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_B, HASH_C)
    assert next(iter(engine.snapshot().values())).confidence == 0.6
    removed = engine.replace_unit(snap([], 3, T2, producer=upgraded))
    assert removed.changes[0]['current']['expressionHashes'] == [HASH_B]
    assert len(engine.snapshot()) == 1
    assert_change_schema([*result.changes, *removed.changes])


def test_overlapping_expression_support_does_not_duplicate_or_remove_other_owner():
    engine = MergeEngine()
    other = 'unit://git/demo/other.sql'
    engine.replace_unit(snap([expression_evidence()]))
    unchanged = engine.replace_unit(snap([expression_evidence(unit=other)], unit=other))
    assert not unchanged.changes
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_A,)
    engine.replace_unit(snap([expression_evidence(HASH_C, at=T1)], 2, T1))
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_A, HASH_C)
    removed = engine.replace_unit(snap([], 3, T2))
    assert removed.changes[0]['current']['expressionHashes'] == [HASH_A]


def test_runtime_expression_support_is_additive_and_survives_static_replacements():
    engine = MergeEngine(graph=BitemporalGraph())
    engine.replace_unit(snap([expression_evidence()]))
    runtime = expression_evidence(HASH_RUNTIME, source='otel_span', ref='archive://runtime/first')
    observed = engine.ingest(runtime)
    assert observed.changes[0]['change'] == 'expression_changed'
    assert observed.changes[0]['current']['expressionHashes'] == [HASH_A, HASH_RUNTIME]
    assert observed.changes[0]['current']['confidence'] == 0.96
    rewritten = engine.replace_unit(snap([expression_evidence(HASH_B, at=T1)], 2, T1))
    assert rewritten.changes[0]['current']['expressionHashes'] == [HASH_B, HASH_RUNTIME]
    assert rewritten.changes[0]['current']['state'] == 'confirmed'
    repeated = engine.ingest(expression_evidence(HASH_RUNTIME, source='otel_span', at=T1,
                                                ref='archive://runtime/repeated'))
    assert not repeated.changes
    next_runtime = engine.ingest(expression_evidence(HASH_C, source='otel_span', at=T2,
                                                    ref='archive://runtime/alternative'))
    assert next_runtime.changes[0]['current']['expressionHashes'] == [HASH_B, HASH_C, HASH_RUNTIME]
    deleted = engine.replace_unit(snap([], 3, T3))
    edge = next(iter(engine.snapshot().values()))
    assert edge.expression_hashes == (HASH_C, HASH_RUNTIME)
    assert edge.confidence == 0.9 and edge.state == 'confirmed'
    assert deleted.changes[0]['change'] == 'expression_changed'
    assert_change_schema([*observed.changes, *rewritten.changes, *next_runtime.changes, *deleted.changes])


def test_expression_sets_are_deterministic_under_delivery_order_and_archive_rebuild():
    other = 'unit://git/demo/other.sql'
    records = [snap([expression_evidence()]),
               snap([expression_evidence(HASH_B, unit=other)], unit=other),
               snap([expression_evidence(HASH_C, at=T1)], 2, T1),
               snap([], 3, T2)]
    live = MergeEngine(graph=BitemporalGraph())
    for record in records:
        live.replace_unit(record)
    rng = random.Random(1214)
    for _ in range(12):
        order = list(records)
        rng.shuffle(order)
        rebuilt = MergeEngine(graph=BitemporalGraph())
        for record in order:
            result = rebuilt.replace_unit(record)
            assert not result.held
            assert_change_schema(result.changes)
        for valid_at in (T0, T1, T2):
            assert rebuilt.graph_hash(valid_at) == live.graph_hash(valid_at)
            assert rebuilt.graph.graph_hash(valid_at) == live.graph.graph_hash(valid_at)
        assert next(iter(rebuilt.snapshot().values())).expression_hashes == (HASH_B,)


def test_expression_event_schema_rejects_invalid_or_duplicate_hashes():
    from jsonschema import ValidationError
    engine = MergeEngine()
    engine.replace_unit(snap([expression_evidence()]))
    event = engine.replace_unit(snap([expression_evidence(HASH_B, at=T1)], 2, T1)).changes[0]
    assert_change_schema([event])
    for invalid in [[HASH_B, HASH_B], ['sha256:xyzxyzxyz'], ['md5:12345678'], ['sha256:123']]:
        broken = copy.deepcopy(event)
        broken['current']['expressionHashes'] = invalid
        with pytest.raises(ValidationError):
            assert_change_schema([broken])
    # Existing history without the optional field means the empty set.
    before = next(iter(engine.snapshot().values())).as_dict()
    before.pop('expressionHashes')
    after = {**before, 'expressionHashes': []}
    assert not diff_snapshots({'edge': before}, {'edge': after}, T2, [{'kind': 'evidence', 'ref': 'archive://same'}])


def test_expression_write_failure_preserves_previous_generation_and_retries():
    class FailedStore:
        def append(self, assertions):
            raise ConnectionError('graph write failed')
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    engine.replace_unit(snap([expression_evidence()]))
    previous_hash, assertions = engine.graph_hash(), graph.assertions
    replacement = snap([expression_evidence(HASH_B, at=T1)], 2, T1)
    graph.store = FailedStore()
    with pytest.raises(ConnectionError):
        engine.replace_unit(replacement)
    assert engine.graph_hash() == previous_hash and graph.assertions == assertions
    graph.store = None
    result = engine.replace_unit(replacement)
    assert result.changes[0]['change'] == 'expression_changed' and not result.duplicate
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_B,)


def test_expression_rewrites_do_not_bypass_mass_close_hold():
    original_elements = [{**element, 'exprHash': HASH_A} for element in fields(17)]
    next_elements = [{**element, 'exprHash': HASH_B} for element in fields(5)]
    engine = MergeEngine(graph=BitemporalGraph())
    engine.replace_unit(snap([evidence(unit=True, elements=original_elements)]))
    previous_hash = engine.graph_hash()
    held = engine.replace_unit(snap([evidence(unit=True, elements=next_elements, at=T1)], 2, T1))
    assert held.held and held.alert['reason'] == 'mass_close_hold'
    assert engine.graph_hash() == previous_hash
    released = engine.release_hold(held.operation_id, owner_action_id='owner/approved-reduction')
    assert sum(event['change'] == 'closed' for event in released.changes) == 12
    assert sum(event['change'] == 'expression_changed' for event in released.changes) == 5
    assert all(edge.expression_hashes == (HASH_B,) for edge in engine.snapshot().values())
    assert_change_schema(released.changes)


def test_expression_event_versioning_preserves_legacy_contract():
    from jsonschema import ValidationError
    plain = MergeEngine()
    legacy = plain.ingest(evidence()).changes[0]
    assert legacy['schemaVersion'] == '1'
    assert 'expressionHashes' not in legacy['current']
    assert_change_schema([legacy])
    modern = MergeEngine()
    opened = modern.replace_unit(snap([expression_evidence()])).changes[0]
    lost = modern.replace_unit(snap([expression_evidence(None, at=T1)], 2, T1)).changes[0]
    for event in (opened, lost):
        assert event['schemaVersion'] == '2'
        assert 'expressionHashes' in event['current']
        if 'previous' in event:
            assert 'expressionHashes' in event['previous']
        assert_change_schema([event])
        mislabeled = {**event, 'schemaVersion': '1'}
        with pytest.raises(ValidationError):
            assert_change_schema([mislabeled])
    assert lost['current']['expressionHashes'] == []
    incompatible_legacy = copy.deepcopy(legacy)
    incompatible_legacy['current']['expressionHashes'] = []
    with pytest.raises(ValidationError):
        assert_change_schema([incompatible_legacy])


def test_expression_set_order_and_duplicate_support_do_not_change_lineage():
    engine = MergeEngine()
    event = expression_evidence()
    event['edge']['elements'] = [
        {**event['edge']['elements'][0], 'exprHash': expression_hash}
        for expression_hash in (HASH_C, HASH_A, HASH_C, HASH_B)
    ]
    opened = engine.replace_unit(snap([event]))
    assert opened.changes[0]['current']['expressionHashes'] == [HASH_A, HASH_B, HASH_C]
    reordered = copy.deepcopy(event)
    reordered['edge']['elements'].reverse()
    refreshed = engine.replace_unit(snap([reordered], 2, T1))
    assert not refreshed.changes
    assert next(iter(engine.snapshot().values())).expression_hashes == (HASH_A, HASH_B, HASH_C)


def test_durable_hold_release_after_runtime_drift_retains_original_id_and_owner_cause():
    baseline = snap([evidence(unit=True, elements=fields(10))])
    deletion = snap([], 2, T1)
    original = MergeEngine()
    original.replace_unit(baseline)
    held = original.replace_unit(deletion)
    assert held.held
    runtime = evidence('otel_span', at=T1, elements=fields(10), ref='archive://runtime/after-hold')
    # On restart only accepted operations are replayed. Runtime now supports every
    # edge, so recalculating the old guard would no longer produce a held result.
    restarted = MergeEngine(graph=BitemporalGraph())
    restarted.replace_unit(baseline)
    restarted.ingest(runtime, recorded_at=T2)
    approval = replace(deletion, recorded_at=T3)
    result = restarted.apply_released_snapshot(approval, owner_action_id='approval/durable-1',
                                               held_operation_id=held.operation_id)
    assert result.operation_id == held.operation_id and not result.held and not result.duplicate
    assert len(result.changes) == 10
    assert all(change['change'] == 'confidence_changed' for change in result.changes)
    assert all(change['recordedAt'] == timestamp(T3) for change in result.changes)
    assert all(change['causes'] == [{'kind': 'owner_action', 'ref': 'approval/durable-1'}]
               for change in result.changes)
    assert all(edge.sources == ('otel_span',) and edge.confidence == 0.9 for edge in restarted.snapshot().values())
    assert all(row['confidence'] == 0.96 for row in restarted.graph.as_of(T1, T2).values())
    assert all(row['confidence'] == 0.9 for row in restarted.graph.as_of(T1, T3).values())
    assert all(row['confidence'] == 0.6 for row in restarted.graph.as_of(T0, T3).values())
    assert_change_schema(result.changes)
    assertions = restarted.graph.assertions
    duplicate = restarted.apply_released_snapshot(replace(approval, recorded_at='2026-11-27T17:00:00Z'),
                                                  owner_action_id='approval/durable-1', held_operation_id=held.operation_id)
    assert duplicate.duplicate and not duplicate.changes
    assert restarted.graph.assertions == assertions


@pytest.mark.parametrize('mutation', [
    {'complete': False}, {'digest': 'sha256:' + '0' * 64}, {'generation': 3}, {'valid_at': T2},
])
def test_durable_release_revalidates_snapshot_content_and_original_identity(mutation):
    engine = MergeEngine()
    engine.replace_unit(snap([evidence(unit=True, elements=fields(10))]))
    deletion = snap([], 2, T1)
    held = engine.replace_unit(deletion)
    before = engine.graph_hash()
    with pytest.raises(ValueError):
        engine.apply_released_snapshot(replace(deletion, recorded_at=T3, **mutation),
                                       owner_action_id='approval/invalid', held_operation_id=held.operation_id)
    assert engine.graph_hash() == before
    with pytest.raises(ValueError):
        engine.apply_released_snapshot(replace(deletion, recorded_at=T3), owner_action_id=' ',
                                       held_operation_id=held.operation_id)


def test_durable_release_cannot_bypass_a_completed_generation_conflict():
    engine = MergeEngine()
    initial = evidence(unit=True, elements=fields(10))
    engine.replace_unit(snap([initial]))
    deletion = snap([], 2, T1)
    held = engine.replace_unit(deletion)
    engine.replace_unit(snap([initial], 2, T1))
    before = engine.graph_hash()
    with pytest.raises(ValueError, match='already completed unit generation'):
        engine.apply_released_snapshot(replace(deletion, recorded_at=T3), owner_action_id='approval/conflict',
                                       held_operation_id=held.operation_id)
    assert engine.graph_hash() == before


def test_durable_release_graph_failure_preserves_hold_and_retries_once():
    class UnavailableStore:
        def append(self, assertions):
            raise ConnectionError('graph temporarily unavailable')
    graph = BitemporalGraph()
    engine = MergeEngine(graph=graph)
    engine.replace_unit(snap([evidence(unit=True, elements=fields(10))]))
    deletion = snap([], 2, T1)
    held = engine.replace_unit(deletion)
    before, assertions = engine.graph_hash(), graph.assertions
    approval = replace(deletion, recorded_at=T3)
    graph.store = UnavailableStore()
    with pytest.raises(ConnectionError):
        engine.apply_released_snapshot(approval, owner_action_id='approval/retry', held_operation_id=held.operation_id)
    assert engine.graph_hash() == before and graph.assertions == assertions
    assert engine.replace_unit(deletion).held
    graph.store = None
    released = engine.apply_released_snapshot(approval, owner_action_id='approval/retry', held_operation_id=held.operation_id)
    assert not released.duplicate and len(released.changes) == 10
    assert all(change['change'] == 'closed' for change in released.changes)
    assert not engine.snapshot()
    assert len(graph.as_of(T1, T2)) == 10 and not graph.as_of(T1, T3)
