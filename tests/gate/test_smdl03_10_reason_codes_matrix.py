from decimal import Decimal

import pytest

from app.contracts.model import CCWinnerEnum
from app.gate import (
    ERR_GATE_EVAL_INCOMPARABLE,
    ERR_GATE_EVAL_STALE,
    ERR_GATE_EVIDENCE_INTEGRITY_FAIL,
    ERR_GATE_HARD_DRAWDOWN_WORSENED,
    ERR_GATE_HARD_OOS_FLAG_FALSE,
    ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY,
    ERR_GATE_HARD_RETURN_NOT_POSITIVE,
    ERR_GATE_HARD_SHARPE_NEGATIVE,
    ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT,
    ERR_GATE_MIN_APPROVALS_FAIL,
    ERR_GATE_MIN_TOTAL_SCORE_UNMET,
    ERR_GATE_WEIGHT_MISSING_REQUIRED,
    ERR_GATE_WEIGHT_OUT_OF_RANGE,
    ERR_GATE_WEIGHT_SUM_INVALID,
    ERR_GATE_WEIGHT_UNKNOWN_KEY,
    ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN,
    GateValidationError,
    PromotionGate,
    THRESHOLD_FAIL_BY_METRIC_KEY,
    ThresholdsConfig,
    WeightsConfig,
    approval_minimum_readonly,
    default_thresholds_v1,
    default_weights_v1,
    evidence_integrity_check,
    validate_weights_definition,
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


def _build_cr(
    champion_metrics, challenger_metrics,
    winner_hint=CCWinnerEnum.CHALLENGER_PROMOTED,
    comparable=True, eval_ts=DEFAULT_EVAL_TS,
    metadata=None,
):
    deltas = _make_metric_deltas(champion_metrics, challenger_metrics)
    payload = _make_payload(
        winner_hint=winner_hint,
        comparable=comparable,
        challenger_metrics=challenger_metrics,
        evaluation_ts=eval_ts,
        metadata=metadata,
    )
    return DummyCompareResult(
        payload=payload, comparable=comparable,
        metric_deltas=deltas, champion_eval=_make_model_eval(champion_metrics),
        metadata=metadata or {},
    )


@pytest.fixture
def baseline_champion():
    return _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.6, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )


def test_rc_weight_sum_invalid_raises():
    w = default_weights_v1()
    w["return_pct"] = 0.90
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_SUM_INVALID


def test_rc_weight_out_of_range_raises():
    w = default_weights_v1()
    w["return_pct"] = -0.05
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_OUT_OF_RANGE


def test_rc_weight_missing_required_raises():
    w = default_weights_v1()
    del w["return_pct"]
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_MISSING_REQUIRED


def test_rc_weight_unknown_key_raises():
    w = default_weights_v1()
    w["weird_metric_xyz"] = 0.01
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_UNKNOWN_KEY


def test_rc_hard_return_not_positive(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["return_pct"] = Decimal("0.08")
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_RETURN_NOT_POSITIVE in result["reasons"]
    assert result["passed"] is False


def test_rc_hard_drawdown_worsened(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["max_drawdown_pct"] = 0.15
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_DRAWDOWN_WORSENED in result["reasons"]
    assert result["passed"] is False


def test_rc_hard_sharpe_negative(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["sharpe_ratio"] = -0.2
    challenger["return_pct"] = Decimal("0.15")
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_SHARPE_NEGATIVE in result["reasons"]
    assert result["passed"] is False


def test_rc_hard_profit_factor_subunity(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["profit_factor"] = 0.9
    challenger["return_pct"] = Decimal("0.15")
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY in result["reasons"]
    assert result["passed"] is False


def test_rc_hard_trade_count_insufficient(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["trade_count"] = 10
    challenger["return_pct"] = Decimal("0.15")
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT in result["reasons"]
    assert result["passed"] is False


def test_rc_hard_oos_flag_false(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["oos_flag"] = False
    challenger["return_pct"] = Decimal("0.15")
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_OOS_FLAG_FALSE in result["reasons"]
    assert result["passed"] is False


def test_rc_eval_stale(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["return_pct"] = Decimal("0.15")
    challenger["max_drawdown_pct"] = 0.05
    cr = _build_cr(baseline_champion, challenger, eval_ts="2024-01-01T00:00:00")
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_EVAL_STALE in result["reasons"]
    assert result["passed"] is False


def test_rc_eval_incomparable(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["return_pct"] = Decimal("0.15")
    challenger["max_drawdown_pct"] = 0.05
    cr = _build_cr(baseline_champion, challenger, comparable=False)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_EVAL_INCOMPARABLE in result["reasons"]
    assert result["passed"] is False


def test_rc_evidence_integrity_fail():
    refs = [{"integrity_ok": False}]
    assert ERR_GATE_EVIDENCE_INTEGRITY_FAIL in evidence_integrity_check(refs)
    md = {"evidence_integrity": False}
    assert ERR_GATE_EVIDENCE_INTEGRITY_FAIL in evidence_integrity_check(metadata=md)


def test_rc_winner_hint_inconclusive_rerun(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["return_pct"] = Decimal("0.15")
    challenger["max_drawdown_pct"] = 0.05
    cr = _build_cr(baseline_champion, challenger, winner_hint=CCWinnerEnum.INCONCLUSIVE_RERUN)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN in result["reasons"]
    assert result["passed"] is False


def test_rc_min_approvals_fail():
    assert ERR_GATE_MIN_APPROVALS_FAIL in approval_minimum_readonly(approval_refs=[], min_count=1)
    assert ERR_GATE_MIN_APPROVALS_FAIL in approval_minimum_readonly(approval_refs=None, min_count=1)


def test_rc_min_approvals_pass():
    assert approval_minimum_readonly(["a1"], 1) == []
    assert approval_minimum_readonly(["a1", "a2"], 1) == []
    assert approval_minimum_readonly(["a1", "a2"], 2) == []


def test_rc_threshold_return_pct_fail(baseline_champion):
    challenger = dict(baseline_champion)
    challenger["return_pct"] = Decimal("0.005")
    challenger["sharpe_ratio"] = 1.5
    challenger["profit_factor"] = 1.3
    challenger["trade_count"] = 100
    challenger["oos_flag"] = True
    cr = _build_cr(baseline_champion, challenger)
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert THRESHOLD_FAIL_BY_METRIC_KEY["return_pct"] in result["reasons"]
    assert result["passed"] is False


def test_rc_min_total_score_unmet():
    w = WeightsConfig()
    t = ThresholdsConfig()
    t.meta_thresholds["min_total_score"] = 0.99
    champion = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.5, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )
    challenger = dict(champion)
    challenger["return_pct"] = Decimal("0.12")
    challenger["max_drawdown_pct"] = 0.08
    cr = _build_cr(champion, challenger)
    gate = PromotionGate(weights_cfg=w, thresholds_cfg=t)
    result = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_MIN_TOTAL_SCORE_UNMET in result["reasons"]
    assert result["passed"] is False
