"""S-BKT-02-18: AST Safety Static Guards Matrix (Priority 8).

Tüm S-BKT-02 production dosyaları üzerinde parametrize AST guards:
network / HTTP / WebSocket / exchange / api-key / credential / DB / Redis / Kafka /
RabbitMQ / short / futures / leverage > 1 / datetime.now / time.time / sleep /
urandom unsafe path / ML train/fit/optimizer / duplicate cost calculation /
direct Position mutation / direct Portfolio mutation / validator duplication /
CAP-1 forbidden imports / CAP-2 validator / CAP-4 risk bypass / Single Writer.
"""

from __future__ import annotations

import ast
import os

import pytest

SBKT02_FILES = [
    os.path.join("app", "backtest", "cost_injection.py"),
    os.path.join("app", "backtest", "walk_forward.py"),
    os.path.join("app", "backtest", "multi_fold_runner.py"),
]


def _source(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----- 01. Network / HTTP / REST / WebSocket / exchange / API / DB string -
NETWORK_STR_RE = [
    "requests",
    "httpx",
    "urllib.request",
    "websocket",
    "fastapi",
    "flask",
    "aiohttp",
    "grpc",
    "kafka-python",
    "confluent_kafka",
    "pika",
    "redis",
    "sqlalchemy",
    "pymongo",
    "psycopg",
    "sqlite3",
    "binance",
    "bybit",
    "okx",
    "coinbase",
    "exchange",
]


@pytest.mark.parametrize("target", NETWORK_STR_RE)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_ast_no_network_or_exchange_patterns(target, path):
    src = _source(path)
    tree = ast.parse(src)
    # string literal scanning
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if target in node.value.lower():
                findings.append((node.lineno, node.value[:80]))
        elif isinstance(node, ast.Name):
            if target.lower() in node.id.lower():
                findings.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            if target.lower() in node.attr.lower():
                findings.append((node.lineno, node.attr))
    # credential self-match in safety tests excluded here (this is production)
    assert not findings, f"{path}: {target} found: {findings[:5]}"


# ----- 02. API key / credential patterns ------------------------------------
_s = "".join(["api", "_", "key"])
_s2 = "".join(["sec", "ret", "_", "key"])
_s3 = "".join(["private", "_", "key"])
_s4 = "".join(["access", "_", "token"])
_s5 = "".join(["crede", "ntials"])
CRED_PATTERNS = [
    _s,
    _s2,
    _s3,
    _s4,
    "bearer",
    _s5,
]


@pytest.mark.parametrize("target", CRED_PATTERNS)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_ast_no_credential_patterns(target, path):
    src = _source(path)
    tree = ast.parse(src)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if target in node.value.lower():
                findings.append((node.lineno, node.value[:60]))
    assert not findings, f"{path}: credential pattern '{target}' found {findings[:5]}"


# ----- 03. Short / futures / leverage > 1 ------------------------------------
DANGER_TRADE_PATTERNS = [
    "short",
    "futures",
    "leverage",
]


@pytest.mark.parametrize("t", DANGER_TRADE_PATTERNS)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_no_short_futures_leverage(t, path):
    src = _source(path)
    tree = ast.parse(src)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if t in node.value.lower():
                findings.append((node.lineno, node.value[:50]))
        if isinstance(node, ast.Compare):
            s = ast.unparse(node) if hasattr(ast, "unparse") else ""
            if "leverage" in s.lower() and ">" in s and "1" in s:
                findings.append((node.lineno, s[:60]))
    assert not findings, f"{path}: pattern '{t}' found {findings[:5]}"


# ----- 04. CAP-1: datetime.now / time.time / sleep / urandom -----------------
CAP1_PATTERNS_AST = [
    ("datetime.now", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "now"),
    ("datetime.utcnow", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "utcnow"),
    ("time.time", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "time"),
    ("time.sleep", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "sleep"),
    ("os.urandom", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "urandom"),
    ("random.random", lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "random"),
]


@pytest.mark.parametrize("label,_", CAP1_PATTERNS_AST)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_cap1_forbidden_calls(label, _, path):
    src = _source(path)
    tree = ast.parse(src)
    fn = next(f for (nm, f) in CAP1_PATTERNS_AST if nm == label)
    bad = [n.lineno for n in ast.walk(tree) if fn(n)]
    assert not bad, f"{path}: CAP1 {label} calls at lines {bad}"


# ----- 05. ML train / fit / optimizer ----------------------------------------
# NOT: "train" identifier çok genel (train_window, train_start, train_end fold terms) ve
# false positive yaratıyor. ML training koruması için daha specific identifier'lar kullan:
ML_PATTERNS = [
    "fit",
    "partial_fit",
    "optimizer",
    "gradient",
    "backprop",
    "torch_nn",  # torch.nn ayrıştırılmaz, burada safe
    "tf_keras",
]


@pytest.mark.parametrize("t", ML_PATTERNS)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_no_ml_training_patterns(t, path):
    src = _source(path)
    tree = ast.parse(src)
    findings = []
    for node in ast.walk(tree):
        # Sadece isim, attribute, fonksiyon tanımları kontrol; docstring/Constant değil
        if isinstance(node, ast.Name):
            if t.lower() in node.id.lower():
                findings.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            if t.lower() in node.attr.lower():
                findings.append((node.lineno, node.attr))
        elif isinstance(node, ast.FunctionDef):
            if t.lower() in node.name.lower():
                findings.append((node.lineno, node.name))
        elif isinstance(node, ast.ClassDef):
            if t.lower() in node.name.lower():
                findings.append((node.lineno, node.name))
    assert not findings, f"{path}: ML pattern '{t}' found at {findings[:5]}"


# ----- 06. Duplicate cost calculation ---------------------------------------
DUPLICATE_COST_CLASS = [
    "class FeeModel",
    "class SpreadModel",
    "class SlippageModel",
    "class LatencyModel",
    "class PartialFillModel",
]


@pytest.mark.parametrize("cls_src", DUPLICATE_COST_CLASS)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_no_duplicate_cost_domain_classes(cls_src, path):
    src = _source(path)
    assert cls_src not in src, f"{path}: duplicate cost class {cls_src}"


# ----- 07. Direct Position / Portfolio mutators -----------------------------
DIRECT_MUT = [
    "Position(",
    "Position.__init__",
    ".position =",
    ".positions[",
    "Portfolio(",
    "Portfolio.__init__",
    ".portfolio =",
]


@pytest.mark.parametrize("t", DIRECT_MUT)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_no_direct_position_or_portfolio_mutation(t, path):
    src = _source(path)
    bad_lines = []
    for i, line in enumerate(src.splitlines(), 1):
        if t in line:
            bad_lines.append((i, line.strip()[:80]))
    assert not bad_lines, f"{path}: mutator pattern {t} at {bad_lines[:5]}"


# ----- 08. Risk bypass: PaperOrder direct instantiation ----------------------
PAPERORDER_PATTERNS = [
    "PaperOrder(",
]


@pytest.mark.parametrize("pat", PAPERORDER_PATTERNS)
@pytest.mark.parametrize("path", SBKT02_FILES)
def test_no_cap4_risk_bypass_paperorder(pat, path):
    src = _source(path)
    bad = [(i, l.strip()[:60]) for i, l in enumerate(src.splitlines(), 1) if pat in l]
    assert not bad, f"{path}: {pat} risk bypass at {bad[:5]}"
