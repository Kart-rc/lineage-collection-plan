"""Bundle pinned, public acceptance inputs so installed CLIs are self-contained.

The source specifications remain authoritative and are never rewritten. Runtime
run records and private holdout material are deliberately outside this allowlist.
"""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithSpecifications(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent
        target = Path(self.build_lib) / "lineage" / "resources"
        files = [source / "factory/parameters.yaml"]
        for directory in ("factory/specs", "factory/work-packages", "factory/gates", "fixtures/otel-demo-3.1.0"):
            files.extend(p for p in (source / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        files.extend(source / "code" / name for name in ("observed_edges.py", "run_checks.py", "reference_slice.py", "spec_pack.py"))
        for path in files:
            if not path.is_file():
                # Minimal collector images only need parameters and schemas.
                continue
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


setup(cmdclass={"build_py": BuildWithSpecifications})
