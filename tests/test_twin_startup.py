"""Strict startup reporting and generated readiness configuration, without Docker starts."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("twin_startup", ROOT / "twin/start.py")
start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start)
DEMO_NAMES = ["accounting", "ad", "astronomy-db", "cart", "checkout", "currency", "email", "flagd", "flagd-ui",
              "fraud-detection", "frontend", "frontend-proxy", "image-provider", "kafka", "load-generator",
              "otel-collector", "payment", "product-catalog", "quote", "recommendation", "shipping", "telemetry-docs", "valkey-cart"]
IMAGE_ID = "sha256:" + "a" * 64
SECRET = "synthetic-payload-must-not-leak"


@pytest.fixture
def configured(monkeypatch, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "bin").mkdir()
    probe = state / "bin/lineage-healthcheck"
    probe.write_bytes(b"test-only-helper")
    probe.chmod(0o755)
    expected = DEMO_NAMES + start.PLATFORM_SERVICES + ["lineage-worker", "lineage-collector"]
    config = {"services": {name: {} for name in expected + ["lineage-topics"]}}
    monkeypatch.setattr(start, "prepare", lambda *args, **kwargs: config)
    calls = []

    def run(args, **kwargs):
        kwargs["deadline"].remaining()
        calls.append((args, kwargs))
        output = "overlay2" if args[1] == "info" else IMAGE_ID if args[1:3] == ["image", "inspect"] else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(start, "command", run)
    rows = [{"service": name, "state": "running", "health": "healthy"} for name in expected]
    monkeypatch.setattr(start, "status", lambda *args, **kwargs: rows if not kwargs.get("services") else [r for r in rows if r["service"] in kwargs["services"]])
    return state, expected, calls, rows


def report(state):
    return json.loads((state / "startup.json").read_text())


def test_full_start_measures_all_phases_and_separates_one_shot(configured):
    state, expected, calls, _ = configured
    assert start.startup(Path("demo"), state) == 0
    result = report(state)
    assert result["expectedServices"] == 28
    assert set(result["expectedServiceNames"]) == set(expected)
    assert result["allContainersHealthy"] and result["exactServiceSet"]
    assert result["oneShotPrerequisites"] == [{"service": "lineage-topics", "status": "completed", "exitCode": 0}]
    assert len(result["probeSha256"]) == 64 and result["workerImageId"] == IMAGE_ID
    commands = [args for args, _ in calls]
    assert commands[2][-3:] == start.PLATFORM_SERVICES
    assert commands[3][-4:] == ["run", "--rm", "--no-deps", "lineage-topics"]
    assert "--profile" in commands[3] and "--rm" in commands[3]
    assert commands[3][-1] == "lineage-topics"
    assert commands[4][-3:-1] == ["--wait", "--wait-timeout"]
    assert len({id(kwargs["deadline"]) for _, kwargs in calls}) == 1


@pytest.mark.parametrize("mutation,category", [
    ("missing", "service_set_mismatch"), ("wrong", "service_set_mismatch"),
    ("duplicate", "service_set_mismatch"), ("extra", "service_set_mismatch"),
    ("no_probe", "services_not_healthy"), ("unhealthy", "services_not_healthy"),
    ("not_running", "services_not_healthy"),
])
def test_exact_services_and_actual_health_are_required(configured, mutation, category):
    state, _, _, rows = configured
    if mutation == "missing":
        rows.pop()
    elif mutation == "wrong":
        rows[0]["service"] = SECRET
    elif mutation == "duplicate":
        rows[-1] = dict(rows[0])
    elif mutation == "extra":
        rows.append({"service": SECRET, "state": "running", "health": "healthy"})
    elif mutation == "not_running":
        rows[0]["state"] = "exited"
    else:
        rows[0]["health"] = "" if mutation == "no_probe" else "unhealthy"
    assert start.startup(Path("demo"), state) == 1
    assert report(state)["category"] == category
    assert SECRET not in (state / "startup.json").read_text()


def test_late_healthy_result_fails(configured, monkeypatch):
    state, _, _, rows = configured
    now = [0.0]
    monkeypatch.setattr(start.time, "monotonic", lambda: now[0])

    def delayed_status(*args, **kwargs):
        now[0] = 901
        return rows

    monkeypatch.setattr(start, "status", delayed_status)
    assert start.startup(Path("demo"), state) == 1
    assert report(state)["category"] == "deadline_exceeded"
    assert report(state)["elapsedSeconds"] == 901


@pytest.mark.parametrize("timeout", [901, 1800, 900.001, 0, -1, float("nan"), float("inf"), True, "900", 10**400])
def test_full_start_rejects_invalid_or_relaxed_timeout_before_any_work(configured, timeout):
    state, _, calls, _ = configured
    assert start.startup(Path("demo"), state, timeout=timeout) == 1
    assert report(state)["category"] == "invalid_timeout"
    assert report(state)["timeoutSeconds"] is None
    assert calls == []


@pytest.mark.parametrize("timeout", ["901", "1800", "0", "-1", "nan", "inf"])
def test_full_start_cli_cannot_relax_the_900_second_bar(tmp_path, monkeypatch, timeout):
    monkeypatch.setattr(start, "TWIN", tmp_path)
    with pytest.raises(SystemExit) as error:
        start.main(["up", "--state", str(tmp_path / ".state"), "--timeout", timeout])
    assert error.value.code == 2
    assert not (tmp_path / ".state").exists()


@pytest.mark.parametrize("mutation", ["missing", "extra", "missing_initializer"])
def test_pinned_inventory_cannot_shrink_or_grow_with_the_rendered_config(configured, monkeypatch, mutation):
    state, expected, calls, rows = configured
    config = {"services": {name: {} for name in expected + ["lineage-topics"]}}
    if mutation == "missing":
        del config["services"]["accounting"]
        rows[:] = [row for row in rows if row["service"] != "accounting"]
    elif mutation == "extra":
        config["services"][SECRET] = {}
        rows.append({"service": SECRET, "state": "running", "health": "healthy"})
    else:
        del config["services"]["lineage-topics"]
    monkeypatch.setattr(start, "prepare", lambda *args, **kwargs: config)
    assert start.startup(Path("demo"), state) == 1
    result = report(state)
    assert result["category"] == "configuration_service_set_mismatch"
    assert result["expectedServices"] == 28
    assert "accounting" in result["expectedServiceNames"]
    assert SECRET not in (state / "startup.json").read_text()
    assert calls == []


def test_command_timeout_covers_pull_and_every_subprocess(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(start.time, "monotonic", lambda: now[0])
    deadline = start.Deadline(10)
    now[0] = 104
    seen = {}

    def run(args, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(start.subprocess, "run", run)
    start.command(["docker", "compose", "up"], deadline=deadline)
    assert seen["timeout"] == 6
    assert seen["capture_output"] is True
    now[0] = 110
    with pytest.raises(start.StartupFailure, match="deadline_exceeded"):
        start.command(["docker", "compose", "up"], deadline=deadline)


@pytest.mark.parametrize("failure,category", [
    (subprocess.TimeoutExpired(["docker", SECRET], 900, output=SECRET, stderr=SECRET), "deadline_exceeded"),
    (subprocess.CalledProcessError(7, ["docker", SECRET], output=SECRET, stderr=SECRET), "command_failed"),
    (ValueError(SECRET), "startup_unavailable"),
    (KeyboardInterrupt(SECRET), "interrupted"),
])
def test_post_init_failures_always_report_without_raw_diagnostics(configured, monkeypatch, capsys, failure, category):
    state, _, _, _ = configured

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(start, "prepare", fail)
    assert start.startup(Path("demo"), state) != 0
    assert report(state)["category"] == category
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err + (state / "startup.json").read_text()


def test_failed_topic_setup_never_claims_healthy_or_launches_full_stack(configured, monkeypatch):
    state, _, calls, _ = configured
    original = start.command

    def fail_setup(args, **kwargs):
        if "run" in args:
            raise subprocess.CalledProcessError(9, args, stderr=SECRET)
        return original(args, **kwargs)

    monkeypatch.setattr(start, "command", fail_setup)
    assert start.startup(Path("demo"), state) == 1
    result = report(state)
    assert result["phase"] == "topic_setup"
    assert result["oneShotPrerequisites"] == [{"service": "lineage-topics", "status": "failed", "exitCode": 9}]
    assert not result["allContainersHealthy"]
    assert len([args for args, _ in calls if "up" in args]) == 1


def test_platform_requires_only_its_three_services_and_no_probe_or_worker(configured):
    state, _, calls, _ = configured
    (state / "bin/lineage-healthcheck").unlink()
    assert start.startup(Path("demo"), state, platform=True) == 0
    assert report(state)["expectedServiceNames"] == start.PLATFORM_SERVICES
    assert report(state)["oneShotPrerequisites"] == []
    assert not any("inspect" in args or "run" in args for args, _ in calls)


def test_vfs_guard_fails_before_any_start(configured, monkeypatch):
    state, _, calls, _ = configured
    original = start.command

    def vfs(args, **kwargs):
        result = original(args, **kwargs)
        if args[1] == "info":
            result.stdout = "vfs"
        return result

    monkeypatch.setattr(start, "command", vfs)
    monkeypatch.setattr(start.shutil, "disk_usage", lambda path: type("Disk", (), {"free": 4 * 1024**3})())
    assert start.startup(Path("demo"), state) == 1
    assert report(state)["category"] == "insufficient_vfs_capacity"
    assert not any("up" in args for args, _ in calls)


def test_missing_probe_fails_before_any_start(configured):
    state, _, calls, _ = configured
    (state / "bin/lineage-healthcheck").unlink()
    assert start.startup(Path("demo"), state) == 1
    assert report(state)["category"] == "probe_unavailable"
    assert not any("up" in args for args, _ in calls)


def test_invalid_demo_path_after_state_init_has_safe_report(configured):
    state, _, calls, _ = configured
    demo = state / "loop"
    demo.symlink_to(demo)
    assert start.startup(demo, state) == 1
    assert report(state)["category"] == "startup_unavailable"
    assert calls == []


def test_generated_readiness_and_pipeline_are_real_and_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCUST_AUTOSTART", "false")
    monkeypatch.setenv("LOCUST_HEADLESS", "true")
    monkeypatch.setenv("LOCUST_USERS", "0")
    monkeypatch.setenv("LOCUST_HTTP_USER_WEIGHT", "0")
    monkeypatch.setenv("LOCUST_BROWSER_USER_WEIGHT", "1")
    demo = tmp_path / "demo"
    for directory in ("flagd", "flagd-ui/config", "image-provider", "telemetry-docs", "otel-collector"):
        (demo / "src" / directory).mkdir(parents=True)
    (demo / "src/flagd/demo.flagd.json").write_text('{"flags":{}}')
    (demo / "src/flagd-ui/config/runtime.exs").write_text("ip: {0, 0, 0, 0, 0, 0, 0, 0}")
    for name in ("image-provider", "telemetry-docs"):
        (demo / f"src/{name}/nginx.conf.template").write_text("listen [::]:8080;\nlisten 8080;\n")
    collector = {"receivers": {"docker_stats": {}, "host_metrics": {}, "otlp": {}},
                 "processors": {"resource_detection": {"detectors": ["docker"]}},
                 "service": {"pipelines": {"metrics": {"receivers": ["docker_stats", "host_metrics", "otlp"]}}}}
    (demo / "src/otel-collector/otelcol-config.yml").write_text(yaml.safe_dump(collector))
    upstream = {"services": {name: {"image": "pinned-image:1", "volumes": [], "container_name": name} for name in DEMO_NAMES}}
    for name, address in (("image-provider", "8081/status"), ("telemetry-docs", "8000/")):
        upstream["services"][name]["healthcheck"] = {
            "test": ["CMD", "wget", "--quiet", "--tries=1", "--spider", f"http://localhost:{address}"],
            "timeout": "5s", "interval": "5s", "retries": 20, "start_period": "10s",
        }

    def command(args, **kwargs):
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, start.DEMO_COMMIT, "")
        if args[0] == "sh":
            return subprocess.run(args, check=True, capture_output=True, text=True)
        assert kwargs["env"]["LOCUST_AUTOSTART"] == "true"
        assert kwargs["env"]["LOCUST_HEADLESS"] == "false"
        assert kwargs["env"]["LOCUST_USERS"] == "5"
        assert kwargs["env"]["LOCUST_HTTP_USER_WEIGHT"] == "1"
        assert kwargs["env"]["LOCUST_BROWSER_USER_WEIGHT"] == "0"
        return subprocess.CompletedProcess(args, 0, json.dumps(upstream), "")

    monkeypatch.setattr(start, "command", command)
    state = tmp_path / "state"
    config = start.prepare(demo, state, full=True)
    assert len(config["services"]) == 29
    assert set(config["services"]) == set(start.FULL_SERVICES) | {"lineage-topics"}
    cart = config["services"]["cart"]["healthcheck"]["test"]
    assert cart == ["CMD", "/bin/grpc_health_probe", "-addr=:7070"]
    for name, address in (("image-provider", "8081/status"), ("telemetry-docs", "8000/")):
        # The sandbox removes IPv6 listeners. Preserve the real HTTP check and
        # its limits while avoiding localhost's IPv6-first resolution.
        expected = dict(upstream["services"][name]["healthcheck"])
        expected["test"] = ["CMD", "wget", "--quiet", "--tries=1", "--spider", f"http://127.0.0.1:{address}"]
        assert config["services"][name]["healthcheck"] == expected
    for name, url in (("flagd", "http://127.0.0.1:8014/readyz"), ("otel-collector", "http://127.0.0.1:13133/")):
        assert config["services"][name]["healthcheck"]["test"] == ["CMD", "/lineage-healthcheck", "http", "--url", url]
    for name in ("accounting", "fraud-detection"):
        assert config["services"][name]["healthcheck"]["test"] == ["CMD", "/lineage-healthcheck", "kafka", "--broker", "kafka:9092", "--group", name, "--topic", "orders"]
    for name in ("flagd", "otel-collector", "accounting", "fraud-detection"):
        probe = next(v for v in config["services"][name]["volumes"] if v["target"] == "/lineage-healthcheck")
        assert probe["read_only"] and probe["source"] == str(state / "bin/lineage-healthcheck")
        assert probe["bind"]["create_host_path"] is False
    assert config["services"]["lineage-topics"]["profiles"] == ["lineage-setup"]
    for name in ("lineage-worker", "lineage-collector"):
        assert "lineage-topics" not in config["services"][name]["depends_on"]
        assert "profiles" not in config["services"][name] and "build" not in config["services"][name]
        assert config["services"][name]["pull_policy"] == "never"
    base = yaml.safe_load((state / "otelcol-base.yaml").read_text())
    assert base["extensions"]["health_check"]["endpoint"] == "127.0.0.1:13133"
    assert "health_check" in base["service"]["extensions"]
    assert (state / "capture").stat().st_mode & 0o777 == 0o700
    for name in ("traces.jsonl", "logs.jsonl", "metrics.jsonl"):
        assert (state / "capture" / name).read_bytes() == b""
        assert (state / "capture" / name).stat().st_mode & 0o777 == 0o600
    assert (demo / "src/image-provider/nginx.conf.template").read_text().startswith("listen [::]")
    assert "[::]" not in (state / "sandbox/image-provider.nginx.conf.template").read_text()


@pytest.mark.parametrize("action", ["prepare", "status", "down"])
def test_compatible_actions_suppress_and_report_failures(tmp_path, monkeypatch, capsys, action):
    monkeypatch.setattr(start, "TWIN", tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(start, "command", fail)
    monkeypatch.setattr(start, "prepare", fail)
    assert start.main([action, "--state", str(tmp_path / ".state")]) == 1
    assert report(tmp_path / ".state")["phase"] == action
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err


def collector_service():
    return yaml.safe_load((ROOT / 'twin/collector.compose.yaml').read_text())['services']['lineage-collector']


def collector_arguments(service):
    args = service['command']
    return {args[index][2:].replace('-', '_'): args[index+1]
            for index in range(0, len(args), 2)}


def test_standalone_collector_retains_every_small_run_default():
    from dataclasses import asdict
    from lineage.collector import Limits
    bridge = collector_service()
    arguments = collector_arguments(bridge)
    defaults = asdict(Limits())
    for name, value in defaults.items():
        template = arguments[name]
        assert template.startswith('${LINEAGE_COLLECTOR_' + name.upper() + ':-')
        rendered_default = template.split(':-', 1)[1][:-1]
        assert type(value)(rendered_default) == value
    assert defaults['max_input_bytes'] == 16 * 1024**2
    assert defaults['max_memory_bytes'] == 512 * 1024**2
    assert defaults['parse_timeout'] == 10.0
    assert bridge['mem_limit'] == '512m'
    assert arguments['poll_interval'] == '5'


def test_reference_collector_profile_renders_all_measured_bounds(monkeypatch):
    for name in start.REFERENCE_COLLECTOR_LIMITS:
        monkeypatch.delenv('LINEAGE_COLLECTOR_' + name.upper(), raising=False)
    bridge = collector_service()
    profile = start.reference_collector_capacity(bridge)
    expected = {'max_input_bytes': 67108864, 'max_line_bytes': 1048576, 'max_events': 4096,
                'max_metadata_bytes': 8388608, 'max_memory_bytes': 1610612736,
                'parse_timeout': 30.0, 'send_timeout': 5.0,
                'max_sends_per_cycle': 128, 'max_acknowledged': 100000}
    assert profile['name'] == 'reference-ten-minute-v1'
    assert profile['scope'] == 'ten-minute-reference-twin'
    assert profile['limits'] == expected
    assert profile['container_memory_bytes'] == bridge['mem_limit'] == 2147483648
    assert profile['parent_headroom_bytes'] == 536870912
    assert bridge['labels']['lineage.collector.capacity-profile'] == profile['name']
    arguments = collector_arguments(bridge)
    for key, value in expected.items():
        assert arguments[key] == str(value)
    assert all('${' not in value for value in arguments.values())
    assert (float(arguments['poll_interval']) + profile['limits']['parse_timeout']
            + profile['limits']['send_timeout']) < 45
    assert profile['limits']['max_memory_bytes'] + profile['parent_headroom_bytes'] <= bridge['mem_limit']
    assert bridge['read_only'] and bridge['cap_drop'] == ['ALL']
    assert bridge['pids_limit'] == 64


@pytest.mark.parametrize('name', list(start.REFERENCE_COLLECTOR_LIMITS))
def test_reference_collector_environment_cannot_expand_any_calibrated_cap(monkeypatch, name):
    monkeypatch.setenv('LINEAGE_COLLECTOR_' + name.upper(), str(start.REFERENCE_COLLECTOR_LIMITS[name] + 1))
    with pytest.raises(start.StartupFailure, match='invalid_collector_limits'):
        start.reference_collector_capacity(collector_service())


@pytest.mark.parametrize('name,value', [
    ('max_input_bytes', '0'), ('max_events', '-1'), ('max_memory_bytes', '1e9'),
    ('max_input_bytes', '9' * 400), ('max_line_bytes', 'nan'), ('max_events', 'True'),
    ('parse_timeout', 'nan'), ('parse_timeout', 'inf'), ('parse_timeout', '-inf'),
    ('parse_timeout', '0'), ('send_timeout', '-1'), ('send_timeout', '1e1000'),
])
def test_reference_collector_rejects_invalid_unbounded_environment_safely(monkeypatch, name, value):
    monkeypatch.setenv('LINEAGE_COLLECTOR_' + name.upper(), value)
    with pytest.raises(start.StartupFailure) as error:
        start.reference_collector_capacity(collector_service())
    assert str(error.value) == 'invalid_collector_limits'


def test_reference_collector_allows_tighter_consistent_limits(monkeypatch):
    monkeypatch.setenv('LINEAGE_COLLECTOR_MAX_INPUT_BYTES', str(32 * 1024**2))
    monkeypatch.setenv('LINEAGE_COLLECTOR_MAX_EVENTS', '2048')
    monkeypatch.setenv('LINEAGE_COLLECTOR_MAX_MEMORY_BYTES', str(1024**3))
    monkeypatch.setenv('LINEAGE_COLLECTOR_PARSE_TIMEOUT', '20')
    profile = start.reference_collector_capacity(collector_service())
    assert profile['limits']['max_input_bytes'] == 33554432
    assert profile['limits']['max_events'] == 2048
    assert profile['limits']['max_memory_bytes'] == 1073741824
    assert profile['limits']['parse_timeout'] == 20.0


@pytest.mark.parametrize('name,value', [('MAX_INPUT_BYTES', '524288'), ('MAX_MEMORY_BYTES', '67108864')])
def test_reference_collector_rejects_inconsistent_memory_and_input_bounds(monkeypatch, name, value):
    monkeypatch.setenv('LINEAGE_COLLECTOR_' + name, value)
    with pytest.raises(start.StartupFailure, match='invalid_collector_limits'):
        start.reference_collector_capacity(collector_service())


def test_full_pipeline_records_capacity_and_isolation(tmp_path, monkeypatch):
    for name in start.REFERENCE_COLLECTOR_LIMITS:
        monkeypatch.delenv('LINEAGE_COLLECTOR_' + name.upper(), raising=False)
    state = tmp_path / 'state'
    (state / 'capture').mkdir(parents=True)
    config = {'services': {}, 'volumes': {}}
    start.add_pipeline(config, state, 'lineage-platform:capacity-candidate')
    bridge = config['services']['lineage-collector']
    assert config['x-lineage-collector-capacity']['limits']['max_input_bytes'] == 67108864
    assert collector_arguments(bridge)['broker'] == 'lineage-kafka:9092'
    assert bridge['networks'] == ['lineage']
    assert bridge['image'] == 'lineage-platform:capacity-candidate'
    assert bridge['pull_policy'] == 'never'
    assert all(volume['read_only'] for volume in bridge['volumes'][:2])
