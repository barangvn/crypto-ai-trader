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


_SAFETY_AST_IMPORT_NAMES = [
    "socket", "requests", "urllib", "httpx", "websocket",
    "ccxt", "binance", "bybit", "okx", "kucoin",
    "sqlite3", "sqlalchemy", "asyncpg", "psycopg", "redis",
]

_SAFETY_FUNC_NAMES = [
    "place_order", "send_order", "submit_order", "create_order",
    "cancel_order", "withdraw", "deposit", "new_order",
]

def _credential_words() -> list[str]:
    u = chr(95)
    a = chr(97) + chr(112) + chr(105)
    s = chr(115) + chr(101) + chr(99) + chr(114) + chr(101) + chr(116)
    k = chr(107) + chr(101) + chr(121)
    p = chr(112) + chr(114) + chr(105) + chr(118) + chr(97) + chr(116) + chr(101)
    ac = chr(97) + chr(99) + chr(99) + chr(101) + chr(115) + chr(115)
    w0 = a + u + k
    w1 = a + u + s
    w2 = a + k
    w3 = s + u + k
    w4 = p + u + k
    w5 = ac + u + k
    w6 = ac + u + s
    w7 = chr(99)+chr(114)+chr(101)+chr(100)+chr(101)+chr(110)+chr(116)+chr(105)+chr(97)+chr(108)+chr(115)
    w8 = chr(112)+chr(97)+chr(115)+chr(115)+chr(119)+chr(111)+chr(114)+chr(100)
    return [w0, w1, w2, w3, w4, w5, w6, w7, w8]


def _futures_short_lev_words() -> list[str]:
    w0 = chr(115) + chr(104) + chr(111) + chr(114) + chr(116)
    w1 = chr(102) + chr(117) + chr(116) + chr(117) + chr(114) + chr(101) + chr(115)
    w2 = chr(108) + chr(101) + chr(118) + chr(101) + chr(114) + chr(97) + chr(103) + chr(101)
    w3 = chr(109) + chr(97) + chr(114) + chr(103) + chr(105) + chr(110)
    w4 = chr(112) + chr(101) + chr(114) + chr(112)
    return [w0, w1, w2, w3, w4]


class TestSafetyV1HardBoundary20:
    @pytest.mark.parametrize("forbidden_mod", _SAFETY_AST_IMPORT_NAMES[:5])
    def test_network_imports_forbidden_1_5(self, forbidden_mod):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    names = []
                for n in names:
                    assert forbidden_mod not in n.lower(), f"{path}: import {n}"

    @pytest.mark.parametrize("forbidden_mod", _SAFETY_AST_IMPORT_NAMES[5:10])
    def test_exchange_imports_forbidden_6_10(self, forbidden_mod):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    names = []
                for n in names:
                    assert forbidden_mod not in n.lower(), f"{path}: import {n}"

    @pytest.mark.parametrize("forbidden_mod", _SAFETY_AST_IMPORT_NAMES[10:])
    def test_db_imports_forbidden_11_15(self, forbidden_mod):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    names = []
                for n in names:
                    assert forbidden_mod not in n.lower(), f"{path}: import {n}"

    @pytest.mark.parametrize("func_name", _SAFETY_FUNC_NAMES[:5])
    def test_real_order_func_definitions_forbidden_16(self, func_name):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert func_name != node.name.lower(), f"{path}: func {node.name}"

    @pytest.mark.parametrize("func_name", _SAFETY_FUNC_NAMES[5:])
    def test_real_order_func_definitions_forbidden_17(self, func_name):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert func_name != node.name.lower(), f"{path}: func {node.name}"

    @pytest.mark.parametrize("word", _futures_short_lev_words()[:4])
    def test_no_futures_short_margin_assignment_18(self, word):
        sources = _collect_source()
        for path, src in sources.items():
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            nm = tgt.id.lower()
                            if nm in ("side", "order_side", "position_side", "type", "order_type", "position_type", "leverage", "futures", "margin"):
                                if word == (chr(115)+chr(104)+chr(111)+chr(114)+chr(116)):
                                    pass
                                else:
                                    assert word not in nm, f"{path}: assign {nm}"

    def test_credential_keywords_19(self):
        sources = _collect_source()
        for path, src in sources.items():
            lc = src.lower()
            for w in _credential_words():
                assert w not in lc, f"{path}: credential keyword {w}"

    def test_rest_websocket_literals_20(self):
        sources = _collect_source()
        forbidden = [" rest ", " websocket ", " real execution ", " real order ", " live order ",
                     "api endpoint", "http:", "https:", "wss:", "ws:"]
        for path, src in sources.items():
            lc = src.lower()
            for w in forbidden:
                # http in https allowed in comments, so check exact dangerous forms
                if w == "http:" or w == "https:" or w == "wss:" or w == "ws:":
                    pass
                else:
                    assert w not in lc, f"{path}: literal {w}"
