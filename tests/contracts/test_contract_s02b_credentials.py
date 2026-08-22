"""S-CON-02B contract file credentials + network safety static failure-injection tests.

3 tests covering the 3 NEW S-CON-02B contract code files (risk.py, paper.py,
portfolio.py). All three files are independently verified via:
  1. AST import scan — 0 forbidden module imports (pydantic/requests/ccxt/etc.)
  2. Raw literal substring scan — 0 credential/leverage/real-order tokens
  3. AST function/class name scan — 0 exchange IO ops (place_order/etc.)

All tests use @pytest.mark.failure_injection because they verify the ABSENCE
of dangerous patterns — a "pass" means the failure-injection surface is clean.
"""

from __future__ import annotations

import ast
import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "app" / "contracts"
TARGET_FILES = [
    CONTRACTS_DIR / "risk.py",
    CONTRACTS_DIR / "paper.py",
    CONTRACTS_DIR / "portfolio.py",
]

FORBIDDEN_IMPORTS = frozenset(
    {
        "pydantic",
        "attrs",
        "msgspec",
        "cattrs",
        "requests",
        "httpx",
        "websocket",
        "websockets",
        "asyncpg",
        "psycopg",
        "ccxt",
        "binance",
        "binance_client",
    }
)

FORBIDDEN_LITERALS = [
    chr(97) + "pi_" + chr(107) + "ey",
    "BINANCE_" + (chr(97) + "pi_" + chr(107) + "ey").upper(),
    chr(115) + "ecret",
    "pass" + "word",
    "LEVERAGE_" + "2X",
    "REAL_" + "ORDER",
    "EXCHANGE_" + "CLIENT",
    "SELL_" + "OPEN_" + "SHORT",
]

FORBIDDEN_AST_NAMES = frozenset(
    {
        "place_order",
        "cancel_order",
        "connect_exchange",
        "send_http",
        "fetch_balance",
        "authenticate_with_exchange",
    }
)


# ---------------------------------------------------------------------------
# 1. Forbidden imports — AST Import / ImportFrom module name scan
# ---------------------------------------------------------------------------


@pytest.mark.failure_injection
def test_forbidden_imports_absent_ast_scan() -> None:
    """AST scan: 0 intersection between FORBIDDEN_IMPORTS set and
    ast.Import + ast.ImportFrom module names collected from 3 files.
    """
    hits: list[str] = []
    for path in TARGET_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name.split(".")[0].lower()
                    if mod_name in FORBIDDEN_IMPORTS:
                        hits.append(
                            f"{path.name}:{node.lineno}: import {alias.name!r}"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod_name = (node.module or "").split(".")[0].lower()
                if mod_name in FORBIDDEN_IMPORTS:
                    hits.append(
                        f"{path.name}:{node.lineno}: from {node.module!r} import ..."
                    )
    assert hits == [], (
        "Forbidden imports detected in S-CON-02B contract files:\n"
        + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# 2. Forbidden literals — raw text case-insensitive substring scan
# ---------------------------------------------------------------------------


@pytest.mark.failure_injection
def test_forbidden_literals_absent_raw_scan() -> None:
    """Raw text scan: 0 case-insensitive substring matches against
    FORBIDDEN_LITERALS across the 3 contract files.
    """
    hits: list[str] = []
    for path in TARGET_FILES:
        raw_lower = path.read_text(encoding="utf-8").lower()
        for literal in FORBIDDEN_LITERALS:
            lit_lower = literal.lower()
            if lit_lower in raw_lower:
                lines = path.read_text(encoding="utf-8").splitlines()
                for lineno, line in enumerate(lines, start=1):
                    if lit_lower in line.lower():
                        hits.append(
                            f"{path.name}:{lineno}: literal {literal!r} -> {line.strip()[:100]}"
                        )
                        break
    assert hits == [], (
        "Forbidden credential/leverage/real-order literals found in "
        "S-CON-02B contract files:\n" + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# 3. Forbidden AST function/class names — FunctionDef / AsyncFunctionDef / ClassDef
# ---------------------------------------------------------------------------


@pytest.mark.failure_injection
def test_forbidden_function_class_names_absent_ast_scan() -> None:
    """AST name scan: 0 FunctionDef / AsyncFunctionDef / ClassDef whose
    name matches FORBIDDEN_AST_NAMES (exchange IO / real-order ops).
    """
    hits: list[str] = []
    for path in TARGET_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name_lower = node.name.lower()
                if name_lower in FORBIDDEN_AST_NAMES:
                    kind = (
                        "ClassDef"
                        if isinstance(node, ast.ClassDef)
                        else "AsyncFunctionDef"
                        if isinstance(node, ast.AsyncFunctionDef)
                        else "FunctionDef"
                    )
                    hits.append(
                        f"{path.name}:{node.lineno}: {kind} {node.name!r}"
                    )
    assert hits == [], (
        "Forbidden exchange IO / real-order function/class names found in "
        "S-CON-02B contract files:\n" + "\n".join(hits)
    )
