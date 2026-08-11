from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.contracts.types import Instant


@dataclass
class MarketTick:
    price: Decimal
    market_ts: Instant
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    last_size: Decimal | None = None
    spread_bps: float | None = None


@dataclass
class TradeEvent:
    trade_id: str
    side: Literal["buy", "sell"]
    price: Decimal
    quantity: Decimal
    market_ts: Instant
    quote_quantity: Decimal | None = None


@dataclass
class OrderBookSnapshot:
    depth_levels: int
    bids: list[list[Decimal]]
    asks: list[list[Decimal]]
    book_ts: Instant
    sequence_start: int | None = None
    sequence_end: int | None = None
    imbalance_bps: float | None = None


@dataclass
class OrderBookUpdate:
    bids_delta: list[list[Decimal]]
    asks_delta: list[list[Decimal]]
    book_ts: Instant
    sequence: int | None = None


@dataclass
class Candle:
    timeframe: str
    open_time: Instant
    close_time: Instant
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool
    quote_volume: Decimal | None = None
    vwap: Decimal | None = None
    trade_count: int | None = None
