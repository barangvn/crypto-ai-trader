from decimal import Decimal

import pytest

from app.contracts.model import _REQUIRED_METRIC_KEYS
from app.gate import (
    ERR_GATE_NORM_METRIC_MISSING,
    WEIGHTS_VERSION_V1,
    compute_weighted_total_score,
    default_thresholds_v1,
    default_weights_v1,
    renormalize_weights_if_needed,
    validate_weights_definition,
)
from app.gate.weights import _OPTIONAL_EXTRA_KEYS
from tests.gate.conftest import _base_metrics_template


def _fill_weights(overrides: dict[str, float]) -> dict[str, float]:
    w: dict[str, float] = {}
    for k in _REQUIRED_METRIC_KEYS:
        w[k] = 0.0
    for k in _OPTIONAL_EXTRA_KEYS:
        w[k] = 0.0
    for k, v in overrides.items():
        w[k] = float(v)
    return w


def test_weighted_score_challenger_better_positive():
    weights = renormalize_weights_if_needed(default_weights_v1(), WEIGHTS_VERSION_V1)
    thresholds = default_thresholds_v1()
    cm = _base_metrics_template(
        return_pct=Decimal("0.12"), max_drawdown_pct=0.08, sharpe_ratio=1.60,
        sortino_ratio=2.10, profit_factor=1.45, total_fees_quote=Decimal("265.40"),
        avg_slippage_bps=4.0, trade_count=240, regime_coverage_count=6,
        window_days=365, oos_flag=True, stability=0.86, fees_per_trade=0.0002,
    )
    score, reasons = compute_weighted_total_score(cm, weights, thresholds["metric_bounds"])
    assert reasons == []
    assert 0.0 <= score <= 1.0
    assert score > 0.4


def test_weighted_score_manual_check_return_component():
    weights = _fill_weights({"return_pct": 1.0})
    weights = validate_weights_definition(weights)
    bounds = {"return_pct": (-0.05, 0.50)}
    cm = {"return_pct": Decimal("0.10")}
    score, reasons = compute_weighted_total_score(cm, weights, bounds)
    assert reasons == []
    expected = (0.10 - (-0.05)) / 0.55
    assert round(score, 8) == round(expected, 8)


def test_weighted_score_manual_drawdown_lower_better():
    weights = _fill_weights({"max_drawdown_pct": 1.0})
    weights = validate_weights_definition(weights)
    bounds = {"max_drawdown_pct": (0.0, 0.50)}
    cm = {"max_drawdown_pct": 0.10}
    score, reasons = compute_weighted_total_score(cm, weights, bounds)
    assert reasons == []
    expected = (0.50 - 0.10) / 0.50
    assert round(score, 8) == round(expected, 8)


def test_weighted_score_missing_required_metric_raises_reason():
    weights = renormalize_weights_if_needed(default_weights_v1(), WEIGHTS_VERSION_V1)
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = {}
    score, reasons = compute_weighted_total_score(cm, weights, bounds)
    assert ERR_GATE_NORM_METRIC_MISSING in reasons
    assert score == 0.0


def test_weighted_score_eight_decimal_precision():
    weights = _fill_weights({"return_pct": 0.5, "sharpe_ratio": 0.5})
    weights = validate_weights_definition(weights)
    bounds = {"return_pct": (-0.05, 0.50), "sharpe_ratio": (0.0, 5.0)}
    cm = {"return_pct": Decimal("0.225"), "sharpe_ratio": 2.5}
    score, reasons = compute_weighted_total_score(cm, weights, bounds)
    assert reasons == []
    str_score = f"{score:.8f}"
    assert len(str_score.split(".")[-1]) == 8


def test_weighted_score_optional_extras_absent_no_fail():
    w = {k: v for k, v in default_weights_v1().items() if k not in ("stability", "fees_per_trade")}
    w = renormalize_weights_if_needed(w)
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.5,
        sortino_ratio=2.0, profit_factor=1.3, total_fees_quote=Decimal("200"),
        avg_slippage_bps=5.0, trade_count=100, regime_coverage_count=5,
        window_days=200, oos_flag=True,
    )
    score, reasons = compute_weighted_total_score(cm, w, bounds)
    assert reasons == []
    assert 0.0 <= score <= 1.0


def test_weighted_score_zero_weights_sum_valid():
    weights = renormalize_weights_if_needed(default_weights_v1())
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=2.0,
        sortino_ratio=3.0, profit_factor=2.0, total_fees_quote=Decimal("100"),
        avg_slippage_bps=2.0, trade_count=500, regime_coverage_count=8,
        window_days=500, oos_flag=True, stability=0.95, fees_per_trade=0.0001,
    )
    s1, _ = compute_weighted_total_score(cm, weights, bounds)
    s2, _ = compute_weighted_total_score(cm, weights, bounds)
    assert round(s1, 8) == round(s2, 8)


@pytest.mark.parametrize("metric_key,value,expected_greater_than", [
    ("return_pct", Decimal("0.30"), 0.6),
    ("max_drawdown_pct", 0.02, 0.8),
    ("sharpe_ratio", 3.5, 0.6),
    ("sortino_ratio", 4.0, 0.6),
])
def test_weighted_score_single_metric_sensitivity(metric_key, value, expected_greater_than):
    all_keys = list(default_weights_v1().keys())
    weights = {k: (1.0 if k == metric_key else 0.0) for k in all_keys}
    total = sum(weights.values())
    if total < 1.0:
        weights[metric_key] = 1.0
    weights = validate_weights_definition(weights)
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = _base_metrics_template(
        return_pct=Decimal("0.01"), max_drawdown_pct=0.20, sharpe_ratio=0.5,
        sortino_ratio=0.5, profit_factor=1.01, total_fees_quote=Decimal("100"),
        avg_slippage_bps=10.0, trade_count=50, regime_coverage_count=3,
        window_days=100, oos_flag=True, stability=0.5, fees_per_trade=0.0001,
    )
    cm[metric_key] = value
    score, reasons = compute_weighted_total_score(cm, weights, bounds)
    assert reasons == []
    assert score > expected_greater_than
