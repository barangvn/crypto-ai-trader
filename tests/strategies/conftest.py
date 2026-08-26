from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Literal

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
from app.contracts.market import Candle
from app.contracts.regime import (
    REGIME_KEYS,
    MarketRegime,
    MarketRegimeState,
    TimeRangeSpec,
)
from app.contracts.strategy import (
    EligibilityContextView,
    OpportunityScoreComponentPolicy,
    PortfolioContextView,
    SignalDirection,
    StrategyContext,
)
from app.contracts.types import Instant, Symbol, ULID
from app.features.engine import FeatureEngine
from app.regime.engine import RegimeEngine
from app.strategies.base import (
    DEFAULT_MOMENTUM_OPTIONS,
    DEFAULT_TREND_OPTIONS,
    MomentumStrategy,
    MomentumStrategyOptions,
    StrategyQualityHint,
    TrendFollowingStrategy,
    TrendStrategyOptions,
)


FIXED_CORR_ID = "01920000-0000-7000-8000-000000000010"
FIXED_CAUS_ID = "01920000-0000-7000-8000-000000000020"
FIXED_CORR_ID_V2 = "01920000-0000-7000-8000-000000000011"
FIXED_CAUS_ID_V2 = "01920000-0000-7000-8000-000000000021"
FIXED_SYMBOL = Symbol("BTC_USDT")
FIXED_TIMEFRAME = "1h"
FIXED_AS_OF = Instant("2026-08-26T10:00:00.000Z")
FEATURE_VERSION = "fea_01_v1"
DETECTOR_VERSION = "reg_01_v1"
STRATEGY_VERSION = "str_01_v1"


def _make_clock_ref(as_of: Instant = FIXED_AS_OF) -> ClockRef:
    return ClockRef(wall=as_of, replay=as_of)


def _make_quality_flags_clean() -> QualityFlags:
    return QualityFlags()


def _make_schema_ref() -> SchemaRef:
    return SchemaRef(
        contracts_md="CONTRACTS.md@1.0.0",
        feature_version=FEATURE_VERSION,
        strategy_version=STRATEGY_VERSION,
    )


def _uniform_features_strong_bull() -> dict[str, Any]:
    close = 112.0
    ema14 = 108.0
    vwap20 = 107.0
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.5),
        "low_raw": float(close - 0.3),
        "ema_14": float(ema14),
        "rsi_14": 58.0,
        "atr_14": 1.2,
        "vwap_20": float(vwap20),
        "mom_10_abs": 3.5,
        "mom_10_pct": 0.015,
        "volatility_20_bps": 40.0,
        "vol_ratio_20": 1.1,
        "vol_std_20_scaled": 5.0,
    }


def _uniform_features_high_vol() -> dict[str, Any]:
    close = 105.0
    ema14 = 104.8
    return {
        "close_raw": float(close),
        "high_raw": float(close + 3.0),
        "low_raw": float(close - 3.0),
        "ema_14": float(ema14),
        "rsi_14": 52.0,
        "atr_14": 5.5,
        "vwap_20": float(104.7),
        "mom_10_abs": 0.5,
        "mom_10_pct": 0.001,
        "volatility_20_bps": 200.0,
        "vol_ratio_20": 2.3,
        "vol_std_20_scaled": 80.0,
    }


def _uniform_features_sideways() -> dict[str, Any]:
    close = 100.0
    ema14 = 100.05
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.3),
        "low_raw": float(close - 0.3),
        "ema_14": float(ema14),
        "rsi_14": 50.0,
        "atr_14": 0.5,
        "vwap_20": float(100.03),
        "mom_10_abs": 0.1,
        "mom_10_pct": 0.0008,
        "volatility_20_bps": 20.0,
        "vol_ratio_20": 1.0,
        "vol_std_20_scaled": 2.0,
    }


def _uniform_features_insufficient(null_count: int = 5) -> dict[str, Any]:
    close = 100.0
    features = _uniform_features_sideways()
    nullable = [
        "ema_14",
        "rsi_14",
        "atr_14",
        "vwap_20",
        "mom_10_abs",
        "mom_10_pct",
        "volatility_20_bps",
        "vol_ratio_20",
        "vol_std_20_scaled",
    ]
    for i in range(null_count):
        features[nullable[i]] = None
    features["close_raw"] = float(close)
    features["high_raw"] = float(close + 0.3)
    features["low_raw"] = float(close - 0.3)
    return features


def _uniform_features_low_vol() -> dict[str, Any]:
    close = 102.0
    ema14 = 101.8
    return {
        "close_raw": float(close),
        "high_raw": float(close + 0.05),
        "low_raw": float(close - 0.05),
        "ema_14": float(ema14),
        "rsi_14": 56.0,
        "atr_14": 0.1,
        "vwap_20": float(101.75),
        "mom_10_abs": 1.5,
        "mom_10_pct": 0.008,
        "volatility_20_bps": 15.0,
        "vol_ratio_20": 0.7,
        "vol_std_20_scaled": 0.5,
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


def make_feature_vector(variant: Literal["bull", "hv", "sideways", "insufficient", "lv", "tu"] = "bull", *, null_count_override: int | None = None) -> FeatureVector:
    if variant == "bull":
        feats = _uniform_features_strong_bull()
    elif variant == "hv":
        feats = _uniform_features_high_vol()
    elif variant == "sideways":
        feats = _uniform_features_sideways()
    elif variant == "insufficient":
        feats = _uniform_features_insufficient()
    elif variant == "lv":
        feats = _uniform_features_low_vol()
    elif variant == "tu":
        feats = _uniform_features_sideways()
    else:
        feats = _uniform_features_strong_bull()

    if null_count_override is not None:
        feats = _uniform_features_insufficient(null_count_override)

    return FeatureVector(
        feature_version=FEATURE_VERSION,
        timeframe=FIXED_TIMEFRAME,
        features=feats,
        lookback_window=_make_lookback(),
        input_refs=_make_input_refs(),
    )


def make_market_regime(primary: MarketRegimeState = MarketRegimeState.BULL, confidence: float = 0.80) -> MarketRegime:
    scores = _make_scores(primary, 0.75)
    return MarketRegime(
        timeframe=FIXED_TIMEFRAME,
        regime=primary,
        confidence=float(confidence),
        scores=scores,
        detector_version=DETECTOR_VERSION,
        feature_version=FEATURE_VERSION,
        lookback_ts=_make_time_range(),
    )


DEFAULT_FV_CUSTOM: dict[str, float] = {
    "close_raw": 100.0,
    "high_raw": 101.0,
    "low_raw": 99.0,
    "ema_14": 100.0,
    "rsi_14": 50.0,
    "atr_14": 1.0,
    "vwap_20": 99.8,
    "mom_10_abs": 50.0,
    "mom_10_pct": 0.005,
    "volatility_20_bps": 100.0,
    "vol_ratio_20": 1.0,
    "vol_std_20_scaled": 0.5,
}


def _canonical_symbol_helper(symbol_raw: str) -> Symbol:
    if "/" in symbol_raw:
        return Symbol(symbol_raw.replace("/", "_"))
    return Symbol(symbol_raw)


def make_strategy_context(
    variant: Literal["bull", "hv", "sideways", "insufficient", "lv", "tu"] = "bull",
    *,
    correlation_id: str = FIXED_CORR_ID,
    causation_id: str = FIXED_CAUS_ID,
    symbol: Symbol = FIXED_SYMBOL,
    as_of: Instant = FIXED_AS_OF,
    run_mode: RunMode = RunMode.BACKTEST,
    source_type: SourceType = SourceType.REPLAY,
    null_count_override: int | None = None,
    regime_override: MarketRegimeState | None = None,
    fv_features: dict[str, Any] | None = None,
    regime_state: MarketRegimeState | None = None,
    regime_confidence: float = 0.9,
    fv_version: str = FEATURE_VERSION,
    det_version: str = DETECTOR_VERSION,
    symbol_str: str | None = None,
    null_count: int = 0,
) -> StrategyContext:
    if symbol_str is not None:
        symbol = _canonical_symbol_helper(symbol_str)

    use_custom_path = (
        fv_features is not None
        or regime_state is not None
        or fv_version != FEATURE_VERSION
        or det_version != DETECTOR_VERSION
        or null_count > 0
    )

    if not use_custom_path:
        fv = make_feature_vector(variant, null_count_override=null_count_override)
        if regime_override is not None:
            regime = make_market_regime(primary=regime_override)
        else:
            if variant == "bull":
                regime = make_market_regime(MarketRegimeState.BULL)
            elif variant == "hv":
                regime = make_market_regime(MarketRegimeState.HIGH_VOLATILITY)
            elif variant == "sideways":
                regime = make_market_regime(MarketRegimeState.SIDEWAYS)
            elif variant == "insufficient":
                regime = make_market_regime(MarketRegimeState.TRANSITION_UNCERTAIN)
            elif variant == "lv":
                regime = make_market_regime(MarketRegimeState.LOW_VOLATILITY)
            elif variant == "tu":
                regime = make_market_regime(MarketRegimeState.TRANSITION_UNCERTAIN)
            else:
                regime = make_market_regime(MarketRegimeState.BULL)
    else:
        features_dict: dict[str, Any] = dict(DEFAULT_FV_CUSTOM)
        if fv_features:
            features_dict.update(fv_features)

        actual_null_count = sum(1 for v in features_dict.values() if v is None)
        if null_count > 0 and null_count != actual_null_count:
            nullable_keys = [
                "ema_14",
                "rsi_14",
                "atr_14",
                "vwap_20",
                "mom_10_abs",
                "mom_10_pct",
                "volatility_20_bps",
                "vol_ratio_20",
                "vol_std_20_scaled",
            ]
            for k in nullable_keys:
                if actual_null_count >= null_count:
                    break
                if features_dict[k] is not None:
                    features_dict[k] = None
                    actual_null_count += 1

        fv = FeatureVector(
            feature_version=fv_version,
            timeframe=FIXED_TIMEFRAME,
            features=features_dict,
            lookback_window=LookbackWindowSpec(count=200, timeframe=FIXED_TIMEFRAME),
            input_refs=["REF_INPUT_1"],
            null_count=null_count if null_count > 0 else actual_null_count,
        )

        effective_regime_state = regime_state or regime_override or MarketRegimeState.BULL
        regime_scores: dict[str, float] = {}
        for key in sorted(REGIME_KEYS):
            if key == effective_regime_state.value:
                regime_scores[key] = float(regime_confidence)
            else:
                regime_scores[key] = max(0.0, (1.0 - regime_confidence) / 5.0)

        regime = MarketRegime(
            timeframe=FIXED_TIMEFRAME,
            regime=effective_regime_state,
            confidence=float(regime_confidence),
            scores=regime_scores,
            detector_version=det_version,
            feature_version=fv_version,
            lookback_ts=TimeRangeSpec(
                start=Instant("2026-08-25T10:00:00.000Z"),
                end=Instant("2026-08-26T10:00:00.000Z"),
            ),
        )

    portfolio_ctx = PortfolioContextView()
    eligibility_ctx = EligibilityContextView(eligible=True, reasons=[])
    scoring_policy = OpportunityScoreComponentPolicy(policy_version="policy_v1.0.0", component_keys=[])
    clock_ref = _make_clock_ref(as_of)

    return StrategyContext(
        symbol=symbol,
        as_of=as_of,
        clock_ref=clock_ref,
        features=fv,
        regime=regime,
        portfolio_ctx=portfolio_ctx,
        eligibility_ctx=eligibility_ctx,
        scoring_policy=scoring_policy,
        run_mode=run_mode,
        source_type=source_type,
        correlation_id=correlation_id,
        causation_id=causation_id,
        strategy_params={},
    )


def make_synthetic_candles(
    n: int = 200,
    pattern: Literal["uptrend", "sideways", "downtrend"] = "uptrend",
    *,
    start_price: float = 100.0,
    end_price: float = 112.0,
    volatility_pct: float = 0.002,
    base_time_str: str = "2026-08-20T00:00:00.000Z",
) -> list[Candle]:
    from datetime import datetime, timezone, timedelta
    prices: list[float] = []
    if pattern == "uptrend":
        step = (end_price - start_price) / max(1, n - 1)
        for i in range(n):
            base = start_price + step * i
            jitter = random.uniform(-volatility_pct, volatility_pct) * base
            prices.append(base + jitter)
    elif pattern == "downtrend":
        step = (start_price - end_price) / max(1, n - 1)
        for i in range(n):
            base = start_price - step * i
            jitter = random.uniform(-volatility_pct, volatility_pct) * base
            prices.append(base + jitter)
    else:
        for i in range(n):
            jitter = random.uniform(-volatility_pct, volatility_pct) * start_price
            prices.append(start_price + jitter)
    dt = datetime.fromisoformat(base_time_str.replace("Z", "+00:00"))
    candles: list[Candle] = []
    for i in range(n):
        ts_dt = dt + timedelta(hours=i)
        open_ts = ts_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts_dt.microsecond // 1000:03d}Z"
        close_ts_dt = ts_dt + timedelta(hours=1)
        close_ts = close_ts_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{close_ts_dt.microsecond // 1000:03d}Z"
        close_p = prices[i]
        open_p = close_p - random.uniform(0.0, 0.003) * close_p
        high_p = close_p + abs(random.uniform(0.0, 0.005)) * close_p
        low_p = min(open_p, close_p) - abs(random.uniform(0.0, 0.005)) * close_p
        volume = Decimal(str(random.uniform(50, 500)))
        candles.append(
            Candle(
                timeframe=FIXED_TIMEFRAME,
                open_time=Instant(open_ts),
                close_time=Instant(close_ts),
                open=Decimal(str(open_p)),
                high=Decimal(str(high_p)),
                low=Decimal(str(low_p)),
                close=Decimal(str(close_p)),
                volume=volume,
                closed=True,
            )
        )
    return candles


@pytest.fixture(scope="session")
def trend_strategy() -> TrendFollowingStrategy:
    return TrendFollowingStrategy()


@pytest.fixture(scope="session")
def momentum_strategy() -> MomentumStrategy:
    return MomentumStrategy()


@pytest.fixture
def ctx_bull() -> StrategyContext:
    return make_strategy_context("bull")


@pytest.fixture
def ctx_hv() -> StrategyContext:
    return make_strategy_context("hv")


@pytest.fixture
def ctx_sideways() -> StrategyContext:
    return make_strategy_context("sideways")


@pytest.fixture
def ctx_insufficient() -> StrategyContext:
    return make_strategy_context("insufficient")


@pytest.fixture
def ctx_lv() -> StrategyContext:
    return make_strategy_context("lv")


@pytest.fixture
def ctx_tu() -> StrategyContext:
    return make_strategy_context("tu")


@pytest.fixture
def ctx_variants(ctx_bull, ctx_hv, ctx_sideways, ctx_lv, ctx_tu, ctx_insufficient):
    return {
        "bull": ctx_bull,
        "hv": ctx_hv,
        "sideways": ctx_sideways,
        "lv": ctx_lv,
        "tu": ctx_tu,
        "insufficient": ctx_insufficient,
    }


@pytest.fixture
def fv_bull() -> FeatureVector:
    return make_feature_vector("bull")


@pytest.fixture
def regime_bull() -> MarketRegime:
    return make_market_regime(MarketRegimeState.BULL)


@pytest.fixture
def quality_hint_clean() -> StrategyQualityHint:
    return StrategyQualityHint()


@pytest.fixture
def quality_hint_stale() -> StrategyQualityHint:
    return StrategyQualityHint(stale=True)


@pytest.fixture
def quality_hint_degraded() -> StrategyQualityHint:
    return StrategyQualityHint(degraded=True)


@pytest.fixture
def quality_hint_invalid() -> StrategyQualityHint:
    return StrategyQualityHint(invalid=True)


@pytest.fixture
def quality_hint_quarantined() -> StrategyQualityHint:
    return StrategyQualityHint(quarantined=True)


@pytest.fixture
def quality_hint_duplicate() -> StrategyQualityHint:
    return StrategyQualityHint(duplicate=True)


@pytest.fixture
def quality_hint_missing() -> StrategyQualityHint:
    return StrategyQualityHint(missing=True)


@pytest.fixture
def quality_hint_out_of_order() -> StrategyQualityHint:
    return StrategyQualityHint(out_of_order=True)


@pytest.fixture
def quality_hint_abnormal_spread() -> StrategyQualityHint:
    return StrategyQualityHint(abnormal_spread=True)


@pytest.fixture
def feature_engine() -> FeatureEngine:
    return FeatureEngine()


@pytest.fixture
def regime_engine() -> RegimeEngine:
    from app.regime.engine import DetectOptions
    return RegimeEngine(options=DetectOptions(unexpected_version_mode="transition"))


@pytest.fixture
def synthetic_candles_uptrend_200() -> list[Candle]:
    random.seed(42)
    return make_synthetic_candles(200, "uptrend", start_price=100.0, end_price=112.0)


@pytest.fixture
def synthetic_candles_sideways_200() -> list[Candle]:
    random.seed(42)
    return make_synthetic_candles(200, "sideways", start_price=100.0, volatility_pct=0.005)


@pytest.fixture
def default_trend_options() -> TrendStrategyOptions:
    return DEFAULT_TREND_OPTIONS


@pytest.fixture
def default_momentum_options() -> MomentumStrategyOptions:
    return DEFAULT_MOMENTUM_OPTIONS
