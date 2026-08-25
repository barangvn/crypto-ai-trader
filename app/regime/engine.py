from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from app.contracts.exceptions import ContractSchemaError
from app.contracts.feature import FeatureVector
from app.contracts.regime import (
    MarketRegime,
    MarketRegimeState,
    REGIME_KEYS,
    TimeRangeSpec,
)
from app.contracts.types import Instant, validate_instant


SREG01_DETECTOR_VERSION: str = "reg_01_v1"
SREG01_EXPECTED_FEATURE_VERSION: str = "fea_01_v1"
SREG01_NULLABLE_FEATURE_COUNT: int = 9


def _clamp(x: float, lo: float, hi: float) -> float:
    if math.isnan(x):
        return 0.0
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


@dataclass(frozen=True)
class QualityHint:
    """CAP-2 READ-ONLY wrapper around event quality flags.

    This class NEVER mutates the source quality payload and NEVER invokes
    the quality validator again. Consumer side should pre-compute these
    booleans from the Envelope quality_flags before passing them in.

    All fields default to False = clean data.
    """

    stale: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    missing: bool = False
    abnormal_spread: bool = False


@dataclass(frozen=True)
class DetectOptions:
    """Fixture/test overrideable thresholds.

    IMPORTANT: these are STORY DEFAULT values and do NOT represent final
    production calibration. Production decisions live in ADN-REG-01..08
    (open decisions) and will be re-evaluated after backtest/paper phases.

    Any value here can be overridden in tests to exercise edge cases.
    """

    # --- Transition trigger thresholds -----------------------------------
    tie_threshold: float = 0.050
    conflict_threshold: float = 0.300
    null_count_pct_transition: float = 0.500
    min_confidence_before_transition: float = 0.350

    # --- Volatility bands (bps) -------------------------------------------
    high_vol_bps_floor: float = 150.0
    low_vol_bps_ceiling: float = 25.0

    # --- Sideways bands ---------------------------------------------------
    sideways_band_ema_pct: float = 0.005
    sideways_rsi_band_lo: float = 43.0
    sideways_rsi_band_hi: float = 57.0
    momentum_band_abs_pct: float = 0.003

    # --- Confidence smoothing --------------------------------------------
    confidence_smooth_alpha: float = 0.85

    # --- Quality penalty multipliers (1.0 = no penalty) ------------------
    quality_penalty_invalid_quarantined: float = 0.20
    quality_penalty_stale_degraded: float = 0.75
    quality_penalty_dup_missing_ooo: float = 0.90
    quality_penalty_abnormal_spread: float = 0.85

    # --- Transition confidence penalty -----------------------------------
    transition_confidence_mult: float = 0.75

    # --- Unexpected feature_version mode ---------------------------------
    # "raise" (default ADN-REG-02 var1) or "transition" (var2)
    unexpected_version_mode: str = "raise"


DEFAULT_OPTIONS: DetectOptions = DetectOptions()


# ---------------------------------------------------------------------------
# 3-axis computation helpers
# ---------------------------------------------------------------------------


def _to_float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _compute_trend_axis(f12: dict[str, float | None]) -> float:
    """Trend axis: EMA dist (0.45), RSI offset (0.35), VWAP dist (0.20). Range [-1, +1]."""
    ema14 = f12.get("ema_14")
    close = f12.get("close_raw")
    rsi14 = f12.get("rsi_14")
    vwap20 = f12.get("vwap_20")

    # a) EMA component
    ema_comp = 0.0
    if ema14 is not None and close is not None and ema14 != 0.0:
        ed = (close - ema14) / ema14
        ed = _clamp(ed, -0.05, 0.05)
        ema_comp = _clamp(ed / 0.05, -1.0, 1.0)

    # b) RSI component (50 center -> 0; 0 -> -1; 100 -> +1)
    rsi_comp = 0.0
    if rsi14 is not None:
        r = _clamp(rsi14, 0.0, 100.0)
        rsi_comp = _clamp((r - 50.0) / 50.0, -1.0, 1.0)

    # c) VWAP component
    vwap_comp = 0.0
    if vwap20 is not None and close is not None and vwap20 != 0.0:
        vd = (close - vwap20) / vwap20
        vd = _clamp(vd, -0.05, 0.05)
        vwap_comp = _clamp(vd / 0.05, -1.0, 1.0)

    raw = 0.45 * ema_comp + 0.35 * rsi_comp + 0.20 * vwap_comp
    return _clamp(raw, -1.0, 1.0)


def _compute_mom_axis(f12: dict[str, float | None]) -> float:
    """Momentum axis: mom_10_abs scaled (0.55), mom_10_pct scaled (0.45). Range [-1, +1]."""
    close = f12.get("close_raw")
    mom_abs = f12.get("mom_10_abs")
    mom_pct = f12.get("mom_10_pct")

    # a) Abs momentum normalized by close
    abs_comp = 0.0
    if mom_abs is not None and close is not None and close != 0.0:
        ratio = mom_abs / close
        ratio = _clamp(ratio, -0.05, 0.05)
        abs_comp = _clamp(ratio / 0.05, -1.0, 1.0)

    # b) Pct momentum (already a percentage, but units are raw decimal e.g.
    # +0.02 means +2%, so scale by +/- 5% band)
    pct_comp = 0.0
    if mom_pct is not None:
        p = _clamp(mom_pct, -0.05, 0.05)
        pct_comp = _clamp(p / 0.05, -1.0, 1.0)

    raw = 0.55 * abs_comp + 0.45 * pct_comp
    return _clamp(raw, -1.0, 1.0)


def _compute_vol_axis(f12: dict[str, float | None], opt: DetectOptions) -> float:
    """Volatility axis: negative = low vol, positive = high vol, 0 = neutral/mid.

    Range [-1, +1]. Uses volatility_20_bps bands + vol_ratio + vol_std scalers.
    """
    v_bps = f12.get("volatility_20_bps")
    vol_ratio = f12.get("vol_ratio_20")
    vol_std_scaled = f12.get("vol_std_20_scaled")

    vol_ax = 0.0
    if v_bps is not None:
        if v_bps <= opt.low_vol_bps_ceiling:
            denom = opt.low_vol_bps_ceiling if opt.low_vol_bps_ceiling > 0 else 1.0
            vol_ax = -1.0 + 2.0 * (v_bps / denom)
            vol_ax = _clamp(vol_ax, -1.0, 0.0)
        elif v_bps >= opt.high_vol_bps_floor:
            spread = opt.high_vol_bps_floor if opt.high_vol_bps_floor > 0 else 1.0
            excess = (v_bps - opt.high_vol_bps_floor) / spread
            vol_ax = _clamp(excess, 0.0, 1.0)
        else:
            # 25 < v < 150, linear 0 neighbourhood
            mid = opt.low_vol_bps_ceiling + (opt.high_vol_bps_floor - opt.low_vol_bps_ceiling) * 0.5
            half_span = (opt.high_vol_bps_floor - opt.low_vol_bps_ceiling) * 0.5
            if half_span <= 0:
                vol_ax = 0.0
            else:
                vol_ax = _clamp((v_bps - mid) / half_span * 0.3, -0.3, 0.3)

    # vol_ratio adds +/- 0.1 at extremes
    ratio_adj = 0.0
    if vol_ratio is not None:
        if vol_ratio >= 2.0:
            ratio_adj = 0.1
        elif vol_ratio <= 0.5:
            ratio_adj = -0.1
        else:
            ratio_adj = _clamp((vol_ratio - 1.0) / 1.0 * 0.1, -0.1, 0.1)

    # vol_std adds +/- 0.1 at extremes
    std_adj = 0.0
    if vol_std_scaled is not None:
        if vol_std_scaled >= 50.0:
            std_adj = 0.1
        elif vol_std_scaled <= 0.0:
            std_adj = 0.0
        else:
            std_adj = _clamp(vol_std_scaled / 50.0 * 0.1, 0.0, 0.1)

    return _clamp(vol_ax + ratio_adj + std_adj, -1.0, 1.0)


# ---------------------------------------------------------------------------
# 6 raw scores -> clamped
# ---------------------------------------------------------------------------


def _six_raw_scores(
    trend: float,
    mom: float,
    vol: float,
    f12: dict[str, float | None],
    opt: DetectOptions,
) -> dict[str, float]:
    rsi14 = f12.get("rsi_14")
    ema14 = f12.get("ema_14")
    close = f12.get("close_raw")
    mom_pct = f12.get("mom_10_pct")
    v_bps = f12.get("volatility_20_bps")
    vol_ratio = f12.get("vol_ratio_20")

    # bull: trend_up(+) + mom_up(+) + low_vol(+)
    bull_raw = 0.55 * max(0.0, trend) + 0.30 * max(0.0, mom) + 0.15 * max(0.0, -vol)

    # bear: trend_down(+) + mom_down(+) + low_vol(+)
    bear_raw = 0.55 * max(0.0, -trend) + 0.30 * max(0.0, -mom) + 0.15 * max(0.0, -vol)

    # sideways: product of neutrality axes + optional bonus
    comp_trend_n = 1.0 - abs(trend)
    comp_mom_n = 1.0 - abs(mom)
    comp_vol_mid = 1.0 - abs(vol)
    sideways_raw = comp_trend_n * comp_mom_n * comp_vol_mid

    ema_flat = False
    if ema14 is not None and close is not None and ema14 != 0.0:
        if abs(close - ema14) / abs(ema14) <= opt.sideways_band_ema_pct:
            ema_flat = True
    rsi_neutral = False
    if rsi14 is not None and opt.sideways_rsi_band_lo <= rsi14 <= opt.sideways_rsi_band_hi:
        rsi_neutral = True
    mom_flat = False
    if mom_pct is not None and abs(mom_pct) <= opt.momentum_band_abs_pct:
        mom_flat = True
    if ema_flat and rsi_neutral and mom_flat:
        sideways_raw = sideways_raw + 0.30

    # high_vol
    hv_spike = 0.0
    if v_bps is not None and vol_ratio is not None and v_bps >= 100.0 and vol_ratio >= 2.0:
        hv_spike = 0.15
    high_vol_raw = 0.85 * max(0.0, vol) + hv_spike

    # low_vol
    lv_calm = 0.0
    if v_bps is not None and vol_ratio is not None and v_bps <= opt.low_vol_bps_ceiling and vol_ratio <= 0.9:
        lv_calm = 0.15
    low_vol_raw = 0.85 * max(0.0, -vol) + lv_calm

    # transition uncertain (floor 0.001 so never exactly zero; may be bumped later)
    transition_raw = 0.001

    unclamped: dict[str, float] = {
        "bull": bull_raw,
        "bear": bear_raw,
        "high_volatility": high_vol_raw,
        "low_volatility": low_vol_raw,
        "sideways": sideways_raw,
        "transition_uncertain": transition_raw,
    }

    # Now clamp every score to [0.0, 1.0] — sum is NOT required to be 1.0 per
    # CONTRACTS §3.6.
    clamped: dict[str, float] = {}
    for k in sorted(unclamped.keys()):
        clamped[k] = _clamp(unclamped[k], 0.0, 1.0)

    # Make sure the dict order is deterministic and matches REGIME_KEYS.
    # (Sorted alphabetical iteration above gives us determinism already;
    #  below we also confirm completeness by re-projecting onto REGIME_KEYS
    #  sorted list.)
    final: dict[str, float] = {}
    for k in sorted(REGIME_KEYS):
        final[k] = clamped[k]
    return final


# ---------------------------------------------------------------------------
# Transition triggers + confidence
# ---------------------------------------------------------------------------


def _transition_triggers(
    scores: dict[str, float],
    f12: dict[str, float | None],
    null_count: int,
    opt: DetectOptions,
    qh: QualityHint,
    trend: float,
    mom: float,
    vol: float,
) -> tuple[bool, dict[str, bool]]:
    flags: dict[str, bool] = {
        "T1_tie": False,
        "T2_conflict": False,
        "T3_insufficient_lookback": False,
        "T4_low_confidence": False,
        "T5_quality_invalid_quarantined": False,
    }

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top1 = ordered[0][1]
    top2 = ordered[1][1] if len(ordered) >= 2 else 0.0
    if top1 - top2 < opt.tie_threshold:
        flags["T1_tie"] = True

    # T2 conflict: strong trend/mom but high volatility → regime-level conflict
    # between bull/bear (trend-driven) and high_volatility. The axis-level
    # magnitude difference was a weak proxy; the real transition fires when
    # trend directionality AND volatility regime signals are BOTH strong.
    trend_mom_avg = (abs(trend) + abs(mom)) * 0.5
    t2_axis_cond = trend_mom_avg >= 0.400 and abs(vol) >= opt.conflict_threshold
    t2_score_cond = False
    if t2_axis_cond:
        t2_score_cond = (
            (scores.get("bull", 0.0) >= 0.40 or scores.get("bear", 0.0) >= 0.40)
            and scores.get("high_volatility", 0.0) >= 0.20
        )
    # Fallback: very strong axis-level opposition always triggers
    t2_extreme_cond = abs(trend) >= 0.60 and abs(vol) >= 0.60
    if t2_axis_cond and (t2_score_cond or t2_extreme_cond):
        flags["T2_conflict"] = True

    # T3 insufficient lookback
    if SREG01_NULLABLE_FEATURE_COUNT > 0:
        ratio = null_count / SREG01_NULLABLE_FEATURE_COUNT
        if ratio >= opt.null_count_pct_transition:
            flags["T3_insufficient_lookback"] = True

    # T4 low proxy confidence (before quality & transition penalties)
    rest_sum = sum(v for _, v in ordered[1:])
    mean_rest = rest_sum / max(1, len(ordered) - 1)
    proxy_conf = _clamp(top1 - mean_rest, 0.0, 1.0)
    if proxy_conf < opt.min_confidence_before_transition:
        flags["T4_low_confidence"] = True

    # T5 quality invalid or quarantined
    if qh.invalid or qh.quarantined:
        flags["T5_quality_invalid_quarantined"] = True

    effective = any(v for v in flags.values())
    return effective, flags


def _confidence_final(
    scores: dict[str, float],
    opt: DetectOptions,
    qh: QualityHint,
    effective_transition: bool,
) -> float:
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top1 = ordered[0][1]
    rest_sum = sum(v for _, v in ordered[1:])
    mean_rest = rest_sum / max(1, len(ordered) - 1)
    conf_base = _clamp(top1 - mean_rest, 0.0, 1.0)
    conf_smoothed = _clamp(
        opt.confidence_smooth_alpha * conf_base + (1.0 - opt.confidence_smooth_alpha) * top1,
        0.0,
        1.0,
    )

    qmul = 1.0
    if qh.invalid or qh.quarantined:
        qmul *= opt.quality_penalty_invalid_quarantined
    if qh.stale or qh.degraded:
        qmul *= opt.quality_penalty_stale_degraded
    if qh.duplicate or qh.out_of_order or qh.missing:
        qmul *= opt.quality_penalty_dup_missing_ooo
    if qh.abnormal_spread:
        qmul *= opt.quality_penalty_abnormal_spread

    if effective_transition:
        qmul *= opt.transition_confidence_mult

    return _clamp(conf_smoothed * qmul, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Lookback TimeRangeSpec derivation
# ---------------------------------------------------------------------------


def _derive_lookback_ts(
    fv: FeatureVector,
    start_override: Instant | None,
    end_override: Instant | None,
) -> TimeRangeSpec:
    refs = getattr(fv, "input_refs", None) or []

    # Need: always need valid values for start and end
    start_s: str | None = None
    end_s: str | None = None

    if not refs:
        if start_override is None or end_override is None:
            raise ContractSchemaError(
                "RegimeEngine: cannot derive lookback_ts because FeatureVector.input_refs is empty. "
                "Provide lookback_start_override and lookback_end_override, or populate input_refs."
            )
    else:
        iso_candidates: list[str] = []
        for r in refs:
            if isinstance(r, str) and validate_instant(r):
                iso_candidates.append(r)
        if not iso_candidates:
            if start_override is None or end_override is None:
                raise ContractSchemaError(
                    "RegimeEngine: cannot derive lookback_ts because FeatureVector.input_refs "
                    "contains no valid ISO-8601 Instant strings. Provide overrides."
                )
        else:
            start_s = min(iso_candidates)
            end_s = max(iso_candidates)

    actual_start = str(start_override) if start_override is not None else start_s
    actual_end = str(end_override) if end_override is not None else end_s

    if actual_start is None or actual_end is None:
        raise ContractSchemaError(
            "RegimeEngine: lookback_ts start/end missing after merging input_refs + overrides."
        )

    if str(actual_start) > str(actual_end):
        raise ContractSchemaError(
            "RegimeEngine: lookback_ts start must be <= end; got "
            f"start={actual_start} end={actual_end}"
        )

    return TimeRangeSpec(start=Instant(actual_start), end=Instant(actual_end))


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


@dataclass
class RegimeEngine:
    """Deterministic 6-state MarketRegime detector — AD-8.

    Public contract (see S-REG-01 §4.1):
        detect(symbol, fv, quality_hint=None, *, lookback_start_override=None,
               lookback_end_override=None, correlation_id=None, causation_id=None)
        -> tuple[MarketRegime, dict[str, Any]]

    The second tuple element is the AUX payload carrying correlation_id,
    causation_id, and debugging metadata. MarketRegime dataclass itself
    keeps exactly 7 fields as per the existing S-CON-02A contract (no
    contract bump in this story — ADN-REG-01 open).
    """

    detector_version: str = SREG01_DETECTOR_VERSION
    options: DetectOptions = field(default_factory=lambda: DEFAULT_OPTIONS)

    # ---------------- public API -------------------------------------------

    def detect(
        self,
        symbol: str,
        feature_vector: FeatureVector,
        quality_hint: QualityHint | None = None,
        *,
        lookback_start_override: Instant | None = None,
        lookback_end_override: Instant | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> tuple[MarketRegime, dict[str, Any]]:
        # Step 1 — input validation (AD-22 feature_version contract enforcement)
        if not isinstance(feature_vector, FeatureVector):
            raise ContractSchemaError(
                f"RegimeEngine.detect expects FeatureVector, got {type(feature_vector).__name__}"
            )

        expected_ver = SREG01_EXPECTED_FEATURE_VERSION
        if feature_vector.feature_version != expected_ver:
            if self.options.unexpected_version_mode == "transition":
                return self._make_transition_fallback(
                    feature_vector,
                    symbol=symbol,
                    quality_hint=quality_hint or QualityHint(),
                    lookback_start_override=lookback_start_override,
                    lookback_end_override=lookback_end_override,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    reason=f"unexpected_feature_version:{feature_vector.feature_version}",
                )
            raise ContractSchemaError(
                f"RegimeEngine: unsupported feature_version={feature_vector.feature_version!r}, "
                f"expected={expected_ver!r}. "
                "Use DetectOptions(unexpected_version_mode='transition') to override."
            )

        qh = quality_hint or QualityHint()

        # Step 2 — extract 12 known features + their floats-or-None
        f12 = self._extract_f12(feature_vector)
        null_count: int = feature_vector.null_count if feature_vector.null_count is not None else 0

        # Step 3 — 3 axes
        trend = _compute_trend_axis(f12)
        mom = _compute_mom_axis(f12)
        vol = _compute_vol_axis(f12, self.options)

        # Step 4 — 6 raw scores then clamp to [0,1]
        scores_clamped = _six_raw_scores(trend, mom, vol, f12, self.options)

        # Step 5 — transition triggers (OR)
        eff_trans, flags = _transition_triggers(
            scores_clamped,
            f12,
            null_count,
            self.options,
            qh,
            trend,
            mom,
            vol,
        )

        # Step 6 — confidence final with quality & transition penalties
        conf = _confidence_final(scores_clamped, self.options, qh, eff_trans)

        # Step 7 — regime state selection (deterministic tie-break via sorted key)
        if eff_trans:
            state = MarketRegimeState.TRANSITION_UNCERTAIN
        else:
            ordered = sorted(scores_clamped.items(), key=lambda kv: (kv[1], [-ord(c) for c in kv[0]]), reverse=False)
            # Stable: sort by value DESC, then alphabetical key ASC (deterministic tie-break)
            ordered_desc = sorted(scores_clamped.items(), key=lambda kv: (-kv[1], kv[0]))
            best_key = ordered_desc[0][0]
            state = MarketRegimeState(best_key)

        # Step 8 — lookback_ts (AD-8 provenance)
        lookback_ts = _derive_lookback_ts(feature_vector, lookback_start_override, lookback_end_override)

        # Step 9 — build MarketRegime (existing 7-field S-CON-02A contract)
        regime_obj = MarketRegime(
            timeframe=feature_vector.timeframe,
            regime=state,
            confidence=float(conf),
            scores=scores_clamped,
            detector_version=str(self.detector_version),
            feature_version=str(feature_vector.feature_version),
            lookback_ts=lookback_ts,
        )

        # Step 10 — build AUX payload
        raw_scores_before_clamp_unordered = _six_raw_scores(trend, mom, vol, f12, self.options)
        # preserve ordering but we actually want the pre-clamp values computed
        # separately here (we'll recalc raw without the clamp step):
        raw_unclamped = self._raw_scores_unclamped(trend, mom, vol, f12, self.options)
        quality_penalty_applied = self._compute_applied_quality_multiplier(qh, eff_trans)

        aux: dict[str, Any] = {
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "symbol": symbol,
            "feature_version_used": feature_vector.feature_version,
            "quality_hint_applied_penalty": quality_penalty_applied,
            "raw_axes": {
                "trend_axis": float(trend),
                "mom_axis": float(mom),
                "vol_axis": float(vol),
            },
            "raw_scores_before_clamp": raw_unclamped,
            "tie_activated": bool(flags["T1_tie"]),
            "conflict_activated": bool(flags["T2_conflict"]),
            "insufficient_lookback_activated": bool(flags["T3_insufficient_lookback"]),
            "low_confidence_activated": bool(flags["T4_low_confidence"]),
            "quality_triggered_transition": bool(flags["T5_quality_invalid_quarantined"]),
            "transition_flags": dict(flags),
            "transition_reasons": sorted([k for k, v in flags.items() if v]),
            "detector_version": self.detector_version,
        }

        # Ensure deterministic aux JSON ordering for downstream hash checks
        _ = json.dumps(aux, sort_keys=True, default=str)  # sanity check sortability
        return regime_obj, aux

    # ---------------- internals (pure helpers) -----------------------------

    def _extract_f12(self, fv: FeatureVector) -> dict[str, float | None]:
        expected12 = [
            "ema_14",
            "rsi_14",
            "atr_14",
            "vwap_20",
            "mom_10_abs",
            "mom_10_pct",
            "volatility_20_bps",
            "vol_ratio_20",
            "vol_std_20_scaled",
            "close_raw",
            "high_raw",
            "low_raw",
        ]
        out: dict[str, float | None] = {}
        for k in expected12:
            out[k] = _to_float_or_none(fv.features.get(k))
        return out

    def _raw_scores_unclamped(
        self,
        trend: float,
        mom: float,
        vol: float,
        f12: dict[str, float | None],
        opt: DetectOptions,
    ) -> dict[str, float]:
        rsi14 = f12.get("rsi_14")
        ema14 = f12.get("ema_14")
        close = f12.get("close_raw")
        mom_pct = f12.get("mom_10_pct")
        v_bps = f12.get("volatility_20_bps")
        vol_ratio = f12.get("vol_ratio_20")

        bull = 0.55 * max(0.0, trend) + 0.30 * max(0.0, mom) + 0.15 * max(0.0, -vol)
        bear = 0.55 * max(0.0, -trend) + 0.30 * max(0.0, -mom) + 0.15 * max(0.0, -vol)
        s1 = 1.0 - abs(trend)
        s2 = 1.0 - abs(mom)
        s3 = 1.0 - abs(vol)
        side = s1 * s2 * s3
        ema_flat = False
        if ema14 is not None and close is not None and ema14 != 0.0:
            if abs(close - ema14) / abs(ema14) <= opt.sideways_band_ema_pct:
                ema_flat = True
        rsi_n = (
            rsi14 is not None and opt.sideways_rsi_band_lo <= rsi14 <= opt.sideways_rsi_band_hi
        )
        mom_f = mom_pct is not None and abs(mom_pct) <= opt.momentum_band_abs_pct
        if ema_flat and rsi_n and mom_f:
            side = side + 0.30

        hv_sp = 0.0
        if v_bps is not None and vol_ratio is not None and v_bps >= 100.0 and vol_ratio >= 2.0:
            hv_sp = 0.15
        hv = 0.85 * max(0.0, vol) + hv_sp

        lv_cl = 0.0
        if v_bps is not None and vol_ratio is not None and v_bps <= opt.low_vol_bps_ceiling and vol_ratio <= 0.9:
            lv_cl = 0.15
        lv = 0.85 * max(0.0, -vol) + lv_cl

        tu = 0.001
        return {
            "bull": float(bull),
            "bear": float(bear),
            "sideways": float(side),
            "high_volatility": float(hv),
            "low_volatility": float(lv),
            "transition_uncertain": float(tu),
        }

    def _compute_applied_quality_multiplier(self, qh: QualityHint, eff_trans: bool) -> float:
        m = 1.0
        if qh.invalid or qh.quarantined:
            m *= self.options.quality_penalty_invalid_quarantined
        if qh.stale or qh.degraded:
            m *= self.options.quality_penalty_stale_degraded
        if qh.duplicate or qh.out_of_order or qh.missing:
            m *= self.options.quality_penalty_dup_missing_ooo
        if qh.abnormal_spread:
            m *= self.options.quality_penalty_abnormal_spread
        if eff_trans:
            m *= self.options.transition_confidence_mult
        return float(m)

    def _make_transition_fallback(
        self,
        fv: FeatureVector,
        symbol: str,
        quality_hint: QualityHint,
        lookback_start_override: Instant | None,
        lookback_end_override: Instant | None,
        correlation_id: str | None,
        causation_id: str | None,
        reason: str,
    ) -> tuple[MarketRegime, dict[str, Any]]:
        # Build low-confidence transition regime.
        lookback_ts = _derive_lookback_ts(fv, lookback_start_override, lookback_end_override)
        scores: dict[str, float] = {k: 0.05 for k in sorted(REGIME_KEYS)}
        scores["transition_uncertain"] = 0.70
        # ensure 0<=v<=1 each
        for k in scores:
            scores[k] = _clamp(scores[k], 0.0, 1.0)
        conf = 0.05
        if quality_hint.invalid or quality_hint.quarantined:
            conf = 0.03
        regime_obj = MarketRegime(
            timeframe=fv.timeframe,
            regime=MarketRegimeState.TRANSITION_UNCERTAIN,
            confidence=float(conf),
            scores=scores,
            detector_version=str(self.detector_version),
            feature_version=str(fv.feature_version),
            lookback_ts=lookback_ts,
        )
        aux: dict[str, Any] = {
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "symbol": symbol,
            "feature_version_used": fv.feature_version,
            "quality_hint_applied_penalty": self._compute_applied_quality_multiplier(quality_hint, True),
            "raw_axes": {"trend_axis": 0.0, "mom_axis": 0.0, "vol_axis": 0.0},
            "raw_scores_before_clamp": dict(scores),
            "tie_activated": False,
            "conflict_activated": False,
            "insufficient_lookback_activated": False,
            "low_confidence_activated": True,
            "quality_triggered_transition": quality_hint.invalid or quality_hint.quarantined,
            "transition_flags": {
                "T1_tie": False,
                "T2_conflict": False,
                "T3_insufficient_lookback": False,
                "T4_low_confidence": True,
                "T5_quality_invalid_quarantined": quality_hint.invalid or quality_hint.quarantined,
            },
            "transition_reasons": sorted([reason, "fallback_unexpected_version"]),
            "detector_version": self.detector_version,
        }
        _ = json.dumps(aux, sort_keys=True, default=str)
        return regime_obj, aux
