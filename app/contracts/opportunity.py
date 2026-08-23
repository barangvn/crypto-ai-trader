from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.contracts.canonical import QualityFlags
from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.types import (
    Instant,
    ULID,
    Symbol,
    validate_instant,
    validate_symbol_canonical,
)


_ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")
_POLICY_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+/:@]+$")
_MODEL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_ulidish(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"OpportunityScore.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"OpportunityScore.{field_name} invalid format: {value!r}"
        )


def _validate_float_unit_range(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float):
        raise ContractSchemaError(
            f"OpportunityScore.{field_name} must be float in [0, 1], got {type(value).__name__}"
        )
    if value < 0.0 or value > 1.0:
        raise ContractSchemaError(
            f"OpportunityScore.{field_name} out of [0, 1] range: {value!r}"
        )
    return value


def _validate_score_components(
    value: Any,
) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ContractSchemaError(
            "OpportunityScore.score_components must be dict[str, float]"
        )
    normalised: dict[str, float] = {}
    for k in sorted(value.keys()):
        if not isinstance(k, str) or not k:
            raise ContractSchemaError(
                "OpportunityScore.score_components keys must be non-empty str"
            )
        v = value[k]
        if isinstance(v, bool) or not isinstance(v, float):
            raise ContractSchemaError(
                f"OpportunityScore.score_components[{k!r}] must be float, got {type(v).__name__}"
            )
        normalised[k] = v
    return normalised


def _validate_reject_reasons(value: Any) -> list[str]:
    if value is None or not isinstance(value, list):
        raise ContractSchemaError(
            "OpportunityScore.reject_reasons must be list[str] (None forbidden)"
        )
    for idx, r in enumerate(value):
        if not isinstance(r, str):
            raise ContractSchemaError(
                f"OpportunityScore.reject_reasons[{idx}] must be str"
            )
    return value


@dataclass
class OpportunityScore:
    """CONTRACTS.md §3.10 + FR-019/020 explainable cost-aware opportunity score.

    7-halka AD-17 zincirinin 2. halkası: StrategySignal → OpportunityScore → RiskDecision
    """

    score_id: ULID
    score_total: float
    confidence: float
    actionable: bool
    reject_reasons: list[str]
    score_components: dict[str, float]
    expected_edge_bps: float
    expected_cost_bps: float
    symbol_ref: Symbol
    regime_ref: str
    strategy_ref: str
    policy_version: str
    correlation_id: ULID
    causation_id: ULID
    created_ts: Instant
    model_version_ref: str | None = None
    quality_flags: QualityFlags | None = None
    expected_hold_bars: int | None = None
    explainability_note: str | None = None

    def __post_init__(self) -> None:
        _validate_ulidish(self.score_id, "score_id")
        self.score_total = _validate_float_unit_range(self.score_total, "score_total")
        self.confidence = _validate_float_unit_range(self.confidence, "confidence")
        if not isinstance(self.actionable, bool):
            raise ContractSchemaError(
                f"OpportunityScore.actionable must be bool, got {type(self.actionable).__name__}"
            )
        self.reject_reasons = _validate_reject_reasons(self.reject_reasons)
        self.score_components = _validate_score_components(self.score_components)
        if isinstance(self.expected_edge_bps, bool) or not isinstance(self.expected_edge_bps, float):
            raise ContractSchemaError(
                "OpportunityScore.expected_edge_bps must be float (bps; may be negative)"
            )
        if isinstance(self.expected_cost_bps, bool) or not isinstance(self.expected_cost_bps, float):
            raise ContractSchemaError(
                "OpportunityScore.expected_cost_bps must be float (bps; non-monetary cost scoring)"
            )
        if not validate_symbol_canonical(self.symbol_ref):
            raise ContractSchemaError(
                f"OpportunityScore.symbol_ref not canonical: {self.symbol_ref!r}"
            )
        if not isinstance(self.regime_ref, str) or not self.regime_ref:
            raise ContractSchemaError(
                "OpportunityScore.regime_ref must be non-empty str"
            )
        if not isinstance(self.strategy_ref, str) or not self.strategy_ref:
            raise ContractSchemaError(
                "OpportunityScore.strategy_ref must be non-empty str"
            )
        if not isinstance(self.policy_version, str) or not _POLICY_VERSION_RE.match(self.policy_version):
            raise ContractSchemaError(
                f"OpportunityScore.policy_version invalid: {self.policy_version!r}"
            )
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        if not validate_instant(self.created_ts):
            raise ContractSchemaError(
                f"OpportunityScore.created_ts invalid Instant format: {self.created_ts!r}"
            )
        if self.model_version_ref is not None and (
            not isinstance(self.model_version_ref, str) or not self.model_version_ref
        ):
            raise ContractSchemaError(
                "OpportunityScore.model_version_ref must be non-empty str|None"
            )
        if self.quality_flags is not None and not isinstance(self.quality_flags, QualityFlags):
            raise ContractSchemaError(
                "OpportunityScore.quality_flags must be QualityFlags|None"
            )
        if self.expected_hold_bars is not None:
            if isinstance(self.expected_hold_bars, bool) or not isinstance(self.expected_hold_bars, int):
                raise ContractSchemaError(
                    "OpportunityScore.expected_hold_bars must be int|None"
                )
            if self.expected_hold_bars < 0:
                raise ContractSchemaError(
                    "OpportunityScore.expected_hold_bars must be >= 0"
                )
        if self.explainability_note is not None and not isinstance(self.explainability_note, str):
            raise ContractSchemaError(
                "OpportunityScore.explainability_note must be str|None"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
