"""Independent candidate-9 traffic boundary probe; fake infrastructure only.

Reuse the existing transport/clock fixture, but choose independent case inputs
and expected outcomes. All temporary reports and synthetic state live in /tmp.
No implementation or oracle is changed, and real subprocess execution is denied.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verify9_fake_transport", ROOT / "tests/test_twin_pilot.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def deny_process(*args, **kwargs):
    raise AssertionError("Independent probe forbids real subprocess execution")


def run_case(name, expected, mutate=None, configure=None, required_category=None):
    with tempfile.TemporaryDirectory(prefix="verify9-traffic-", dir="/tmp") as folder:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(subprocess, "run", deny_process)
            kwargs, commands, clock, _, _, _ = fixture.trial.__wrapped__(Path(folder), patch)
            if mutate:
                commands.locust_mutation = lambda value, number: mutate(value, number, clock)
            if configure:
                configure(kwargs, commands, clock)
            report = fixture.pilot.run_pilot(**kwargs)
            traffic = report["load"]["traffic"]
            samples = [traffic["baseline"], *traffic["samples"]]
            serialized = [path.read_text() for path in kwargs["output"].glob("*.json")]
            checks = {
                "expected_status": report["status"] == expected,
                "minimum_window": report["run_window"]["duration_seconds"] >= 600,
                "matching_traffic_verdict": traffic["holds"] == (expected == "passed"),
                "stopped_before_scoring": commands.stopped,
                "metadata_sentinel_absent": all(fixture.SECRET not in text for text in serialized),
                "no_full_acceptance_claims": not any(report["claims"].values()),
                "required_category_present": required_category is None or required_category in report["failure_categories"],
            }
            if required_category == "load_progress_unproven":
                checks["no_inactivity_inference"] = "load_generator_inactive" not in report["failure_categories"]
            return {
                "case": name,
                "expected_status": expected,
                "pilot_status": report["status"],
                "duration_seconds": report["run_window"]["duration_seconds"],
                "traffic_holds": traffic["holds"],
                "progress_proven": traffic["progress_proven"],
                "max_no_progress_interval_seconds": traffic["max_no_progress_interval_seconds"],
                "request_count_delta": traffic["request_count_delta"],
                "user_counts": sorted({row["user_count"] for row in samples if "user_count" in row}),
                "sample_intervals": len(samples) - 1,
                "failure_categories": report["failure_categories"],
                "checks": checks,
                "all_checks_passed": all(checks.values()),
            }


def tail_delay(kwargs, commands, clock):
    original = kwargs["memory_probe"]
    count = 0

    def probe():
        nonlocal count
        count += 1
        if count == 21:
            clock.seconds += 61
        return original()

    kwargs["memory_probe"] = probe


def delayed_progress(value, number, clock):
    if number == 4:
        clock.seconds += 31


results = [
    run_case("five_users_control", "passed"),
    run_case("only_one_user_for_entire_window", "blocked", lambda v, n, c: v.update(user_count=1),
             required_category="load_user_count_mismatch"),
    run_case("four_users_for_entire_window", "blocked", lambda v, n, c: v.update(user_count=4),
             required_category="load_user_count_mismatch"),
    run_case("six_users_for_entire_window", "blocked", lambda v, n, c: v.update(user_count=6),
             required_category="load_user_count_mismatch"),
    run_case("five_users_only_one_request_at_final_sample", "blocked",
             lambda v, n, c: v.update(num_requests=100 + int(n == 22)), required_category="load_progress_unproven"),
    run_case("one_user_at_baseline_then_five", "blocked",
             lambda v, n, c: v.update(user_count=1 if n == 1 else 5), required_category="load_user_count_mismatch"),
    run_case("four_users_midwindow_then_recovered", "blocked",
             lambda v, n, c: v.update(user_count=4 if n == 12 else 5), required_category="load_user_count_mismatch"),
    run_case("four_users_at_final_sample", "blocked",
             lambda v, n, c: v.update(user_count=4 if n == 22 else 5), required_category="load_user_count_mismatch"),
    run_case("flat_long_inflight_is_unproven", "blocked", lambda v, n, c: v.update(num_requests=100),
             required_category="load_progress_unproven"),
    run_case("large_initial_burst_cannot_prove_rest_of_window", "blocked",
             lambda v, n, c: v.update(num_requests=100 if n == 1 else 100000), required_category="load_progress_unproven"),
    run_case("completion_each_sixty_seconds_control", "passed",
             lambda v, n, c: v.update(num_requests=100 + max(0, n - 2) // 2)),
    run_case("completion_each_ninety_seconds_is_unproven", "blocked",
             lambda v, n, c: v.update(num_requests=100 + max(0, n - 2) // 3), required_category="load_progress_unproven"),
    run_case("late_progress_cannot_cover_sixty_one_second_probe_gap", "blocked", delayed_progress,
             required_category="load_progress_unproven"),
    run_case("post_sample_delay_cannot_cover_sixty_one_second_tail", "blocked", configure=tail_delay,
             required_category="load_progress_unproven"),
    run_case("counter_reset_then_recovery", "blocked",
             lambda v, n, c: v.update(num_requests=0) if n == 12 else None,
             required_category="load_request_counter_reset"),
    run_case("unavailable_sample_then_recovery", "blocked",
             lambda v, n, c: v.update(available=False) if n == 12 else None,
             required_category="load_generator_probe_unavailable"),
]
document = {
    "candidate": 9,
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Deterministic execution of actual pilot; no live workload or Docker operations",
    "temporary_raw_state_location": "/tmp; removed by TemporaryDirectory",
    "real_subprocess_execution_denied": True,
    "cases": results,
    "all_checks_passed": all(result["all_checks_passed"] for result in results),
}
(HERE / "traffic-boundary-results.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({"cases": len(results), "all_checks_passed": document["all_checks_passed"],
                  "outcomes": {result["case"]: result["pilot_status"] for result in results}}, indent=2))
assert document["all_checks_passed"]
