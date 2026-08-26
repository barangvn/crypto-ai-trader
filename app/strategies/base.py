from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.contracts.exceptions import ContractSchemaError
from app.contracts.feature import FeatureVector
from app.contracts.regime import REGIME_KEYS, MarketRegime, MarketRegimeState
from app.contracts.strategy import (
    SignalDirection,
    StrategyContext,
    StrategySignal,
)

FEATURE_VERSION_EXPECTED: str = "fea_01_v1"
DETECTOR_VERSION_EXPECTED: str = "reg_01_v1"
STRATEGY_VERSION_DEFAULT: str = "str_01_v1"

NULLABLE_KEY_COUNT: int = 9
NULLABLE_KEYS: tuple[str, ...] = (
    "ema_14",
    "rsi_14",
    "atr_14",
    "vwap_20",
    "mom_10_abs",
    "mom_10_pct",
    "volatility_20_bps",
    "vol_ratio_20",
    "vol_std_20_scaled",
)


@dataclass(frozen=True)
class StrategyQualityHint:
    stale: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    missing: bool = False
    abnormal_spread: bool = False


@dataclass(frozen=True)
class StrategyOptions:
    feature_version: str = FEATURE_VERSION_EXPECTED
    detector_version: str = DETECTOR_VERSION_EXPECTED
    strategy_version: str = STRATEGY_VERSION_DEFAULT
    unexpected_version_mode: str = "flat_hold"
    null_count_pct_insufficient_lookback: float = 0.500
    signal_strength_floor: float = 0.05
    confidence_on_insufficient: float = 0.10
    clamp_min: float = 0.0
    clamp_max: float = 1.0
    long_threshold: float = 0.50


@dataclass(frozen=True)
class TrendStrategyOptions(StrategyOptions):
    price_vs_ema14_min_gap_bps: float = 30.0
    price_vs_ema14_max_gap_bps: float = 75.0
    rsi_entry_min: float = 48.0
    rsi_entry_max: float = 70.0
    mom_pct_max_reference: float = 0.020
    trend_component_weights: tuple[float, float, float] = (0.45, 0.35, 0.20)
    regime_compat_bull: float = 1.00
    regime_compat_bear: float = 0.00
    regime_compat_sideways: float = 0.00
    regime_compat_high_vol: float = 0.00
    regime_compat_low_vol: float = 0.85
    regime_compat_transition: float = 0.00
    confidence_signal_weight: float = 0.70
    confidence_regime_weight: float = 0.30
    long_threshold: float = 0.55


@dataclass(frozen=True)
class MomentumStrategyOptions(StrategyOptions):
    mom_entry_min_bps_abs: float = 80.0
    mom_entry_max_bps_abs: float = 200.0
    mom_pct_max_reference: float = 0.020
    rsi_overbought_max: float = 74.0
    rsi_oversold_min: float = 32.0
    momentum_component_weights: tuple[float, float] = (0.55, 0.45)
    regime_compat_bull: float = 1.00
    regime_compat_bear: float = 0.00
    regime_compat_sideways: float = 0.00
    regime_compat_high_vol: float = 0.40
    regime_compat_low_vol: float = 0.90
    regime_compat_transition: float = 0.00
    confidence_signal_weight: float = 0.75
    confidence_regime_weight: float = 0.25
    long_threshold: float = 0.50


DEFAULT_STRATEGY_OPTIONS: StrategyOptions = StrategyOptions()
DEFAULT_TREND_OPTIONS: TrendStrategyOptions = TrendStrategyOptions()
DEFAULT_MOMENTUM_OPTIONS: MomentumStrategyOptions = MomentumStrategyOptions()

QUALITY_PENALTY_TABLE: dict[str, float] = {
    "invalid": 0.15,
    "quarantined": 0.15,
    "stale": 0.60,
    "degraded": 0.60,
    "duplicate": 0.85,
    "out_of_order": 0.85,
    "missing": 0.85,
    "abnormal_spread": 0.80,
}

QUALITY_FORCE_FLAT_FLAGS: tuple[str, ...] = ("invalid", "quarantined")

TREND_SUPPORTING_KEYS: tuple[str, ...] = (
    "close_raw",
    "ema_14",
    "mom_10_pct",
    "rsi_14",
    "vwap_20",
    "volatility_20_bps",
)

MOMENTUM_SUPPORTING_KEYS: tuple[str, ...] = (
    "mom_10_abs",
    "mom_10_pct",
    "rsi_14",
    "volatility_20_bps",
    "close_raw",
)


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _to_float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    return None


def _regime_compat_map(options: StrategyOptions) -> dict[str, float]:
    result: dict[str, float] = {}
    for key in sorted(REGIME_KEYS):
        if key == MarketRegimeState.BULL.value:
            result[key] = float(options.regime_compat_bull)  # type: ignore[attr-defined]
        elif key == MarketRegimeState.BEAR.value:
            result[key] = float(options.regime_compat_bear)  # type: ignore[attr-defined]
        elif key == MarketRegimeState.SIDEWAYS.value:
            result[key] = float(options.regime_compat_sideways)  # type: ignore[attr-defined]
        elif key == MarketRegimeState.HIGH_VOLATILITY.value:
            result[key] = float(options.regime_compat_high_vol)  # type: ignore[attr-defined]
        elif key == MarketRegimeState.LOW_VOLATILITY.value:
            result[key] = float(options.regime_compat_low_vol)  # type: ignore[attr-defined]
        elif key == MarketRegimeState.TRANSITION_UNCERTAIN.value:
            result[key] = float(options.regime_compat_transition)  # type: ignore[attr-defined]
    return result


def _quality_penalty_multiplier(hint: StrategyQualityHint) -> float:
    penalties: list[float] = []
    flag_order: tuple[str, ...] = (
        "stale",
        "invalid",
        "quarantined",
        "degraded",
        "duplicate",
        "out_of_order",
        "missing",
        "abnormal_spread",
    )
    for name in flag_order:
        if getattr(hint, name, False):
            penalties.append(QUALITY_PENALTY_TABLE[name])
    if not penalties:
        return 1.0
    return min(penalties)


def _quality_force_flat(hint: StrategyQualityHint) -> bool:
    for name in QUALITY_FORCE_FLAT_FLAGS:
        if getattr(hint, name, False):
            return True
    return False


def _check_versions(ctx: StrategyContext, options: StrategyOptions) -> tuple[bool, bool]:
    fv_ok: bool = ctx.features.feature_version == options.feature_version
    dv_ok: bool = ctx.regime.detector_version == options.detector_version
    return fv_ok, dv_ok


def _insufficient_lookback(fv: FeatureVector, options: StrategyOptions) -> tuple[bool, float]:
    null_count: int = int(fv.null_count if fv.null_count is not None else 0)
    null_pct: float = 0.0
    if NULLABLE_KEY_COUNT > 0:
        null_pct = null_count / float(NULLABLE_KEY_COUNT)
    insufficient: bool = null_pct >= options.null_count_pct_insufficient_lookback
    return insufficient, null_pct


def _compute_trend_raw_strength(
    ctx: StrategyContext, options: TrendStrategyOptions
) -> float:
    features = ctx.features.features
    close_raw = _to_float_or_none(features.get("close_raw"))
    ema_14 = _to_float_or_none(features.get("ema_14"))
    mom_10_pct = _to_float_or_none(features.get("mom_10_pct"))
    rsi_14 = _to_float_or_none(features.get("rsi_14"))
    w_price, w_mom, w_rsi = options.trend_component_weights

    f_price: float = 0.0
    if close_raw is not None and ema_14 is not None and ema_14 != 0.0:
        gap_bps = (close_raw - ema_14) / ema_14 * 10000.0
        if gap_bps >= options.price_vs_ema14_min_gap_bps:
            span = options.price_vs_ema14_max_gap_bps - options.price_vs_ema14_min_gap_bps
            if span > 0.0:
                f_price = _clamp(
                    (gap_bps - options.price_vs_ema14_min_gap_bps) / span,
                    0.0,
                    1.0,
                )
            else:
                f_price = 1.0

    f_mom: float = 0.0
    if mom_10_pct is not None and mom_10_pct > 0.0:
        ref = options.mom_pct_max_reference
        if ref > 0.0:
            f_mom = _clamp(mom_10_pct / ref, 0.0, 1.0)
        else:
            f_mom = 1.0 if mom_10_pct > 0.0 else 0.0

    f_rsi: float = 0.0
    rsi_in_band = False
    if rsi_14 is not None:
        if options.rsi_entry_min <= rsi_14 <= options.rsi_entry_max:
            rsi_in_band = True
            band_span = options.rsi_entry_max - options.rsi_entry_min
            if band_span > 0.0:
                f_rsi = _clamp((rsi_14 - options.rsi_entry_min) / band_span, 0.0, 1.0)
            else:
                f_rsi = 1.0

    raw = w_price * f_price + w_mom * f_mom + w_rsi * f_rsi
    if rsi_14 is not None and not rsi_in_band:
        raw = 0.0
    return _clamp(raw, 0.0, 1.0)


def _compute_momentum_raw_strength(
    ctx: StrategyContext, options: MomentumStrategyOptions
) -> float:
    features = ctx.features.features
    mom_10_abs = _to_float_or_none(features.get("mom_10_abs"))
    mom_10_pct = _to_float_or_none(features.get("mom_10_pct"))
    rsi_14 = _to_float_or_none(features.get("rsi_14"))
    w_abs, w_pct = options.momentum_component_weights

    f_abs: float = 0.0
    if mom_10_abs is not None:
        abs_bps = abs(mom_10_abs)
        if abs_bps >= options.mom_entry_min_bps_abs:
            span = options.mom_entry_max_bps_abs - options.mom_entry_min_bps_abs
            if span > 0.0:
                f_abs = _clamp(
                    (abs_bps - options.mom_entry_min_bps_abs) / span,
                    0.0,
                    1.0,
                )
            else:
                f_abs = 1.0

    f_pct: float = 0.0
    if mom_10_pct is not None and mom_10_pct > 0.0:
        ref = options.mom_pct_max_reference
        if ref > 0.0:
            f_pct = _clamp(mom_10_pct / ref, 0.0, 1.0)
        else:
            f_pct = 1.0

    raw = w_abs * f_abs + w_pct * f_pct

    if rsi_14 is not None:
        if rsi_14 > options.rsi_overbought_max or rsi_14 < options.rsi_oversold_min:
            raw = 0.0

    return _clamp(raw, 0.0, 1.0)


def _build_regime_evidence(
    compat_map: dict[str, float], signal_strength: float
) -> dict[str, float]:
    evidence: dict[str, float] = {}
    for key in sorted(REGIME_KEYS):
        compat = float(compat_map.get(key, 0.0))
        evidence[key] = _clamp(compat * signal_strength, 0.0, 1.0)
    return evidence


def _entry_price_ref_from_ctx(ctx: StrategyContext) -> Decimal | None:
    v = ctx.features.features.get("close_raw")
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    if isinstance(v, str):
        try:
            return Decimal(v)
        except Exception:
            return None
    return None


class PureStrategy(ABC):
    strategy_id: str
    strategy_version: str

    @abstractmethod
    def evaluate(
        self,
        ctx: StrategyContext,
        *,
        quality_hint: StrategyQualityHint | None = None,
        options: Any | None = None,
    ) -> StrategySignal:
        raise NotImplementedError


@dataclass
class TrendFollowingStrategy(PureStrategy):
    strategy_id: str = "trend_following"
    strategy_version: str = STRATEGY_VERSION_DEFAULT
    default_options: TrendStrategyOptions = field(
        default_factory=lambda: DEFAULT_TREND_OPTIONS
    )

    def evaluate(
        self,
        ctx: StrategyContext,
        *,
        quality_hint: StrategyQualityHint | None = None,
        options: TrendStrategyOptions | None = None,
    ) -> StrategySignal:
        opt: TrendStrategyOptions = options if options is not None else self.default_options
        hint: StrategyQualityHint = quality_hint if quality_hint is not None else StrategyQualityHint()

        # Step 1: Version check
        fv_ok, dv_ok = _check_versions(ctx, opt)
        versions_ok = fv_ok and dv_ok
        if not versions_ok and opt.unexpected_version_mode == "raise":
            raise ContractSchemaError(
                f"Version mismatch: feature_version={ctx.features.feature_version!r} (expected {opt.feature_version!r}), "
                f"detector_version={ctx.regime.detector_version!r} (expected {opt.detector_version!r})"
            )

        # Step 2: Insufficient lookback
        insufficient, null_pct = _insufficient_lookback(ctx.features, opt)

        # Step 3: Quality
        q_mult = _quality_penalty_multiplier(hint)
        q_flat = _quality_force_flat(hint)

        # Step 4: Regime compat
        compat_map = _regime_compat_map(opt)
        regime_key = str(ctx.regime.regime.value) if isinstance(ctx.regime.regime, MarketRegimeState) else str(ctx.regime.regime)
        regime_mult = float(compat_map.get(regime_key, 0.0))

        # Step 5: Raw strength
        if not versions_ok or insufficient:
            raw_strength = 0.0
        else:
            raw_strength = _compute_trend_raw_strength(ctx, opt)

        # Step 6: Signal strength
        signal_strength = _clamp(raw_strength * regime_mult * q_mult, opt.clamp_min, opt.clamp_max)
        if signal_strength < opt.signal_strength_floor:
            signal_strength = opt.clamp_min

        # Step 7: Direction
        direction: SignalDirection
        if insufficient or q_flat or not versions_ok:
            direction = SignalDirection.FLAT
        elif regime_mult == 0.0:
            if regime_key == MarketRegimeState.BEAR.value:
                direction = SignalDirection.FLAT
            else:
                direction = SignalDirection.HOLD
        elif signal_strength >= opt.long_threshold:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.HOLD

        # Step 8: Confidence
        if insufficient or not versions_ok:
            confidence_base = float(opt.confidence_on_insufficient)
        else:
            regime_conf = _clamp(float(ctx.regime.confidence), 0.0, 1.0)
            confidence_base = (
                opt.confidence_signal_weight * signal_strength
                + opt.confidence_regime_weight * regime_conf
            )
        confidence = _clamp(confidence_base * q_mult, opt.clamp_min, opt.clamp_max)

        # Step 9: Supporting keys + regime evidence
        supporting_keys: list[str] = []
        for k in TREND_SUPPORTING_KEYS:
            supporting_keys.append(k)
        regime_evidence = _build_regime_evidence(compat_map, signal_strength)

        # Step 10: Entry thesis
        thesis_parts: list[str] = []
        thesis_parts.append(f"Trend v{self.strategy_version}")
        thesis_parts.append(f"ss={signal_strength:.2f}")
        thesis_parts.append(f"reg={regime_key}")
        thesis_parts.append(f"conf={confidence:.0%}")
        entry_thesis = " | ".join(thesis_parts)
        if len(entry_thesis) > 120:
            entry_thesis = entry_thesis[:120]

        # Step 11: Entry price ref
        entry_price_ref = _entry_price_ref_from_ctx(ctx)

        # Step 12: Correlation / causation preservation
        correlation_id = str(ctx.correlation_id)
        causation_id = str(ctx.causation_id)

        return StrategySignal(
            strategy_id=str(self.strategy_id),
            strategy_version=str(self.strategy_version),
            direction=direction,
            signal_strength=signal_strength,
            correlation_id=correlation_id,
            causation_id=causation_id,
            supporting_feature_keys=supporting_keys,
            supporting_regime_evidence=regime_evidence,
            entry_thesis=entry_thesis,
            entry_price_ref=entry_price_ref,
            stop_policy=None,
            take_profit_policy=None,
            confidence=confidence,
            expected_edge_bps=None,
        )


@dataclass
class MomentumStrategy(PureStrategy):
    strategy_id: str = "momentum"
    strategy_version: str = STRATEGY_VERSION_DEFAULT
    default_options: MomentumStrategyOptions = field(
        default_factory=lambda: DEFAULT_MOMENTUM_OPTIONS
    )

    def evaluate(
        self,
        ctx: StrategyContext,
        *,
        quality_hint: StrategyQualityHint | None = None,
        options: MomentumStrategyOptions | None = None,
    ) -> StrategySignal:
        opt: MomentumStrategyOptions = options if options is not None else self.default_options
        hint: StrategyQualityHint = quality_hint if quality_hint is not None else StrategyQualityHint()

        # Step 1: Version check
        fv_ok, dv_ok = _check_versions(ctx, opt)
        versions_ok = fv_ok and dv_ok
        if not versions_ok and opt.unexpected_version_mode == "raise":
            raise ContractSchemaError(
                f"Version mismatch: feature_version={ctx.features.feature_version!r} (expected {opt.feature_version!r}), "
                f"detector_version={ctx.regime.detector_version!r} (expected {opt.detector_version!r})"
            )

        # Step 2: Insufficient lookback
        insufficient, null_pct = _insufficient_lookback(ctx.features, opt)

        # Step 3: Quality
        q_mult = _quality_penalty_multiplier(hint)
        q_flat = _quality_force_flat(hint)

        # Step 4: Regime compat
        compat_map = _regime_compat_map(opt)
        regime_key = str(ctx.regime.regime.value) if isinstance(ctx.regime.regime, MarketRegimeState) else str(ctx.regime.regime)
        regime_mult = float(compat_map.get(regime_key, 0.0))

        # Step 5: Raw strength
        if not versions_ok or insufficient:
            raw_strength = 0.0
        else:
            raw_strength = _compute_momentum_raw_strength(ctx, opt)

        # Step 6: Signal strength
        signal_strength = _clamp(raw_strength * regime_mult * q_mult, opt.clamp_min, opt.clamp_max)
        if signal_strength < opt.signal_strength_floor:
            signal_strength = opt.clamp_min

        # Step 7: Direction
        direction: SignalDirection
        if insufficient or q_flat or not versions_ok:
            direction = SignalDirection.FLAT
        elif regime_mult == 0.0:
            if regime_key == MarketRegimeState.BEAR.value:
                direction = SignalDirection.FLAT
            else:
                direction = SignalDirection.HOLD
        elif signal_strength >= opt.long_threshold:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.HOLD

        # Step 8: Confidence
        if insufficient or not versions_ok:
            confidence_base = float(opt.confidence_on_insufficient)
        else:
            regime_conf = _clamp(float(ctx.regime.confidence), 0.0, 1.0)
            confidence_base = (
                opt.confidence_signal_weight * signal_strength
                + opt.confidence_regime_weight * regime_conf
            )
        confidence = _clamp(confidence_base * q_mult, opt.clamp_min, opt.clamp_max)

        # Step 9: Supporting keys + regime evidence
        supporting_keys: list[str] = []
        for k in MOMENTUM_SUPPORTING_KEYS:
            supporting_keys.append(k)
        regime_evidence = _build_regime_evidence(compat_map, signal_strength)

        # Step 10: Entry thesis
        thesis_parts: list[str] = []
        thesis_parts.append(f"Mom v{self.strategy_version}")
        thesis_parts.append(f"ss={signal_strength:.2f}")
        thesis_parts.append(f"reg={regime_key}")
        thesis_parts.append(f"conf={confidence:.0%}")
        entry_thesis = " | ".join(thesis_parts)
        if len(entry_thesis) > 120:
            entry_thesis = entry_thesis[:120]

        # Step 11: Entry price ref
        entry_price_ref = _entry_price_ref_from_ctx(ctx)

        # Step 12: Correlation / causation preservation
        correlation_id = str(ctx.correlation_id)
        causation_id = str(ctx.causation_id)

        return StrategySignal(
            strategy_id=str(self.strategy_id),
            strategy_version=str(self.strategy_version),
            direction=direction,
            signal_strength=signal_strength,
            correlation_id=correlation_id,
            causation_id=causation_id,
            supporting_feature_keys=supporting_keys,
            supporting_regime_evidence=regime_evidence,
            entry_thesis=entry_thesis,
            entry_price_ref=entry_price_ref,
            stop_policy=None,
            take_profit_policy=None,
            confidence=confidence,
            expected_edge_bps=None,
        )
