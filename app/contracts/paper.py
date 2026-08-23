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
)


_ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")
_STRATEGY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")


def _validate_ulidish(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"PaperContract.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"PaperContract.{field_name} invalid format: {value!r}"
        )


def _validate_decimal_positive(value: Any, field_name: str) -> Decimal:
    """Decimal > 0 zorunlu."""
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ContractSchemaError(
            f"PaperContract.{field_name} must be Decimal > 0, got {type(value).__name__}"
        )
    if value <= 0:
        raise ContractSchemaError(
            f"PaperContract.{field_name} must be > 0, got {value!r}"
        )
    return value


def _validate_decimal_nonneg(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ContractSchemaError(
            f"PaperContract.{field_name} must be Decimal >= 0, got {type(value).__name__}"
        )
    if value < 0:
        raise ContractSchemaError(
            f"PaperContract.{field_name} must be >= 0, got {value!r}"
        )
    return value


# ---------------------------------------------------------------------------
# §3.12 PaperOrder enums + helpers (v1 hard boundary — short/futures YOK)
# ---------------------------------------------------------------------------


class PaperOrderSide(StrEnum):
    """v1 long-only side enum. SHORT AÇMA YOKTUR. `sell` yalnızca long kapatır."""

    BUY = "buy"
    SELL = "sell"


class PaperOrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class PaperOrderStatus(StrEnum):
    CREATED = "created"
    SIMULATING = "simulating"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


def _validate_enum_cast(value: Any, enum_type: type[Any], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise ContractSchemaError(
                f"PaperContract.{field_name} invalid {enum_type.__name__}: {value!r}"
            ) from exc
    raise ContractSchemaError(
        f"PaperContract.{field_name} must be {enum_type.__name__}, got {type(value).__name__}"
    )


@dataclass
class PaperOrderPolicyRefs:
    """CAP-4 zorunlu policy refs: risk_decision_id REQUIRED (approved RiskDecision.decision_id)."""

    risk_decision_id: ULID
    strategy_id: str
    strategy_version: str

    def __post_init__(self) -> None:
        # risk_decision_id: ULID-like (>= 8 chars, alpha-num + dash)
        if not isinstance(self.risk_decision_id, str):
            raise ContractSchemaError(
                "PaperOrderPolicyRefs.risk_decision_id must be str (ULID-like)"
            )
        if len(self.risk_decision_id) < 8 or not _ULIDISH_RE.match(
            self.risk_decision_id
        ):
            raise ContractSchemaError(
                f"PaperOrderPolicyRefs.risk_decision_id invalid ULID-like: {self.risk_decision_id!r} "
                f"(CAP-4: her PaperOrder ZORUNLU approved RiskDecision'a bağlanır)"
            )
        # strategy_id
        if not isinstance(self.strategy_id, str) or not _STRATEGY_ID_RE.match(
            self.strategy_id
        ):
            raise ContractSchemaError(
                f"PaperOrderPolicyRefs.strategy_id invalid: {self.strategy_id!r}"
            )
        # strategy_version
        if not isinstance(self.strategy_version, str) or not _VERSION_RE.match(
            self.strategy_version
        ):
            raise ContractSchemaError(
                f"PaperOrderPolicyRefs.strategy_version invalid: {self.strategy_version!r}"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# §3.12 PaperOrder — typed schema (paper-only, simulated; gerçek exchange YOK)
# ---------------------------------------------------------------------------


_PRICE_REQUIRED_ORDER_TYPES = frozenset(
    {PaperOrderType.LIMIT, PaperOrderType.STOP_LIMIT}
)


@dataclass
class PaperOrder:
    """CONTRACTS §3.12 PaperOrder. Paper-only; gerçek order/API/key/para YOK."""

    paper_order_id: ULID
    side: PaperOrderSide
    order_type: PaperOrderType
    requested_qty_base: Decimal
    policy_refs: PaperOrderPolicyRefs
    status: PaperOrderStatus
    created_at: Instant
    updated_at: Instant
    correlation_id: ULID
    causation_id: ULID
    client_order_id: str | None = None
    requested_price: Decimal | None = None
    time_in_force: TimeInForce | None = None

    def __post_init__(self) -> None:
        # paper_order_id
        _validate_ulidish(self.paper_order_id, "paper_order_id")
        # side (v1: buy/sell ONLY — short enum'da YOK → string verirse ValueError)
        self.side = _validate_enum_cast(self.side, PaperOrderSide, "side")
        # order_type
        self.order_type = _validate_enum_cast(
            self.order_type, PaperOrderType, "order_type"
        )
        # requested_qty_base: Decimal > 0
        self.requested_qty_base = _validate_decimal_positive(
            self.requested_qty_base, "requested_qty_base"
        )
        # policy_refs (CAP-4: risk_decision_id ZORUNLU nested)
        if not isinstance(self.policy_refs, PaperOrderPolicyRefs):
            raise ContractSchemaError(
                "PaperOrder.policy_refs must be PaperOrderPolicyRefs "
                "(CAP-4: nested raw dict rejected; risk_decision_id REQUIRED)"
            )
        # status
        self.status = _validate_enum_cast(
            self.status, PaperOrderStatus, "status"
        )
        # created_at / updated_at
        if not validate_instant(self.created_at):
            raise ContractSchemaError(
                f"PaperOrder.created_at invalid Instant: {self.created_at!r}"
            )
        if not validate_instant(self.updated_at):
            raise ContractSchemaError(
                f"PaperOrder.updated_at invalid Instant: {self.updated_at!r}"
            )
        # corr/caus
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # client_order_id
        if self.client_order_id is not None and not isinstance(
            self.client_order_id, str
        ):
            raise ContractSchemaError(
                "PaperOrder.client_order_id must be str|None"
            )
        # requested_price: Decimal|None — order_type ∈ {limit, stop_limit} ise ZORUNLU
        if self.requested_price is not None:
            if isinstance(self.requested_price, bool) or not isinstance(
                self.requested_price, Decimal
            ):
                raise ContractSchemaError(
                    "PaperOrder.requested_price must be Decimal|None"
                )
            if self.requested_price <= 0:
                raise ContractSchemaError(
                    f"PaperOrder.requested_price must be > 0 if given, got {self.requested_price!r}"
                )
        if self.order_type in _PRICE_REQUIRED_ORDER_TYPES:
            if self.requested_price is None:
                raise ContractSchemaError(
                    f"PaperOrder.requested_price REQUIRED for order_type={self.order_type.value} "
                    f"(limit/stop_limit price zorunlu)"
                )
        # time_in_force: enum|None
        if self.time_in_force is not None:
            self.time_in_force = _validate_enum_cast(
                self.time_in_force, TimeInForce, "time_in_force"
            )

    # ---- serialisation / determinism -------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# §3.13 PaperFill — simulated fill typed contract (fee / slippage / latency / partial)
# ---------------------------------------------------------------------------


_QUOTE_QTY_TOL = Decimal("1e-12")


@dataclass
class PaperFill:
    """CONTRACTS §3.13 PaperFill. Simulated; gerçek exchange execution YOK."""

    paper_fill_id: ULID
    paper_order_id: ULID
    side: PaperOrderSide
    fill_price: Decimal
    fill_qty_base: Decimal
    fill_qty_quote: Decimal
    fees_quote: Decimal
    fill_ts: Instant
    fill_model_version: str
    correlation_id: ULID
    causation_id: ULID
    slippage_bps: float | None = None
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        # ids
        _validate_ulidish(self.paper_fill_id, "paper_fill_id")
        _validate_ulidish(self.paper_order_id, "paper_order_id")
        # side
        self.side = _validate_enum_cast(self.side, PaperOrderSide, "side")
        # fill_price: Decimal > 0
        self.fill_price = _validate_decimal_positive(self.fill_price, "fill_price")
        # fill_qty_base: Decimal > 0 (partial fill bile miktar > 0)
        self.fill_qty_base = _validate_decimal_positive(
            self.fill_qty_base, "fill_qty_base"
        )
        # fill_qty_quote: Decimal >= 0; daha sonra tutar tutarlılığı (price × qty) doğrulanacak
        if isinstance(self.fill_qty_quote, bool) or not isinstance(
            self.fill_qty_quote, Decimal
        ):
            raise ContractSchemaError(
                "PaperFill.fill_qty_quote must be Decimal (= fill_price * fill_qty_base)"
            )
        if self.fill_qty_quote < 0:
            raise ContractSchemaError(
                f"PaperFill.fill_qty_quote must be >= 0, got {self.fill_qty_quote!r}"
            )
        # fees_quote: Decimal > 0 (Pozitif ZORUNLU v1 — maker rebate YOK)
        if isinstance(self.fees_quote, bool) or not isinstance(
            self.fees_quote, Decimal
        ):
            raise ContractSchemaError(
                "PaperFill.fees_quote must be Decimal > 0 (v1: fee pozitif ZORUNLU, negatif/maker-rebate YOK)"
            )
        if self.fees_quote <= 0:
            raise ContractSchemaError(
                f"PaperFill.fees_quote must be > 0, got {self.fees_quote!r} "
                f"(fee negatif / sıfır — v1 hard kural: her fill fee > 0)"
            )
        # fill_ts
        if not validate_instant(self.fill_ts):
            raise ContractSchemaError(
                f"PaperFill.fill_ts invalid Instant: {self.fill_ts!r}"
            )
        # fill_model_version: non-empty str
        if not isinstance(self.fill_model_version, str) or not self.fill_model_version:
            raise ContractSchemaError(
                "PaperFill.fill_model_version must be non-empty str"
            )
        # corr/caus
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # slippage_bps (float|None — sınır yok type dışında, sadece tip kontrolü)
        if self.slippage_bps is not None:
            if isinstance(self.slippage_bps, bool) or not isinstance(
                self.slippage_bps, float
            ):
                raise ContractSchemaError(
                    "PaperFill.slippage_bps must be float|None"
                )
        # latency_ms (int|None, >= 0)
        if self.latency_ms is not None:
            if isinstance(self.latency_ms, bool) or not isinstance(
                self.latency_ms, int
            ):
                raise ContractSchemaError(
                    "PaperFill.latency_ms must be int|None"
                )
            if self.latency_ms < 0:
                raise ContractSchemaError(
                    f"PaperFill.latency_ms must be >= 0, got {self.latency_ms!r}"
                )

        # ---- Invariant: fill_qty_quote == fill_price * fill_qty_base (± tolerans) ----
        expected_quote = self.fill_price * self.fill_qty_base
        diff = abs(self.fill_qty_quote - expected_quote)
        if diff > _QUOTE_QTY_TOL:
            raise ContractSchemaError(
                f"PaperFill invariant: fill_qty_quote ({self.fill_qty_quote}) != "
                f"fill_price * fill_qty_base ({expected_quote}); "
                f"diff={diff} > tol={_QUOTE_QTY_TOL}"
            )

    # ---- serialisation / determinism -------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
