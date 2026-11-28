"""A built wheel works outside the source tree without implicit environment paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from lineage.config import repository_root


def test_installed_wheel_carries_pinned_specs(tmp_path):
    root = repository_root()
    result = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                             "--wheel-dir", str(tmp_path / "wheels"), str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    wheel = next((tmp_path / "wheels").glob("*.whl"))
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "lineage/resources/factory/parameters.yaml" in names
        assert not any("factory/runs/" in name or "oracle/holdout/" in name for name in names)
        archive.extractall(installed)
    environment = {k: v for k, v in os.environ.items() if k != "LINEAGE_REPO_ROOT"}
    environment["PYTHONPATH"] = str(installed)
    config = root / "fixtures/otel-demo-3.1.0/onboarding/otel-orders-dbt.lineage.yaml"
    run = subprocess.run([sys.executable, "-m", "lineage.ci", "validate", "--config", str(config)],
                         env=environment, cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0
    assert "unavailable" not in run.stdout + run.stderr
    assert "valid" in run.stdout.lower(), run.stdout + run.stderr
    probe = subprocess.run([sys.executable, "-c", "from lineage.config import repository_root; print(repository_root())"],
                           env=environment, cwd=tmp_path, capture_output=True, text=True)
    assert probe.returncode == 0
    assert str(installed / "lineage/resources") in probe.stdout
