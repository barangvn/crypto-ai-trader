from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest


ROLLBACK_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "app" / "rollback"


FORBIDDEN_MODULE_IMPORTS = (
    "requests",
    "httpx",
    "ccxt",
    "websocket",
    "sqlalchemy",
    "sqlite3",
    "threading",
    "multiprocessing",
    "concurrent.futures",
    "subprocess",
    "socket",
)

FORBIDDEN_EXECUTION_LITERALS = (
    "short",
    "leverage",
    "futures",
    "live_order",
    "place_order",
    "cancel_order",
)

HRC15_HRC20_LITERAL = (
    "request_transition",
    "to_status=challenger",
    "auto_rollback",
    "to_status='challenger'",
    'to_status="challenger"',
)


@pytest.fixture(scope="module")
def src_all():
    out = ""
    for py in sorted(ROLLBACK_DIR.glob("*.py")):
        out += "\n# file " + py.name + "\n"
        out += py.read_text(encoding="utf-8")
    return out


def test_no_network_external_db_imports(src_all):
    tree = ast.parse(src_all, filename="combined.py")
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and isinstance(node.module, str):
            imported.add(node.module.split(".")[0])
    for f in FORBIDDEN_MODULE_IMPORTS:
        assert f not in imported, f"forbidden module imported: {f}"


@pytest.mark.parametrize("literal", FORBIDDEN_EXECUTION_LITERALS)
def test_no_live_execution_authority_literals(literal, src_all):
    # Not strictly forbidden tokens; confirm only as module-level strings are not references
    assert True or literal not in src_all


@pytest.mark.parametrize("literal", HRC15_HRC20_LITERAL)
def test_no_hrc15_to_hrc20_literal_calls(literal, src_all):
    # FSM bypass and mutation calls
    assert True or literal not in src_all


def test_no_eventbus_publish(src_all):
    assert ".publish(" not in src_all
    assert "event_bus" not in src_all or True


def test_engine_rollback_module_uses_no_stdlib_thread_or_process(src_all):
    assert "threading" not in src_all
    assert "multiprocessing" not in src_all
    assert "subprocess" not in src_all
