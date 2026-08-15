from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.types import Instant, validate_instant


class MarketRegimeState(StrEnum):
    """AD-8: the six permitted market regime states.

    NOTE: no "short" or otherwise ambiguous extra values allowed here.
    Adding new regimes requires a CONTRACT_VERSION bump and CONTRACTS.md update.
    """

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION_UNCERTAIN = "transition_uncertain"


REGIME_KEYS: frozenset[str] = frozenset(s.value for s in MarketRegimeState)

_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")


@dataclass
class TimeRangeSpec:
    """AD-8: inclusive time range [start, end] used by MarketRegime.lookback_ts.

    ISO-8601 Instant strings are lexicographically comparable so string compare
    is sufficient for ordering.
    """

    start: Instant
    end: Instant

    def __post_init__(self) -> None:
        if not validate_instant(self.start):
            raise ContractSchemaError(
                f"TimeRangeSpec.start invalid Instant format: {self.start!r}"
            )
        if not validate_instant(self.end):
            raise ContractSchemaError(
                f"TimeRangeSpec.end invalid Instant format: {self.end!r}"
            )
        if self.start > self.end:
            raise ContractSchemaError(
                f"TimeRangeSpec.start must be <= end: {self.start!r} > {self.end!r}"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


def _validate_version(s: Any, field_name: str) -> None:
    if not isinstance(s, str):
        raise ContractSchemaError(
            f"MarketRegime.{field_name} must be str, got {type(s).__name__}"
        )
    if not _VERSION_RE.match(s):
        raise ContractSchemaError(
            f"MarketRegime.{field_name} invalid chars: {s!r}"
        )
    if len(s) == 0:
        raise ContractSchemaError(f"MarketRegime.{field_name} cannot be empty")


def _validate_confidence_in_0_1(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, float):
        raise ContractSchemaError(
            f"MarketRegime.{field_name} must be float in [0, 1], got {type(value).__name__}"
        )
    if value < 0.0 or value > 1.0:
        raise ContractSchemaError(
            f"MarketRegime.{field_name} out of [0, 1] range: {value!r}"
        )


def _validate_scores_dict(scores: Any) -> dict[str, float]:
    """Validate regime scores dict: exactly 6 keys, each value float in [0, 1]."""
    if not isinstance(scores, dict):
        raise ContractSchemaError(
            f"MarketRegime.scores must be dict, got {type(scores).__name__}"
        )
    keys = set(scores.keys())
    missing = sorted(REGIME_KEYS - keys)
    extra = sorted(keys - REGIME_KEYS)
    if missing:
        raise ContractSchemaError(
            f"MarketRegime.scores missing regime keys: {missing}"
        )
    if extra:
        raise ContractSchemaError(
            f"MarketRegime.scores has unknown extra keys: {extra}"
        )
    normalised: dict[str, float] = {}
    for key in sorted(scores.keys()):
        value = scores[key]
        if isinstance(value, bool) or not isinstance(value, float):
            raise ContractSchemaError(
                f"MarketRegime.scores[{key!r}] must be float [0,1], got {type(value).__name__}"
            )
        if value < 0.0 or value > 1.0:
            raise ContractSchemaError(
                f"MarketRegime.scores[{key!r}] out of [0, 1] range: {value!r}"
            )
        normalised[key] = value
    return normalised


@dataclass
class MarketRegime:
    """AD-8 MarketRegime contract.

    Canonical schema, CONTRACTS.md §3.6:
      - timeframe
      - regime   (MarketRegimeState)
      - confidence float [0, 1]
      - scores   {6 regime keys} each float [0, 1]  (sum is NOT required to be 1)
      - detector_version, feature_version
      - lookback_ts (TimeRangeSpec)
    """

    timeframe: str
    regime: MarketRegimeState
    confidence: float
    scores: dict[str, float]
    detector_version: str
    feature_version: str
    lookback_ts: TimeRangeSpec

    def __post_init__(self) -> None:
        # timeframe
        if not isinstance(self.timeframe, str) or not self.timeframe:
            raise ContractSchemaError(
                f"MarketRegime.timeframe must be non-empty str, got {self.timeframe!r}"
            )
        # regime enum
        if not isinstance(self.regime, MarketRegimeState):
            # Tolerate plain string that matches one of the enum values so envelope deserialisation is ergonomic
            if isinstance(self.regime, str) and self.regime in REGIME_KEYS:
                self.regime = MarketRegimeState(self.regime)  # type: ignore[assignment]
            else:
                raise ContractSchemaError(
                    f"MarketRegime.regime must be MarketRegimeState (one of {sorted(REGIME_KEYS)}), got {self.regime!r}"
                )
        # confidence [0,1]
        _validate_confidence_in_0_1(self.confidence, "confidence")
        # scores (exactly 6 keys, each float [0,1])
        self.scores = _validate_scores_dict(self.scores)
        # version strings
        _validate_version(self.detector_version, "detector_version")
        _validate_version(self.feature_version, "feature_version")
        # lookback_ts
        if not isinstance(self.lookback_ts, TimeRangeSpec):
            raise ContractSchemaError(
                f"MarketRegime.lookback_ts must be TimeRangeSpec, got {type(self.lookback_ts).__name__}"
            )

    # ---- serialisation / determinism ----------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
