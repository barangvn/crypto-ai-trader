"""app.evaluation — S-MDL-02 Model Evaluation Compare + Score Delta.

Public surface exported in __all__. stdlib-only. No registry write.
"""

from app.evaluation.exceptions import (
    CompareValidationError,
    ERR_ARTIFACT_CORRUPT,
    ERR_ARTIFACT_NOT_FOUND,
    ERR_DRAWDOWN_OUT_OF_RANGE,
    ERR_EMPTY_ARTIFACT_URI,
    ERR_EMPTY_CHALLENGER_MODEL,
    ERR_EMPTY_CHAMPION_MODEL,
    ERR_INCOMPARABLE_COMPATIBILITY,
    ERR_INCOMPARABLE_COST,
    ERR_INCOMPARABLE_DATASET,
    ERR_INCOMPARABLE_FOLD_COUNT,
    ERR_INCOMPARABLE_REGIME_GROUPS,
    ERR_INCOMPARABLE_THRESHOLDS,
    ERR_INCOMPARABLE_UNIVERSE,
    ERR_INCOMPARABLE_WINDOW,
    ERR_INCOMPATIBLE_STATUS_TRANSITION,
    ERR_INTEGRITY_SHA_MISMATCH,
    ERR_INVALID_ROUNDING_PRECISION,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_MISSING_METRIC,
    ERR_MODEL_NOT_FOUND,
    ERR_NAN_NUMERIC,
    ERR_NEGATIVE_TRADE_COUNT,
    ERR_NOT_CHALLENGER_STATUS,
    ERR_NOT_CHAMPION_STATUS,
    ERR_SAME_MODEL_SAME_VERSION,
    ERR_UNKNOWN_METRIC_KEY,
    ERR_VERSION_MISMATCH,
    REASON_CODES,
)
from app.evaluation.delta import (
    CRITICAL_DELTA_KEYS_ORDERED,
    DIRECTION_HIGHER_BETTER,
    DIRECTION_LOWER_BETTER,
    DIRECTION_NEUTRAL_MATCH,
    Directionality,
    MetricDelta,
    compare_metric_delta,
    metric_direction_table,
    metric_type_table,
    round_metric_value,
    sorted_metric_keys,
    validate_metrics_strict,
)
from app.evaluation.comparability import (
    ComparabilityResult,
    build_comparability_invariants,
    check_comparability,
)
from app.evaluation.contract_payload import (
    ChampionChallengerEvaluationPayload,
    build_cce_payload,
)
from app.evaluation.engine import (
    CompareEngine,
    CompareResult,
)

__all__ = [
    # exceptions
    "CompareValidationError",
    "REASON_CODES",
    "ERR_MODEL_NOT_FOUND",
    "ERR_VERSION_MISMATCH",
    "ERR_NOT_CHAMPION_STATUS",
    "ERR_NOT_CHALLENGER_STATUS",
    "ERR_SAME_MODEL_SAME_VERSION",
    "ERR_EMPTY_CHAMPION_MODEL",
    "ERR_EMPTY_CHALLENGER_MODEL",
    "ERR_ARTIFACT_NOT_FOUND",
    "ERR_EMPTY_ARTIFACT_URI",
    "ERR_ARTIFACT_CORRUPT",
    "ERR_INTEGRITY_SHA_MISMATCH",
    "ERR_MISSING_METRIC",
    "ERR_UNKNOWN_METRIC_KEY",
    "ERR_METRIC_TYPE_MISMATCH",
    "ERR_NAN_NUMERIC",
    "ERR_NEGATIVE_TRADE_COUNT",
    "ERR_DRAWDOWN_OUT_OF_RANGE",
    "ERR_INVALID_ROUNDING_PRECISION",
    "ERR_INCOMPARABLE_WINDOW",
    "ERR_INCOMPARABLE_DATASET",
    "ERR_INCOMPARABLE_COST",
    "ERR_INCOMPARABLE_UNIVERSE",
    "ERR_INCOMPARABLE_COMPATIBILITY",
    "ERR_INCOMPARABLE_THRESHOLDS",
    "ERR_INCOMPARABLE_FOLD_COUNT",
    "ERR_INCOMPARABLE_REGIME_GROUPS",
    "ERR_INCOMPATIBLE_STATUS_TRANSITION",
    # delta
    "MetricDelta",
    "Directionality",
    "DIRECTION_HIGHER_BETTER",
    "DIRECTION_LOWER_BETTER",
    "DIRECTION_NEUTRAL_MATCH",
    "CRITICAL_DELTA_KEYS_ORDERED",
    "metric_direction_table",
    "metric_type_table",
    "round_metric_value",
    "compare_metric_delta",
    "validate_metrics_strict",
    "sorted_metric_keys",
    # comparability
    "ComparabilityResult",
    "check_comparability",
    "build_comparability_invariants",
    # contract payload
    "ChampionChallengerEvaluationPayload",
    "build_cce_payload",
    # engine
    "CompareEngine",
    "CompareResult",
]
