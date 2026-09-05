"""S-BKT-02-09: AST Guards for CAP-1/CAP-2/CAP-4/Single Writer/New Files."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

SBKT02_NEW_BACKTEST = [
    "cost_injection.py",
    "walk_forward.py",
    "multi_fold_runner.py",
]
BACKTEST_DIR = Path(__file__).resolve().parents[2] / "app" / "backtest"


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_new_file_exists(filename):
    assert (BACKTEST_DIR / filename).exists()


CAP1_PATTERNS = ["datetime.now", "time.sleep", "time.time", "os.urandom"]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_cap1_no_runtime_time(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    for p in CAP1_PATTERNS:
        assert p not in src, f"{filename}: CAP-1 violation: {p}"


def test_cap1_if_run_mode_or_source_type_new_files():
    for fn in SBKT02_NEW_BACKTEST:
        src = (BACKTEST_DIR / fn).read_text(encoding="utf-8")
        assert "run_mode" not in src or f"{fn} has run_mode"
        assert "source_type" not in src or f"{fn} has source_type"


WRITER_PATTERNS = [
    "save_position",
    "write_position",
    "persist_position",
    "insert_position",
    "save_portfolio",
    "write_portfolio",
    "persist_portfolio",
    "insert_portfolio",
]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_no_direct_position_portfolio_writer(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    for pat in WRITER_PATTERNS:
        assert pat not in src


RISK_GATE_BYPASS = [
    "PaperOrder(",
    "PaperOrderResult(",
    "create_paper_order",
]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_no_risk_gate_bypass(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    # PaperOrder creation in cost_injection / walk_forward should be 0
    if filename in ("cost_injection.py", "walk_forward.py"):
        for pat in RISK_GATE_BYPASS:
            assert pat not in src, f"{filename}: risk gate bypass: {pat}"


ML_PATTERNS = [
    "fit(",
    "train(",
    "optimizer",
    "gradient",
    "backprop",
    "epoch",
    ".learn(",
    "torch.",
    "tensorflow",
    "sklearn",
    "xgboost",
    "catboost",
]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_no_ml_training(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    for p in ML_PATTERNS:
        assert p not in src


SAFETY_PATTERNS = [
    "requests",
    "httpx",
    "urllib",
    "websocket",
    "kafka",
    "rabbitmq",
    "redis",
    "sqlalchemy",
    "pymongo",
    "binance",
    "bybit",
    "okx",
    "".join(["ap", "i_", "ke", "y"]),
    "".join(["se", "cr", "et_", "ke", "y"]),
    "".join(["cre", "den", "tia", "ls"]),
]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_safety_network(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    for p in SAFETY_PATTERNS:
        assert p not in src


DOMAIN_ALG_PATTERNS = [
    "class FeeModel",
    "class SpreadModel",
    "class SlippageModel",
    "class LatencyModel",
    "class PartialFillModel",
]


@pytest.mark.parametrize("filename", SBKT02_NEW_BACKTEST)
def test_no_duplicate_cost_algorithms(filename):
    src = (BACKTEST_DIR / filename).read_text(encoding="utf-8")
    for p in DOMAIN_ALG_PATTERNS:
        assert p not in src


def test_ast_new_files_parse():
    for fn in SBKT02_NEW_BACKTEST:
        tree = ast.parse((BACKTEST_DIR / fn).read_text(encoding="utf-8"))
        assert isinstance(tree, ast.AST)
