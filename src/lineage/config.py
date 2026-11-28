"""Locate versioned specifications without copying or relaxing them."""
from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path

import yaml


def repository_root() -> Path:
    configured = os.environ.get("LINEAGE_REPO_ROOT")
    root = Path(configured).resolve() if configured else Path(__file__).resolve().parents[2]
    if configured is None and not (root / "factory/parameters.yaml").is_file():
        root = Path(str(files("lineage").joinpath("resources")))
    if not (root / "factory/parameters.yaml").is_file():
        raise RuntimeError("Set LINEAGE_REPO_ROOT to the checkout containing the approved factory specifications")
    return root


def parameters() -> dict:
    return yaml.safe_load((repository_root() / "factory/parameters.yaml").read_text())


def schema(relative_path: str) -> dict:
    return json.loads((repository_root() / relative_path).read_text())
