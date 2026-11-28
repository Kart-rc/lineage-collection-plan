"""WP-18 / XC-7, XC-8, IN-1, IN-7 and IA-6 visible candidate checks."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from lineage.ci import MANIFEST_SCHEMA, main, read_config, scan
from lineage.config import repository_root, schema
from lineage.plugins import (InputRef, PluginRegistry, RepoView, StubExtractor,
                             WorkerFailure, WorkerTimeout, check_conformance,
                             isolated, stub_fixture)

FIXTURES = repository_root() / "fixtures/otel-demo-3.1.0/onboarding"


def git(directory, *arguments):
    return subprocess.check_output(["git", "-C", str(directory), *arguments], stderr=subprocess.DEVNULL).decode().strip()


def commit(directory, message="fixture"):
    git(directory, "add", ".")
    git(directory, "-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture", "commit", "-qm", message)
    return git(directory, "rev-parse", "HEAD")


@pytest.fixture
def demo(tmp_path):
    directory = tmp_path / "repo"
    directory.mkdir()
    git(directory, "init", "-q")
    content = (FIXTURES / "opentelemetry-demo.lineage.yaml").read_text()
    (directory / ".lineage.yaml").write_text(content)
    (directory / ".gitignore").write_text(".lineage-state/\n.lineage-out/\n")
    config = yaml.safe_load(content)
    for item in config["services"]:
        path = directory / item["path"] / "main.go"
        path.parent.mkdir(parents=True)
        path.write_text("package main\n")
    for item in config["schemas"]:
        path = directory / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("schema example\n")
    return directory, commit(directory)


def run(demo, tmp_path, **kwargs):
    directory, sha = demo
    return scan(repository_dir=directory, stage="merged", commit=sha, out_dir=tmp_path / "out", stub=True, **kwargs)


@pytest.mark.parametrize("name", ["opentelemetry-demo", "otel-orders-dbt"])
def test_onboarding_valid_examples(name, capsys):
    path = FIXTURES / (name + ".lineage.yaml")
    assert read_config(path.read_bytes())[1] == []
    assert main(["validate", "--config", str(path)]) == 0
    assert "configuration valid" in capsys.readouterr().out


@pytest.mark.parametrize("name,field", [
    ("missing-owner", "owner"), ("service-name-not-runtime-form", "services[0].name"),
    ("unknown-extractor", "services[0].extractors[0]"), ("over-budget", "build.max_minutes"),
    ("nothing-to-scan", "services, schemas or projects"),
])
def test_invalid_examples_name_fields_and_fail_open(name, field, capsys):
    path = FIXTURES / "invalid" / (name + ".lineage.yaml")
    assert any(field in error for error in read_config(path.read_bytes())[1])
    assert main(["validate", "--config", str(path)]) == 0
    assert field in capsys.readouterr().out


def test_git_view_uses_commit_not_worktree_and_excludes_symlinks(demo):
    directory, sha = demo
    path = directory / "src/checkout/main.go"
    path.write_text("mutable worktree text")
    (directory / "unsafe").symlink_to("/etc/passwd")
    view = RepoView.from_git(directory, sha)
    assert view.read_text("src/checkout/main.go") == "package main\n"
    assert "unsafe" not in view.files()
    assert path.read_text() == "mutable worktree text"
    with pytest.raises(ValueError):
        view.read_bytes("../secret")


def test_stub_first_rescan_and_pr_isolation(demo, tmp_path):
    directory, sha = demo
    first = run(demo, tmp_path)
    assert first["record"]["errors"] == []
    assert first["manifest"]["outcome"] == "emitted"
    assert len(first["manifest"]["units"]) == 16
    assert all(unit["status"] == "extracted" for unit in first["manifest"]["units"])
    Draft202012Validator(schema(MANIFEST_SCHEMA), format_checker=FormatChecker()).validate(first["manifest"])
    again = run(demo, tmp_path)
    assert all(unit["status"] == "unchanged" for unit in again["manifest"]["units"])
    before = (directory / ".lineage-state/opentelemetry-demo/candidate-merged.json").read_bytes()
    (directory / "src/checkout/main.go").write_text("package checkout\n")
    proposed = commit(directory, "checkout only")
    result = scan(repository_dir=directory, stage="proposed", commit=proposed, base=sha, pr=12,
                  out_dir=tmp_path / "pr", stub=True)
    rows = result["manifest"]["units"]
    assert sum(row["status"] == "extracted" for row in rows) == 1
    assert sum(row["status"] == "unchanged" for row in rows) == 15
    assert next(row for row in rows if row["status"] == "extracted")["urn"].endswith("src/checkout")
    staging = json.loads((tmp_path / "pr/candidate-snapshots.json").read_text())
    assert staging["route"] == {"repository": "opentelemetry-demo", "stage": "proposed", "pr": 12}
    assert all(event["unit"]["pr"] == 12 for snapshot in staging["snapshots"] for event in snapshot["events"])
    assert all(event["evidence"]["weight"] == 0.6 for snapshot in staging["snapshots"] for event in snapshot["events"])
    assert before == (directory / ".lineage-state/opentelemetry-demo/candidate-merged.json").read_bytes()
    assert (directory / f".lineage-state/overlays/opentelemetry-demo/12/{proposed}/candidate-snapshots.json").is_file()


def test_unavailable_never_updates_state_and_prepares_alert(demo, tmp_path):
    result = run(demo, tmp_path, transport="unavailable")
    assert result["manifest"]["outcome"] == "unavailable"
    assert result["record"]["alerts"][0]["code"] == "LINEAGE_CHECK_UNAVAILABLE"
    assert not (demo[0] / ".lineage-state/opentelemetry-demo/candidate-merged.json").exists()
    comment = json.loads((tmp_path / "out/comment.json").read_text())
    assert comment == {"message": "lineage check unavailable", "posted": False}
    assert main(["scan", "--repo", str(demo[0]), "--stage", "merged", "--commit", demo[1], "--stub",
                 "--transport", "unavailable", "--out", str(tmp_path / "cli")]) == 0


def test_stale_state_is_ignored(demo, tmp_path):
    run(demo, tmp_path)
    cache = demo[0] / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    value = json.loads(cache.read_text())
    value["commit"] = "f" * 40
    cache.write_text(json.dumps(value))
    result = run(demo, tmp_path)
    assert all(row["status"] == "extracted" for row in result["manifest"]["units"])
    assert "state: stale merged cache ignored" in result["record"]["errors"]


def test_corrupt_cached_snapshot_is_reextracted(demo, tmp_path):
    run(demo, tmp_path)
    cache = demo[0] / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    value = json.loads(cache.read_text())
    value["units"]["unit://git/opentelemetry-demo/src/checkout"]["snapshot"]["events"] = []
    cache.write_text(json.dumps(value))
    result = run(demo, tmp_path)
    assert sum(row["status"] == "extracted" for row in result["manifest"]["units"]) == 1


def test_older_merged_scan_cannot_roll_back_cache(demo, tmp_path):
    directory, older = demo
    run(demo, tmp_path)
    (directory / "src/checkout/main.go").write_text("package changed\n")
    newer = commit(directory, "later merged change")
    scan(repository_dir=directory, stage="merged", commit=newer, stub=True, out_dir=tmp_path / "newer")
    cache = directory / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    before = cache.read_bytes()
    stale = run((directory, older), tmp_path)
    assert stale["manifest"]["outcome"] == "unavailable"
    assert before == cache.read_bytes()


class SchemaDependentStub(StubExtractor):
    def inputs(self, unit):
        return [InputRef("pb/demo.proto")] if unit.name == "checkout" else []


def registered(plugin=None):
    registry = PluginRegistry()
    assert registry.register(plugin or StubExtractor(), stub_fixture())
    return registry


def test_schema_and_extractor_versions_invalidate_units(demo, tmp_path):
    directory, sha = demo
    registry = registered(SchemaDependentStub())
    # Explicit config extractors are production names; fixture selection is opt-in.
    config = yaml.safe_load((directory / ".lineage.yaml").read_text())
    for service in config["services"]:
        service.pop("extractors", None)
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    sha = commit(directory, "fixture registry")
    first = scan(repository_dir=directory, stage="merged", commit=sha, registry=registry, out_dir=tmp_path / "first")
    assert first["manifest"]["outcome"] == "emitted"
    (directory / "pb/demo.proto").write_text("schema example changed\n")
    changed = commit(directory, "schema dependency")
    result = scan(repository_dir=directory, stage="merged", commit=changed, registry=registry, out_dir=tmp_path / "changed")
    extracted = [row["urn"] for row in result["manifest"]["units"] if row["status"] == "extracted"]
    assert sorted(extracted) == ["unit://git/opentelemetry-demo/pb/demo.proto", "unit://git/opentelemetry-demo/src/checkout"]
    upgraded = SchemaDependentStub()
    upgraded.version = "0.2.0"
    newer = scan(repository_dir=directory, stage="merged", commit=changed, registry=registered(upgraded), out_dir=tmp_path / "newer")
    assert sum(row["status"] == "extracted" for row in newer["manifest"]["units"]) == 16


def test_unclaimed_paths_are_visible_gaps(demo, tmp_path):
    result = scan(repository_dir=demo[0], stage="merged", commit=demo[1], registry=PluginRegistry(), out_dir=tmp_path / "out")
    shipping = next(row for row in result["manifest"]["units"] if row["urn"].endswith("src/shipping"))
    assert shipping["status"] == "opaque"
    assert shipping["reason"] == "UNPARSED_LANGUAGE"
    assert "src/shipping: claimed by no extractor" in result["record"]["errors"]


def test_scan_content_is_deterministic_without_fabricating_timing(demo, tmp_path):
    first = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True,
                 state_dir=tmp_path / "state-one", out_dir=tmp_path / "one")
    second = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True,
                  state_dir=tmp_path / "state-two", out_dir=tmp_path / "two")
    assert (tmp_path / "one/scan-content.json").read_bytes() == (tmp_path / "two/scan-content.json").read_bytes()
    assert first["manifest"]["started"] != second["manifest"]["started"]
    assert first["record"]["published"] is True
    assert first["record"]["graph_accepted"] is False


def test_stub_passes_every_conformance_check():
    assert all(check_conformance(StubExtractor(), stub_fixture()).values())


def test_kernel_isolation_blocks_python_and_direct_syscall_network():
    def socket_call():
        import socket
        socket.socket()
    with pytest.raises(WorkerFailure):
        isolated(socket_call, 1)

    def syscall_call():
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        return [libc.socket(2, 1, 0), ctypes.get_errno()]
    assert isolated(syscall_call, 1) == [-1, 1]


def test_workers_timeout_crash_and_deny_subprocesses():
    def hang():
        while True:
            pass
    with pytest.raises(WorkerTimeout):
        isolated(hang, 0.03)
    with pytest.raises(WorkerFailure):
        isolated(lambda: os._exit(7), 1)
    with pytest.raises(WorkerFailure):
        isolated(lambda: subprocess.run(["true"], check=True), 1)


def test_failing_plugin_is_refused_with_check_names():
    class Broken(StubExtractor):
        def extract(self, unit, ctx):
            raise RuntimeError("must never appear in logs")
    registry = PluginRegistry()
    assert not registry.register(Broken(), stub_fixture())
    assert registry.values() == ()
    assert "golden" in registry.rejected["stub"]


def accuracy_fixture(plugin_name, emitted_names, *, precision, recall, expected_count=10):
    """Synthetic, labeled edges isolate accuracy policy from extractor parsing."""
    from copy import deepcopy

    class AccuracyPlugin(StubExtractor):
        name = plugin_name

        def extract(self, unit, ctx):
            original = next(super().extract(unit, ctx))
            for name in emitted_names if unit.files else ["unreadable"]:
                event = deepcopy(original)
                event["edge"]["to"]["name"] = name
                yield event

    fixture = stub_fixture()
    expected = []
    for index in range(expected_count):
        edge = deepcopy(fixture.expected_edges[0])
        edge["to"]["name"] = f"expected-{index}"
        expected.append(edge)
    return AccuracyPlugin(), replace(fixture, expected_edges=tuple(expected),
                                      minimum_precision=precision, minimum_recall=recall)


@pytest.mark.parametrize("name", ["ef-core-orm", "protobuf"])
def test_deterministic_extractors_cannot_weaken_approved_accuracy_floor(name):
    plugin, fixture = accuracy_fixture(name, [f"expected-{index}" for index in range(9)], precision=0.9, recall=0.9)
    registry = PluginRegistry()
    assert registry.register(plugin, fixture) is False
    assert registry.get(name) is None
    assert "golden" in registry.rejected[name]


def test_deterministic_extractor_measured_recall_must_meet_approved_floor():
    plugin, fixture = accuracy_fixture("ef-core-orm", [f"expected-{index}" for index in range(9)], precision=0.95, recall=0.95)
    checks = check_conformance(plugin, fixture)
    assert checks["golden"] is False
    assert all(passed for name, passed in checks.items() if name != "golden")


def test_model_assisted_uses_wp29_precision_without_inventing_recall_bar():
    # Four true edges and one false edge: precision .80, recall .40. WP-29
    # requires .80 accepted-edge precision and specifies no recall threshold.
    plugin, fixture = accuracy_fixture("model-assisted", ["expected-0", "expected-1", "expected-2", "expected-3", "false-positive"],
                                      precision=0.80, recall=0.0)
    assert all(check_conformance(plugin, fixture).values())
    assert PluginRegistry().register(plugin, fixture)


def test_model_assisted_cannot_weaken_wp29_precision_or_ignore_stricter_fixture():
    plugin, fixture = accuracy_fixture("model-assisted", ["expected-0", "expected-1", "expected-2", "false-positive"],
                                      precision=0.75, recall=0.0)
    assert PluginRegistry().register(plugin, fixture) is False
    # A stronger fixture remains binding even though the approved floor is .80.
    plugin, fixture = accuracy_fixture("model-assisted", ["expected-0", "expected-1", "expected-2", "expected-3", "false-positive"],
                                      precision=0.90, recall=0.0)
    assert check_conformance(plugin, fixture)["golden"] is False


def test_impact_is_honest_and_fail_open(tmp_path, capsys):
    assert main(["impact", "--pr", "1", "--comment", "--out", str(tmp_path)]) == 0
    assert "not implemented" in capsys.readouterr().out
    assert json.loads((tmp_path / "comment.json").read_text())["posted"] is False


def test_bad_cli_and_missing_commit_fail_open(demo, tmp_path):
    assert main(["scan"]) == 0
    result = scan(repository_dir=demo[0], stage="merged", commit="f" * 40, out_dir=tmp_path)
    assert result["manifest"] is None
    assert result["record"]["alerts"]


def test_twenty_scan_overhead_p95_under_approved_limit(demo, tmp_path):
    values = [run(demo, tmp_path)["record"]["timings"]["runner_overhead_ms"] for _ in range(20)]
    assert sorted(values)[18] <= 60_000


def test_local_snapshots_are_consumed_by_core_and_pr_cannot_enter_production(demo, tmp_path):
    from lineage.merge import MergeEngine, UnitSnapshot
    result = run(demo, tmp_path)
    bundle = json.loads((tmp_path / "out/candidate-snapshots.json").read_text())
    engine = MergeEngine()
    for snapshot in bundle["snapshots"]:
        accepted = engine.replace_unit(UnitSnapshot.from_dict(snapshot))
        assert not accepted.held
    assert len(engine.snapshot()) == 16
    scan(repository_dir=demo[0], stage="proposed", commit=demo[1], pr=7, stub=True,
         state_dir=tmp_path / "isolated-pr-state", out_dir=tmp_path / "pr")
    pr_bundle = json.loads((tmp_path / "pr/candidate-snapshots.json").read_text())
    with pytest.raises(ValueError, match="isolated overlay"):
        engine.replace_unit(UnitSnapshot.from_dict(pr_bundle["snapshots"][0]))


@pytest.mark.parametrize("failure", ["crash", "timeout", "schema"])
def test_scan_failure_retains_last_successful_baseline(demo, tmp_path, failure):
    run(demo, tmp_path)
    cache = demo[0] / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    before = cache.read_bytes()

    class FailsOnCheckout(StubExtractor):
        version = "0.2.0"

        def extract(self, unit, ctx):
            if unit.name == "checkout":
                if failure == "crash":
                    os._exit(9)
                if failure == "timeout":
                    while True:
                        pass
                yield {"not": "an envelope"}
                return
            yield from super().extract(unit, ctx)

    registry = registered(FailsOnCheckout())
    # Fixture mode enables the test registry across explicitly listed paths.
    result = scan(repository_dir=demo[0], stage="merged", commit=demo[1], registry=registry,
                  stub=True, unit_seconds=0.1, out_dir=tmp_path / "bad")
    assert result["manifest"]["outcome"] == "emitted_partial"
    checkout = next(row for row in result["manifest"]["units"] if row["urn"].endswith("src/checkout"))
    assert checkout["status"] == ("over_budget" if failure == "timeout" else "failed")
    assert checkout["reason"] == "EXTRACTOR_ERROR"
    assert before == cache.read_bytes()
    completions = json.loads((tmp_path / "bad/completion-manifests.json").read_text())
    assert all(not item["unit"]["urn"].endswith("src/checkout") for item in completions)
    diagnostics = json.loads((tmp_path / "bad/diagnostic-events.json").read_text())
    assert diagnostics[0]["evidence"]["replaces"] == "none"


def test_entrypoint_without_conformance_fixture_is_never_loaded(monkeypatch):
    from lineage import plugins

    class Unknown:
        name = "unknown"

        def load(self):
            raise AssertionError("uncertified code was loaded")

    monkeypatch.setattr(plugins.metadata, "entry_points", lambda *, group: [Unknown()] if group == "lineage_ci.extractors" else [])
    registry = PluginRegistry()
    registry.discover()
    assert registry.values() == ()
    assert registry.rejected == {"unknown": ["missing_conformance_fixture"]}


def test_companion_entrypoint_loads_executable_fixture_without_importing_plugin_in_parent(tmp_path, monkeypatch):
    import sys
    package = "wp18_fixture_plugin"
    (tmp_path / (package + ".py")).write_text(
        "from lineage.plugins import StubExtractor, stub_fixture\n"
        "extractor = StubExtractor()\nfixture = stub_fixture\n")
    distribution = tmp_path / "wp18_fixture_plugin-0.1.0.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text("Metadata-Version: 2.1\nName: wp18-fixture-plugin\nVersion: 0.1.0\n")
    (distribution / "entry_points.txt").write_text(
        "[lineage_ci.extractors]\nstub = wp18_fixture_plugin:extractor\n"
        "[lineage_ci.conformance]\nstub = wp18_fixture_plugin:fixture\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = PluginRegistry()
    registry.discover()
    assert registry.get("stub") is not None, registry.rejected
    assert package not in sys.modules


def test_explicit_extractor_assignment_runs_when_detection_declines(demo, tmp_path):
    class Assigned(StubExtractor):
        name = "go-assembly"

        def detect(self, repo, paths):
            return []

    registry = PluginRegistry()
    assert registry.register(Assigned(), stub_fixture())
    result = scan(repository_dir=demo[0], stage="merged", commit=demo[1], registry=registry, out_dir=tmp_path)
    go_units = [row for row in result["manifest"]["units"] if row["extractor"] == "go-assembly"]
    assert len(go_units) == 2
    assert all(row["status"] == "extracted" for row in go_units)


def test_wrapper_runs_same_cli_and_normalized_manifest(demo, tmp_path):
    directory, sha = demo
    common = {**os.environ, "PATH": str(Path(os.sys.executable).parent) + os.pathsep + os.environ["PATH"],
              "PYTHONPATH": str(repository_root() / "src"), "LINEAGE_REPO_ROOT": str(repository_root())}
    binary = Path(os.sys.executable).parent / "lineage-ci"
    subprocess.run([str(binary), "scan", "--stage", "merged", "--commit", sha, "--stub",
                    "--out", str(tmp_path / "plain"), "--state-dir", str(tmp_path / "plain-state")],
                   cwd=directory, env=common, check=True, capture_output=True)
    subprocess.run(["bash", str(repository_root() / "lineage-ci/action.sh")], cwd=directory,
                   env={**common, "LINEAGE_STAGE": "merged", "LINEAGE_COMMIT": sha, "LINEAGE_STUB": "true",
                        "LINEAGE_OUT": str(tmp_path / "action"), "LINEAGE_STATE_DIR": str(tmp_path / "action-state")},
                   check=True, capture_output=True)
    assert (tmp_path / "plain/scan-content.json").read_bytes() == (tmp_path / "action/scan-content.json").read_bytes()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LINEAGE_CI_IMAGE"), reason="set LINEAGE_CI_IMAGE after building lineage-ci/Dockerfile")
def test_plain_container_and_action_parity_with_network_disabled(demo, tmp_path):
    test_wrapper_runs_same_cli_and_normalized_manifest(demo, tmp_path)
    container_output = tmp_path / "container"
    container_output.mkdir()
    result = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
                             "--user", f"{os.getuid()}:{os.getgid()}",
                             "-v", f"{demo[0]}:/repo:ro", "-v", f"{container_output}:/out",
                             os.environ["LINEAGE_CI_IMAGE"], "scan", "--stage", "merged", "--commit", demo[1],
                             "--stub", "--state-dir", "/out/state", "--out", "/out/result"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert (container_output / "result/scan-content.json").read_bytes() == (tmp_path / "action/scan-content.json").read_bytes(), result.stdout


def test_reservation_precedes_extraction_and_survives_restart(demo, tmp_path):
    from lineage.snapshots import SnapshotPublisher
    archive = tmp_path / "shared"

    class ReservationAware(StubExtractor):
        def extract(self, unit, ctx):
            if unit.name == "checkout":
                import sqlite3
                with sqlite3.connect(archive / "reservations.sqlite") as database:
                    assert database.execute("SELECT COUNT(*) FROM reservations WHERE scope LIKE '%src/checkout%'").fetchone()[0] > 0
            yield from super().extract(unit, ctx)

    plugin = registered(ReservationAware())
    first = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True, registry=plugin,
                 snapshot_root=archive, state_dir=tmp_path / "state1", out_dir=tmp_path / "first")
    assert first["manifest"]["outcome"] == "emitted"
    initial = json.loads((tmp_path / "first/completion-manifests.json").read_text())
    restarted = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True, registry=plugin,
                     snapshot_root=archive, state_dir=tmp_path / "state2", out_dir=tmp_path / "retry")
    assert restarted["manifest"]["outcome"] == "emitted"
    assert initial == json.loads((tmp_path / "retry/completion-manifests.json").read_text())
    assert len(initial) == 16
    for completion in initial:
        assert completion["generation"] == 1
        assert SnapshotPublisher(archive).load(completion).events


def test_failed_publication_preserves_cache_and_retries_same_objects(demo, tmp_path):
    from lineage.snapshots import SnapshotPublisher
    archive = tmp_path / "shared"
    run(demo, tmp_path, snapshot_root=archive)
    cache = demo[0] / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    baseline = cache.read_bytes()
    plugin = StubExtractor()
    plugin.version = "0.2.0"
    registry = registered(plugin)
    backing = SnapshotPublisher(archive)

    class InterruptPublication:
        calls = 0

        def publish(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 3:
                raise ConnectionError("fault injection")
            return backing.publish(*args, **kwargs)

    failure = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True, registry=registry,
                   snapshot_root=archive, publisher=InterruptPublication(), out_dir=tmp_path / "failed")
    assert failure["manifest"]["outcome"] == "unavailable"
    assert failure["record"]["completion_count"] == 2
    assert failure["record"]["published"] is True
    assert failure["record"]["publication_complete"] is False
    assert baseline == cache.read_bytes()
    before = json.loads((tmp_path / "failed/completion-manifests.json").read_text())
    retried = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True, registry=registry,
                   snapshot_root=archive, publisher=backing, out_dir=tmp_path / "retried")
    assert retried["manifest"]["outcome"] == "emitted"
    after = json.loads((tmp_path / "retried/completion-manifests.json").read_text())
    assert after[:2] == before
    assert all(completion["generation"] == 2 for completion in after)


def test_completed_empty_and_deleted_units_publish_explicit_revisions(demo, tmp_path):
    directory, original = demo

    class EmptyCheckout(StubExtractor):
        def extract(self, unit, ctx):
            if unit.name != "checkout":
                yield from super().extract(unit, ctx)

    result = scan(repository_dir=directory, stage="merged", commit=original, stub=True,
                  registry=registered(EmptyCheckout()), out_dir=tmp_path / "empty")
    assert result["manifest"]["outcome"] == "emitted"
    completions = json.loads((tmp_path / "empty/completion-manifests.json").read_text())
    empty = next(item for item in completions if item["unit"]["urn"].endswith("src/checkout"))
    assert empty["eventCount"] == 0 and empty["complete"] is True and empty["deleted"] is False
    config = yaml.safe_load((directory / ".lineage.yaml").read_text())
    config["services"] = [item for item in config["services"] if item["name"] != "checkout"]
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    removed = commit(directory, "remove checkout unit")
    result = scan(repository_dir=directory, stage="merged", commit=removed, stub=True,
                  registry=registered(EmptyCheckout()), out_dir=tmp_path / "deleted")
    assert result["manifest"]["outcome"] == "emitted"
    deleted = json.loads((tmp_path / "deleted/completion-manifests.json").read_text())
    assert len(deleted) == 1
    assert deleted[0]["deleted"] is True and deleted[0]["eventCount"] == 0
    assert deleted[0]["unit"]["commit"] == removed and deleted[0]["generation"] == 2


def test_pr_revert_refreshes_overlay_without_reextracting_unchanged_units(demo, tmp_path):
    directory, base = demo
    run(demo, tmp_path)
    (directory / "src/checkout/main.go").write_text("package changed\n")
    changed = commit(directory, "PR change")
    scan(repository_dir=directory, stage="proposed", commit=changed, base=base, pr=19,
         stub=True, out_dir=tmp_path / "changed")
    (directory / "src/checkout/main.go").write_text("package main\n")
    reverted = commit(directory, "PR revert")
    result = scan(repository_dir=directory, stage="proposed", commit=reverted, base=base, pr=19,
                  stub=True, out_dir=tmp_path / "reverted")
    assert result["manifest"]["outcome"] == "emitted"
    assert all(row["status"] == "unchanged" for row in result["manifest"]["units"])
    completions = json.loads((tmp_path / "reverted/completion-manifests.json").read_text())
    assert len(completions) == 16
    checkout = next(item for item in completions if item["unit"]["urn"].endswith("src/checkout"))
    assert checkout["generation"] == 2
    assert checkout["route"] == {"repository": "opentelemetry-demo", "stage": "proposed", "pr": 19}


def test_removed_pr_only_unit_gets_deletion_completion(demo, tmp_path):
    directory, base = demo
    run(demo, tmp_path)
    config = yaml.safe_load((directory / ".lineage.yaml").read_text())
    config["services"].append({"name": "new-service", "path": "src/new-service", "language": "go"})
    path = directory / "src/new-service/main.go"
    path.parent.mkdir()
    path.write_text("package newservice\n")
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    added = commit(directory, "PR introduced unit")
    scan(repository_dir=directory, stage="proposed", commit=added, base=base, pr=20,
         stub=True, out_dir=tmp_path / "added")
    config["services"].pop()
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    removed = commit(directory, "PR removed introduced unit")
    result = scan(repository_dir=directory, stage="proposed", commit=removed, base=base, pr=20,
                  stub=True, out_dir=tmp_path / "removed")
    assert result["manifest"]["outcome"] == "emitted"
    completions = json.loads((tmp_path / "removed/completion-manifests.json").read_text())
    deleted = [item for item in completions if item["deleted"]]
    assert len(deleted) == 1 and deleted[0]["unit"]["urn"].endswith("src/new-service")


def test_ambiguous_pr_publication_intent_is_retired_without_advancing_cache(demo, tmp_path):
    from lineage.snapshots import SnapshotPublisher
    directory, base = demo
    archive = tmp_path / "shared"
    run(demo, tmp_path, snapshot_root=archive)
    merged_cache = directory / ".lineage-state/opentelemetry-demo/candidate-merged.json"
    baseline = merged_cache.read_bytes()
    config = yaml.safe_load((directory / ".lineage.yaml").read_text())
    config["services"].append({"name": "new-service", "path": "aaa-new-service", "language": "go"})
    path = directory / "aaa-new-service/main.go"
    path.parent.mkdir()
    path.write_text("package newservice\n")
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    added = commit(directory, "PR new unit before ambiguous ack")
    delivered = []

    def ambiguous_ack(key, manifest):
        delivered.append(manifest)
        raise ConnectionError("broker accepted but caller did not observe acknowledgment")

    failed = scan(repository_dir=directory, stage="proposed", commit=added, base=base, pr=22,
                  stub=True, snapshot_root=archive, publisher=SnapshotPublisher(archive, sink=ambiguous_ack),
                  out_dir=tmp_path / "ambiguous")
    assert failed["manifest"]["outcome"] == "unavailable"
    assert delivered[0]["unit"]["urn"].endswith("aaa-new-service")
    assert merged_cache.read_bytes() == baseline
    assert not (directory / ".lineage-state/overlays/opentelemetry-demo/22/completed-units.json").exists()
    config["services"].pop()
    (directory / ".lineage.yaml").write_text(yaml.safe_dump(config))
    removed = commit(directory, "PR remove possibly delivered unit")
    result = scan(repository_dir=directory, stage="proposed", commit=removed, base=base, pr=22,
                  stub=True, snapshot_root=archive, out_dir=tmp_path / "removed")
    assert result["manifest"]["outcome"] == "emitted"
    completions = json.loads((tmp_path / "removed/completion-manifests.json").read_text())
    tombstone = next(item for item in completions if item["deleted"])
    assert tombstone["unit"]["urn"].endswith("aaa-new-service")
    assert tombstone["generation"] == delivered[0]["generation"] + 1
    assert merged_cache.read_bytes() == baseline


def test_detection_failure_does_not_publish_deletions(demo, tmp_path):
    run(demo, tmp_path)

    class FailedDetection(StubExtractor):
        def detect(self, repo, paths):
            raise ValueError("unreadable package metadata")

    result = scan(repository_dir=demo[0], stage="merged", commit=demo[1], stub=True,
                  registry=registered(FailedDetection()), out_dir=tmp_path / "failed-detection")
    assert result["manifest"]["outcome"] == "emitted_partial"
    assert all(row["status"] == "failed" for row in result["manifest"]["units"])
    assert json.loads((tmp_path / "failed-detection/completion-manifests.json").read_text()) == []


@pytest.mark.integration
def test_cli_publishes_durable_completions_to_kafka_without_forking_kafka_threads(demo, tmp_path):
    import time
    import uuid
    broker = os.environ.get("LINEAGE_TEST_BROKER")
    if not broker:
        pytest.skip("Requires an explicitly configured disposable Kafka")
    from confluent_kafka import Consumer
    from confluent_kafka.admin import AdminClient, NewTopic
    from lineage.snapshots import SnapshotPublisher

    identity = "ci-snapshots-" + uuid.uuid4().hex
    topic = identity + ".complete"
    admin = AdminClient({"bootstrap.servers": broker})
    for future in admin.create_topics([NewTopic(topic, 1, 1)]).values():
        future.result(timeout=15)
    consumer = Consumer({"bootstrap.servers": broker, "group.id": identity, "auto.offset.reset": "earliest"})
    consumer.subscribe([topic])
    archive = tmp_path / "shared"
    try:
        result = subprocess.run([os.sys.executable, "-m", "lineage.ci", "scan", "--repo", str(demo[0]),
                                 "--stage", "merged", "--commit", demo[1], "--stub", "--transport", "kafka",
                                 "--broker", broker, "--snapshot-topic", topic, "--snapshot-root", str(archive),
                                 "--out", str(tmp_path / "published")], capture_output=True, text=True, timeout=60,
                                env={**os.environ, "PYTHONWARNINGS": "error::DeprecationWarning"})
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["outcome"] == "emitted", result.stdout
        manifest = json.loads((tmp_path / "published/unit-manifest.json").read_text())
        assert all(unit["status"] == "extracted" for unit in manifest["units"])
        messages = []
        deadline = time.monotonic() + 20
        while len(messages) < 16 and time.monotonic() < deadline:
            message = consumer.poll(0.2)
            if message is not None and not message.error():
                messages.append(json.loads(message.value()))
        assert len(messages) == 16
        publisher = SnapshotPublisher(archive)
        for message in messages:
            assert message["eventType"] == "UNIT_SNAPSHOT_COMPLETE"
            assert message["route"]["stage"] == "merged"
            assert publisher.load(message).events
    finally:
        consumer.close()
        for future in admin.delete_topics([topic]).values():
            future.result(timeout=15)
