from __future__ import annotations

import math

import pytest

from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.strategies.base import _compute_trend_raw_strength
from app.strategies import TrendFollowingStrategy, TrendStrategyOptions
from tests.strategies.conftest import make_strategy_context as _orig_make_ctx


def make_strategy_context(**kwargs):
    kwargs.setdefault("correlation_id", "CORR_STR_TEST_000001")
    kwargs.setdefault("causation_id", "CAUS_PARENT_000001")
    return _orig_make_ctx(**kwargs)


@pytest.fixture
def trend_strategy():
    return TrendFollowingStrategy()


def test_component_weights_exact_verification():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        regime_compat_bull=1.0,
    )
    fv = {
        "close_raw": 109.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.016,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_trend_raw_strength(ctx, opts)
    expected_raw = 0.45 * 1.0 + 0.35 * 0.8 + 0.20 * 0.5
    assert math.isclose(raw, expected_raw, abs_tol=0.01)


def test_component_weights_signal_strength_full():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        regime_compat_bull=1.0,
        long_threshold=0.55,
    )
    fv = {
        "close_raw": 109.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.016,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    expected_ss = 0.45 * 1.0 + 0.35 * 0.8 + 0.20 * 0.5
    assert math.isclose(sig.signal_strength, expected_ss, abs_tol=0.01)
    assert sig.direction == SignalDirection.LONG


def test_only_rsi_perfect_others_zero_hold():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=1000.0,
        rsi_entry_min=48.0,
        rsi_entry_max=70.0,
    )
    fv = {
        "close_raw": 100.0,
        "ema_14": 100.0,
        "mom_10_pct": -0.01,
        "rsi_14": 59.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    assert sig.direction == SignalDirection.HOLD


def test_only_price_below_threshold_hold():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        mom_pct_max_reference=1.0,
    )
    fv = {
        "close_raw": 108.0,
        "ema_14": 100.0,
        "mom_10_pct": -0.001,
        "rsi_14": 40.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    raw = 0.45 * 0.8
    assert raw < 0.55
    assert sig.direction == SignalDirection.HOLD


def test_price_plus_mom_only_long():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=1000.0,
        rsi_entry_min=48.0,
        rsi_entry_max=70.0,
        mom_pct_max_reference=0.02,
    )
    fv = {
        "close_raw": 108.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.016,
        "rsi_14": None,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    expected_raw = 0.45 * 0.8 + 0.35 * 0.8
    assert math.isclose(sig.signal_strength, expected_raw, abs_tol=0.02)
    assert sig.direction == SignalDirection.LONG


def test_fixture_rsi_band_wider():
    opts_default = TrendStrategyOptions()
    opts_wider = TrendStrategyOptions(
        rsi_entry_min=35.0,
        rsi_entry_max=85.0,
    )
    fv = {
        "close_raw": 105.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.018,
        "rsi_14": 38.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig_default = strategy.evaluate(ctx, options=opts_default)
    sig_wider = strategy.evaluate(ctx, options=opts_wider)
    assert sig_default.direction == SignalDirection.HOLD
    assert sig_wider.signal_strength > sig_default.signal_strength


def test_price_gap_span_35bps():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=30.0,
        price_vs_ema14_max_gap_bps=40.0,
        rsi_entry_min=30.0,
        rsi_entry_max=40.0,
    )
    fv = {
        "close_raw": 100.35,
        "ema_14": 100.0,
        "mom_10_pct": -0.001,
        "rsi_14": 30.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_trend_raw_strength(ctx, opts)
    expected_price = (35.0 - 30.0) / (40.0 - 30.0)
    expected_raw = 0.45 * expected_price
    assert math.isclose(raw, expected_raw, abs_tol=0.01)


def test_negative_price_gap_f_price_zero():
    opts = TrendStrategyOptions()
    fv = {
        "close_raw": 95.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.018,
        "rsi_14": 58.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_trend_raw_strength(ctx, opts)
    gap_bps = (95.0 - 100.0) / 100.0 * 10000.0
    assert gap_bps < opts.price_vs_ema14_min_gap_bps
    raw_no_price = 0.35 * (0.018 / 0.020) + 0.20 * ((58.0 - 48.0) / (70.0 - 48.0))
    assert math.isclose(raw, raw_no_price, abs_tol=0.01)


def test_divide_by_zero_price_min_equals_max():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=50.0,
        price_vs_ema14_max_gap_bps=50.0,
    )
    fv = {
        "close_raw": 100.5,
        "ema_14": 100.0,
        "mom_10_pct": -0.001,
        "rsi_14": 40.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_trend_raw_strength(ctx, opts)
    gap_bps = (100.5 - 100.0) / 100.0 * 10000.0
    assert gap_bps >= 50.0
    assert raw >= 0.0


def test_all_components_zero_hold():
    opts = TrendStrategyOptions()
    fv = {
        "close_raw": 100.0,
        "ema_14": 100.0,
        "mom_10_pct": -0.010,
        "rsi_14": 20.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength == 0.0
    assert sig.direction == SignalDirection.HOLD


def test_perfect_components_max_confidence():
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        mom_pct_max_reference=0.02,
    )
    fv = {
        "close_raw": 110.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.020,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
        regime_confidence=1.0,
    )
    strategy = TrendFollowingStrategy()
    sig = strategy.evaluate(ctx, options=opts)
    assert sig.signal_strength <= 1.0
    assert sig.direction == SignalDirection.LONG
    assert sig.confidence is not None
    assert sig.confidence >= 0.75


PARTIAL_VARIANTS = [
    (1.0, 0.0, 0.0, 0.45),
    (0.0, 1.0, 0.0, 0.35),
    (0.0, 0.0, 1.0, 0.20),
    (1.0, 1.0, 0.0, 0.80),
    (1.0, 0.0, 1.0, 0.65),
    (0.0, 1.0, 1.0, 0.55),
    (0.5, 0.5, 0.5, 0.50),
    (0.25, 0.75, 0.50, 0.45 * 0.25 + 0.35 * 0.75 + 0.20 * 0.50),
    (0.80, 0.20, 0.90, 0.45 * 0.80 + 0.35 * 0.20 + 0.20 * 0.90),
    (0.10, 0.90, 0.10, 0.45 * 0.10 + 0.35 * 0.90 + 0.20 * 0.10),
]


@pytest.mark.parametrize("f_price,f_mom,f_rsi,expected_raw", PARTIAL_VARIANTS)
def test_partial_components_variants(f_price, f_mom, f_rsi, expected_raw):
    opts = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        mom_pct_max_reference=1.0,
    )
    close_raw = 100.0 + f_price * 1.0
    mom_10_pct = f_mom * 1.0
    rsi_14 = f_rsi * 100.0
    fv = {
        "close_raw": close_raw,
        "ema_14": 100.0,
        "mom_10_pct": mom_10_pct,
        "rsi_14": rsi_14,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw = _compute_trend_raw_strength(ctx, opts)
    assert math.isclose(raw, expected_raw, abs_tol=0.02)


def test_weights_override_different_raw():
    opts_default = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        mom_pct_max_reference=1.0,
    )
    opts_custom = TrendStrategyOptions(
        price_vs_ema14_min_gap_bps=0.0,
        price_vs_ema14_max_gap_bps=100.0,
        rsi_entry_min=0.0,
        rsi_entry_max=100.0,
        mom_pct_max_reference=1.0,
        trend_component_weights=(0.60, 0.20, 0.20),
    )
    fv = {
        "close_raw": 150.0,
        "ema_14": 100.0,
        "mom_10_pct": 0.5,
        "rsi_14": 50.0,
    }
    ctx = make_strategy_context(
        fv_features=fv,
        regime_state=MarketRegimeState.BULL,
    )
    raw_default = _compute_trend_raw_strength(ctx, opts_default)
    raw_custom = _compute_trend_raw_strength(ctx, opts_custom)
    expected_default = 0.45 * 1.0 + 0.35 * 0.5 + 0.20 * 0.5
    expected_custom = 0.60 * 1.0 + 0.20 * 0.5 + 0.20 * 0.5
    assert math.isclose(raw_default, expected_default, abs_tol=0.02)
    assert math.isclose(raw_custom, expected_custom, abs_tol=0.02)
    assert raw_custom != raw_default
