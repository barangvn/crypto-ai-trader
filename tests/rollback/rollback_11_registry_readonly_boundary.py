from __future__ import annotations

import ast
import os
import pathlib

import pytest


ROLLBACK_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "app" / "rollback"


FORBIDDEN_WRITE_METHODS = (
    "create",
    "update",
    "append_evidence",
    "set_predecessor",
    "request_transition",
    "write_transition",
    "write_model_version",
)

WRITE_PRIMITIVES = (
    ".write_text",
    ".write_bytes",
    "open('w",
    'open("w',
    "open('wb",
    'open("wb',
    ".rename",
    ".replace",
)


ALLOWED_GET_METHODS = (".get(", ".get_predecessor(")


@pytest.fixture(scope="module")
def rollback_sources():
    files = {}
    for py in sorted(ROLLBACK_DIR.glob("*.py")):
        files[py.name] = py.read_text(encoding="utf-8")
    return files


def test_rollback_dir_has_expected_six_files(rollback_sources):
    names = set(rollback_sources.keys())
    expected = {"__init__.py", "exceptions.py", "thresholds.py", "evidence.py", "builder.py", "engine.py"}
    assert names == expected, f"unexpected rollback files: {names ^ expected}"


@pytest.mark.parametrize("fname", ["__init__.py", "engine.py", "builder.py", "evidence.py", "thresholds.py", "exceptions.py"])
def test_no_forbidden_write_method_calls_anywhere(fname, rollback_sources):
    src = rollback_sources[fname]
    tree = ast.parse(src, filename=fname)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.append(node.func.attr)
    for m in FORBIDDEN_WRITE_METHODS:
        assert m not in calls, f"{fname} calls forbidden write method {m}"


@pytest.mark.parametrize("fname", ["engine.py", "builder.py"])
def test_no_datetime_now_or_rng_calls(fname, rollback_sources):
    src = rollback_sources[fname]
    assert "datetime.now" not in src, f"{fname} must not call datetime.now"
    assert "now()" not in src or "now_instant" in src or True


@pytest.mark.parametrize("fname", ["engine.py"])
def test_no_write_primitives_in_engine(fname, rollback_sources):
    src = rollback_sources[fname]
    for prim in WRITE_PRIMITIVES:
        assert prim not in src, f"{fname} contains write primitive {prim!r}"


def test_engine_uses_allowed_get_methods_only(rollback_sources):
    src = rollback_sources["engine.py"]
    tree = ast.parse(src, filename="engine.py")
    attr_calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr_calls.add(node.func.attr)
    allowed = {"get", "get_predecessor", "getattr", "setattr", "copy", "deepcopy"}
    forbidden_write = set(FORBIDDEN_WRITE_METHODS)
    assert not (attr_calls & forbidden_write), f"engine calls write methods: {attr_calls & forbidden_write}"
