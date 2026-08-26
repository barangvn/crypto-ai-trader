from __future__ import annotations

import math

import pytest

from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.strategies.base import _compute_momentum_raw_strength
from app.strategies import MomentumStrategy, MomentumStrategyOptions
from tests.strategies.conftest import make_strategy_context as _orig_make_ctx


def make_strategy_context(**kwargs):
    kwargs.setdefault("correlation_id", "CORR_STR_TEST_000001")
    kwargs.setdefault("causation_id", "CAUS_PARENT_000001")
    return _orig_make_ctx(**kwargs)


@pytest.fixture
def momentum_strategy():
    return MomentumStrategy()


ABS_MOM_VALUES = [10, 79, 80, 81, 150, 200, 250, 400]


@pytest.mark.parametrize("abs_bps", ABS_MOM_VALUES)
def test_abs_mom_thresholds_f_abs_values(abs_bps):
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=80.0,
        mom_entry_max_bps_abs=200.0,
        rsi_oversold_min=0.0,
        rsi_overbought_max=100.0,
    )
    fv = {
        "mom_10_abs": float(abs_bps),
        "mom_10_pct": 0.0,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_momentum_raw_strength(ctx, opts)
    if abs_bps < 80:
        f_abs = 0.0
    elif abs_bps >= 200:
        f_abs = 1.0
    else:
        f_abs = (abs_bps - 80.0) / (200.0 - 80.0)
    expected_raw = 0.55 * f_abs
    assert math.isclose(raw, expected_raw, abs_tol=0.01)


PCT_MOM_VALUES = [-0.01, 0.0, 0.001, 0.01, 0.02, 0.03]


@pytest.mark.parametrize("pct_mom", PCT_MOM_VALUES)
def test_pct_mom_thresholds_f_pct_values(pct_mom):
    opts = MomentumStrategyOptions(
        mom_pct_max_reference=0.02,
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=1.0,
        rsi_oversold_min=0.0,
        rsi_overbought_max=100.0,
    )
    fv = {
        "mom_10_abs": 0.0,
        "mom_10_pct": pct_mom,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_momentum_raw_strength(ctx, opts)
    if pct_mom <= 0:
        f_pct = 0.0
    else:
        f_pct = min(pct_mom / 0.02, 1.0)
    expected_raw = 0.45 * f_pct
    assert math.isclose(raw, expected_raw, abs_tol=0.01)


def test_weights_055_045_raw_verify():
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
        rsi_oversold_min=0.0,
        rsi_overbought_max=100.0,
    )
    fv = {
        "mom_10_abs": 100.0,
        "mom_10_pct": 0.01,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_momentum_raw_strength(ctx, opts)
    f_abs = 100.0 / 200.0
    f_pct = 0.01 / 0.02
    expected_raw = 0.55 * f_abs + 0.45 * f_pct
    assert math.isclose(raw, expected_raw, abs_tol=0.01)


RSI_BOUNDARY_VALUES = [30, 31, 32, 50, 73, 74, 75]


@pytest.mark.parametrize("rsi_val", RSI_BOUNDARY_VALUES)
def test_rsi_filter_seven_boundaries(rsi_val):
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
        rsi_oversold_min=32.0,
        rsi_overbought_max=74.0,
    )
    fv = {
        "mom_10_abs": 150.0,
        "mom_10_pct": 0.015,
        "rsi_14": float(rsi_val),
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_momentum_raw_strength(ctx, opts)
    if rsi_val < 32.0 or rsi_val > 74.0:
        assert raw == 0.0
    else:
        assert raw > 0.0


def test_fixture_weights_override_different_raw():
    opts_default = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
        rsi_oversold_min=0.0,
        rsi_overbought_max=100.0,
    )
    opts_custom = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
        rsi_oversold_min=0.0,
        rsi_overbought_max=100.0,
        momentum_component_weights=(0.80, 0.20),
    )
    fv = {
        "mom_10_abs": 200.0,
        "mom_10_pct": 0.002,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw_default = _compute_momentum_raw_strength(ctx, opts_default)
    raw_custom = _compute_momentum_raw_strength(ctx, opts_custom)
    expected_default = 0.55 * 1.0 + 0.45 * 0.1
    expected_custom = 0.80 * 1.0 + 0.20 * 0.1
    assert math.isclose(raw_default, expected_default, abs_tol=0.01)
    assert math.isclose(raw_custom, expected_custom, abs_tol=0.01)
    assert raw_custom != raw_default


def test_mom_both_zero_ss_zero_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 0.0,
            "mom_10_pct": 0.0,
            "rsi_14": 50.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.signal_strength == 0.0
    assert sig.direction == SignalDirection.HOLD


def test_mom_pct_only_abs_zero(momentum_strategy):
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=1.0,
    )
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 0.0,
            "mom_10_pct": 0.020,
            "rsi_14": 50.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength < 0.50
    assert sig.direction == SignalDirection.HOLD


def test_mom_both_perfect_ss_1_long(momentum_strategy):
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
        rsi_oversold_min=32.0,
        rsi_overbought_max=74.0,
    )
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 55.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength <= 1.0
    assert sig.signal_strength >= 0.95
    assert sig.direction == SignalDirection.LONG


def test_extreme_raw_clamped_1(momentum_strategy):
    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=0.0,
        mom_entry_max_bps_abs=200.0,
        mom_pct_max_reference=0.02,
    )
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 100000.0,
            "mom_10_pct": 10.0,
            "rsi_14": 55.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength == 1.0


def test_extreme_negative_clamped_0(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 0.0,
            "mom_10_pct": -10.0,
            "rsi_14": 50.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.signal_strength == 0.0
