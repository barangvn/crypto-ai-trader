from __future__ import annotations

from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import (
    Candle,
    MarketTick,
    OrderBookSnapshot,
    OrderBookUpdate,
    TradeEvent,
)
from app.contracts.types import (
    ContractVersion,
    Instant,
    RunMode,
    SourceType,
    Symbol,
    ULID,
    format_instant,
    normalize_symbol,
    validate_instant,
    validate_symbol_canonical,
)


CONTRACT_VERSION: ContractVersion = ContractVersion("1.0.0")


def now_instant() -> Instant:
    return format_instant()


__all__ = [
    "CONTRACT_VERSION",
    "ContractVersion",
    "Instant",
    "Symbol",
    "ULID",
    "RunMode",
    "SourceType",
    "QualityFlags",
    "ClockRef",
    "SchemaRef",
    "CanonicalEventEnvelope",
    "MarketTick",
    "TradeEvent",
    "OrderBookSnapshot",
    "OrderBookUpdate",
    "Candle",
    "format_instant",
    "validate_instant",
    "normalize_symbol",
    "validate_symbol_canonical",
    "now_instant",
]
