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
    Symbol,
    ULID,
    validate_instant,
    validate_symbol_canonical,
)


_ULIDISH_RE = re.compile(r"^[A-Za-z0-9\-]{8,}$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")


def _validate_ulidish(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} invalid format: {value!r}"
        )


def _validate_decimal_nonneg(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} must be Decimal >= 0, got {type(value).__name__}"
        )
    if value < 0:
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} must be >= 0, got {value!r}"
        )
    return value


def _validate_decimal_positive(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} must be Decimal > 0, got {type(value).__name__}"
        )
    if value <= 0:
        raise ContractSchemaError(
            f"PortfolioContract.{field_name} must be > 0, got {value!r}"
        )
    return value


# ---------------------------------------------------------------------------
# §3.14 Position enums (v1 hard boundary — SHORT YOKTUR)
# ---------------------------------------------------------------------------


class PositionSide(StrEnum):
    """v1 long-only pozisyon side enum. SHORT TAMAMEN YOKTUR."""

    LONG = "long"
    FLAT = "flat"


def _validate_enum_cast(value: Any, enum_type: type[Any], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise ContractSchemaError(
                f"PortfolioContract.{field_name} invalid {enum_type.__name__}: {value!r}"
            ) from exc
    raise ContractSchemaError(
        f"PortfolioContract.{field_name} must be {enum_type.__name__}, got {type(value).__name__}"
    )


# ---------------------------------------------------------------------------
# §3.14 Position — typed canonical position schema (AD-13 portfolio truth)
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """CONTRACTS §3.14 Position. v1 hard boundary: short YOK (side ∈ {long, flat}).

    Writer (AD-7/13/24): SADECE PortfolioSimulator (app/simulation/portfolio)
    tarafından yazılır. Backtest doğrudan yazamaz.
    """

    position_id: ULID
    symbol: Symbol
    side: PositionSide
    base_qty: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    unrealized_pnl_quote: Decimal
    realized_pnl_quote: Decimal
    fees_quote: Decimal
    opened_ts: Instant
    last_updated_ts: Instant
    open_refs: list[ULID]
    correlation_id: ULID
    causation_id: ULID
    stop_loss_ref: Decimal | None = None
    take_profit_ref: Decimal | None = None

    def __post_init__(self) -> None:
        # position_id
        _validate_ulidish(self.position_id, "position_id")
        # symbol canonical
        if not validate_symbol_canonical(self.symbol):
            raise ContractSchemaError(
                f"Position.symbol not canonical: {self.symbol!r}"
            )
        # side (v1: long/flat — short VALUE YOK)
        self.side = _validate_enum_cast(self.side, PositionSide, "side")
        # base_qty: Decimal >= 0 (short yok → negatif YOK)
        self.base_qty = _validate_decimal_nonneg(self.base_qty, "base_qty")
        # avg_entry_price: Decimal >= 0 (flat 0 olabilir)
        if isinstance(self.avg_entry_price, bool) or not isinstance(
            self.avg_entry_price, Decimal
        ):
            raise ContractSchemaError(
                "Position.avg_entry_price must be Decimal >= 0"
            )
        if self.avg_entry_price < 0:
            raise ContractSchemaError(
                f"Position.avg_entry_price must be >= 0, got {self.avg_entry_price!r}"
            )
        # current_price: Decimal > 0 (son fiyat 0 YOK)
        self.current_price = _validate_decimal_positive(
            self.current_price, "current_price"
        )
        # unrealized_pnl_quote: Decimal (negatif olabilir = kayıp)
        if isinstance(self.unrealized_pnl_quote, bool) or not isinstance(
            self.unrealized_pnl_quote, Decimal
        ):
            raise ContractSchemaError(
                "Position.unrealized_pnl_quote must be Decimal (negatif=kayıp)"
            )
        # realized_pnl_quote: Decimal (aynı)
        if isinstance(self.realized_pnl_quote, bool) or not isinstance(
            self.realized_pnl_quote, Decimal
        ):
            raise ContractSchemaError(
                "Position.realized_pnl_quote must be Decimal"
            )
        # fees_quote: Decimal >= 0
        self.fees_quote = _validate_decimal_nonneg(self.fees_quote, "fees_quote")
        # opened_ts / last_updated_ts
        if not validate_instant(self.opened_ts):
            raise ContractSchemaError(
                f"Position.opened_ts invalid Instant: {self.opened_ts!r}"
            )
        if not validate_instant(self.last_updated_ts):
            raise ContractSchemaError(
                f"Position.last_updated_ts invalid Instant: {self.last_updated_ts!r}"
            )
        # open_refs: list[str|ULID] — None YOK, boş dizi olabilir
        if not isinstance(self.open_refs, list):
            raise ContractSchemaError(
                "Position.open_refs must be list[ULID] (None YOK; boş [] olabilir)"
            )
        for idx, r in enumerate(self.open_refs):
            if not isinstance(r, str):
                raise ContractSchemaError(
                    f"Position.open_refs[{idx}] must be str ULID-like, got {type(r).__name__}"
                )
        # corr/caus
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # stop_loss_ref / take_profit_ref (Decimal|None)
        if self.stop_loss_ref is not None:
            if isinstance(self.stop_loss_ref, bool) or not isinstance(
                self.stop_loss_ref, Decimal
            ):
                raise ContractSchemaError(
                    "Position.stop_loss_ref must be Decimal|None"
                )
        if self.take_profit_ref is not None:
            if isinstance(self.take_profit_ref, bool) or not isinstance(
                self.take_profit_ref, Decimal
            ):
                raise ContractSchemaError(
                    "Position.take_profit_ref must be Decimal|None"
                )

        # ---- v1 invariant: side == FLAT → base_qty MUTLAKA 0 ----
        if self.side == PositionSide.FLAT and self.base_qty != Decimal("0"):
            raise ContractSchemaError(
                "Position invariant (v1 no-short boundary): "
                "side=flat iken base_qty MUTLAKA Decimal('0') olmalı; "
                f"got base_qty={self.base_qty!r}"
            )

    # ---- serialisation / determinism --------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# §3.15 PortfolioSnapshot — single writer snapshot (AD-7/13/24)
# ---------------------------------------------------------------------------


@dataclass
class PortfolioSnapshot:
    """CONTRACTS §3.15 PortfolioSnapshot. Drawdown + PnL + exposure canonical alanları.

    Writer: SADECE PortfolioSimulator (AD-7/13/24). Backtest doğrudan yazamaz.
    """

    snapshot_id: ULID
    account_ref: str
    ts: Instant
    cash_quote: Decimal
    equity_quote: Decimal
    realized_pnl_quote_24h: Decimal
    unrealized_pnl_quote: Decimal
    fees_quote_total: Decimal
    exposure_notional: Decimal
    drawdown_pct: float
    peak_equity_quote: Decimal
    correlation_id: ULID
    causation_id: ULID
    positions_snapshot: list[Position] | None = None

    def __post_init__(self) -> None:
        # snapshot_id
        _validate_ulidish(self.snapshot_id, "snapshot_id")
        # account_ref
        if not isinstance(self.account_ref, str) or not self.account_ref:
            raise ContractSchemaError(
                "PortfolioSnapshot.account_ref must be non-empty str"
            )
        # ts
        if not validate_instant(self.ts):
            raise ContractSchemaError(
                f"PortfolioSnapshot.ts invalid Instant: {self.ts!r}"
            )
        # cash_quote: Decimal >= 0
        self.cash_quote = _validate_decimal_nonneg(self.cash_quote, "cash_quote")
        # equity_quote: Decimal >= 0
        self.equity_quote = _validate_decimal_nonneg(self.equity_quote, "equity_quote")
        # realized_pnl_quote_24h: Decimal (negatif olabilir)
        if isinstance(self.realized_pnl_quote_24h, bool) or not isinstance(
            self.realized_pnl_quote_24h, Decimal
        ):
            raise ContractSchemaError(
                "PortfolioSnapshot.realized_pnl_quote_24h must be Decimal"
            )
        # unrealized_pnl_quote: Decimal
        if isinstance(self.unrealized_pnl_quote, bool) or not isinstance(
            self.unrealized_pnl_quote, Decimal
        ):
            raise ContractSchemaError(
                "PortfolioSnapshot.unrealized_pnl_quote must be Decimal"
            )
        # fees_quote_total >= 0
        self.fees_quote_total = _validate_decimal_nonneg(
            self.fees_quote_total, "fees_quote_total"
        )
        # exposure_notional >= 0
        self.exposure_notional = _validate_decimal_nonneg(
            self.exposure_notional, "exposure_notional"
        )
        # drawdown_pct float [0, 1]
        if isinstance(self.drawdown_pct, bool) or not isinstance(
            self.drawdown_pct, float
        ):
            raise ContractSchemaError(
                "PortfolioSnapshot.drawdown_pct must be float in [0, 1]"
            )
        if self.drawdown_pct < 0.0 or self.drawdown_pct > 1.0:
            raise ContractSchemaError(
                f"PortfolioSnapshot.drawdown_pct out of [0, 1] range: {self.drawdown_pct!r}"
            )
        # peak_equity_quote >= 0
        self.peak_equity_quote = _validate_decimal_nonneg(
            self.peak_equity_quote, "peak_equity_quote"
        )
        # corr/caus
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # positions_snapshot: list[Position] | None — None veya list[Position]
        if self.positions_snapshot is not None:
            if not isinstance(self.positions_snapshot, list):
                raise ContractSchemaError(
                    "PortfolioSnapshot.positions_snapshot must be list[Position]|None"
                )
            for idx, p in enumerate(self.positions_snapshot):
                if not isinstance(p, Position):
                    raise ContractSchemaError(
                        f"PortfolioSnapshot.positions_snapshot[{idx}] must be Position"
                        " (raw dict rejected — nested to_sorted_dict determinism için typed gerekli)"
                    )

    # ---- serialisation / determinism ------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
