import math
from decimal import Decimal

import pytest

from app.contracts.model import _REQUIRED_METRIC_KEYS
from app.evaluation.delta import Directionality
from app.gate import (
    ERR_GATE_NORM_BOUNDS_INVALID,
    ERR_GATE_NORM_METRIC_MISSING,
    default_thresholds_v1,
    normalize_metric,
)


NORM_CASES = [
    ("return_pct", 0.01, (-0.05, 0.50), Directionality.HIGHER_BETTER, (0.01 - (-0.05)) / 0.55),
    ("return_pct", -0.05, (-0.05, 0.50), Directionality.HIGHER_BETTER, 0.0),
    ("return_pct", 0.50, (-0.05, 0.50), Directionality.HIGHER_BETTER, 1.0),
    ("return_pct", 0.60, (-0.05, 0.50), Directionality.HIGHER_BETTER, 1.0),
    ("return_pct", -0.10, (-0.05, 0.50), Directionality.HIGHER_BETTER, 0.0),
    ("max_drawdown_pct", 0.10, (0.0, 0.50), Directionality.LOWER_BETTER, (0.50 - 0.10) / 0.50),
    ("max_drawdown_pct", 0.0, (0.0, 0.50), Directionality.LOWER_BETTER, 1.0),
    ("max_drawdown_pct", 0.50, (0.0, 0.50), Directionality.LOWER_BETTER, 0.0),
    ("sharpe_ratio", 1.0, (0.0, 5.0), Directionality.HIGHER_BETTER, 0.2),
    ("sharpe_ratio", 0.0, (0.0, 5.0), Directionality.HIGHER_BETTER, 0.0),
    ("sharpe_ratio", 5.0, (0.0, 5.0), Directionality.HIGHER_BETTER, 1.0),
    ("sortino_ratio", 1.5, (0.0, 5.0), Directionality.HIGHER_BETTER, 0.3),
    ("profit_factor", 1.5, (0.0, 5.0), Directionality.HIGHER_BETTER, 0.3),
    ("profit_factor", 1.0, (0.0, 5.0), Directionality.HIGHER_BETTER, 0.2),
    ("total_fees_quote", 100.0, (0.0, 500.0), Directionality.LOWER_BETTER, (500.0 - 100.0) / 500.0),
    ("total_fees_quote", 0.0, (0.0, 500.0), Directionality.LOWER_BETTER, 1.0),
    ("total_fees_quote", 500.0, (0.0, 500.0), Directionality.LOWER_BETTER, 0.0),
    ("avg_slippage_bps", 5.0, (0.0, 50.0), Directionality.LOWER_BETTER, 0.9),
    ("avg_slippage_bps", 15.0, (0.0, 50.0), Directionality.LOWER_BETTER, 0.7),
    ("avg_slippage_bps", 30.0, (0.0, 50.0), Directionality.LOWER_BETTER, 0.4),
    ("trade_count", 100, (0.0, 1000.0), Directionality.HIGHER_BETTER, 0.1),
    ("trade_count", 30, (0.0, 1000.0), Directionality.HIGHER_BETTER, 0.03),
    ("regime_coverage_count", 5, (0.0, 10.0), Directionality.HIGHER_BETTER, 0.5),
    ("window_days", 365, (0.0, 730.0), Directionality.HIGHER_BETTER, 0.5),
    ("window_days", 90, (0.0, 730.0), Directionality.HIGHER_BETTER, 90.0 / 730.0),
    ("oos_flag", True, (0.0, 1.0), Directionality.HIGHER_BETTER, 1.0),
    ("oos_flag", False, (0.0, 1.0), Directionality.HIGHER_BETTER, 0.0),
    ("stability", 0.80, (0.0, 1.0), Directionality.HIGHER_BETTER, 0.8),
    ("fees_per_trade", 0.0002, (0.0, 0.001), Directionality.LOWER_BETTER, (0.001 - 0.0002) / 0.001),
]


@pytest.mark.parametrize("key,value,bounds,direction,expected", NORM_CASES)
def test_normalize_metric_exact_match(key, value, bounds, direction, expected):
    got, reason = normalize_metric(key, value, bounds, direction)
    assert reason is None
    assert round(got, 8) == round(expected, 8)


def test_normalize_metric_bounds_invalid_equal():
    got, reason = normalize_metric("return_pct", 0.01, (0.0, 0.0), Directionality.HIGHER_BETTER)
    assert reason == ERR_GATE_NORM_BOUNDS_INVALID
    assert got == 0.0


def test_normalize_metric_bounds_inverted():
    got, reason = normalize_metric("return_pct", 0.01, (0.5, 0.1), Directionality.HIGHER_BETTER)
    assert reason == ERR_GATE_NORM_BOUNDS_INVALID


def test_normalize_metric_missing_nan():
    got, reason = normalize_metric("return_pct", float("nan"), (-0.05, 0.50), Directionality.HIGHER_BETTER)
    assert reason == ERR_GATE_NORM_METRIC_MISSING


def test_normalize_metric_default_direction():
    got, reason = normalize_metric("return_pct", 0.10, (-0.05, 0.50))
    assert reason is None
    assert round(got, 8) == round((0.10 - (-0.05)) / 0.55, 8)


def test_normalize_metric_decimal_value():
    got, reason = normalize_metric("return_pct", Decimal("0.10"), (-0.05, 0.50))
    assert reason is None
    assert round(got, 8) == round((0.10 - (-0.05)) / 0.55, 8)


def test_normalize_metric_int_value():
    got, reason = normalize_metric("trade_count", 500, (0.0, 1000.0))
    assert reason is None
    assert round(got, 8) == 0.5


def test_normalize_metric_bool_true():
    got, reason = normalize_metric("oos_flag", True, (0.0, 1.0))
    assert reason is None
    assert got == 1.0


def test_normalize_metric_bool_false():
    got, reason = normalize_metric("oos_flag", False, (0.0, 1.0))
    assert reason is None
    assert got == 0.0


@pytest.mark.parametrize("bad_bounds", [None, (1.0,), "abc", 42])
def test_normalize_metric_bad_bounds_type(bad_bounds):
    got, reason = normalize_metric("return_pct", 0.01, bad_bounds)
    assert reason == ERR_GATE_NORM_BOUNDS_INVALID


def test_default_thresholds_v1_metric_bounds_present():
    cfg = default_thresholds_v1()
    for key in _REQUIRED_METRIC_KEYS:
        assert key in cfg["metric_bounds"]
        lo, hi = cfg["metric_bounds"][key]
        assert hi > lo
