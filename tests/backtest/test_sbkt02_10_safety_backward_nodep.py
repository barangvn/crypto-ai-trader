"""S-BKT-02-10: Safety/Backward/NoDeps Regression Guards + SBKT01 Regression Unchanged."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest


def test_pyproject_toml_no_new_runtime_dependencies():
    import tomllib

    root = Path(__file__).resolve().parents[2]
    pp = root / "pyproject.toml"
    data = tomllib.loads(pp.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    assert deps == []


def test_new_backtest_files_imports_stdlib_or_app():
    backtest = Path(__file__).resolve().parents[2] / "app" / "backtest"
    new_files = ["cost_injection.py", "walk_forward.py", "multi_fold_runner.py"]
    forbidden_external = {
        "pydantic",
        "msgspec",
        "numpy",
        "pandas",
        "sklearn",
        "requests",
        "httpx",
        "websocket",
    }
    for fn in new_files:
        src = (backtest / fn).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden_external, f"{fn}: bad import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    assert top not in forbidden_external, f"{fn}: bad import {node.module}"


def test_no_futures_leverage_short():
    backtest = Path(__file__).resolve().parents[2] / "app" / "backtest"
    new_files = ["cost_injection.py", "walk_forward.py", "multi_fold_runner.py"]
    pats = ["short_side", "short_position", "is_short", "futures_", "leverage > 1", "leverage>1", "leverage_ratio > 1"]
    for fn in new_files:
        src = (backtest / fn).read_text(encoding="utf-8").lower()
        for pat in pats:
            assert pat.lower() not in src


def test_contracts_unchanged_by_diff(tmp_path):
    # contracts klasöründe bugünün itibarıyla S-BKT-02 tarafından file change olmamalı
    import subprocess as sp

    root = Path(__file__).resolve().parents[2]
    r = sp.run(
        ["git", "diff", "--stat", "--", "app/contracts/"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert "|" not in (r.stdout or "") or r.stdout.strip() == ""
