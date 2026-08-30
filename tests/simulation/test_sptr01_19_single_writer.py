from __future__ import annotations

import ast
import os

import pytest


HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation"))
FILES = [
    os.path.join(APP_ROOT, "__init__.py"),
    os.path.join(APP_ROOT, "execution.py"),
    os.path.join(APP_ROOT, "fill_config.py"),
]


def _collect_source() -> dict[str, str]:
    out = {}
    for fp in FILES:
        with open(fp, "r", encoding="utf-8") as f:
            out[fp] = f.read()
    return out


class TestSingleWriter:
    def test_19_01_no_position_import(self):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    nm = node.module or ""
                    assert "position" not in nm.lower(), f"{path}: import Position {nm}"
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "position" not in alias.name.lower(), f"{path}: import {alias.name}"

    def test_19_02_no_portfoliosnapshot_import(self):
        sources = _collect_source()
        forbidden_tokens = ["PortfolioSnapshot", "portfolio_snapshot", "Portfolio"]
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    m = (node.module or "").lower()
                    assert "portfolio" not in m, f"{path}: from {m}"
                if isinstance(node, ast.Name):
                    low = node.id.lower()
                    for tok in forbidden_tokens:
                        if tok.lower() == low:
                            assert False, f"{path}: Name {node.id}"

    def test_19_03_no_save_position_write_portfolio_func_defs(self):
        forbidden_funcs = [
            "save_position", "write_portfolio", "persist_portfolio",
            "update_portfolio", "set_position", "close_position",
        ]
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name.lower() not in forbidden_funcs, f"{path}: func {node.name}"

    def test_19_04_no_assign_to_position_variable_literal(self):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            nm = tgt.id.lower()
                            assert nm != "position", f"{path}: assign position"
                            assert nm != "portfolio", f"{path}: assign portfolio"
                            assert "portfolio" not in nm, f"{path}: assign {nm}"

    def test_19_05_no_portfoliosnapshot_class_ref_anywhere(self):
        sources = _collect_source()
        for path, src in sources.items():
            assert "PortfolioSnapshot" not in src, f"{path}: PortfolioSnapshot literal"
            assert "PositionSnapshot" not in src, f"{path}: PositionSnapshot literal"

    def test_19_06_no_db_persist_methods_imported(self):
        forbidden_tokens = ["sqlite", "sqlalchemy", "asyncpg", "psycopg", "redis",
                            "save_to_db", "write_db", "persist_db", "store_db"]
        sources = _collect_source()
        for path, src in sources.items():
            lc = src.lower()
            for tok in forbidden_tokens:
                if tok == "position":
                    continue
                assert tok not in lc, f"{path}: db tok '{tok}'"
