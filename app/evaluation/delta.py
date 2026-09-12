"""Metric direction table, MetricDelta dataclass, rounding, canonical ordering.

Rules:
- 11 required keys from S-CON-02C _REQUIRED_METRIC_KEYS (exact reuse, no new metric)
- stability: optional extra (when present → HigherBetter; when absent → ignore, not MISSING)
- Numeric rounding matches S-BKT-03: Decimal q=1e-8 ROUND_HALF_EVEN, float round(8)
- NaN / infinity → fail-closed (ERR_NAN_NUMERIC)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from enum import StrEnum
from typing import Any

from app.contracts.model import _REQUIRED_METRIC_KEYS

from app.evaluation.exceptions import (
    CompareValidationError,
    ERR_DRAWDOWN_OUT_OF_RANGE,
    ERR_INVALID_ROUNDING_PRECISION,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_MISSING_METRIC,
    ERR_NAN_NUMERIC,
    ERR_NEGATIVE_TRADE_COUNT,
    ERR_UNKNOWN_METRIC_KEY,
)


DIRECTION_HIGHER_BETTER = "higher_better"
DIRECTION_LOWER_BETTER = "lower_better"
DIRECTION_NEUTRAL_MATCH = "neutral_match"


class Directionality(StrEnum):
    """3-valued direction per metric."""

    HIGHER_BETTER = DIRECTION_HIGHER_BETTER
    LOWER_BETTER = DIRECTION_LOWER_BETTER
    NEUTRAL_MATCH = DIRECTION_NEUTRAL_MATCH


ROUNDING_DECIMAL_Q = Decimal("1e-8")
ROUNDING_FLOAT_DP = 8


DECIMAL_KEYS = ("return_pct", "total_fees_quote")
FLOAT_KEYS = (
    "max_drawdown_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "profit_factor",
    "avg_slippage_bps",
)
INT_NONNEG_KEYS = ("trade_count", "regime_coverage_count", "window_days")
BOOL_KEYS = ("oos_flag",)


metric_type_table: dict[str, str] = {}
for k in DECIMAL_KEYS:
    metric_type_table[k] = "Decimal"
for k in FLOAT_KEYS:
    metric_type_table[k] = "float"
for k in INT_NONNEG_KEYS:
    metric_type_table[k] = "int"
for k in BOOL_KEYS:
    metric_type_table[k] = "bool"


metric_direction_table: dict[str, Directionality] = {
    "return_pct": Directionality.HIGHER_BETTER,
    "sharpe_ratio": Directionality.HIGHER_BETTER,
    "sortino_ratio": Directionality.HIGHER_BETTER,
    "profit_factor": Directionality.HIGHER_BETTER,
    "trade_count": Directionality.HIGHER_BETTER,
    "regime_coverage_count": Directionality.HIGHER_BETTER,
    "max_drawdown_pct": Directionality.LOWER_BETTER,
    "total_fees_quote": Directionality.LOWER_BETTER,
    "avg_slippage_bps": Directionality.LOWER_BETTER,
    "window_days": Directionality.NEUTRAL_MATCH,
    "oos_flag": Directionality.NEUTRAL_MATCH,
    # optional extras — FR-038 mentions stability (S-CON-02C 11-key required set içinde değil)
    "stability": Directionality.HIGHER_BETTER,
    "fees_per_trade": Directionality.LOWER_BETTER,
}

CRITICAL_DELTA_KEYS_ORDERED: tuple[str, ...] = (
    "return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "profit_factor",
    "total_fees_quote",
)


def _validate_required_present(metrics: dict[str, Any], metric_set_label: str) -> None:
    missing = [k for k in _REQUIRED_METRIC_KEYS if k not in metrics]
    if missing:
        raise CompareValidationError(
            ERR_MISSING_METRIC,
            f"{metric_set_label} missing required metric keys",
            {"missing": sorted(missing), "required": sorted(list(_REQUIRED_METRIC_KEYS))},
        )
    for k in list(metrics.keys()):
        if k in _REQUIRED_METRIC_KEYS:
            continue
        # optional extras allowed; unknown key not starting with "ext_" / "stability" / "fees_per_trade" / "aggregate_" / "fold_" / "regime_" → unknown reject
        if k in {"stability", "fees_per_trade"}:
            continue
        if k.startswith(("aggregate_", "fold_", "regime_", "per_", "group_")):
            continue
        # anything else → unknown reject (conservative fail-closed vs silent garbage metric)
        raise CompareValidationError(
            ERR_UNKNOWN_METRIC_KEY,
            f"{metric_set_label} unknown metric key; known required={sorted(list(_REQUIRED_METRIC_KEYS))} + opt extras=stability/fees_per_trade + fold_*/regime_*/aggregate_*",
            {"unknown_key": k, "keys": sorted(metrics.keys())},
        )


def _validate_types_and_ranges(metrics: dict[str, Any], metric_set_label: str) -> None:
    # Decimal keys (strict Decimal; bool forbidden because bool is subclass of int)
    for k in DECIMAL_KEYS:
        v = metrics[k]
        if isinstance(v, bool) or not isinstance(v, Decimal):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{metric_set_label}[{k!r}] must be Decimal (monetary), got {type(v).__name__}",
                {"metric_key": k, "type": type(v).__name__},
            )
    for k in FLOAT_KEYS:
        v = metrics[k]
        if isinstance(v, bool) or not isinstance(v, float):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{metric_set_label}[{k!r}] must be float, got {type(v).__name__}",
                {"metric_key": k, "type": type(v).__name__},
            )
        if math.isnan(v) or math.isinf(v):
            raise CompareValidationError(
                ERR_NAN_NUMERIC,
                f"{metric_set_label}[{k!r}] invalid numeric (nan/inf)",
                {"metric_key": k, "value": str(v)},
            )
    dd = metrics["max_drawdown_pct"]
    if dd < 0.0 or dd > 1.0:
        raise CompareValidationError(
            ERR_DRAWDOWN_OUT_OF_RANGE,
            f"{metric_set_label}.max_drawdown_pct out of [0,1]",
            {"value": dd},
        )
    for k in INT_NONNEG_KEYS:
        v = metrics[k]
        if isinstance(v, bool) or not isinstance(v, int):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{metric_set_label}[{k!r}] must be int, got {type(v).__name__}",
                {"metric_key": k, "type": type(v).__name__},
            )
        if k == "trade_count" and v < 0:
            raise CompareValidationError(
                ERR_NEGATIVE_TRADE_COUNT,
                f"{metric_set_label}.trade_count negative",
                {"value": v},
            )
        if v < 0:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{metric_set_label}[{k!r}] must be int >= 0",
                {"metric_key": k, "value": v},
            )
    for k in BOOL_KEYS:
        v = metrics[k]
        if not isinstance(v, bool):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{metric_set_label}[{k!r}] must be bool, got {type(v).__name__}",
                {"metric_key": k, "type": type(v).__name__},
            )


def validate_metrics_strict(metrics: Any, metric_set_label: str) -> dict[str, Any]:
    """Strict 11-required + typed + ranges (conservative fail-closed)."""
    if not isinstance(metrics, dict):
        raise CompareValidationError(
            ERR_METRIC_TYPE_MISMATCH,
            f"{metric_set_label} must be dict",
            {"type": type(metrics).__name__},
        )
    _validate_required_present(metrics, metric_set_label)
    _validate_types_and_ranges(metrics, metric_set_label)
    return metrics


def round_metric_value(value: Any, metric_key: str) -> Any:
    """Apply deterministic rounding per metric type.

    Decimal: quantize ROUND_HALF_EVEN 1e-8
    Float: round 8 dp
    Int: exact (no round)
    Bool: exact
    """
    if metric_key in DECIMAL_KEYS:
        if not isinstance(value, Decimal) or isinstance(value, bool):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"round_metric_value[{metric_key!r}] expects Decimal",
                {"type": type(value).__name__},
            )
        if value.is_nan() or not value.is_finite():
            raise CompareValidationError(
                ERR_NAN_NUMERIC,
                f"round_metric_value[{metric_key!r}] invalid numeric (nan/inf)",
                {"value": str(value)},
            )
        try:
            return value.quantize(ROUNDING_DECIMAL_Q, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, ValueError) as exc:
            raise CompareValidationError(
                ERR_INVALID_ROUNDING_PRECISION,
                f"round_metric_value[{metric_key!r}] decimal quantize invalid",
                {"value": str(value)},
            ) from exc
    if metric_key in FLOAT_KEYS or (metric_key == "stability" and isinstance(value, float)):
        if not isinstance(value, float) or isinstance(value, bool):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"round_metric_value[{metric_key!r}] expects float",
                {"type": type(value).__name__},
            )
        if math.isnan(value) or math.isinf(value):
            raise CompareValidationError(
                ERR_NAN_NUMERIC,
                f"round_metric_value[{metric_key!r}] invalid numeric",
                {"value": str(value)},
            )
        if metric_key == "max_drawdown_pct":
            if value < 0.0 or value > 1.0:
                raise CompareValidationError(
                    ERR_DRAWDOWN_OUT_OF_RANGE,
                    f"round_metric_value.max_drawdown_pct out of [0,1]",
                    {"value": value},
                )
        return round(value, ROUNDING_FLOAT_DP)
    if metric_key in INT_NONNEG_KEYS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"round_metric_value[{metric_key!r}] expects int",
                {"type": type(value).__name__},
            )
        if value < 0:
            if metric_key == "trade_count":
                raise CompareValidationError(
                    ERR_NEGATIVE_TRADE_COUNT,
                    f"round_metric_value[{metric_key!r}] negative",
                    {"value": value},
                )
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"round_metric_value[{metric_key!r}] must be int >= 0",
                {"metric_key": metric_key, "value": value},
            )
        return value
    if metric_key in BOOL_KEYS:
        if not isinstance(value, bool):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"round_metric_value[{metric_key!r}] expects bool",
                {"type": type(value).__name__},
            )
        return value
    # Optional extras: handle numeric best-effort (fail-closed on non-numeric invalid)
    if isinstance(value, Decimal) and not isinstance(value, bool):
        try:
            return value.quantize(ROUNDING_DECIMAL_Q, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, ValueError) as exc:
            raise CompareValidationError(
                ERR_INVALID_ROUNDING_PRECISION,
                f"round_metric_value[{metric_key!r}] decimal extra quantize invalid",
                {"value": str(value)},
            ) from exc
    if isinstance(value, float) and not isinstance(value, bool):
        if math.isnan(value) or math.isinf(value):
            raise CompareValidationError(
                ERR_NAN_NUMERIC,
                f"round_metric_value[{metric_key!r}] invalid numeric",
                {"value": str(value)},
            )
        return round(value, ROUNDING_FLOAT_DP)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, bool):
        return value
    # Unsupported type
    raise CompareValidationError(
        ERR_METRIC_TYPE_MISMATCH,
        f"round_metric_value[{metric_key!r}] unsupported type",
        {"type": type(value).__name__},
    )


def _rounding_precision_for(metric_key: str) -> str:
    if metric_key in DECIMAL_KEYS:
        return "Decimal(1e-8)"
    if metric_key in FLOAT_KEYS or metric_key == "stability":
        return "Float(8dp)"
    if metric_key in INT_NONNEG_KEYS:
        return "IntExact"
    if metric_key in BOOL_KEYS:
        return "BoolExact"
    return "AutoInferred"


@dataclass
class MetricDelta:
    """Per-metric delta: champion vs challenger.

    directionality meaning (stored as string for JSON-friendly serialization):
      HIGHER_BETTER: delta = challenger - champion → positive = challenger better
      LOWER_BETTER:  delta = champion - challenger → positive = challenger better
      NEUTRAL_MATCH: delta=0 on match else ERR (oos_flag bool)
    winner_hint per-metric: "challenger" | "champion" | "tie" (non-binding)
    """

    metric_key: str
    champion_value: Any
    challenger_value: Any
    delta: Any
    directionality: str  # string: higher_better / lower_better / neutral_match (JSON-friendly)
    winner_hint: str = "tie"
    metric_version: str = "1.0.0-smdl02"
    rounding_precision: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.metric_key, str) or not self.metric_key:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                "MetricDelta.metric_key required",
                {},
            )
        # Accept Directionality enum or string; normalize to string
        if isinstance(self.directionality, Directionality):
            self.directionality = self.directionality.value
        if not isinstance(self.directionality, str) or self.directionality not in {DIRECTION_HIGHER_BETTER, DIRECTION_LOWER_BETTER, DIRECTION_NEUTRAL_MATCH}:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                "MetricDelta.directionality must be higher_better/lower_better/neutral_match",
                {"value": self.directionality},
            )
        if self.winner_hint not in {"challenger", "champion", "tie"}:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                "MetricDelta.winner_hint must be challenger/champion/tie",
                {"value": self.winner_hint},
            )
        if not self.rounding_precision:
            self.rounding_precision = _rounding_precision_for(self.metric_key)


def _hint_from_delta(delta: Any, direction: Directionality | str) -> str:
    # normalize str to enum for comparison
    if isinstance(direction, str):
        try:
            direction = Directionality(direction)
        except ValueError:
            return "tie"
    if direction == Directionality.NEUTRAL_MATCH:
        return "tie"
    try:
        if delta > 0:
            return "challenger"
        if delta < 0:
            return "champion"
        return "tie"
    except TypeError:
        return "tie"


def compare_metric_delta(metric_key: str, champion_metrics: dict[str, Any], challenger_metrics: dict[str, Any]) -> MetricDelta:
    """Compute a single MetricDelta. Strict typed + rounded."""
    if metric_key not in champion_metrics or metric_key not in challenger_metrics:
        raise CompareValidationError(
            ERR_MISSING_METRIC,
            f"compare_metric_delta required metric {metric_key!r} missing in champion/challenger",
            {"metric_key": metric_key, "champion_has": metric_key in champion_metrics, "challenger_has": metric_key in challenger_metrics},
        )
    _is_known = (
        metric_key in _REQUIRED_METRIC_KEYS
        or metric_key in metric_direction_table
        or metric_key.startswith(("aggregate_", "fold_", "regime_", "per_", "group_", "ext_"))
    )
    if not _is_known:
        raise CompareValidationError(
            ERR_UNKNOWN_METRIC_KEY,
            f"compare_metric_delta unknown metric key {metric_key!r}",
            {"metric_key": metric_key, "known_required": sorted(list(_REQUIRED_METRIC_KEYS)), "known_opt": sorted(metric_direction_table.keys())},
        )
    direction = metric_direction_table.get(metric_key, Directionality.HIGHER_BETTER)
    c_val = round_metric_value(champion_metrics[metric_key], metric_key)
    t_val = round_metric_value(challenger_metrics[metric_key], metric_key)

    if direction == Directionality.NEUTRAL_MATCH:
        # bool/int match → delta 0; mismatch → reject fail-closed (incomparable neutral)
        if c_val != t_val:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"metric {metric_key!r} neutral match required; champion={c_val!r} challenger={t_val!r} mismatch (incomparable)",
                {"metric_key": metric_key, "champion": c_val, "challenger": t_val},
            )
        delta: Any = 0
        return MetricDelta(
            metric_key=metric_key,
            champion_value=c_val,
            challenger_value=t_val,
            delta=delta,
            directionality=direction,
            winner_hint="tie",
        )
    if direction == Directionality.HIGHER_BETTER:
        if isinstance(c_val, Decimal) and isinstance(t_val, Decimal):
            delta = (t_val - c_val).quantize(ROUNDING_DECIMAL_Q, rounding=ROUND_HALF_EVEN)
        elif isinstance(c_val, float) and isinstance(t_val, float):
            delta = round(t_val - c_val, ROUNDING_FLOAT_DP)
        elif isinstance(c_val, int) and isinstance(t_val, int):
            delta = t_val - c_val
        else:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"metric {metric_key!r} direction HIGHER_BETTER but type mismatch (champion={type(c_val).__name__}, challenger={type(t_val).__name__})",
                {"metric_key": metric_key, "champion_type": type(c_val).__name__, "challenger_type": type(t_val).__name__},
            )
        return MetricDelta(metric_key, c_val, t_val, delta, direction, winner_hint=_hint_from_delta(delta, direction))
    # LOWER_BETTER
    if isinstance(c_val, Decimal) and isinstance(t_val, Decimal):
        delta = (c_val - t_val).quantize(ROUNDING_DECIMAL_Q, rounding=ROUND_HALF_EVEN)
    elif isinstance(c_val, float) and isinstance(t_val, float):
        delta = round(c_val - t_val, ROUNDING_FLOAT_DP)
    elif isinstance(c_val, int) and isinstance(t_val, int):
        delta = c_val - t_val
    else:
        raise CompareValidationError(
            ERR_METRIC_TYPE_MISMATCH,
            f"metric {metric_key!r} direction LOWER_BETTER but type mismatch",
            {"metric_key": metric_key, "champion_type": type(c_val).__name__, "challenger_type": type(t_val).__name__},
        )
    return MetricDelta(metric_key, c_val, t_val, delta, direction, winner_hint=_hint_from_delta(delta, direction))


def sorted_metric_keys(metrics: dict[str, Any]) -> list[str]:
    """Canonical metric order:
    1. CRITICAL_DELTA_KEYS_ORDERED (if present) – exact order preserved
    2. remaining required keys (from _REQUIRED_METRIC_KEYS) in order of appearance in _REQUIRED_METRIC_KEYS
    3. extras sorted ASC
    """
    result: list[str] = []
    seen: set[str] = set()
    for k in CRITICAL_DELTA_KEYS_ORDERED:
        if k in metrics and k not in seen:
            result.append(k)
            seen.add(k)
    for k in _REQUIRED_METRIC_KEYS:
        if k in metrics and k not in seen:
            result.append(k)
            seen.add(k)
    extras = sorted([k for k in metrics.keys() if k not in seen])
    result.extend(extras)
    return result
