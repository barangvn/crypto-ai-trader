from decimal import Decimal

import pytest

from app.gate import (
    THRESHOLD_FAIL_BY_METRIC_KEY,
    check_soft_thresholds,
    default_thresholds_v1,
)
from tests.gate.conftest import _base_metrics_template


@pytest.fixture
def perfect_challenger() -> dict:
    return _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=2.0,
        sortino_ratio=2.5, profit_factor=1.8, total_fees_quote=Decimal("150"),
        avg_slippage_bps=5.0, trade_count=200, regime_coverage_count=6,
        window_days=300, oos_flag=True,
    )


@pytest.fixture
def champion_for_fees() -> dict:
    return _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.08, sharpe_ratio=1.5,
        sortino_ratio=2.0, profit_factor=1.4, total_fees_quote=Decimal("200"),
        avg_slippage_bps=10.0, trade_count=150, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )


def test_soft_thresholds_all_pass(perfect_challenger, champion_for_fees):
    reasons = check_soft_thresholds(perfect_challenger, champion_for_fees)
    assert reasons == []


FAIL_CASES = [
    ("return_pct", Decimal("-0.005"), "THRESHOLD_RETURN_PCT_FAIL"),
    ("return_pct", Decimal("0.005"), "THRESHOLD_RETURN_PCT_FAIL"),
    ("max_drawdown_pct", 0.30, "THRESHOLD_MAX_DRAWDOWN_PCT_FAIL"),
    ("sharpe_ratio", 0.5, "THRESHOLD_SHARPE_RATIO_FAIL"),
    ("sortino_ratio", 0.8, "THRESHOLD_SORTINO_RATIO_FAIL"),
    ("profit_factor", 1.05, "THRESHOLD_PROFIT_FACTOR_FAIL"),
    ("avg_slippage_bps", 25.0, "THRESHOLD_AVG_SLIPPAGE_BPS_FAIL"),
    ("trade_count", 15, "THRESHOLD_TRADE_COUNT_FAIL"),
    ("regime_coverage_count", 1, "THRESHOLD_REGIME_COVERAGE_COUNT_FAIL"),
    ("window_days", 45, "THRESHOLD_WINDOW_DAYS_FAIL"),
    ("oos_flag", False, "THRESHOLD_OOS_FLAG_FAIL"),
]


@pytest.mark.parametrize("key,bad_value,expected_reason", FAIL_CASES)
def test_soft_thresholds_single_fail(key, bad_value, expected_reason, perfect_challenger, champion_for_fees):
    perfect_challenger[key] = bad_value
    reasons = check_soft_thresholds(perfect_challenger, champion_for_fees)
    assert expected_reason in reasons


def test_soft_thresholds_fees_too_high_vs_champion(perfect_challenger, champion_for_fees):
    champion_for_fees["total_fees_quote"] = Decimal("200")
    perfect_challenger["total_fees_quote"] = Decimal("250")
    reasons = check_soft_thresholds(perfect_challenger, champion_for_fees)
    assert "THRESHOLD_TOTAL_FEES_QUOTE_FAIL" in reasons


def test_soft_thresholds_fees_within_10_pct_ok(perfect_challenger, champion_for_fees):
    champion_for_fees["total_fees_quote"] = Decimal("200")
    perfect_challenger["total_fees_quote"] = Decimal("210")
    reasons = check_soft_thresholds(perfect_challenger, champion_for_fees)
    assert "THRESHOLD_TOTAL_FEES_QUOTE_FAIL" not in reasons


def test_soft_thresholds_multiple_fails_detected():
    bad = _base_metrics_template(
        return_pct=Decimal("-0.01"), max_drawdown_pct=0.50, sharpe_ratio=-0.5,
        sortino_ratio=0.0, profit_factor=0.5, total_fees_quote=Decimal("500"),
        avg_slippage_bps=40.0, trade_count=5, regime_coverage_count=1,
        window_days=30, oos_flag=False,
    )
    champion = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.0,
        sortino_ratio=1.5, profit_factor=1.3, total_fees_quote=Decimal("100"),
        avg_slippage_bps=10.0, trade_count=100, regime_coverage_count=5,
        window_days=200, oos_flag=True,
    )
    reasons = check_soft_thresholds(bad, champion)
    assert len(reasons) >= 8


def test_soft_thresholds_missing_metric_still_reports():
    incomplete = {"oos_flag": True}
    champion = {"total_fees_quote": Decimal("100")}
    reasons = check_soft_thresholds(incomplete, champion)
    assert len(reasons) >= 6


def test_soft_thresholds_pass_exact_boundary_return():
    cfg = default_thresholds_v1()
    ok = _base_metrics_template(
        return_pct=Decimal("0.01"), max_drawdown_pct=0.10, sharpe_ratio=1.0,
        sortino_ratio=1.2, profit_factor=1.2, total_fees_quote=Decimal("100"),
        avg_slippage_bps=15.0, trade_count=30, regime_coverage_count=3,
        window_days=90, oos_flag=True,
    )
    champion = {"total_fees_quote": Decimal("100")}
    reasons = check_soft_thresholds(ok, champion)
    assert reasons == []
