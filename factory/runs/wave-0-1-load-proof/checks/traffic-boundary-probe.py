"""Read-only verifier probe: execute the candidate with fake infrastructure only."""
import importlib.util
import json
from pathlib import Path
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verifier_candidate8_pilot_tests", ROOT / "tests/test_twin_pilot.py")
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


def run_case(name, mutate):
    with tempfile.TemporaryDirectory(prefix="traffic-probe-", dir=HERE) as folder:
        with pytest.MonkeyPatch.context() as patch:
            kwargs, commands, _, _, _, _ = cases.trial.__wrapped__(Path(folder), patch)
            commands.locust_mutation = mutate
            report = cases.pilot.run_pilot(**kwargs)
            traffic = report["load"]["traffic"]
            samples = [traffic["baseline"], *traffic["samples"]]
            return {
                "case": name,
                "pilot_status": report["status"],
                "duration_seconds": report["run_window"]["duration_seconds"],
                "traffic_holds": traffic["holds"],
                "user_counts": sorted({row["user_count"] for row in samples}),
                "request_count_delta": traffic["request_count_delta"],
                "samples_with_increase": sum(right["num_requests"] > left["num_requests"]
                    for left, right in zip(samples, samples[1:])),
                "sample_intervals": len(samples) - 1,
                "failure_categories": report["failure_categories"],
                "real_docker_or_network_operations": False,
            }


results = [
    run_case("five_users_control", lambda value, count: None),
    run_case("only_one_user_for_entire_window", lambda value, count: value.update(user_count=1)),
    run_case("four_users_for_entire_window", lambda value, count: value.update(user_count=4)),
    run_case("five_users_only_one_request_at_final_sample",
             lambda value, count: value.update(num_requests=100 + int(count == 22))),
]
(HERE / "traffic-boundary-results.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
