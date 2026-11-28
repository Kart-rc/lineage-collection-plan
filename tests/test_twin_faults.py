import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("twin_flip", ROOT / "twin/flip.py")
flip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flip)


@pytest.fixture
def state(tmp_path):
    (tmp_path / "flags").mkdir()
    document = {"flags": {
        "productCatalogFailure": {"defaultVariant": "off", "variants": {"off": False, "on": True},
                                  "targeting": {"if": [{"==": [{"var": "product_id"}, "synthetic-product"]}, "off", "off"]}},
        "paymentFailure": {"defaultVariant": "off", "variants": {"off": 0, "50%": 0.5}},
    }}
    (tmp_path / "flags/demo.flagd.json").write_text(json.dumps(document))
    return tmp_path


def test_targeted_flag_mutates_true_branch_and_preserves_default(state):
    event = flip.apply(state, "flag", "productCatalogFailure", "on")
    flag = json.loads((state / "flags/demo.flagd.json").read_text())["flags"]["productCatalogFailure"]
    assert flag["defaultVariant"] == "off"
    assert flag["targeting"]["if"][1:] == ["on", "off"]
    assert event["change"]["from"] == "off"
    assert json.loads((state / "changes.jsonl").read_text()) == event
    Draft202012Validator(json.loads(flip.SCHEMA.read_text()), format_checker=FormatChecker()).validate(event)


def test_regular_flag_roundtrip_logged(state):
    flip.apply(state, "flag", "paymentFailure", "50%")
    second = flip.apply(state, "flag", "paymentFailure", "off")
    assert second["change"]["from"] == "50%"
    assert len((state / "changes.jsonl").read_text().splitlines()) == 2


@pytest.mark.parametrize("rule", [{"and": []}, {"if": [True, {"nested": "off"}, "off"]}])
def test_unsupported_targeting_never_falls_back_to_default(rule):
    document = {"flags": {"flag": {"targeting": rule, "defaultVariant": "off", "variants": {"off": False, "on": True}}}}
    with pytest.raises(ValueError, match="Unsupported targeting"):
        flip.update_flag(document, "flag", "on")
    assert document["flags"]["flag"]["defaultVariant"] == "off"


def test_unknown_variant_does_not_change_file_or_append_event(state):
    original = (state / "flags/demo.flagd.json").read_bytes()
    with pytest.raises(ValueError):
        flip.apply(state, "flag", "paymentFailure", "wrong")
    assert (state / "flags/demo.flagd.json").read_bytes() == original
    assert not (state / "changes.jsonl").exists()


@pytest.mark.parametrize("action", ["stop", "start"])
def test_service_command_is_project_scoped_and_envelope_valid(state, monkeypatch, action):
    commands = []
    monkeypatch.setattr(flip.subprocess, "run", lambda args, **kwargs: commands.append(args))
    event = flip.apply(state, action, "accounting")
    assert commands[0][0:4] == ["docker", "compose", "--project-name", "lineage-twin"]
    assert commands[0][-2:] == [action, "accounting"]
    assert event["change"]["kind"] == f"service_{action}"
    Draft202012Validator(json.loads(flip.SCHEMA.read_text()), format_checker=FormatChecker()).validate(event)


def test_failed_service_action_records_only_intent(state, monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "docker")
    monkeypatch.setattr(flip.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        flip.apply(state, "stop", "accounting")
    assert (state / "change-intents.jsonl").exists()
    assert not (state / "changes.jsonl").exists()


def test_platform_services_cannot_be_mutated_by_fault_tool(state):
    with pytest.raises(ValueError):
        flip.apply(state, "stop", "lineage-neo4j")
