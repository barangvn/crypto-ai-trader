from __future__ import annotations

from typing import Any

from app.contracts.model import _REQUIRED_METRIC_KEYS
from app.gate.exceptions import (
    ERR_GATE_WEIGHT_MISSING_REQUIRED,
    ERR_GATE_WEIGHT_OUT_OF_RANGE,
    ERR_GATE_WEIGHT_SUM_INVALID,
    ERR_GATE_WEIGHT_UNKNOWN_KEY,
    GateValidationError,
)


WEIGHTS_VERSION_V1 = "promotion-gate-default-v1"

_OPTIONAL_EXTRA_KEYS = frozenset({"stability", "fees_per_trade"})
_REQUIRED_KEYS_SET = frozenset(_REQUIRED_METRIC_KEYS)


def default_weights_v1() -> dict[str, float]:
    w: dict[str, float] = {
        "return_pct": 0.22,
        "max_drawdown_pct": 0.20,
        "sharpe_ratio": 0.15,
        "sortino_ratio": 0.12,
        "profit_factor": 0.10,
        "total_fees_quote": 0.10,
        "avg_slippage_bps": 0.04,
        "trade_count": 0.03,
        "regime_coverage_count": 0.02,
        "window_days": 0.00,
        "oos_flag": 0.00,
        "stability": 0.015,
        "fees_per_trade": 0.005,
    }
    return w


def validate_weights_definition(weights: dict[str, Any]) -> dict[str, float]:
    if not isinstance(weights, dict):
        raise GateValidationError(
            ERR_GATE_WEIGHT_OUT_OF_RANGE,
            "weights must be a dict[str, float]",
            {"got_type": type(weights).__name__},
        )

    for key in _REQUIRED_METRIC_KEYS:
        if key not in weights:
            raise GateValidationError(
                ERR_GATE_WEIGHT_MISSING_REQUIRED,
                f"required weight key missing: {key}",
                {"missing_key": key, "required_keys": list(_REQUIRED_METRIC_KEYS)},
            )

    allowed_keys = _REQUIRED_KEYS_SET | _OPTIONAL_EXTRA_KEYS
    for key in weights.keys():
        if key not in allowed_keys:
            raise GateValidationError(
                ERR_GATE_WEIGHT_UNKNOWN_KEY,
                f"unknown weight key: {key}",
                {"unknown_key": key, "allowed_keys": sorted(allowed_keys)},
            )

    parsed: dict[str, float] = {}
    for key, value in weights.items():
        try:
            fv = float(value)
        except (TypeError, ValueError) as exc:
            raise GateValidationError(
                ERR_GATE_WEIGHT_OUT_OF_RANGE,
                f"weight {key!r} cannot be cast to float",
                {"key": key, "value": repr(value), "error": str(exc)},
            ) from exc
        if fv != fv or fv in (float("inf"), float("-inf")):
            raise GateValidationError(
                ERR_GATE_WEIGHT_OUT_OF_RANGE,
                f"weight {key!r} is NaN or infinite",
                {"key": key, "value": fv},
            )
        if fv < 0.0 or fv > 1.0:
            raise GateValidationError(
                ERR_GATE_WEIGHT_OUT_OF_RANGE,
                f"weight {key!r} out of [0, 1] range",
                {"key": key, "value": fv},
            )
        parsed[key] = fv

    total = sum(parsed.values())
    if not (0.99999999 <= total <= 1.00000001):
        raise GateValidationError(
            ERR_GATE_WEIGHT_SUM_INVALID,
            f"weight sum {total:.12f} not within ±1e-8 of 1.0",
            {"sum": total, "weights": dict(sorted(parsed.items()))},
        )

    return parsed


def renormalize_weights_if_needed(
    weights: dict[str, float],
    weights_version: str = WEIGHTS_VERSION_V1,
) -> dict[str, float]:
    if not isinstance(weights, dict) or not weights:
        raise GateValidationError(
            ERR_GATE_WEIGHT_SUM_INVALID,
            "cannot renormalize empty weights",
            {"weights_version": weights_version},
        )
    total = sum(weights.values())
    if total <= 0.0:
        raise GateValidationError(
            ERR_GATE_WEIGHT_SUM_INVALID,
            "weight sum is not positive for renormalization",
            {"sum": total, "weights_version": weights_version},
        )
    if abs(total - 1.0) <= 1e-12:
        return dict(weights)
    factor = 1.0 / total
    renormed = {k: float(v * factor) for k, v in weights.items()}
    re_sum = sum(renormed.values())
    if not (0.99999999 <= re_sum <= 1.00000001):
        raise GateValidationError(
            ERR_GATE_WEIGHT_SUM_INVALID,
            f"renormalized weight sum {re_sum:.12f} invalid",
            {"sum_before": total, "sum_after": re_sum, "weights_version": weights_version},
        )
    return renormed
