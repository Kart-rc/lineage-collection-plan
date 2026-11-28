"""G1 compatibility and negative contract examples; no implementation imports."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def validator(path):
    schema = read(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


CHANGES = validator('factory/specs/changes/interfaces/lineage-changes.schema.json')
SNAPSHOTS = validator('factory/specs/evidence/interfaces/unit-snapshot.schema.json')


def expression_event():
    event = read('factory/specs/changes/example-condition-activated.json')
    event['schemaVersion'] = '2'
    event['change'] = 'expression_changed'
    event['previous']['expressionHashes'] = ['sha256:' + 'a' * 64]
    event['current']['expressionHashes'] = ['sha256:' + 'b' * 64]
    return event


def snapshot():
    unit = read('factory/specs/evidence/examples/golden-field-edge.json')['unit']
    return dict(schemaVersion='1', eventType='UNIT_SNAPSHOT_COMPLETE',
                route=dict(repository='opentelemetry-demo', stage='merged', pr=None),
                unit=unit, producer='fixture@1.0.0', generation=1, requestId='first',
                validAt='2026-11-28T12:00:00Z', complete=True, deleted=False,
                eventCount=0, eventsHash='sha256:' + 'a' * 64,
                objectRef='snapshot://sha256/' + 'b' * 64)


def test_legacy_condition_event_remains_valid():
    CHANGES.validate(read('factory/specs/changes/example-condition-activated.json'))


@pytest.mark.parametrize('hashes', [['sha256:' + 'b' * 64], []])
def test_v2_expression_rewrite_and_loss_are_representable(hashes):
    event = expression_event()
    event['current']['expressionHashes'] = hashes
    CHANGES.validate(event)


@pytest.mark.parametrize('failure', ['v1', 'missing_previous', 'missing_current_hashes', 'duplicate_hashes'])
def test_invalid_expression_contract_is_rejected(failure):
    event = expression_event()
    if failure == 'v1':
        event['schemaVersion'] = '1'
    elif failure == 'missing_previous':
        del event['previous']
    elif failure == 'missing_current_hashes':
        del event['current']['expressionHashes']
    else:
        event['current']['expressionHashes'] *= 2
    assert list(CHANGES.iter_errors(event))


def test_complete_empty_deleted_and_pr_manifests_are_representable():
    event = snapshot()
    SNAPSHOTS.validate(event)
    event['deleted'] = True
    SNAPSHOTS.validate(event)
    event['route'].update(stage='proposed', pr=42)
    event['unit']['pr'] = 42
    SNAPSHOTS.validate(event)


@pytest.mark.parametrize('failure', ['incomplete', 'nonempty_deleted', 'merged_pr', 'missing_pr', 'zero_generation', 'path_escape'])
def test_invalid_snapshot_contract_is_rejected(failure):
    event = deepcopy(snapshot())
    if failure == 'incomplete':
        event['complete'] = False
    elif failure == 'nonempty_deleted':
        event.update(deleted=True, eventCount=1)
    elif failure == 'merged_pr':
        event['route']['pr'] = 42
    elif failure == 'missing_pr':
        event['route']['stage'] = 'proposed'
    elif failure == 'zero_generation':
        event['generation'] = 0
    else:
        event['objectRef'] = 'snapshot://sha256/../../elsewhere'
    assert list(SNAPSHOTS.iter_errors(event))
