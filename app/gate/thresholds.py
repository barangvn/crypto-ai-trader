from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from app.contracts.model import _REQUIRED_METRIC_KEYS
from app.evaluation.delta import (
    Directionality,
    metric_direction_table,
    round_metric_value,
)
from app.gate.exceptions import (
    ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT,
    ERR_GATE_HARD_DRAWDOWN_WORSENED,
    ERR_GATE_HARD_OOS_FLAG_FALSE,
    ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY,
    ERR_GATE_HARD_RETURN_NOT_POSITIVE,
    ERR_GATE_HARD_SHARPE_NEGATIVE,
    ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT,
    ERR_GATE_NORM_BOUNDS_INVALID,
    ERR_GATE_NORM_METRIC_MISSING,
    THRESHOLD_FAIL_BY_METRIC_KEY,
)


THRESHOLDS_VERSION_V1 = "gate-thresholds-default-v1"


def default_thresholds_v1() -> dict[str, Any]:
    metric_bounds: dict[str, tuple[float, float]] = {
        "return_pct": (-0.05, 0.50),
        "max_drawdown_pct": (0.0, 0.50),
        "sharpe_ratio": (0.0, 5.0),
        "sortino_ratio": (0.0, 5.0),
        "profit_factor": (0.0, 5.0),
        "total_fees_quote": (0.0, 10000.0),
        "avg_slippage_bps": (0.0, 50.0),
        "trade_count": (0.0, 1000.0),
        "regime_coverage_count": (0.0, 10.0),
        "window_days": (0.0, 730.0),
        "oos_flag": (0.0, 1.0),
        "stability": (0.0, 1.0),
        "fees_per_trade": (0.0, 0.01),
    }

    hard_thresholds: dict[str, Any] = {
        "return_delta_min_positive": True,
        "drawdown_delta_worsened": True,
        "sharpe_min": 0.0,
        "profit_factor_min": 1.0,
        "trade_count_min": 30,
        "oos_flag_exact_true": True,
    }

    soft_thresholds: dict[str, Any] = {
        "return_pct_min": 0.01,
        "max_drawdown_pct_max": 0.25,
        "sharpe_ratio_min": 1.0,
        "sortino_ratio_min": 1.2,
        "profit_factor_min": 1.2,
        "total_fees_quote_champion_factor_max": 1.10,
        "avg_slippage_bps_max": 15.0,
        "trade_count_min": 30,
        "regime_coverage_count_min": 3,
        "window_days_min": 90,
        "oos_flag_exact_true": True,
    }

    meta_thresholds: dict[str, Any] = {
        "min_total_score": 0.65,
        "max_eval_age_days": 30,
        "min_approval_count": 1,
    }

    return {
        "metric_bounds": metric_bounds,
        "hard_thresholds": hard_thresholds,
        "soft_thresholds": soft_thresholds,
        "meta_thresholds": meta_thresholds,
        "version": THRESHOLDS_VERSION_V1,
    }


def _to_float_for_norm(value: Any, metric_key: str) -> float:
    try:
        rounded = round_metric_value(value, metric_key)
        if isinstance(rounded, Decimal):
            return float(rounded)
        if isinstance(rounded, bool):
            return 1.0 if rounded else 0.0
        if isinstance(rounded, int):
            return float(rounded)
        return float(rounded)
    except Exception:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, int):
            return float(value)
        return float(value)


def normalize_metric(
    key: str,
    value: Any,
    bounds: tuple[float, float],
    direction: Directionality | None = None,
) -> tuple[float, str | None]:
    if direction is None:
        direction = metric_direction_table.get(key, Directionality.HIGHER_BETTER)

    if not isinstance(bounds, tuple) or len(bounds) != 2:
        return 0.0, ERR_GATE_NORM_BOUNDS_INVALID
    lo, hi = bounds
    try:
        lo_f = float(lo)
        hi_f = float(hi)
    except (TypeError, ValueError):
        return 0.0, ERR_GATE_NORM_BOUNDS_INVALID
    if hi_f <= lo_f:
        return 0.0, ERR_GATE_NORM_BOUNDS_INVALID

    try:
        v = _to_float_for_norm(value, key)
    except Exception:
        return 0.0, ERR_GATE_NORM_METRIC_MISSING
    if v != v:
        return 0.0, ERR_GATE_NORM_METRIC_MISSING

    span = hi_f - lo_f
    if span <= 0.0:
        return 0.0, ERR_GATE_NORM_BOUNDS_INVALID

    if direction is Directionality.LOWER_BETTER:
        raw = (hi_f - v) / span
    else:
        raw = (v - lo_f) / span

    if raw < 0.0:
        clamped = 0.0
    elif raw > 1.0:
        clamped = 1.0
    else:
        clamped = raw

    rounded = round(clamped, 8)
    return rounded, None


def check_hard_constraints(
    challenger_metrics: dict[str, Any],
    champion_metrics: dict[str, Any] | None = None,
    delta_map: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    delta_map = delta_map or {}
    champion_metrics = champion_metrics or {}

    return_delta = delta_map.get("return_pct")
    if return_delta is None:
        try:
            c_ret = round_metric_value(challenger_metrics["return_pct"], "return_pct")
            p_ret = round_metric_value(champion_metrics["return_pct"], "return_pct")
            return_delta = float(Decimal(str(c_ret)) - Decimal(str(p_ret)))
        except Exception:
            return_delta = None
    if return_delta is None or not (return_delta > 0.0):
        reasons.append(ERR_GATE_HARD_RETURN_NOT_POSITIVE)

    drawdown_delta = delta_map.get("max_drawdown_pct")
    if drawdown_delta is None:
        try:
            c_dd = round_metric_value(challenger_metrics["max_drawdown_pct"], "max_drawdown_pct")
            p_dd = round_metric_value(champion_metrics["max_drawdown_pct"], "max_drawdown_pct")
            drawdown_delta = float(Decimal(str(c_dd)) - Decimal(str(p_dd)))
        except Exception:
            drawdown_delta = None
    if drawdown_delta is None or drawdown_delta > 0.0:
        reasons.append(ERR_GATE_HARD_DRAWDOWN_WORSENED)

    try:
        sharpe_v = round_metric_value(challenger_metrics["sharpe_ratio"], "sharpe_ratio")
        if not (float(Decimal(str(sharpe_v))) >= 0.0):
            reasons.append(ERR_GATE_HARD_SHARPE_NEGATIVE)
    except Exception:
        reasons.append(ERR_GATE_HARD_SHARPE_NEGATIVE)

    try:
        pf_v = round_metric_value(challenger_metrics["profit_factor"], "profit_factor")
        if not (float(Decimal(str(pf_v))) >= 1.0):
            reasons.append(ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY)
    except Exception:
        reasons.append(ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY)

    try:
        tc_v = round_metric_value(challenger_metrics["trade_count"], "trade_count")
        if not (int(tc_v) >= 30):
            reasons.append(ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT)
    except Exception:
        reasons.append(ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT)

    try:
        oos_v = challenger_metrics["oos_flag"]
        if oos_v is not True:
            reasons.append(ERR_GATE_HARD_OOS_FLAG_FALSE)
    except Exception:
        reasons.append(ERR_GATE_HARD_OOS_FLAG_FALSE)

    challenger_wins = 0
    for key in _REQUIRED_METRIC_KEYS:
        direction = metric_direction_table.get(key, Directionality.HIGHER_BETTER)
        delta_val = delta_map.get(key)
        if delta_val is None:
            try:
                c_val = round_metric_value(challenger_metrics[key], key)
                p_val = round_metric_value(champion_metrics[key], key)
                c_float = float(Decimal(str(c_val))) if isinstance(c_val, Decimal) else float(c_val)
                p_float = float(Decimal(str(p_val))) if isinstance(p_val, Decimal) else float(p_val)
                delta_val = c_float - p_float
            except Exception:
                continue
        try:
            d = float(delta_val)
        except Exception:
            continue
        if direction is Directionality.LOWER_BETTER:
            if d < -1e-12:
                challenger_wins += 1
        else:
            if d > 1e-12:
                challenger_wins += 1
    if challenger_wins < 3:
        reasons.append(ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT)

    return reasons


def check_soft_thresholds(
    challenger_metrics: dict[str, Any],
    champion_metrics: dict[str, Any] | None = None,
    soft_cfg: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    soft_cfg = soft_cfg or default_thresholds_v1()["soft_thresholds"]
    champion_metrics = champion_metrics or {}

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["return_pct"], "return_pct"))))
        if v < float(soft_cfg["return_pct_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["return_pct"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["return_pct"])

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["max_drawdown_pct"], "max_drawdown_pct"))))
        if v > float(soft_cfg["max_drawdown_pct_max"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["max_drawdown_pct"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["max_drawdown_pct"])

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["sharpe_ratio"], "sharpe_ratio"))))
        if v < float(soft_cfg["sharpe_ratio_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["sharpe_ratio"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["sharpe_ratio"])

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["sortino_ratio"], "sortino_ratio"))))
        if v < float(soft_cfg["sortino_ratio_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["sortino_ratio"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["sortino_ratio"])

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["profit_factor"], "profit_factor"))))
        if v < float(soft_cfg["profit_factor_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["profit_factor"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["profit_factor"])

    try:
        c_fees = float(Decimal(str(round_metric_value(challenger_metrics["total_fees_quote"], "total_fees_quote"))))
        p_fees = float(Decimal(str(round_metric_value(champion_metrics["total_fees_quote"], "total_fees_quote"))))
        factor_max = float(soft_cfg["total_fees_quote_champion_factor_max"])
        if p_fees > 0.0:
            if c_fees > p_fees * factor_max:
                reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["total_fees_quote"])
        else:
            if c_fees > 0.0:
                reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["total_fees_quote"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["total_fees_quote"])

    try:
        v = float(Decimal(str(round_metric_value(challenger_metrics["avg_slippage_bps"], "avg_slippage_bps"))))
        if v > float(soft_cfg["avg_slippage_bps_max"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["avg_slippage_bps"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["avg_slippage_bps"])

    try:
        v = int(round_metric_value(challenger_metrics["trade_count"], "trade_count"))
        if v < int(soft_cfg["trade_count_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["trade_count"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["trade_count"])

    try:
        v = int(round_metric_value(challenger_metrics["regime_coverage_count"], "regime_coverage_count"))
        if v < int(soft_cfg["regime_coverage_count_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["regime_coverage_count"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["regime_coverage_count"])

    try:
        v = int(round_metric_value(challenger_metrics["window_days"], "window_days"))
        if v < int(soft_cfg["window_days_min"]):
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["window_days"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["window_days"])

    try:
        v = challenger_metrics["oos_flag"]
        if v is not True:
            reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["oos_flag"])
    except Exception:
        reasons.append(THRESHOLD_FAIL_BY_METRIC_KEY["oos_flag"])

    return reasons


def compute_weighted_total_score(
    challenger_metrics: dict[str, Any],
    weights_renormed: dict[str, float],
    metric_bounds: dict[str, tuple[float, float]],
    champion_metrics: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    total = Decimal("0")
    weight_keys = sorted(weights_renormed.keys())
    champion_metrics = champion_metrics or {}
    for key in weight_keys:
        w = Decimal(str(weights_renormed[key]))
        w_float = float(w)
        if abs(w_float) <= 1e-12:
            continue
        if key not in challenger_metrics:
            if key in _REQUIRED_METRIC_KEYS:
                reasons.append(ERR_GATE_NORM_METRIC_MISSING)
                return 0.0, reasons
            continue
        bounds = metric_bounds.get(key)
        if bounds is None:
            if key in _REQUIRED_METRIC_KEYS:
                reasons.append(ERR_GATE_NORM_BOUNDS_INVALID)
                return 0.0, reasons
            continue
        if key == "total_fees_quote" and champion_metrics and "total_fees_quote" in champion_metrics:
            try:
                p_fees_val = _to_float_for_norm(champion_metrics["total_fees_quote"], "total_fees_quote")
                dynamic_hi = max(2.0 * float(p_fees_val), 1000.0)
                bounds = (0.0, dynamic_hi)
            except Exception:
                pass
        if key == "fees_per_trade" and champion_metrics and "fees_per_trade" in champion_metrics:
            try:
                p_fpt = _to_float_for_norm(champion_metrics["fees_per_trade"], "fees_per_trade")
                dynamic_hi = max(2.0 * float(p_fpt), 0.001)
                bounds = (0.0, dynamic_hi)
            except Exception:
                pass
        direction = metric_direction_table.get(key, Directionality.HIGHER_BETTER)
        norm_value, norm_reason = normalize_metric(key, challenger_metrics[key], bounds, direction)
        if norm_reason is not None:
            reasons.append(norm_reason)
            return 0.0, reasons
        contribution = w * Decimal(str(norm_value))
        total = total + contribution
    q = Decimal("1e-8")
    quantized = total.quantize(q, rounding=ROUND_HALF_EVEN)
    return float(quantized), reasons
