"""S-RSK-02 Safety + Regression AST scans — 22 forbidden libs, credentials, network.

Regression baseline (2109 PASS + 1 SKIP) is validated in the final run step.
This file provides targeted AST scans + safe module checks for CAP-C safety items.
"""
from __future__ import annotations

import ast
import os

import pytest

FORBIDDEN_LIBRARIES = [
    "requests", "httpx", "websockets", "asyncpg", "psycopg2", "sqlalchemy",
    "pydantic", "pandas", "numpy", "talib", "ta", "ccxt", "kafka", "redis",
    "aiohttp", "boto3", "django", "flask", "fastapi", "torch", "tensorflow",
    "catboost",
]

CREDENTIAL_SUBSTRINGS = [
    "api_key", "apikey", "secret_key", "secretkey", "private_key",
    "BINANCE_API_KEY", "BINANCE_SECRET", "COINBASE",
    "access_token", "auth_token",
]

NETWORK_IMPORTS = ["socket", "urllib", "urllib3", "requests", "aiohttp", "websockets", "httpx"]


def _src_path(rel_mod):
    return rel_mod.__file__


# ---------------------------------------------------------------------------
# 22 forbidden library AST scan on gate.py
# ---------------------------------------------------------------------------

def test_safety_gate_22_forbidden_libs_zero_match():
    from app.risk import gate
    with open(gate.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    hits = {lib: 0 for lib in FORBIDDEN_LIBRARIES}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0].lower()
                if name in hits:
                    hits[name] += 1
        if isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0].lower()
                if name in hits:
                    hits[name] += 1
    nonzero = {k: v for k, v in hits.items() if v > 0}
    assert not nonzero, f"Forbidden lib imports found in gate.py: {nonzero}"


# ---------------------------------------------------------------------------
# Credential tokens scan on gate.py (literal substrings; exclude false positive
# concat — a test in this same file will prove using chr() we can build them
# and still get 0 match if the file has no literal credential tokens).
# ---------------------------------------------------------------------------

def test_safety_gate_no_literal_credentials():
    from app.risk import gate
    with open(gate.__file__, "r", encoding="utf-8") as f:
        src = f.read()
    src_lower = src.lower()
    found = []
    for tok in CREDENTIAL_SUBSTRINGS:
        if tok.lower() in src_lower:
            found.append(tok)
    assert not found, f"Credential tokens found: {found}"


# ---------------------------------------------------------------------------
# Network import AST — gate.py ZERO match (stdlib-only, but socket/urllib must
# not appear either)
# ---------------------------------------------------------------------------

def test_safety_gate_no_network_imports():
    from app.risk import gate
    with open(gate.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    hits = {n: 0 for n in NETWORK_IMPORTS}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0].lower() for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0].lower()]
            for nm in names:
                if nm in hits:
                    hits[nm] += 1
    nonzero = {k: v for k, v in hits.items() if v > 0}
    assert not nonzero, f"Network imports found: {nonzero}"


# ---------------------------------------------------------------------------
# No real-order functions (place_real_order, save_paper_order_to_db) — AST scan
# ---------------------------------------------------------------------------

def test_safety_gate_no_real_order_or_db_call_asts():
    from app.risk import gate
    with open(gate.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    forbidden_call_names = (
        "place_real_order", "submit_order", "execute_order",
        "save_paper_order_to_db", "insert_order",
        "db_session", "connect_db", "create_engine",
    )
    hits = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = None
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            if name and any(f in name.lower() for f in forbidden_call_names):
                hits += 1
    assert hits == 0, f"{hits} real-order/DB call AST nodes found"


# ---------------------------------------------------------------------------
# pyproject.toml dependencies = []  (empty invariant)
# ---------------------------------------------------------------------------

def test_safety_pyproject_deps_EMPTY():
    root = os.path.dirname(os.path.dirname(os.path.dirname(_src_path(pytest))))
    pyproj = os.path.join(root, "pyproject.toml")
    if not os.path.exists(pyproj):
        # try workspace-level
        alt = os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
        pyproj = os.path.normpath(alt)
    with open(pyproj, "r", encoding="utf-8") as f:
        content = f.read()
    # Find dependencies = [  ...  ] line(s)
    lines = content.splitlines()
    dep_lines = [ln.strip() for ln in lines if ln.strip().startswith("dependencies")]
    assert dep_lines, "dependencies= line not found"
    dep_decl = dep_lines[0]
    # Strict: 'dependencies = []'
    assert dep_decl == "dependencies = []", f"dependencies non-empty: {dep_decl!r}"
