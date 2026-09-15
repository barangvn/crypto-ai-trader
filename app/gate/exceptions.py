from __future__ import annotations

from typing import Any


ERR_GATE_WEIGHT_SUM_INVALID = "WEIGHT_SUM_INVALID"
ERR_GATE_WEIGHT_OUT_OF_RANGE = "WEIGHT_OUT_OF_RANGE"
ERR_GATE_WEIGHT_MISSING_REQUIRED = "WEIGHT_MISSING_REQUIRED"
ERR_GATE_WEIGHT_UNKNOWN_KEY = "WEIGHT_UNKNOWN_KEY"
ERR_GATE_NORM_BOUNDS_INVALID = "NORM_BOUNDS_INVALID"
ERR_GATE_NORM_METRIC_MISSING = "NORM_METRIC_MISSING"
ERR_GATE_HARD_RETURN_NOT_POSITIVE = "HARD_RETURN_NOT_POSITIVE"
ERR_GATE_HARD_DRAWDOWN_WORSENED = "HARD_DRAWDOWN_WORSENED"
ERR_GATE_HARD_SHARPE_NEGATIVE = "HARD_SHARPE_NEGATIVE"
ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY = "HARD_PROFIT_FACTOR_SUBUNITY"
ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT = "HARD_TRADE_COUNT_INSUFFICIENT"
ERR_GATE_HARD_OOS_FLAG_FALSE = "HARD_OOS_FLAG_FALSE"
ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT = "HARD_DELTA_SIGN_INSUFFICIENT"
ERR_GATE_EVAL_STALE = "EVAL_STALE"
ERR_GATE_EVAL_INCOMPARABLE = "EVAL_INCOMPARABLE"
ERR_GATE_EVIDENCE_INTEGRITY_FAIL = "EVIDENCE_INTEGRITY_FAIL"
ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT = "EVIDENCE_DELTAS_INSUFFICIENT"
ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN = "WINNER_HINT_INCONCLUSIVE_RERUN"
ERR_GATE_THRESHOLDS_VERSION_MISMATCH = "THRESHOLDS_VERSION_MISMATCH"
ERR_GATE_WEIGHTS_VERSION_MISMATCH = "WEIGHTS_VERSION_MISMATCH"
ERR_GATE_MIN_APPROVALS_FAIL = "GATE_MIN_APPROVALS_FAIL"
ERR_GATE_MIN_TOTAL_SCORE_UNMET = "GATE_MIN_TOTAL_SCORE_UNMET"


THRESHOLD_FAIL_BY_METRIC_KEY = {
    "return_pct": "THRESHOLD_RETURN_PCT_FAIL",
    "max_drawdown_pct": "THRESHOLD_MAX_DRAWDOWN_PCT_FAIL",
    "sharpe_ratio": "THRESHOLD_SHARPE_RATIO_FAIL",
    "sortino_ratio": "THRESHOLD_SORTINO_RATIO_FAIL",
    "profit_factor": "THRESHOLD_PROFIT_FACTOR_FAIL",
    "total_fees_quote": "THRESHOLD_TOTAL_FEES_QUOTE_FAIL",
    "avg_slippage_bps": "THRESHOLD_AVG_SLIPPAGE_BPS_FAIL",
    "trade_count": "THRESHOLD_TRADE_COUNT_FAIL",
    "regime_coverage_count": "THRESHOLD_REGIME_COVERAGE_COUNT_FAIL",
    "window_days": "THRESHOLD_WINDOW_DAYS_FAIL",
    "oos_flag": "THRESHOLD_OOS_FLAG_FAIL",
}


GATE_REASON_CODES = (
    ERR_GATE_WEIGHT_SUM_INVALID,
    ERR_GATE_WEIGHT_OUT_OF_RANGE,
    ERR_GATE_WEIGHT_MISSING_REQUIRED,
    ERR_GATE_WEIGHT_UNKNOWN_KEY,
    ERR_GATE_NORM_BOUNDS_INVALID,
    ERR_GATE_NORM_METRIC_MISSING,
    ERR_GATE_HARD_RETURN_NOT_POSITIVE,
    ERR_GATE_HARD_DRAWDOWN_WORSENED,
    ERR_GATE_HARD_SHARPE_NEGATIVE,
    ERR_GATE_HARD_PROFIT_FACTOR_SUBUNITY,
    ERR_GATE_HARD_TRADE_COUNT_INSUFFICIENT,
    ERR_GATE_HARD_OOS_FLAG_FALSE,
    ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT,
    ERR_GATE_EVAL_STALE,
    ERR_GATE_EVAL_INCOMPARABLE,
    ERR_GATE_EVIDENCE_INTEGRITY_FAIL,
    ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT,
    ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN,
    ERR_GATE_THRESHOLDS_VERSION_MISMATCH,
    ERR_GATE_WEIGHTS_VERSION_MISMATCH,
    ERR_GATE_MIN_APPROVALS_FAIL,
    ERR_GATE_MIN_TOTAL_SCORE_UNMET,
    *THRESHOLD_FAIL_BY_METRIC_KEY.values(),
)


class GateValidationError(Exception):
    def __init__(
        self,
        reason_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(reason_code, str) or not reason_code:
            raise ValueError("GateValidationError.reason_code must be a non-empty str")
        if not isinstance(message, str) or not message:
            raise ValueError("GateValidationError.message must be a non-empty str")
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise ValueError("GateValidationError.details must be a dict")
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message
        self.details = details

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "message": self.message,
            "details": dict(sorted(self.details.items())),
        }


class GateInvariantError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise ValueError("GateInvariantError.reason must be a non-empty str")
        if not isinstance(message, str) or not message:
            raise ValueError("GateInvariantError.message must be a non-empty str")
        super().__init__(f"[{reason}] {message}")
        self.reason = reason
        self.message = message
