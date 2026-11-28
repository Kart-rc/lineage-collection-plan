"""One-trial pilot orchestration with fake clocks and commands, never a live demo."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("twin_pilot", ROOT / "twin/pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
SECRET = "synthetic-payload-never-in-pilot-artifacts"
IMAGE = "sha256:" + "a" * 64


class FakeClock:
    def __init__(self):
        self.seconds = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.seconds += seconds

    def utc(self):
        return (datetime(2026, 11, 28, tzinfo=timezone.utc) + timedelta(seconds=self.seconds)).isoformat()


class FakeCommands:
    def __init__(self, state, clock):
        self.state, self.clock = state, clock
        self.calls = []
        self.started = self.stopped = False
        self.preexisting_container = self.preexisting_volume = False
        self.driver = "overlay2"
        self.start_elapsed = 12
        self.start_code = 0
        self.start_exception = None
        self.report_mutation = lambda report: None
        self.health_mutation = lambda rows, count: None
        self.health_calls = self.flow_calls = 0
        self.locust_calls = 0
        self.locust_mutation = lambda value, count: None
        self.no_receipt_growth = False
        self.stop_fails = False

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        stdout, code = "", 0
        if args[0] == "git":
            stdout = "b" * 40 if args[2] == str(ROOT) else pilot.start.DEMO_COMMIT
        elif args[:2] == ["docker", "info"]:
            stdout = json.dumps({"driver": self.driver, "root": "/actual-docker-root", "secret": SECRET})
        elif args[:3] == ["docker", "image", "inspect"]:
            stdout = IMAGE
        elif args[:3] == ["docker", "volume", "ls"]:
            stdout = SECRET if self.preexisting_volume else ""
        elif args[:2] == ["docker", "ps"]:
            if self.preexisting_container or self.started and not self.stopped:
                stdout = "c" * 64
        elif args[:2] == ["docker", "stop"]:
            if self.stop_fails:
                code = 1
            else:
                self.stopped = True
        elif len(args) > 1 and args[1].endswith("start.py"):
            assert args[args.index("--timeout") + 1] == "900"
            assert kwargs["timeout"] == 900 and kwargs["capture"] is False
            self.started = True
            self.clock.seconds += self.start_elapsed
            rows = [{"service": name, "state": "running", "health": "healthy"} for name in sorted(pilot.EXPECTED)]
            report = {"demoCommit": pilot.start.DEMO_COMMIT, "scope": "full-demo", "status": "passed", "phase": "complete",
                      "elapsedSeconds": self.start_elapsed, "timeoutSeconds": 900, "expectedServices": 28,
                      "expectedServiceNames": sorted(pilot.EXPECTED), "services": rows, "allRunning": True,
                      "allContainersHealthy": True, "exactServiceSet": True,
                      "workerImageId": IMAGE, "probeSha256": __import__("hashlib").sha256(b"synthetic-probe").hexdigest(),
                      "oneShotPrerequisites": [{"service": "lineage-topics", "status": "completed", "exitCode": 0}],
                      "raw_exception": SECRET}
            self.report_mutation(report)
            (self.state / "startup.json").write_text(json.dumps(report))
            if self.start_exception:
                raise self.start_exception
            code = self.start_code
        elif args[:2] == ["docker", "compose"] and "ps" in args:
            self.health_calls += 1
            rows = [{"Service": name, "State": "running", "Health": "healthy", "Command": SECRET} for name in sorted(pilot.EXPECTED)]
            self.health_mutation(rows, self.health_calls)
            stdout = json.dumps(rows)
        elif args[:2] == ["docker", "compose"] and "exec" in args:
            if "load-generator" in args:
                assert kwargs["timeout"] == 10
                self.locust_calls += 1
                value = {"available": True, "state": "running", "user_count": 5,
                         "num_requests": 100 + self.locust_calls * 10, "raw": SECRET}
                self.locust_mutation(value, self.locust_calls)
                stdout = json.dumps(value)
            else:
                self.flow_calls += 1
                stdout = json.dumps({"accepted_receipts": 5 if self.flow_calls == 1 or self.no_receipt_growth else 10,
                                     "outbox_total": 3, "outbox_sent": 3, "graph_revisions": 4, "graph_nodes": 4,
                                     "graph_versions": 4, "raw": SECRET})
        else:
            raise AssertionError(f"unexpected fake command {args[:3]}")
        return subprocess.CompletedProcess(args, code, stdout, SECRET)


@pytest.fixture
def trial(tmp_path, monkeypatch):
    twin = tmp_path / "twin"
    state = twin / ".state"
    (state / "bin").mkdir(parents=True)
    probe = state / "bin/lineage-healthcheck"
    probe.write_bytes(b"synthetic-probe")
    probe.chmod(0o700)
    monkeypatch.setattr(pilot, "TWIN", twin)
    clock = FakeClock()
    commands = FakeCommands(state, clock)
    stats_calls, score_calls, disks = [], [], []

    def stats(path, **kwargs):
        stats_calls.append((path, kwargs))
        return {"raw_files": {"traces.jsonl": {"present": True, "size_bytes": 42, "sha256": "f" * 64,
                                                 "complete_jsonl_lines": 1, "max_complete_jsonl_line_bytes": 42,
                                                 "trailing_bytes": 0, "jsonl_validated": False, "processed": False,
                                                 "raw": SECRET}}, "failure_categories": []}

    def score(path, window, **kwargs):
        assert commands.stopped, "offline scoring competed with the running demo"
        assert window["duration_seconds"] >= 600
        assert kwargs == {"timeout_seconds": 180, "memory_limit_mb": 8192, "max_capture_bytes": 4 * pilot.GIB,
                          "max_line_bytes": 128 * 1024 ** 2}
        score_calls.append((path, window, kwargs))
        return {"status": "pass", "precision": {"hit": 19, "observed": 20, "expected": 20, "bar": 0.95},
                "raw_capture_replayed": True, "raw_files": stats(path)["raw_files"], "failure_categories": [],
                "edges": {"extra": [{"from": SECRET}]}, "raw": SECRET,
                "counts": {"data_edges": 20, "control_edges": 1, "collector_events": 44, "redacted_endpoints": 0}}

    def disk(path, run):
        assert path == Path("/actual-docker-root"), "workspace substituted for the Docker root"
        disks.append(path)
        return {"free_bytes": 60 * pilot.GIB, "total_bytes": 100 * pilot.GIB, "method": "statvfs", "raw": SECRET}

    kwargs = {"demo": tmp_path / "reference-demo", "state": state, "output": tmp_path / "results", "clock": clock,
              "run": commands, "stats": stats, "score": score, "disk_probe": disk,
              "memory_probe": lambda: {"total_bytes": 16 * pilot.GIB, "available_bytes": 8 * pilot.GIB, "raw": SECRET}}
    return kwargs, commands, clock, stats_calls, score_calls, disks


def test_full_ten_minute_trial_stops_before_scoring_and_records_only_metadata(trial):
    kwargs, commands, clock, stats_calls, score_calls, disks = trial
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "passed", report["failure_categories"]
    assert report["purpose"] == "readiness_feasibility_pilot"
    assert report["run_window"]["duration_seconds"] == 600
    assert len(report["load"]["samples"]) == 21
    assert clock.sleeps == [30] * 20
    assert len(disks) == 22 and report["flow"]["holds"]
    assert report["flow"]["baseline"]["outbox_total"] == report["flow"]["final"]["outbox_total"]
    assert report["load"]["traffic"]["holds"] and report["load"]["traffic"]["all_active"]
    assert report["load"]["traffic"]["request_count_delta"] == 210 and commands.locust_calls == 22
    assert len(score_calls) == 1 and stats_calls
    assert report["startup_scope"]["image_preparation_included"] is False
    assert not any(report["claims"].values())
    marker = json.loads((kwargs["state"] / "pilot-attempt.json").read_text())
    assert marker == {"schema_version": 1, "project": pilot.PROJECT, "run_id": report["run_id"], "fresh_project_acquired": True}
    for name in ("pilot.json", "startup.json", "smoke.json"):
        assert SECRET not in (kwargs["output"] / name).read_text()
    assert all("down" not in args and "rm" not in args for args, _ in commands.calls)


@pytest.mark.parametrize("kind", ["container", "volume", "state", "stale_marker"])
def test_refuses_existing_baselines_without_stopping_or_owning_project(trial, kind):
    kwargs, commands, _, stats_calls, score_calls, _ = trial
    if kind == "container":
        commands.preexisting_container = True
    elif kind == "volume":
        commands.preexisting_volume = True
    elif kind == "state":
        (kwargs["state"] / "capture").mkdir()
    else:
        (kwargs["state"] / "pilot-attempt.json").write_text(json.dumps({"run_id": "0" * 32, "fresh_project_acquired": True}))
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and not commands.started and not commands.stopped
    assert not report["ownership"]["acquired"] and not report["shutdown"]["attempted"]
    assert all("stop" not in args for args, _ in commands.calls)
    assert stats_calls and not score_calls
    if kind == "stale_marker":
        assert report["run_id"] != json.loads((kwargs["state"] / "pilot-attempt.json").read_text())["run_id"]


def test_vfs_capacity_uses_actual_docker_root_and_never_starts(trial):
    kwargs, commands, _, _, score_calls, _ = trial
    commands.driver = "vfs"
    seen = []

    def disk(path, _run):
        seen.append(path)
        return {"free_bytes": 49 * pilot.GIB, "total_bytes": 100 * pilot.GIB, "method": "statvfs"}

    report = pilot.run_pilot(**{**kwargs, "disk_probe": disk})
    assert seen == [Path("/actual-docker-root")]
    assert report["first_failure"] == "insufficient_vfs_capacity"
    assert not commands.started and not commands.stopped and not score_calls


def test_docker_root_permission_fallback_is_bounded_read_only_sudo(monkeypatch):
    def denied(path):
        raise PermissionError(SECRET)
    monkeypatch.setattr(pilot.os, "statvfs", denied)
    calls = []

    def command(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "4096:123:456", SECRET)

    result = pilot.docker_disk(Path("/private/docker"), command)
    assert result == {"free_bytes": 4096 * 123, "total_bytes": 4096 * 456, "method": "sudo_stat_read_only"}
    assert calls == [(["sudo", "-n", "stat", "-f", "--format=%S:%a:%b", "--", "/private/docker"], {"timeout": 10})]


@pytest.mark.parametrize("mode", ["actual_elapsed", "reported_elapsed", "loosened_starter_timeout"])
def test_startup_900_seconds_is_enforced_independently(trial, mode):
    kwargs, commands, clock, stats_calls, score_calls, _ = trial
    if mode == "actual_elapsed":
        commands.start_elapsed = 901
        commands.report_mutation = lambda value: value.update(elapsedSeconds=20)
    elif mode == "reported_elapsed":
        commands.report_mutation = lambda value: value.update(elapsedSeconds=901)
    else:
        commands.report_mutation = lambda value: value.update(timeoutSeconds=3600)
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and "startup_deadline_exceeded" in report["failure_categories"]
    assert commands.stopped and commands.health_calls >= 1 and not clock.sleeps
    assert stats_calls and not score_calls


def test_starter_failure_still_observes_health_stops_and_retains_capture_stats(trial):
    kwargs, commands, _, stats_calls, score_calls, _ = trial
    commands.start_exception = subprocess.TimeoutExpired([SECRET], 900, output=SECRET, stderr=SECRET)
    commands.report_mutation = lambda value: value.update(status="failed", phase="full_start", category="command_failed")
    report = pilot.run_pilot(**kwargs)
    assert report["first_failure"] == "startup_deadline_exceeded"
    assert len(report["startup_observation"]["services"]) == 28
    assert commands.stopped and stats_calls and not score_calls
    assert SECRET not in (kwargs["output"] / "pilot.json").read_text()
    assert sum(len(args) > 1 and args[1].endswith("start.py") for args, _ in commands.calls) == 1


def test_fixed_28_services_do_not_trust_rendered_27_service_success(trial):
    kwargs, commands, _, _, score_calls, _ = trial
    commands.report_mutation = lambda value: value.update(expectedServices=27, expectedServiceNames=sorted(pilot.EXPECTED)[:-1])
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and "startup_not_ready" in report["failure_categories"]
    assert not score_calls and commands.stopped


def test_unhealthy_sample_fails_but_retains_full_measurement_window(trial):
    kwargs, commands, clock, _, score_calls, _ = trial

    def unhealthy(rows, count):
        if count == 3:
            rows[0]["Health"] = "unhealthy"

    commands.health_mutation = unhealthy
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and report["first_failure"] == "load_services_not_healthy"
    assert report["run_window"]["duration_seconds"] == 600 and len(clock.sleeps) == 20
    assert not report["load"]["all_healthy"] and score_calls


def test_resource_unsafe_is_the_only_early_load_stop(trial):
    kwargs, commands, clock, stats_calls, score_calls, _ = trial
    samples = [0]

    def disk(path, _run):
        samples[0] += 1
        return {"free_bytes": (60 * pilot.GIB if samples[0] < 3 else pilot.GIB - 1),
                "total_bytes": 100 * pilot.GIB, "method": "statvfs"}

    report = pilot.run_pilot(**{**kwargs, "disk_probe": disk})
    assert report["first_failure"] == "host_resource_unsafe"
    assert report["run_window"]["duration_seconds"] == 30
    assert commands.stopped and stats_calls and not score_calls


def test_forwarding_requires_receipt_growth_not_just_nonzero_counts(trial):
    kwargs, commands, _, _, _, _ = trial
    commands.no_receipt_growth = True
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and "forwarding_proof_failed" in report["failure_categories"]
    assert report["run_window"]["duration_seconds"] >= 600


def test_cannot_score_while_owned_containers_remain_running(trial):
    kwargs, commands, _, stats_calls, score_calls, _ = trial
    commands.stop_fails = True
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and "shutdown_failed" in report["failure_categories"]
    assert stats_calls and not score_calls


def test_cli_has_no_short_load_or_longer_startup_escape(monkeypatch, tmp_path):
    for option in ("--load-seconds", "--timeout"):
        with pytest.raises(SystemExit) as error:
            pilot.main(["--demo", "reference", "--output", str(tmp_path), option, "1"])
        assert error.value.code == 2


def test_precision_report_rechecks_exact_counts_instead_of_trusting_pass():
    with pytest.raises(ValueError):
        pilot.smoke_summary({"status": "pass", "raw_capture_replayed": True, "failure_categories": [],
                             "precision": {"hit": 18, "observed": 19, "expected": 20, "bar": 0.95, "holds": True}})


@pytest.mark.parametrize("mode,category", [("idle", "load_generator_inactive"), ("no_users", "load_generator_inactive"),
                                          ("no_progress", "load_requests_not_increasing"), ("reset", "load_request_counter_reset"),
                                          ("unavailable", "load_generator_probe_unavailable")])
def test_actual_load_requires_active_users_and_monotonic_increasing_requests(trial, mode, category):
    kwargs, commands, clock, _, _, _ = trial

    def mutate(value, count):
        if mode == "idle":
            value.update(state="stopped", user_count=0)
        elif mode == "no_users" and count == 5:
            value["user_count"] = 0
        elif mode == "no_progress":
            value["num_requests"] = 100
        elif mode == "reset" and count == 10:
            value["num_requests"] = 0
        elif mode == "unavailable" and count == 3:
            value["available"] = False

    commands.locust_mutation = mutate
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and category in report["failure_categories"]
    assert not report["load"]["traffic"]["holds"]
    assert report["run_window"]["duration_seconds"] >= 600 and len(clock.sleeps) == 20
    assert SECRET not in (kwargs["output"] / "pilot.json").read_text()


def test_locust_projection_matches_pinned_2444_shape_and_discards_raw_fields(monkeypatch, capsys):
    import signal
    import urllib.request
    document = {"state": "running", "user_count": 5,
                "stats": [{"name": SECRET, "method": "GET", "num_requests": 123},
                          {"name": "Aggregated", "method": None, "num_requests": 999}],
                "errors": [{"error": SECRET}], "other": SECRET}
    requests = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == 1048577
            return json.dumps(document).encode()

    class Opener:
        def open(self, url, *, timeout):
            requests.append((url, timeout))
            return Response()

    alarms = []
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    monkeypatch.setattr(signal, "alarm", alarms.append)
    exec(pilot.LOCUST_SCRIPT, {})
    output = capsys.readouterr().out
    assert json.loads(output) == {"available": True, "state": "running", "user_count": 5, "num_requests": 999}
    assert SECRET not in output
    assert requests == [("http://127.0.0.1:8089/stats/requests", 5)]
    assert alarms == [8, 0]


@pytest.mark.parametrize("fault", ["oversized", "ambiguous_total", "exception", "boolean_counter"])
def test_locust_child_rejects_bad_responses_without_raw_diagnostics(monkeypatch, capsys, fault):
    import signal
    import urllib.request

    class Response:
        status = 200

        def __enter__(self):
            if fault == "exception":
                raise ValueError(SECRET)
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            if fault == "oversized":
                return b"x" * limit
            rows = [{"name": "Aggregated", "method": None, "num_requests": True if fault == "boolean_counter" else 9}]
            if fault == "ambiguous_total":
                rows *= 2
            return json.dumps({"state": "running", "user_count": 5, "stats": rows, "raw": SECRET}).encode()

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    monkeypatch.setattr(signal, "alarm", lambda seconds: None)
    exec(pilot.LOCUST_SCRIPT, {})
    output = capsys.readouterr().out
    assert json.loads(output) == {"available": False}
    assert SECRET not in output


def test_workflow_supplied_invocation_id_binds_marker_and_report(trial):
    kwargs, _, _, _, _, _ = trial
    invocation = "d" * 32
    report = pilot.run_pilot(**kwargs, invocation_id=invocation)
    marker = json.loads((kwargs["state"] / "pilot-attempt.json").read_text())
    stored = json.loads((kwargs["output"] / "pilot.json").read_text())
    assert invocation == marker["run_id"] == stored["run_id"] == report["run_id"]
    assert report["status"] == "passed"


def test_ownership_is_persisted_before_starter_can_be_interrupted(trial):
    kwargs, commands, _, _, _, _ = trial
    invocation = "e" * 32
    observed = []

    def guarded(args, **options):
        if len(args) > 1 and args[1].endswith("start.py"):
            stored = json.loads((kwargs["output"] / "pilot.json").read_text())
            marker = json.loads((kwargs["state"] / "pilot-attempt.json").read_text())
            assert stored["ownership"]["acquired"] is True
            assert marker["fresh_project_acquired"] is True
            assert stored["run_id"] == marker["run_id"] == invocation
            observed.append(True)
        return commands(args, **options)

    report = pilot.run_pilot(**{**kwargs, "run": guarded}, invocation_id=invocation)
    assert report["status"] == "passed" and observed == [True]


def test_stale_pair_cannot_authorize_fresh_invocation_cleanup_when_report_write_fails(trial, monkeypatch):
    kwargs, commands, _, _, _, _ = trial
    previous, invocation = "a" * 32, "b" * 32
    kwargs["output"].mkdir()
    (kwargs["output"] / "pilot.json").write_text(json.dumps({"run_id": previous, "ownership": {"project": pilot.PROJECT, "acquired": True}}))
    (kwargs["state"] / "pilot-attempt.json").write_text(json.dumps({"schema_version": 1, "project": pilot.PROJECT,
                                                                  "run_id": previous, "fresh_project_acquired": True}))
    monkeypatch.setenv("LINEAGE_PILOT_INVOCATION", invocation)

    def denied(*args, **kwargs):
        raise PermissionError(SECRET)

    monkeypatch.setattr(pilot, "write_json", denied)
    report = pilot.run_pilot(**kwargs, invocation_id=invocation)
    marker = json.loads((kwargs["state"] / "pilot-attempt.json").read_text())
    stored = json.loads((kwargs["output"] / "pilot.json").read_text())
    assert report["status"] == "blocked" and report["run_id"] == invocation
    assert not (invocation == marker["run_id"] == stored["run_id"])
    assert not report["ownership"]["acquired"] and not commands.started and not commands.stopped


def test_invalid_invocation_id_is_not_echoed_or_used_for_ownership(trial):
    kwargs, commands, _, _, _, _ = trial
    report = pilot.run_pilot(**kwargs, invocation_id=SECRET)
    assert report["run_id"] is None and report["first_failure"] == "invalid_invocation_id"
    assert not commands.started and not commands.stopped
    assert SECRET not in (kwargs["output"] / "pilot.json").read_text()


def test_passed_startup_report_requires_its_own_service_rows_to_be_healthy(trial):
    kwargs, commands, _, _, score_calls, _ = trial
    commands.report_mutation = lambda value: value["services"][0].update(health="unhealthy")
    report = pilot.run_pilot(**kwargs)
    assert report["first_failure"] == "startup_report_invalid"
    assert commands.stopped and not score_calls


def test_candidate6_starter_failure_categories_are_retained(trial):
    kwargs, commands, _, _, _, _ = trial
    commands.start_code = 1
    commands.report_mutation = lambda value: value.update(status="failed", phase="validate", category="invalid_timeout", timeoutSeconds=None)
    report = pilot.run_pilot(**kwargs)
    assert report["startup"]["category"] == "invalid_timeout"
    assert report["startup"]["phase"] == "validate" and report["startup"]["timeoutSeconds"] is None


def collector_database(state, value):
    import sqlite3
    folder = state / "collector"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "progress.sqlite"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE health (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        database.execute("INSERT INTO health VALUES (1, ?)", (json.dumps(value),))
    return path


def test_collector_diagnostic_is_read_only_bounded_and_discards_new_fields(tmp_path, monkeypatch):
    value = {"status": "error", "category": "input_limit", "updated_at": 1795867200.25,
             "sent": 3, "pending": 4, "input_bytes": 100, "partial_lines": 1, "new_field": SECRET}
    path = collector_database(tmp_path, value)
    before = path.read_bytes()
    original, calls = pilot.sqlite3.connect, []

    def read_only(database_uri, **kwargs):
        assert database_uri == path.as_uri() + "?mode=ro" and kwargs == {"uri": True, "timeout": 0.2}
        calls.append(database_uri)
        connection = original(database_uri, **kwargs)
        with pytest.raises(pilot.sqlite3.OperationalError):
            connection.execute("UPDATE health SET value='changed'")
        return connection

    monkeypatch.setattr(pilot.sqlite3, "connect", read_only)
    assert pilot.collector_health(tmp_path) == {"available": True, **{key: item for key, item in value.items() if key != "new_field"}}
    assert path.read_bytes() == before and len(calls) == 1


@pytest.mark.parametrize("field,value", [("status", SECRET), ("category", SECRET), ("sent", True), ("pending", -1),
                                        ("input_bytes", 2 ** 63), ("partial_lines", 1.5), ("updated_at", float("nan")),
                                        ("updated_at", 1e100), ("updated_at", SECRET)])
def test_collector_diagnostic_rejects_malicious_values(tmp_path, field, value):
    collector_database(tmp_path, {"status": "ok", "category": "complete", "updated_at": 1795867200, field: value})
    result = pilot.collector_health(tmp_path)
    assert result == {"available": False, "reason": "invalid_record"}
    assert SECRET not in json.dumps(result)


def test_collector_diagnostic_missing_and_oversized_state(tmp_path):
    assert pilot.collector_health(tmp_path) == {"available": False, "reason": "missing_state"}
    collector_database(tmp_path, {"status": "ok", "category": "complete", "updated_at": 1, "raw": SECRET * 4096})
    assert pilot.collector_health(tmp_path) == {"available": False, "reason": "record_too_large"}


@pytest.mark.parametrize("existing", ["container", "volume", "state"])
def test_no_collector_diagnostic_read_when_trial_does_not_own_project(trial, monkeypatch, existing):
    kwargs, commands, _, _, _, _ = trial
    if existing == "container":
        commands.preexisting_container = True
    elif existing == "volume":
        commands.preexisting_volume = True
    else:
        collector_database(kwargs["state"], {"status": "ok", "category": "complete", "updated_at": 1})
    monkeypatch.setattr(pilot, "collector_health", lambda state: pytest.fail("read unowned collector state"))
    report = pilot.run_pilot(**kwargs)
    assert report["collector_health"] == {"available": False, "reason": "not_owned"}


@pytest.mark.parametrize("startup_fails", [False, True])
def test_collector_health_is_after_shutdown_before_parse_and_cannot_change_outcome(trial, monkeypatch, startup_fails):
    kwargs, commands, _, _, _, _ = trial
    commands.start_code = 1 if startup_fails else 0
    reads = []

    def diagnostic(state):
        assert commands.stopped
        reads.append(state)
        return {"available": True, "status": "error", "category": "input_limit", "updated_at": 1}

    original_score = kwargs["score"]

    def score(*args, **options):
        assert reads == [kwargs["state"]]
        return original_score(*args, **options)

    monkeypatch.setattr(pilot, "collector_health", diagnostic)
    report = pilot.run_pilot(**{**kwargs, "score": score})
    assert reads == [kwargs["state"]] and report["collector_health"]["category"] == "input_limit"
    assert report["status"] == ("blocked" if startup_fails else "passed")


def test_safe_structural_failure_survives_metadata_reports(trial):
    kwargs, _, _, _, _, _ = trial
    detail = {"filename": "traces.jsonl", "line": 9, "field_path": "$", "category": "expected_object"}

    def score(*args, **options):
        return {"status": "blocked", "failure_categories": ["invalid_otlp"], "structural_failure": detail,
                "raw_exception": SECRET}

    report = pilot.run_pilot(**{**kwargs, "score": score})
    assert report["status"] == "blocked" and report["smoke"]["structural_failure"] == detail
    for filename in ("pilot.json", "smoke.json"):
        raw = (kwargs["output"] / filename).read_text()
        saved = json.loads(raw)
        assert (saved["smoke"] if filename == "pilot.json" else saved)["structural_failure"] == detail
        assert SECRET not in raw


@pytest.mark.parametrize("detail", [
    None, SECRET, [], {},
    {"filename": "traces.jsonl", "line": 1, "field_path": "$", "category": "expected_object", "raw": SECRET},
    *[{"filename": "traces.jsonl", "line": 1, "field_path": "$", "category": "expected_object", key: bad}
      for key, bad in [("filename", SECRET), ("filename", [SECRET]), ("field_path", SECRET),
                       ("field_path", {"raw": SECRET}), ("category", SECRET), ("category", None),
                       ("line", True), ("line", 0), ("line", -1), ("line", 1.0),
                       ("line", 2 ** 63), ("line", SECRET)]],
])
def test_malicious_structural_detail_is_discarded_without_affecting_acceptance(detail):
    value = {"status": "pass", "raw_capture_replayed": True, "failure_categories": [],
             "precision": {"hit": 19, "observed": 20, "expected": 20, "bar": 0.95},
             "structural_failure": detail}
    result = pilot.smoke_summary(value)
    assert result["status"] == "pass" and result["structural_failure"] is None
    assert SECRET not in json.dumps(result)


def reference_capacity_profile():
    return {"name": "reference-ten-minute-v1", "scope": "ten-minute-reference-twin",
            "limits": {"max_input_bytes": 67108864, "max_line_bytes": 1048576, "max_events": 4096,
                       "max_metadata_bytes": 8388608, "max_memory_bytes": 1610612736, "parse_timeout": 30.0,
                       "send_timeout": 5.0, "max_sends_per_cycle": 128, "max_acknowledged": 100000},
            "container_memory_bytes": 2147483648, "parent_headroom_bytes": 536870912}


@pytest.mark.parametrize("tightened", [False, True])
def test_effective_capacity_profile_and_compose_hash_survive_hosted_reports(trial, tightened):
    import hashlib
    kwargs, commands, _, _, _, _ = trial
    profile = reference_capacity_profile()
    if tightened:
        profile["limits"].update(max_input_bytes=33554432, max_memory_bytes=1073741824, parse_timeout=20.0)
    commands.report_mutation = lambda value: value.update(collectorCapacityProfile=profile)
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "passed" and report["startup"]["collectorCapacityProfile"] == profile
    saved = json.loads((kwargs["output"] / "startup.json").read_text())
    assert saved["collectorCapacityProfile"] == profile
    name = "twin/collector.compose.yaml"
    assert report["identities"]["source_sha256"][name] == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


@pytest.mark.parametrize("key", list(reference_capacity_profile()["limits"]))
def test_capacity_summary_rejects_every_expanded_profile_limit(key):
    profile = reference_capacity_profile()
    profile["limits"][key] += 1
    with pytest.raises(ValueError):
        pilot.collector_capacity_summary(profile)


@pytest.mark.parametrize("field,bad", [
    ("name", SECRET), ("scope", SECRET), ("raw", SECRET), ("limits", []), ("limits", {}),
    ("container_memory_bytes", 2147483649), ("container_memory_bytes", 2147483648.0),
    ("parent_headroom_bytes", 0), ("parent_headroom_bytes", True),
])
def test_capacity_summary_rejects_unknown_or_malformed_profile_metadata(field, bad):
    profile = reference_capacity_profile()
    profile[field] = bad
    with pytest.raises(ValueError):
        pilot.collector_capacity_summary(profile)


@pytest.mark.parametrize("key,bad", [
    ("max_events", True), ("max_events", 1.0), ("max_events", 0), ("max_events", -1),
    ("parse_timeout", float("nan")), ("send_timeout", float("inf")), ("parse_timeout", SECRET),
    ("max_input_bytes", 524288), ("max_memory_bytes", 67108864), ("raw", SECRET),
])
def test_capacity_summary_rejects_unsafe_types_and_inconsistent_relationships(key, bad):
    profile = reference_capacity_profile()
    profile["limits"][key] = bad
    with pytest.raises(ValueError):
        pilot.collector_capacity_summary(profile)


def test_malformed_capacity_profile_rejects_startup_summary_without_leaking_raw_metadata(trial):
    kwargs, commands, _, _, score_calls, _ = trial
    commands.report_mutation = lambda value: value.update(collectorCapacityProfile={"raw": SECRET})
    report = pilot.run_pilot(**kwargs)
    assert report["status"] == "blocked" and report["first_failure"] == "startup_report_invalid"
    assert commands.stopped and not score_calls
    assert SECRET not in (kwargs["output"] / "pilot.json").read_text()
