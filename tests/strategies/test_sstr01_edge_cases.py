from __future__ import annotations

import pytest

from app.contracts.exceptions import ContractSchemaError
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.strategies.base import StrategyQualityHint
from app.strategies import (
    MomentumStrategy,
    MomentumStrategyOptions,
    TrendFollowingStrategy,
    TrendStrategyOptions,
)
from tests.strategies.conftest import make_strategy_context as _orig_make_ctx


def make_strategy_context(**kwargs):
    kwargs.setdefault("correlation_id", "CORR_STR_TEST_000001")
    kwargs.setdefault("causation_id", "CAUS_PARENT_000001")
    return _orig_make_ctx(**kwargs)


@pytest.fixture
def trend_strategy():
    return TrendFollowingStrategy()


@pytest.fixture
def momentum_strategy():
    return MomentumStrategy()


STRONG_TREND_FV = {
    "close_raw": 105.0,
    "ema_14": 100.0,
    "mom_10_pct": 0.018,
    "rsi_14": 58.0,
}

STRONG_MOM_FV = {
    "mom_10_abs": 250.0,
    "mom_10_pct": 0.015,
    "rsi_14": 60.0,
}


def test_wrong_fv_version_trend_flat_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        fv_version="fv_unknown",
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT
    assert sig.signal_strength <= 0.20
    assert sig.confidence is not None
    assert sig.confidence <= 0.20


def test_wrong_fv_version_mom_flat_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
        fv_version="fv_unknown",
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT
    assert sig.signal_strength <= 0.20
    assert sig.confidence is not None
    assert sig.confidence <= 0.20


def test_wrong_fv_version_raise_trend(trend_strategy):
    opts = TrendStrategyOptions(
        unexpected_version_mode="raise",
    )
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        fv_version="fv_unknown",
    )
    with pytest.raises(ContractSchemaError):
        trend_strategy.evaluate(ctx, options=opts)


def test_wrong_fv_version_raise_mom(momentum_strategy):
    opts = MomentumStrategyOptions(
        unexpected_version_mode="raise",
    )
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
        fv_version="fv_unknown",
    )
    with pytest.raises(ContractSchemaError):
        momentum_strategy.evaluate(ctx, options=opts)


def test_wrong_detector_version_trend_flat(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        det_version="det_vX",
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT
    assert sig.signal_strength <= 0.20
    assert sig.confidence is not None
    assert sig.confidence <= 0.20


def test_wrong_detector_version_mom_flat(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
        det_version="det_vX",
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT
    assert sig.signal_strength <= 0.20
    assert sig.confidence is not None
    assert sig.confidence <= 0.20


def test_wrong_detector_version_raise_trend(trend_strategy):
    opts = TrendStrategyOptions(
        unexpected_version_mode="raise",
    )
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        det_version="det_vX",
    )
    with pytest.raises(ContractSchemaError):
        trend_strategy.evaluate(ctx, options=opts)


def test_wrong_detector_version_raise_mom(momentum_strategy):
    opts = MomentumStrategyOptions(
        unexpected_version_mode="raise",
    )
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
        det_version="det_vX",
    )
    with pytest.raises(ContractSchemaError):
        momentum_strategy.evaluate(ctx, options=opts)


def test_insufficient_lookback_nullcount5_trend(trend_strategy):
    opts = TrendStrategyOptions(
        null_count_pct_insufficient_lookback=0.5,
    )
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        null_count=5,
    )
    sig = trend_strategy.evaluate(ctx, options=opts)
    assert sig.direction == SignalDirection.FLAT
    assert sig.confidence is not None
    assert sig.confidence <= 0.15


def test_insufficient_lookback_nullcount9_trend(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
        null_count=9,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT


def test_sufficient_lookback_nullcount4_trend(trend_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "high_raw": 106.0,
            "low_raw": 104.0,
            "ema_14": 100.0,
            "rsi_14": 58.0,
            "atr_14": 1.0,
            "vwap_20": 99.8,
            "mom_10_abs": None,
            "mom_10_pct": 0.018,
            "volatility_20_bps": None,
            "vol_ratio_20": None,
            "vol_std_20_scaled": None,
        },
        regime_state=MarketRegimeState.BULL,
        null_count=4,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction != SignalDirection.FLAT


def test_sideways_regime_strong_trend_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.SIDEWAYS,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_sideways_regime_strong_mom_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.SIDEWAYS,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.HOLD


def test_tu_regime_strong_trend(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.TRANSITION_UNCERTAIN,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction in (SignalDirection.FLAT, SignalDirection.HOLD)


def test_tu_regime_strong_mom(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.TRANSITION_UNCERTAIN,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.direction in (SignalDirection.FLAT, SignalDirection.HOLD)


def test_quality_stale_confidence_reduced(trend_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = trend_strategy.evaluate(ctx_clean)

    ctx_stale = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(stale=True)
    sig_stale = trend_strategy.evaluate(ctx_stale, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_stale.confidence is not None
    expected_reduced = sig_clean.confidence * 0.60
    assert abs(sig_stale.confidence - expected_reduced) < 0.20


def test_quality_degraded_060x(trend_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = trend_strategy.evaluate(ctx_clean)

    ctx_deg = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(degraded=True)
    sig_deg = trend_strategy.evaluate(ctx_deg, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_deg.confidence is not None
    assert abs(sig_deg.confidence - sig_clean.confidence * 0.60) < 0.20


def test_quality_duplicate_085x(momentum_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = momentum_strategy.evaluate(ctx_clean)

    ctx_dup = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(duplicate=True)
    sig_dup = momentum_strategy.evaluate(ctx_dup, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_dup.confidence is not None
    assert abs(sig_dup.confidence - sig_clean.confidence * 0.85) < 0.20


def test_quality_out_of_order_085x(momentum_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = momentum_strategy.evaluate(ctx_clean)

    ctx_ooo = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(out_of_order=True)
    sig_ooo = momentum_strategy.evaluate(ctx_ooo, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_ooo.confidence is not None
    assert abs(sig_ooo.confidence - sig_clean.confidence * 0.85) < 0.20


def test_quality_missing_085x(momentum_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = momentum_strategy.evaluate(ctx_clean)

    ctx_mis = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(missing=True)
    sig_mis = momentum_strategy.evaluate(ctx_mis, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_mis.confidence is not None
    assert abs(sig_mis.confidence - sig_clean.confidence * 0.85) < 0.20


def test_quality_abnormal_spread_080x(trend_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = trend_strategy.evaluate(ctx_clean)

    ctx_ab = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(abnormal_spread=True)
    sig_ab = trend_strategy.evaluate(ctx_ab, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig_ab.confidence is not None
    assert abs(sig_ab.confidence - sig_clean.confidence * 0.80) < 0.20


def test_quality_invalid_force_flat(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(invalid=True)
    sig = trend_strategy.evaluate(ctx, quality_hint=hint)
    assert sig.direction == SignalDirection.FLAT


def test_quality_quarantined_force_flat(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(quarantined=True)
    sig = momentum_strategy.evaluate(ctx, quality_hint=hint)
    assert sig.direction == SignalDirection.FLAT


def test_quality_stale_plus_duplicate_min_worst(trend_strategy):
    ctx_clean = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig_clean = trend_strategy.evaluate(ctx_clean)

    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(stale=True, duplicate=True)
    sig = trend_strategy.evaluate(ctx, quality_hint=hint)
    assert sig_clean.confidence is not None
    assert sig.confidence is not None
    expected = sig_clean.confidence * 0.60
    assert abs(sig.confidence - expected) < 0.20


def test_quality_invalid_plus_stale_priority_flat(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    hint = StrategyQualityHint(invalid=True, stale=True)
    sig = trend_strategy.evaluate(ctx, quality_hint=hint)
    assert sig.direction == SignalDirection.FLAT


def test_trend_null_ema14_and_close_weak(trend_strategy):
    ctx_normal = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "ema_14": 100.0,
            "mom_10_pct": 0.018,
            "rsi_14": 58.0,
        },
        regime_state=MarketRegimeState.BULL,
    )
    sig_normal = trend_strategy.evaluate(ctx_normal)

    ctx_null = make_strategy_context(
        fv_features={
            "close_raw": None,
            "high_raw": 106.0,
            "low_raw": 104.0,
            "ema_14": None,
            "rsi_14": 58.0,
            "atr_14": 1.0,
            "vwap_20": 99.8,
            "mom_10_abs": 50.0,
            "mom_10_pct": 0.018,
            "volatility_20_bps": 100.0,
            "vol_ratio_20": 1.0,
            "vol_std_20_scaled": 0.5,
        },
        regime_state=MarketRegimeState.BULL,
        null_count=2,
    )
    sig_null = trend_strategy.evaluate(ctx_null)
    assert sig_null.signal_strength < sig_normal.signal_strength


def test_mom_null_abs_and_pct_hold(momentum_strategy):
    ctx = make_strategy_context(
        fv_features={
            "close_raw": 105.0,
            "high_raw": 106.0,
            "low_raw": 104.0,
            "ema_14": 100.0,
            "rsi_14": 60.0,
            "atr_14": 1.0,
            "vwap_20": 99.8,
            "mom_10_abs": None,
            "mom_10_pct": None,
            "volatility_20_bps": 100.0,
            "vol_ratio_20": 1.0,
            "vol_std_20_scaled": 0.5,
        },
        regime_state=MarketRegimeState.BULL,
        null_count=2,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.signal_strength == 0.0
    assert sig.direction == SignalDirection.HOLD


def test_trend_strategy_version_field(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.strategy_version == "str_01_v1"
    assert sig.strategy_id == "trend_following"


def test_momentum_strategy_version_field(momentum_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_MOM_FV),
        regime_state=MarketRegimeState.BULL,
    )
    sig = momentum_strategy.evaluate(ctx)
    assert sig.strategy_version == "str_01_v1"
    assert sig.strategy_id == "momentum"
