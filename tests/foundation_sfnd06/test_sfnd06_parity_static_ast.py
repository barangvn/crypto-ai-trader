"""TP-12 / SEC-06 / HR-11 — static AST parity scan over the 6 new production modules.

SEC-06: helpers must contain NO paper/live branching; `run_mode` / `source_type`
are opaque pass-through strings (zero comparison branches).
HR-11: no production NOW() source outside the explicitly fixture-only helper.
"""

from __future__ import annotations

import ast

from tests.foundation_sfnd06._helpers import new_prod_paths

NOW_ATTRS = {"now", "utcnow", "time_ns", "monotonic"}
FIXTURE_FUNC = "now_instant_utc_fixture"
PARITY_NAMES = {"run_mode", "source_type"}
DYNAMIC_EXEC_NAMES = {"eval", "exec", "__import__", "compile"}


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _is_now_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in NOW_ATTRS
    )


def _now_calls_by_enclosing_function(tree: ast.AST) -> tuple[dict[str, list[str]], list[str]]:
    """Return (function_name -> [now attr], module_level [now attr])."""
    inside: dict[str, list[str]] = {}
    covered: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if _is_now_call(sub):
                    inside.setdefault(node.name, []).append(sub.func.attr)  # type: ignore[attr-defined]
                    covered.add(id(sub))
    module_level: list[str] = []
    for sub in ast.walk(tree):
        if _is_now_call(sub) and id(sub) not in covered:
            module_level.append(sub.func.attr)  # type: ignore[attr-defined]
    return inside, module_level


def test_hr11_no_module_level_now_source_and_only_fixture_function_uses_now():
    all_inside: dict[str, list[str]] = {}
    for path in new_prod_paths():
        inside, module_level = _now_calls_by_enclosing_function(_parse(path))
        assert module_level == [], f"module-level NOW() source in {path.name}: {module_level}"
        for func_name, attrs in inside.items():
            assert func_name == FIXTURE_FUNC, (
                f"production NOW() source in {path.name}::{func_name} -> {attrs} (HR-11)"
            )
            all_inside.setdefault(func_name, []).extend(attrs)
    # Only the explicit fixture-only helper may touch a wall clock, and only once.
    assert set(all_inside) == {FIXTURE_FUNC}
    assert all_inside[FIXTURE_FUNC] == ["now"]


def test_sec06_no_run_mode_or_source_type_branch_in_new_prod():
    for path in new_prod_paths():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                for operand in operands:
                    if isinstance(operand, ast.Name) and operand.id in PARITY_NAMES:
                        raise AssertionError(
                            f"parity branch on {operand.id} in {path.name} "
                            f"(SEC-06 zero-branch required)"
                        )
        source = path.read_text(encoding="utf-8")
        for marker in ("if run_mode", "if source_type", '== "live"', '== "paper"'):
            assert marker not in source, f"{path.name} contains parity branch marker {marker!r}"


def test_hr03_no_dynamic_execution_calls_in_new_prod():
    for path in new_prod_paths():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in DYNAMIC_EXEC_NAMES, (
                    f"dynamic execution call {node.func.id}() in {path.name} (HR-03)"
                )
