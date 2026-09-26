from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._validation import ContractValidationError, QualityReason, _require


@dataclass(frozen=True)
class QualityFlags:
    stale: bool = False
    missing: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    reasons: tuple[QualityReason, ...] = ()

    def __post_init__(self) -> None:
        for flag in (
            "stale",
            "missing",
            "duplicate",
            "out_of_order",
            "invalid",
            "quarantined",
            "degraded",
        ):
            val = object.__getattribute__(self, flag)
            _require(isinstance(val, bool), f"quality_flags.{flag}", "must be bool")

        reasons = object.__getattribute__(self, "reasons")
        if isinstance(reasons, list):
            object.__setattr__(self, "reasons", tuple(reasons))
            reasons = object.__getattribute__(self, "reasons")
        _require(
            isinstance(reasons, tuple),
            "quality_flags.reasons",
            "must be tuple or list of QualityReason",
        )
        for i, r in enumerate(reasons):
            _require(
                isinstance(r, QualityReason),
                f"quality_flags.reasons[{i}]",
                "must be QualityReason",
            )

        other_true = any(
            (
                object.__getattribute__(self, "stale"),
                object.__getattribute__(self, "missing"),
                object.__getattribute__(self, "duplicate"),
                object.__getattribute__(self, "out_of_order"),
                object.__getattribute__(self, "invalid"),
                object.__getattribute__(self, "quarantined"),
            )
        )
        degraded_set = object.__getattribute__(self, "degraded")
        if degraded_set and (not other_true):
            raise ContractValidationError(
                "[quality_flags.degraded] invariant violation: degraded=True requires at least one "
                "other flag (stale/missing/duplicate/out_of_order/invalid/quarantined) also True. "
                "Fail-closed FC-06."
            )
        if other_true and (not degraded_set):
            object.__setattr__(self, "degraded", True)


__all__ = ["QualityFlags"]
