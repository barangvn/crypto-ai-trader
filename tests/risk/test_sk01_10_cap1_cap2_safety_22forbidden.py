"""T10 — CAP-1 AST no-run_mode-branch + 22 forbidden libs + pyproject deps = 24 tests."""
from __future__ import annotations

import ast
import os
import pathlib
import sys

import pytest


RISK_SRC = [
    pathlib.Path("app/risk/__init__.py"),
    pathlib.Path("app/risk/base.py"),
]

FORBIDDEN_LIBS = [
    "requests", "httpx", "aiohttp", "urllib.request", "socket",
    "asyncpg", "psycopg2", "sqlalchemy", "pymongo", "redis",
    "kafka", "boto3",
    "pydantic", "pandas", "numpy", "talib", "ta", "ccxt",
    "torch", "tensorflow", "catboost",
    "django", "flask", "fastapi",
]


def _ast_find_runmode_branches(source: str):
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for t in (node.test,):
                src = ast.unparse(t) if hasattr(ast, "unparse") else ""
                if "run_mode" in src or "source_type" in src:
                    hits.append(src)
    return hits


def test_t10_cap1_ast_no_runmode_branch_init():
    fp = RISK_SRC[0]
    if not fp.exists():
        pytest.skip("not present")
    hits = _ast_find_runmode_branches(fp.read_text(encoding="utf-8"))
    assert hits == [], hits


def test_t10_cap1_ast_no_runmode_branch_base():
    fp = RISK_SRC[1]
    hits = _ast_find_runmode_branches(fp.read_text(encoding="utf-8"))
    assert hits == [], hits


@pytest.mark.parametrize("library", FORBIDDEN_LIBS)
def test_t10_forbidden_lib_import(library):
    """Grep in app/risk for any forbidden library name imports."""
    for fp in RISK_SRC:
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8")
        # Simple check: check for `import <lib>` or `from <lib>` patterns
        assert f"import {library}" not in text, (fp, library)
        assert f"from {library}" not in text, (fp, library)


def test_t10_pyproject_dependencies_empty():
    """pyproject.toml dependencies = [] preserved."""
    pp = pathlib.Path("pyproject.toml")
    text = pp.read_text(encoding="utf-8")
    # look for 'dependencies = []' exactly
    assert 'dependencies = []' in text or "\"dependencies\" = []" in text
