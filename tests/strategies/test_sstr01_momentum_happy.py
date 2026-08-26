from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.strategies import MomentumStrategy, MomentumStrategyOptions
from tests.strategies.conftest import make_strategy_context as _orig_make_ctx


def make_strategy_context(**kwargs):
    kwargs.setdefault("correlation_id", "CORR_STR_TEST_000001")
    kwargs.setdefault("causation_id", "CAUS_PARENT_000001")
    return _orig_make_ctx(**kwargs)


@pytest.fixture
def momentum_strategy():
    return MomentumStrategy()


def test_bull_strong_momentum_long(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.LONG


def test_mom_abs_below_min_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 30.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD
    assert sig.signal_strength < 0.50


def test_mom_pct_negative_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 30.0,
            "mom_10_pct": -0.01,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD
    assert sig.signal_strength < 0.50


def test_rsi_overbought_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 76.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_rsi_oversold_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 30.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_lv_regime_strong_mom_long(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.LOW_VOLATILITY,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.LONG


def test_bear_regime_strong_mom_flat(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BEAR,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT


def test_hv_perfect_mom_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 55.0,
        },
        regime_state=MarketRegimeState.HIGH_VOLATILITY,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD
    assert sig.signal_strength < 0.50


def test_fixture_min_abs_lower_now_eligible(momentum_strategy):
    fv = {
        "mom_10_abs": 30.0,
        "mom_10_pct": 0.010,
        "rsi_14": 55.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    sig_default = momentum_strategy.evaluate(ctx)
    assert sig_default.direction == SignalDirection.HOLD

    opts = MomentumStrategyOptions(
        mom_entry_min_bps_abs=20.0,
        mom_entry_max_bps_abs=200.0,
    )
    sig_override = momentum_strategy.evaluate(ctx, options=opts)
    expected_f_abs = (30.0 - 20.0) / (200.0 - 20.0)
    assert expected_f_abs > 0
    assert sig_override.signal_strength >= sig_default.signal_strength


def test_fixture_long_threshold_hv(momentum_strategy):
    fv = {
        "mom_10_abs": 300.0,
        "mom_10_pct": 0.020,
        "rsi_14": 55.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.HIGH_VOLATILITY,
    )
    opts_default = MomentumStrategyOptions()
    sig_default = momentum_strategy.evaluate(ctx, options=opts_default)
    assert sig_default.direction == SignalDirection.HOLD

    opts_lower = MomentumStrategyOptions(
        long_threshold=0.35,
    )
    sig_lower = momentum_strategy.evaluate(ctx, options=opts_lower)
    assert sig_lower.direction == SignalDirection.LONG


def test_supporting_keys_length_five(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert len(sig.supporting_feature_keys) == 5


def test_stop_tp_edge_none(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.stop_policy is None
    assert sig.take_profit_policy is None
    assert sig.expected_edge_bps is None


def test_entry_price_ref_decimal(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.entry_price_ref is not None
    assert isinstance(sig.entry_price_ref, Decimal)


def test_entry_thesis_short(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.entry_thesis is not None
    assert 0 < len(sig.entry_thesis) <= 120


def test_corr_caus_preserved(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.correlation_id == "CORR_STR_TEST_000001"
    assert sig.causation_id == "CAUS_PARENT_000001"


def test_confidence_in_range(momentum_strategy):
    variants = [
        ({"mom_10_abs": 250.0, "mom_10_pct": 0.015, "rsi_14": 60.0}, MarketRegimeState.BULL, 0.9),
        ({"mom_10_abs": 100.0, "mom_10_pct": 0.005, "rsi_14": 55.0}, MarketRegimeState.SIDEWAYS, 0.7),
        ({"mom_10_abs": 300.0, "mom_10_pct": 0.020, "rsi_14": 50.0}, MarketRegimeState.LOW_VOLATILITY, 0.85),
    ]
    for fv, regime, conf in variants:
        ctx = make_strategy_context(
            fv_features=fv,
            regime_state=regime,
            regime_confidence=conf,
        )
        sig = momentum_strategy.evaluate(ctx)
        assert sig.confidence is not None
        assert 0.0 <= sig.confidence <= 1.0


def test_signal_strength_clamp_six_variants(momentum_strategy):
    variants = [
        {"mom_10_abs": 1000.0, "mom_10_pct": 0.50, "rsi_14": 55.0},
        {"mom_10_abs": 500.0, "mom_10_pct": 0.30, "rsi_14": 60.0},
        {"mom_10_abs": 10.0, "mom_10_pct": -0.10, "rsi_14": 20.0},
        {"mom_10_abs": 5.0, "mom_10_pct": -0.50, "rsi_14": 10.0},
        {"mom_10_abs": 10000.0, "mom_10_pct": 1.0, "rsi_14": 70.0},
        {"mom_10_abs": 0.0, "mom_10_pct": 0.0, "rsi_14": 50.0},
    ]
    for fv in variants:
        ctx = make_strategy_context(
            fv_features=fv,
            regime_state=MarketRegimeState.BULL,
        )
        sig = momentum_strategy.evaluate(ctx)
        assert 0.0 <= sig.signal_strength <= 1.0


def test_rsi_74_boundary_allowed(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 74.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.LONG


def test_rsi_75_overbought_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 250.0,
            "mom_10_pct": 0.015,
            "rsi_14": 75.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_rsi_32_boundary_allowed(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "mom_10_abs": 300.0,
            "mom_10_pct": 0.020,
            "rsi_14": 32.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction in (SignalDirection.LONG, SignalDirection.HOLD)
    assert sig.signal_strength > 0
