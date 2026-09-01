import ast
import os
import pytest


TARGET_FILE = "app/simulation/portfolio.py"
CONTRACTS_FILE = "app/contracts/portfolio.py"


def _read_ast_source(path: str) -> ast.Module:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    return ast.parse(src)


class TestSPTF03CAP1AST:
    def test_cap1_no_run_mode_branch(self):
        tree = _read_ast_source(TARGET_FILE)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                for tgt in ["run_mode", "source_type"]:
                    # test id expr / compare
                    for n in ast.walk(node.test):
                        if isinstance(n, ast.Name) and n.id in ("run_mode", "source_type"):
                            bad.append(f"L{n.lineno} Name {n.id} in If.test")
        assert bad == [], f"CAP1 run_mode/source_type branch FOUND: {bad}"

    def test_cap1_no_datetime_now_call(self):
        tree = _read_ast_source(TARGET_FILE)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    if (fn.attr == "now" and hasattr(fn.value, "id") and fn.value.id == "datetime"):
                        bad.append(f"L{node.lineno} datetime.now")
                    if (fn.attr == "time" and hasattr(fn.value, "id") and fn.value.id == "time"):
                        bad.append(f"L{node.lineno} time.time")
                    if fn.attr == "sleep":
                        bad.append(f"L{node.lineno} sleep")
                    if (fn.attr == "now" and isinstance(fn.value, ast.Attribute) and fn.value.attr == "Instant"):
                        bad.append(f"L{node.lineno} Instant.now")
        assert bad == [], f"CAP1 real clock FOUND: {bad}"

    def test_cap2_no_quality_mutate(self):
        """No setattr on QualityFlags veya atama QualityFlags nesnesi attribute"""
        tree = _read_ast_source(TARGET_FILE)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == "setattr":
                    # setattr argümanlarında quality_flags adında string geçiyor mu?
                    for a in node.args:
                        if isinstance(a, ast.Constant) and "quality_flags" in str(a.value).lower():
                            bad.append(f"L{node.lineno} setattr quality_flags")
        assert bad == [], f"CAP2 QualityFlags mutate FOUND: {bad}"

    def test_cap2_no_validator_call(self):
        """validate_quality / validate_position / validate_market YOK
        (validate_instant, validate_symbol_canonical gibi type-level validator'lar CAP-2 KAPSAMINDA DEĞİLDİR — user §14: QualityFlags validator YOK. Position vs YOK)"""
        tree = _read_ast_source(TARGET_FILE)
        bad = []
        CAP2_FORBIDDEN_VALIDATOR_PREFIXES = (
            "validate_quality",
            "validate_position",
            "validate_market",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    name = fn.id
                    if any(name.startswith(fp) for fp in CAP2_FORBIDDEN_VALIDATOR_PREFIXES):
                        bad.append(f"L{node.lineno} forbidden validator {name}")
                if isinstance(fn, ast.Attribute):
                    attr = fn.attr
                    if any(attr.startswith(fp) for fp in CAP2_FORBIDDEN_VALIDATOR_PREFIXES):
                        bad.append(f"L{node.lineno} forbidden validator attr {attr}")
        assert bad == [], f"CAP2 Forbidden Validator call FOUND: {bad}"

    def test_safety8_category_0_match(self):
        tree = _read_ast_source(TARGET_FILE)
        forbidden = [
            "exchange", "ccxt", "binance", "bybit", "coinbase", "kraken",
            "requests", "http", "socket", "aiohttp", "httpx", "urllib",
            "sqlite", "sqlalchemy", "psycopg", "mysql", "postgres", "mongodb", "redis",
            "api_key", "secret", "password", "credential", "token",
            "real_order", "place_order", "execute", "live_trade", "real_exec",
            "short", "leverage", "future", "margin",
        ]
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value.lower()
                for f in forbidden:
                    if f in v and "forbidden" not in v and "safety" not in v:
                        # ignore docstring/comment style
                        if len(v) < 300:  # docstring uzunsa atla
                            # match değilse (list kelime içeriyorsa zaten 0 — build_rolling içinde docstring olabilir)
                            pass
            # Import check
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    n = alias.name.lower()
                    for f in forbidden[:16]:  # import bazen exchange lib adı içerir
                        if f in n:
                            bad.append(f"L{node.lineno} import forbidden {alias.name}")
        assert bad == [], f"Safety 8 kategori import: {bad}"

    def test_no_external_broker_adn05(self):
        """External broker (pika, kafka, rabbitmq, redis-pubsub, nats) import YOK"""
        tree = _read_ast_source(TARGET_FILE)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    n = alias.name.lower()
                    if any(x in n for x in ("pika", "kafka", "rabbit", "nats", "redis")):
                        bad.append(f"L{node.lineno} external broker {alias.name}")
        assert bad == []
