from decimal import Decimal

import pytest

from app.gate import (
    ERR_GATE_HARD_DRAWDOWN_WORSENED,
    ERR_GATE_HARD_OOS_FLAG_FALSE,
    ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY,
    ERR_GATE_HARD_RETURN_NOT_POSITIVE,
    ERR_GATE_HARD_SHARPE_NEGATIVE,
    ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT,
    check_hard_constraints,
)
from tests.gate.conftest import _base_metrics_template


@pytest.fixture
def hard_ok_challenger():
    return _base_metrics_template(
        return_pct=Decimal("0.15"), max_drawdown_pct=0.06, sharpe_ratio=1.8,
        sortino_ratio=2.2, profit_factor=1.5, total_fees_quote=Decimal("200"),
        avg_slippage_bps=5.0, trade_count=100, regime_coverage_count=5,
        window_days=300, oos_flag=True,
    )


@pytest.fixture
def hard_ok_champion():
    return _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.5, profit_factor=1.3, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=80, regime_coverage_count=4,
        window_days=280, oos_flag=True,
    )


def test_hard_constraints_all_pass(hard_ok_challenger, hard_ok_champion):
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert reasons == []


def test_hard_return_not_positive(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["return_pct"] = hard_ok_champion["return_pct"]
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_RETURN_NOT_POSITIVE in reasons


def test_hard_return_negative(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["return_pct"] = Decimal("-0.02")
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_RETURN_NOT_POSITIVE in reasons


def test_hard_drawdown_worsened(hard_ok_challenger, hard_ok_champion):
    hard_ok_champion["max_drawdown_pct"] = 0.05
    hard_ok_challenger["max_drawdown_pct"] = 0.08
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_DRAWDOWN_WORSENED in reasons


def test_hard_sharpe_negative(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["sharpe_ratio"] = -0.1
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_SHARPE_NEGATIVE in reasons


def test_hard_profit_factor_subunity(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["profit_factor"] = 0.95
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY in reasons


def test_hard_profit_factor_exactly_one(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["profit_factor"] = 1.00
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY not in reasons


def test_hard_trade_count_insufficient(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["trade_count"] = 29
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT in reasons


def test_hard_trade_count_exactly_30(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["trade_count"] = 30
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT not in reasons


def test_hard_oos_flag_false(hard_ok_challenger, hard_ok_champion):
    hard_ok_challenger["oos_flag"] = False
    reasons = check_hard_constraints(hard_ok_challenger, hard_ok_champion)
    assert ERR_GATE_HARD_OOS_FLAG_FALSE in reasons


def test_hard_multiple_failures():
    bad = _base_metrics_template(
        return_pct=Decimal("-0.01"), max_drawdown_pct=0.20, sharpe_ratio=-1.0,
        sortino_ratio=0.5, profit_factor=0.5, total_fees_quote=Decimal("100"),
        avg_slippage_bps=5.0, trade_count=5, regime_coverage_count=1,
        window_days=100, oos_flag=False,
    )
    champion = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.05, sharpe_ratio=1.0,
        sortino_ratio=1.0, profit_factor=1.3, total_fees_quote=Decimal("100"),
        avg_slippage_bps=5.0, trade_count=100, regime_coverage_count=5,
        window_days=100, oos_flag=True,
    )
    reasons = check_hard_constraints(bad, champion)
    assert len(reasons) >= 5
