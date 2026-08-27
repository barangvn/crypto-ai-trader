from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    RunMode,
    SourceType,
    format_instant,
)
from app.contracts.canonical import ClockRef, QualityFlags, SchemaRef
from app.contracts.feature import (
    FEATURE_SCHEMA_REGISTRY,
    FeatureVector,
    LookbackWindowSpec,
)
from app.contracts.regime import (
    REGIME_KEYS,
    MarketRegime,
    MarketRegimeState,
    TimeRangeSpec,
)
from app.contracts.strategy import (
    SignalDirection,
    StrategySignal,
)
from app.contracts.types import Instant, Symbol
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    DEFAULT_SCORING_WEIGHTS,
    DeterministicOpportunityScorer,
    MarketCostAssumptions,
    POLICY_VERSION_STORY_DEFAULT,
    ScoringWeights,
    SCORER_VERSION_STORY_DEFAULT,
    build_explainability_bundle,
    compute_confidence,
    compute_cost_multiplier,
    compute_expected_gross_edge_bps,
    compute_fee_cost_bps,
    compute_final_opportunity_score,
    compute_latency_impact_bps,
    compute_net_expected_edge_bps,
    compute_raw_opportunity_score,
    compute_regime_adjustment,
    compute_slippage_cost_bps,
    compute_spread_cost_bps,
    compute_strategy_adjustment,
)
from app.strategies.base import (
    MomentumStrategy,
    TrendFollowingStrategy,
)


FIXED_CORR_ID = "01920000-0000-7000-8000-000000000AAA"
FIXED_SIGNAL_ID = "01920000-0000-7000-8000-000000000BBB"
FIXED_CAUS_ID = "01920000-0000-7000-8000-000000000CCC"
FIXED_SYMBOL = Symbol("BTC_USDT")
FIXED_TIMEFRAME = "1h"
FIXED_AS_OF = Instant("2026-08-26T10:00:00.000Z")
FEATURE_VERSION = "fea_01_v1"
DETECTOR_VERSION = "reg_01_v1"
STRATEGY_VERSION = "str_01_v1"


def _chr_join(chars: list[str]) -> str:
    return "".join(chr(ord(c)) for c in chars)


def _make_clock_ref(as_of: Instant = FIXED_AS_OF) -> ClockRef:
    return ClockRef(wall=as_of, replay=as_of)


def make_quality_clean() -> QualityFlags:
    return QualityFlags()


def make_quality(**flags: bool) -> QualityFlags:
    q = QualityFlags()
    # degraded is an aggregate: only set if explicit OR any of the critical flags AND caller didn't pass degraded explicitly.
    for name, value in flags.items():
        object.__setattr__(q, name, value)
    if not flags.get("degraded"):
        critical = any(flags.get(n) for n in ("invalid", "quarantined"))
        if critical:
            object.__setattr__(q, "degraded", True)
    return q


def _uniform_features_strong_bull() -> dict[str, Any]:
    close = 112.0
    ema14 = 108.0
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.5),
        "low_raw": float(close - 0.3),
        "ema_14": float(ema14),
        "ema_28": float(105.0),
        "rsi_14": 58.0,
        "atr_14": 1.2,
        "vwap_20": float(107.0),
        "mom_10_abs": 3.5,
        "mom_10_pct": 0.015,
        "volatility_20_bps": 40.0,
        "vol_ratio_20": 1.1,
        "vol_std_20_scaled": 5.0,
        "spread_bps": 2.0,
    }


def _uniform_features_high_vol() -> dict[str, Any]:
    close = 105.0
    return {
        "close_raw": float(close),
        "high_raw": float(close + 3.0),
        "low_raw": float(close - 3.0),
        "ema_14": float(104.8),
        "ema_28": float(104.7),
        "rsi_14": 52.0,
        "atr_14": 5.5,
        "vwap_20": float(104.7),
        "mom_10_abs": 0.5,
        "mom_10_pct": 0.001,
        "volatility_20_bps": 200.0,
        "vol_ratio_20": 2.3,
        "vol_std_20_scaled": 80.0,
        "spread_bps": 25.0,
    }


def _uniform_features_sideways() -> dict[str, Any]:
    close = 100.0
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.3),
        "low_raw": float(close - 0.3),
        "ema_14": float(100.05),
        "ema_28": float(100.08),
        "rsi_14": 50.0,
        "atr_14": 0.5,
        "vwap_20": float(100.03),
        "mom_10_abs": 0.1,
        "mom_10_pct": 0.0008,
        "volatility_20_bps": 20.0,
        "vol_ratio_20": 1.0,
        "vol_std_20_scaled": 2.0,
        "spread_bps": 1.0,
    }


def _uniform_features_low_vol() -> dict[str, Any]:
    close = 102.0
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.05),
        "low_raw": float(close - 0.05),
        "ema_14": float(101.8),
        "ema_28": float(101.5),
        "rsi_14": 56.0,
        "atr_14": 0.1,
        "vwap_20": float(101.75),
        "mom_10_abs": 1.5,
        "mom_10_pct": 0.008,
        "volatility_20_bps": 15.0,
        "vol_ratio_20": 0.7,
        "vol_std_20_scaled": 0.5,
        "spread_bps": 0.5,
    }


def _make_lookback(count: int = 200, timeframe: str = FIXED_TIMEFRAME) -> LookbackWindowSpec:
    return LookbackWindowSpec(count=count, timeframe=timeframe)


def _make_input_refs(n: int = 200) -> list[str]:
    return [f"CANDLE_{i:06d}" for i in range(n)]


def _make_time_range(start_offset_days: int = 9, end_offset_days: int = 0, base: Instant = FIXED_AS_OF) -> TimeRangeSpec:
    from datetime import datetime, timezone, timedelta
    dt = datetime.fromisoformat(base.replace("Z", "+00:00"))
    start_dt = dt - timedelta(days=start_offset_days)
    end_dt = dt - timedelta(days=end_offset_days)
    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{start_dt.microsecond // 1000:03d}Z"
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end_dt.microsecond // 1000:03d}Z"
    return TimeRangeSpec(start=Instant(start_iso), end=Instant(end_iso))


def _make_scores(primary: MarketRegimeState, strength: float = 0.70) -> dict[str, float]:
    s: dict[str, float] = {}
    for k in sorted(REGIME_KEYS):
        s[k] = 0.05
    s[primary.value] = float(strength)
    residual = 1.0 - float(strength)
    other = [k for k in sorted(REGIME_KEYS) if k != primary.value]
    share = residual / float(len(other)) if other else 0.0
    for k in other:
        s[k] = round(s[k] + share, 6)
    for k in s:
        if s[k] < 0.0:
            s[k] = 0.0
        if s[k] > 1.0:
            s[k] = 1.0
    return s


def make_feature_vector(
    variant: Literal["bull", "hv", "sideways", "lv", "tu"] = "bull",
    *,
    custom_features: dict[str, Any] | None = None,
) -> FeatureVector:
    if variant == "bull":
        feats = _uniform_features_strong_bull()
    elif variant == "hv":
        feats = _uniform_features_high_vol()
    elif variant == "sideways" or variant == "tu":
        feats = _uniform_features_sideways()
    elif variant == "lv":
        feats = _uniform_features_low_vol()
    else:
        feats = _uniform_features_strong_bull()
    if custom_features:
        feats.update(custom_features)
    return FeatureVector(
        feature_version=FEATURE_VERSION,
        timeframe=FIXED_TIMEFRAME,
        features=feats,
        lookback_window=_make_lookback(),
        input_refs=_make_input_refs(),
    )


def make_market_regime(
    primary: MarketRegimeState = MarketRegimeState.BULL,
    confidence: float = 0.80,
    strength: float = 0.75,
) -> MarketRegime:
    scores = _make_scores(primary, strength)
    return MarketRegime(
        timeframe=FIXED_TIMEFRAME,
        regime=primary,
        confidence=float(confidence),
        scores=scores,
        detector_version=DETECTOR_VERSION,
        feature_version=FEATURE_VERSION,
        lookback_ts=_make_time_range(),
    )


def make_strategy_signal(
    strategy_id: Literal["trend_following_v1", "momentum_v1", "unknown_v1"] = "trend_following_v1",
    direction: SignalDirection = SignalDirection.LONG,
    signal_strength: float = 0.75,
    confidence: float | None = 0.80,
    correlation_id: str = FIXED_CORR_ID,
    causation_id: str = FIXED_CAUS_ID,
    signal_id: str | None = FIXED_SIGNAL_ID,
    expected_edge_bps: float | None = None,
    supporting_regime_evidence: dict[str, float] | None = None,
) -> StrategySignal:
    default_reg: dict[str, float] = {k: 0.05 for k in sorted(REGIME_KEYS)}
    if direction == SignalDirection.LONG:
        default_reg["bull"] = 0.75
    reg_ev = supporting_regime_evidence or default_reg
    sig = StrategySignal(
        strategy_id=str(strategy_id),
        strategy_version=STRATEGY_VERSION,
        direction=direction,
        signal_strength=float(signal_strength),
        correlation_id=str(correlation_id),
        causation_id=str(causation_id),
        supporting_feature_keys=["close_raw", "ema_14", "rsi_14"],
        supporting_regime_evidence=reg_ev,
        entry_thesis="test thesis",
        confidence=float(confidence) if confidence is not None else None,
        expected_edge_bps=float(expected_edge_bps) if expected_edge_bps is not None else None,
    )
    if signal_id is not None:
        try:
            object.__setattr__(sig, "signal_id", signal_id)
        except Exception:
            pass
    return sig


def make_default_scorer() -> DeterministicOpportunityScorer:
    return DeterministicOpportunityScorer(
        costs=DEFAULT_MARKET_COST_ASSUMPTIONS,
        weights=DEFAULT_SCORING_WEIGHTS,
        policy_version=POLICY_VERSION_STORY_DEFAULT,
        scorer_version=SCORER_VERSION_STORY_DEFAULT,
    )
