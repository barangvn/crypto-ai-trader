from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.types import (
    Instant,
    ULID,
    validate_instant,
    validate_symbol_canonical,
)


_ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")


def _validate_ulidish(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"RiskDecision.{field_name} invalid format: {value!r}"
        )


# ---------------------------------------------------------------------------
# 3.11 RiskDecision nested enums + typed helpers
# ---------------------------------------------------------------------------


class RiskDecisionResult(StrEnum):
    """AD-11 final gate — tam 2 değer: approved / rejected. Başka değer YOK."""

    APPROVED = "approved"
    REJECTED = "rejected"


def _validate_decimal_nonneg(value: Any, field_name: str) -> Decimal:
    """Return normalised Decimal >= 0 or raise ContractSchemaError."""
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be Decimal >= 0, got {type(value).__name__}"
        )
    if value < 0:
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be >= 0, got {value!r}"
        )
    return value


def _validate_float_range(value: Any, field_name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, float):
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be float in [{lo}, {hi}], got {type(value).__name__}"
        )
    if value < lo or value > hi:
        raise ContractSchemaError(
            f"RiskDecision.{field_name} out of [{lo}, {hi}] range: {value!r}"
        )
    return value


def _validate_int_nonneg(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be int >= 0, got {type(value).__name__}"
        )
    if value < 0:
        raise ContractSchemaError(
            f"RiskDecision.{field_name} must be >= 0, got {value!r}"
        )
    return value


@dataclass
class PositionSizingSpec:
    """RiskDecision.position_sizing nested typed spec — v1 sizing contract şeması."""

    base_qty: Decimal | None
    quote_qty: Decimal | None
    notional: Decimal
    method: str

    def __post_init__(self) -> None:
        # notional: Decimal >= 0
        self.notional = _validate_decimal_nonneg(self.notional, "position_sizing.notional")
        # base_qty / quote_qty: both None or both Decimal >= 0
        if self.base_qty is not None:
            if isinstance(self.base_qty, bool) or not isinstance(self.base_qty, Decimal):
                raise ContractSchemaError(
                    "RiskDecision.PositionSizingSpec.base_qty must be Decimal|None"
                )
            if self.base_qty < 0:
                raise ContractSchemaError(
                    "RiskDecision.PositionSizingSpec.base_qty must be >= 0"
                )
        if self.quote_qty is not None:
            if isinstance(self.quote_qty, bool) or not isinstance(self.quote_qty, Decimal):
                raise ContractSchemaError(
                    "RiskDecision.PositionSizingSpec.quote_qty must be Decimal|None"
                )
            if self.quote_qty < 0:
                raise ContractSchemaError(
                    "RiskDecision.PositionSizingSpec.quote_qty must be >= 0"
                )
        # method: non-empty str (extensible)
        if not isinstance(self.method, str) or not self.method:
            raise ContractSchemaError(
                "RiskDecision.PositionSizingSpec.method must be non-empty str"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class LimitsSnapshot:
    """CONTRACTS.md §3.11 LimitsSnapshot — 10 alan + v1 hard boundary max_leverage=1."""

    max_position_notional_per_symbol: Decimal
    max_exposure_notional_total: Decimal
    max_daily_loss_notional: Decimal
    max_drawdown_pct: float
    max_consecutive_losses: int
    max_leverage_allowed: int
    current_exposure_notional: Decimal
    current_daily_pnl: Decimal
    current_drawdown_pct: float
    current_consecutive_losses: int

    def __post_init__(self) -> None:
        # ---- v1 HARD BOUNDARY (kırılmaz): max_leverage_allowed == 1 ----
        if not isinstance(self.max_leverage_allowed, int) or isinstance(
            self.max_leverage_allowed, bool
        ):
            raise ContractSchemaError(
                "LimitsSnapshot.max_leverage_allowed must be int"
            )
        if self.max_leverage_allowed != 1:
            raise ContractSchemaError(
                f"LimitsSnapshot.max_leverage_allowed MUST be 1 "
                f"(v1 hard boundary — no futures/leverage/short), "
                f"got {self.max_leverage_allowed!r}"
            )
        # Decimal non-neg (pnl hariç — daily pnl negatif olabilir)
        self.max_position_notional_per_symbol = _validate_decimal_nonneg(
            self.max_position_notional_per_symbol,
            "limits_snapshot.max_position_notional_per_symbol",
        )
        self.max_exposure_notional_total = _validate_decimal_nonneg(
            self.max_exposure_notional_total,
            "limits_snapshot.max_exposure_notional_total",
        )
        # max_daily_loss_notional: genelde negatif ya da 0 (tavan) — sign yok, sadece Decimal zorunlu
        if isinstance(self.max_daily_loss_notional, bool) or not isinstance(
            self.max_daily_loss_notional, Decimal
        ):
            raise ContractSchemaError(
                "LimitsSnapshot.max_daily_loss_notional must be Decimal"
            )
        # max_drawdown_pct [0, 1]
        self.max_drawdown_pct = _validate_float_range(
            self.max_drawdown_pct, "limits_snapshot.max_drawdown_pct", 0.0, 1.0
        )
        # max_consecutive_losses >= 0
        self.max_consecutive_losses = _validate_int_nonneg(
            self.max_consecutive_losses, "limits_snapshot.max_consecutive_losses"
        )
        # current_exposure_notional >= 0
        self.current_exposure_notional = _validate_decimal_nonneg(
            self.current_exposure_notional,
            "limits_snapshot.current_exposure_notional",
        )
        # current_daily_pnl: decimal (negatif = kayıp)
        if isinstance(self.current_daily_pnl, bool) or not isinstance(
            self.current_daily_pnl, Decimal
        ):
            raise ContractSchemaError(
                "LimitsSnapshot.current_daily_pnl must be Decimal"
            )
        # current_drawdown_pct [0, 1]
        self.current_drawdown_pct = _validate_float_range(
            self.current_drawdown_pct,
            "limits_snapshot.current_drawdown_pct",
            0.0,
            1.0,
        )
        # current_consecutive_losses >= 0
        self.current_consecutive_losses = _validate_int_nonneg(
            self.current_consecutive_losses, "limits_snapshot.current_consecutive_losses"
        )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class KillSwitchStateSpec:
    """CONTRACTS §3.11 kill_switch_state nested spec — AD-12."""

    global_kill: bool
    per_symbol: dict[str, bool] = field(default_factory=dict)
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.global_kill, bool):
            raise ContractSchemaError(
                "KillSwitchStateSpec.global_kill must be bool"
            )
        if not isinstance(self.per_symbol, dict):
            raise ContractSchemaError(
                "KillSwitchStateSpec.per_symbol must be dict[Symbol, bool]"
            )
        for sym, v in self.per_symbol.items():
            if not validate_symbol_canonical(sym):
                raise ContractSchemaError(
                    f"KillSwitchStateSpec.per_symbol invalid symbol: {sym!r}"
                )
            if not isinstance(v, bool):
                raise ContractSchemaError(
                    f"KillSwitchStateSpec.per_symbol[{sym!r}] must be bool"
                )
        if self.reason is not None and not isinstance(self.reason, str):
            raise ContractSchemaError(
                "KillSwitchStateSpec.reason must be str|None"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# RiskDecision — top-level typed contract (AD-11 + CAP-4)
# ---------------------------------------------------------------------------


@dataclass
class RiskDecision:
    """CONTRACTS.md §3.11 RiskDecision — Risk Engine BAĞIMSIZ çıktısı.

    AD-11 fail-closed:
      * Eğer kill_switch_state.global_kill=True ise decision=approved OLAMAZ.
      * decision yalnızca approved/rejected (tam 2 değer).
    CAP-4 prelude:
      * PaperOrder yaratılmadan ÖNCE aynı correlation_id ile decision=approved olmalı
        (zorunlu correlation_id + PaperOrder.policy_refs.risk_decision_id bağlantısı).
    """

    decision_id: ULID
    decision: RiskDecisionResult
    reason_codes: list[str]
    position_sizing: PositionSizingSpec
    limits_snapshot: LimitsSnapshot
    kill_switch_state: KillSwitchStateSpec
    valid_until: Instant
    correlation_id: ULID
    causation_id: ULID
    stop_loss_ref: Decimal | None = None
    take_profit_ref: Decimal | None = None
    approval_chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # decision_id
        _validate_ulidish(self.decision_id, "decision_id")
        # decision (enum or string cast)
        if not isinstance(self.decision, RiskDecisionResult):
            if isinstance(self.decision, str):
                try:
                    self.decision = RiskDecisionResult(self.decision)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"RiskDecision.decision invalid: {self.decision!r} "
                        f"(AD-11 allowed: approved|rejected — tam 2 değer)"
                    ) from exc
            else:
                raise ContractSchemaError(
                    f"RiskDecision.decision must be RiskDecisionResult, "
                    f"got {type(self.decision).__name__}"
                )
        # reason_codes (list[str] — None YOK, boş dizi olabilir)
        if not isinstance(self.reason_codes, list):
            raise ContractSchemaError(
                "RiskDecision.reason_codes must be list[str]"
            )
        for idx, rc in enumerate(self.reason_codes):
            if not isinstance(rc, str):
                raise ContractSchemaError(
                    f"RiskDecision.reason_codes[{idx}] must be str, got {type(rc).__name__}"
                )
        # nested typed helpers
        if not isinstance(self.position_sizing, PositionSizingSpec):
            raise ContractSchemaError(
                "RiskDecision.position_sizing must be PositionSizingSpec (raw dict rejected)"
            )
        if not isinstance(self.limits_snapshot, LimitsSnapshot):
            raise ContractSchemaError(
                "RiskDecision.limits_snapshot must be LimitsSnapshot (raw dict rejected)"
            )
        if not isinstance(self.kill_switch_state, KillSwitchStateSpec):
            raise ContractSchemaError(
                "RiskDecision.kill_switch_state must be KillSwitchStateSpec (raw dict rejected)"
            )
        # valid_until Instant
        if not validate_instant(self.valid_until):
            raise ContractSchemaError(
                f"RiskDecision.valid_until invalid Instant format: {self.valid_until!r}"
            )
        # corr/caus
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # stop_loss_ref / take_profit_ref (Decimal|None, parasal)
        if self.stop_loss_ref is not None:
            if isinstance(self.stop_loss_ref, bool) or not isinstance(
                self.stop_loss_ref, Decimal
            ):
                raise ContractSchemaError(
                    "RiskDecision.stop_loss_ref must be Decimal|None"
                )
        if self.take_profit_ref is not None:
            if isinstance(self.take_profit_ref, bool) or not isinstance(
                self.take_profit_ref, Decimal
            ):
                raise ContractSchemaError(
                    "RiskDecision.take_profit_ref must be Decimal|None"
                )
        # approval_chain: list[str]
        if not isinstance(self.approval_chain, list):
            raise ContractSchemaError(
                "RiskDecision.approval_chain must be list[str]"
            )
        for idx, ac in enumerate(self.approval_chain):
            if not isinstance(ac, str):
                raise ContractSchemaError(
                    f"RiskDecision.approval_chain[{idx}] must be str"
                )

        # ---- AD-11 FAIL-CLOSED HARD INVARIANT ----
        # kill_switch_state.global_kill=True ise decision APPROVED OLAMAZ.
        if (
            self.kill_switch_state.global_kill
            and self.decision == RiskDecisionResult.APPROVED
        ):
            raise ContractSchemaError(
                "RiskDecision invariant (AD-11 fail-closed): "
                "kill_switch_state.global_kill=True iken decision='approved' OLAMAZ"
            )

        # ---- Sizing uyumluluğu: decision=approved -> notional > 0; rejected -> notional 0 ----
        if self.decision == RiskDecisionResult.APPROVED:
            if self.position_sizing.notional <= 0:
                raise ContractSchemaError(
                    "RiskDecision approved: position_sizing.notional must be > 0"
                )
        else:  # REJECTED
            if self.position_sizing.notional != Decimal("0"):
                raise ContractSchemaError(
                    "RiskDecision rejected: position_sizing.notional must be exactly Decimal('0')"
                )

    # ---- serialisation / determinism --------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
