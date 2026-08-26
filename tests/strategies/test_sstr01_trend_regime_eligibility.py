from __future__ import annotations

import pytest

from app.contracts.regime import REGIME_KEYS, MarketRegimeState
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


STRONG_TREND_FV = {
    "close_raw": 105.0,
    "ema_14": 100.0,
    "mom_10_pct": 0.018,
    "rsi_14": 58.0,
}

WEAK_TREND_FV = {
    "close_raw": 100.5,
    "ema_14": 100.0,
    "mom_10_pct": 0.002,
    "rsi_14": 52.0,
}

PERFECT_LV_FV = {
    "close_raw": 108.0,
    "ema_14": 100.0,
    "mom_10_pct": 0.020,
    "rsi_14": 59.0,
}


REGIMES = [
    (MarketRegimeState.BULL, "bull"),
    (MarketRegimeState.BEAR, "bear"),
    (MarketRegimeState.SIDEWAYS, "sideways"),
    (MarketRegimeState.HIGH_VOLATILITY, "high_volatility"),
    (MarketRegimeState.LOW_VOLATILITY, "low_volatility"),
    (MarketRegimeState.TRANSITION_UNCERTAIN, "transition_uncertain"),
]


@pytest.mark.parametrize("regime_state,regime_name", REGIMES)
def test_regime_strong_trend_variant(trend_strategy, regime_state, regime_name):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=regime_state,
        regime_confidence=0.9,
    )
    sig = trend_strategy.evaluate(ctx)
    assert isinstance(sig.direction, SignalDirection)
    assert set(sig.supporting_regime_evidence.keys()) == set(REGIME_KEYS)
    for v in sig.supporting_regime_evidence.values():
        assert 0.0 <= v <= 1.0

    if regime_name == "bull":
        assert sig.direction in (SignalDirection.LONG, SignalDirection.HOLD)
    elif regime_name == "bear":
        assert sig.direction == SignalDirection.FLAT
    elif regime_name == "low_volatility":
        assert sig.direction in (SignalDirection.LONG, SignalDirection.HOLD)
    else:
        assert sig.direction in (SignalDirection.HOLD, SignalDirection.FLAT)


@pytest.mark.parametrize("regime_state,regime_name", REGIMES)
def test_regime_weak_trend_variant(trend_strategy, regime_state, regime_name):
    ctx = make_strategy_context(
        fv_features=dict(WEAK_TREND_FV),
        regime_state=regime_state,
        regime_confidence=0.7,
    )
    sig = trend_strategy.evaluate(ctx)
    assert isinstance(sig.direction, SignalDirection)
    assert set(sig.supporting_regime_evidence.keys()) == set(REGIME_KEYS)
    for v in sig.supporting_regime_evidence.values():
        assert 0.0 <= v <= 1.0

    if regime_name == "bear":
        assert sig.direction == SignalDirection.FLAT
    elif regime_name in ("sideways", "high_volatility", "transition_uncertain"):
        assert sig.direction in (SignalDirection.HOLD, SignalDirection.FLAT)


@pytest.mark.parametrize("regime_state,regime_name", REGIMES)
def test_regime_perfect_lv_variant(trend_strategy, regime_state, regime_name):
    ctx = make_strategy_context(
        fv_features=dict(PERFECT_LV_FV),
        regime_state=regime_state,
        regime_confidence=0.95,
    )
    sig = trend_strategy.evaluate(ctx)
    assert isinstance(sig.direction, SignalDirection)
    assert set(sig.supporting_regime_evidence.keys()) == set(REGIME_KEYS)
    for v in sig.supporting_regime_evidence.values():
        assert 0.0 <= v <= 1.0

    if regime_name == "bull":
        assert sig.direction == SignalDirection.LONG
    elif regime_name == "low_volatility":
        assert sig.direction in (SignalDirection.LONG, SignalDirection.HOLD)
    elif regime_name == "bear":
        assert sig.direction == SignalDirection.FLAT


@pytest.mark.parametrize("regime_state,regime_name", REGIMES)
def test_regime_evidence_keyset_and_values(trend_strategy, regime_state, regime_name):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=regime_state,
    )
    sig = trend_strategy.evaluate(ctx)
    keys = set(sig.supporting_regime_evidence.keys())
    assert keys == set(REGIME_KEYS)
    assert len(keys) == 6
    for k in keys:
        v = sig.supporting_regime_evidence[k]
        assert isinstance(v, float)
        assert 0.0 <= v <= 1.0


def test_tu_wrong_version_flat(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.TRANSITION_UNCERTAIN,
        fv_version="fv_unknown",
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT


def test_tu_quality_invalid_flat(trend_strategy):
    from app.strategies.base import StrategyQualityHint

    ctx = make_strategy_context(
        fv_features=dict(STRONG_TREND_FV),
        regime_state=MarketRegimeState.TRANSITION_UNCERTAIN,
    )
    hint = StrategyQualityHint(invalid=True)
    sig = trend_strategy.evaluate(ctx, quality_hint=hint)
    assert sig.direction == SignalDirection.FLAT


def test_bear_strong_trend_flat_not_hold(trend_strategy):
    ctx = make_strategy_context(
        fv_features=dict(PERFECT_LV_FV),
        regime_state=MarketRegimeState.BEAR,
        regime_confidence=0.99,
    )
    sig = trend_strategy.evaluate(ctx)
    assert sig.direction == SignalDirection.FLAT
    assert sig.direction != SignalDirection.HOLD
