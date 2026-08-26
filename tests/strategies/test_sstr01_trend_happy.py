from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.strategies import TrendFollowingStrategy, TrendStrategyOptions
from tests.strategies.conftest import make_strategy_context as _orig_make_ctx


def make_strategy_context(**kwargs):
    kwargs.setdefault("correlation_id", "CORR_STR_TEST_000001")
    kwargs.setdefault("causation_id", "CAUS_PARENT_000001")
    return _orig_make_ctx(**kwargs)


@pytest.fixture
def trend_strategy():
    return TrendFollowingStrategy()


def test_bull_strong_trend_long_signal(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.signal_strength >= 0.7
    assert sig.direction == SignalDirection.LONG
    assert isinstance(sig.direction, SignalDirection)


def test_bull_price_gap_small_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 100.2,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_bull_rsi_overbought_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 71.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_bull_rsi_too_low_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 42.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_bull_negative_momentum_weaker_signal(trend_strategy):
    ctx_strong = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    ctx_weak_mom = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": -0.005,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig_strong = trend_strategy.evaluate(ctx_strong)
    sig_weak = trend_strategy.evaluate(ctx_weak_mom)
    assert sig_weak.signal_strength < sig_strong.signal_strength


def test_low_vol_regime_strong_trend_long(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.LOW_VOLATILITY,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.LONG


def test_low_vol_vs_bull_signal_strength(trend_strategy):
    ctx_bull = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    ctx_lv = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.LOW_VOLATILITY,
    )
    sig_bull = trend_strategy.evaluate(ctx_bull)
    sig_lv = trend_strategy.evaluate(ctx_lv)
    assert sig_lv.signal_strength < sig_bull.signal_strength


def test_bear_regime_trend_up_flat(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BEAR,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT


def test_perfect_trend_components_max_signal(trend_strategy):
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=30.0,
        price_vs_ema14_max_gap_bps=50.0,
    )
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 110.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.020,
            "rsi_14": 60.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength <= 1.0
    assert sig.signal_strength >= 0.9


def test_fixture_override_min_gap_20bps_was_hold_now_long(trend_strategy):
    fv = {
        "close_raw": 100.2,
        "ema_14": 100.0,
        "mom_10_pct": 0.020,
        "rsi_14": 65.0,
    }
    ctx_default = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    sig_default = trend_strategy.evaluate(ctx_default)
    assert sig_default.direction == SignalDirection.HOLD

    opts_lower_gap = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=10.0,
    )
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    sig_override = trend_strategy.evaluate(ctx, options=opts_lower_gap)
    assert sig_override.signal_strength > sig_default.signal_strength
    assert sig_override.direction == SignalDirection.LONG


def test_direction_is_enum_not_string(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert isinstance(sig.direction, SignalDirection)
    assert sig.direction == SignalDirection.LONG
    assert sig.direction.value == "long"


def test_stop_policy_none(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.stop_policy is None
    assert sig.take_profit_policy is None
    assert sig.expected_edge_bps is None


def test_entry_price_ref_decimal(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.entry_price_ref is not None
    assert isinstance(sig.entry_price_ref, Decimal)


def test_entry_thesis_non_empty_and_short(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.entry_thesis is not None
    assert len(sig.entry_thesis) > 0
    assert len(sig.entry_thesis) <= 120


def test_supporting_feature_keys_length_six(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert len(sig.supporting_feature_keys) == 6


def test_correlation_id_preserved(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.correlation_id == "CORR_STR_TEST_000001"


def test_causation_id_preserved(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.causation_id == "CAUS_PARENT_000001"


def test_strategy_version_str01_v1(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.strategy_version == "str_01_v1"


def test_strategy_version_second_check(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 102.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.010,
            "rsi_14": 55.0,
        },
        regime_state=MarketRegimeState.LOW_VOLATILITY,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.strategy_version == "str_01_v1"


def test_high_vol_regime_trend_up_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.HIGH_VOLATILITY,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_confidence_in_0_1_range(trend_strategy):
    variants = [
        ({"close_raw": 105.0, "ema_14": 100.0, "mom_10_pct": 0.018, "rsi_14": 58.0}, MarketRegimeState.BULL),
        ({"close_raw": 100.2, "ema_14": 100.0, "mom_10_pct": 0.010, "rsi_14": 55.0}, MarketRegimeState.SIDEWAYS),
        ({"close_raw": 103.0, "ema_14": 100.0, "mom_10_pct": 0.015, "rsi_14": 60.0}, MarketRegimeState.LOW_VOLATILITY),
        ({"close_raw": 101.0, "ema_14": 100.0, "mom_10_pct": 0.005, "rsi_14": 50.0}, MarketRegimeState.TRANSITION_UNCERTAIN),
    ]
    for fv, regime in variants:
        ctx = make_strategy_context(fv_features=fv, regime_state=regime)
        sig = trend_strategy.evaluate(ctx)
        assert sig.confidence is not None
        assert 0.0 <= sig.confidence <= 1.0


def test_signal_strength_clamp_8_variants(trend_strategy):
    variants = [
        {"close_raw": 200.0, "ema_14": 100.0, "mom_10_pct": 0.50, "rsi_14": 59.0},
        {"close_raw": 150.0, "ema_14": 100.0, "mom_10_pct": 0.30, "rsi_14": 60.0},
        {"close_raw": 130.0, "ema_14": 100.0, "mom_10_pct": 0.20, "rsi_14": 58.0},
        {"close_raw": 110.0, "ema_14": 100.0, "mom_10_pct": 0.10, "rsi_14": 55.0},
        {"close_raw": 90.0, "ema_14": 100.0, "mom_10_pct": -0.20, "rsi_14": 30.0},
        {"close_raw": 50.0, "ema_14": 100.0, "mom_10_pct": -0.50, "rsi_14": 20.0},
        {"close_raw": 10.0, "ema_14": 100.0, "mom_10_pct": -0.90, "rsi_14": 10.0},
        {"close_raw": 1000.0, "ema_14": 100.0, "mom_10_pct": 1.0, "rsi_14": 65.0},
    ]
    for fv in variants:
        ctx = make_strategy_context(fv_features=fv, regime_state=MarketRegimeState.BULL)
        sig = trend_strategy.evaluate(ctx)
        assert 0.0 <= sig.signal_strength <= 1.0
