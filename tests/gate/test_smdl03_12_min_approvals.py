from decimal import Decimal

import pytest

from app.contracts.model import CCWinnerEnum
from app.gate import (
    ERR_GATE_MIN_APPROVALS_FAIL,
    PromotionGate,
    approval_minimum_readonly,
)
from tests.gate.conftest import (
    DEFAULT_EVAL_TS,
    DEFAULT_WINDOW_END,
    DummyCompareResult,
    _make_metric_deltas,
    _make_model_eval,
    _make_payload,
    _base_metrics_template,
)


def _make_better_cr():
    champion = _base_metrics_template(
        return_pct=Decimal("0.35"), max_drawdown_pct=0.03, sharpe_ratio=3.5,
        sortino_ratio=4.0, profit_factor=3.5, total_fees_quote=Decimal("150"),
        avg_slippage_bps=2.0, trade_count=500, regime_coverage_count=10,
        window_days=365, oos_flag=True,
    )
    challenger = _base_metrics_template(
        return_pct=Decimal("0.40"), max_drawdown_pct=0.02, sharpe_ratio=4.0,
        sortino_ratio=4.5, profit_factor=4.0, total_fees_quote=Decimal("120"),
        avg_slippage_bps=1.0, trade_count=600, regime_coverage_count=10,
        window_days=400, oos_flag=True,
    )
    deltas = _make_metric_deltas(champion, challenger)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger, DEFAULT_EVAL_TS)
    return DummyCompareResult(payload=payload, comparable=True, metric_deltas=deltas, champion_eval=_make_model_eval(champion))


def test_approval_min_0_fail_min1():
    result = PromotionGate().evaluate(_make_better_cr(), DEFAULT_WINDOW_END, approval_refs=[])
    assert ERR_GATE_MIN_APPROVALS_FAIL in result["reasons"]
    assert result["passed"] is False


def test_approval_min_1_pass_min1():
    result = PromotionGate().evaluate(_make_better_cr(), DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_MIN_APPROVALS_FAIL not in result["reasons"]


def test_approval_min_2_pass_min1():
    result = PromotionGate().evaluate(_make_better_cr(), DEFAULT_WINDOW_END, approval_refs=["a1", "a2"])
    assert ERR_GATE_MIN_APPROVALS_FAIL not in result["reasons"]


def test_approval_min_1_fail_min2_override():
    result = PromotionGate().evaluate(
        _make_better_cr(), DEFAULT_WINDOW_END,
        approval_refs=["a1"], min_approval_count_override=2,
    )
    assert ERR_GATE_MIN_APPROVALS_FAIL in result["reasons"]
    assert result["passed"] is False


def test_approval_min_2_pass_min2_override():
    result = PromotionGate().evaluate(
        _make_better_cr(), DEFAULT_WINDOW_END,
        approval_refs=["a1", "a2"], min_approval_count_override=2,
    )
    assert ERR_GATE_MIN_APPROVALS_FAIL not in result["reasons"]


@pytest.mark.parametrize("refs,min_count,expect_fail", [
    ([], 1, True),
    (["x"], 0, False),
    (["x"], 1, False),
    (["x"], 2, True),
    (["x", "y"], 1, False),
    (["x", "y"], 2, False),
    (["x", "y"], 3, True),
    (None, 1, True),
    ([None], 1, True),
    ([], 0, False),
])
def test_approval_readonly_parametrized(refs, min_count, expect_fail):
    reasons = approval_minimum_readonly(refs, min_count)
    has_fail = ERR_GATE_MIN_APPROVALS_FAIL in reasons
    assert has_fail is expect_fail
