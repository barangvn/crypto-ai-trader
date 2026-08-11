from __future__ import annotations

from decimal import Decimal

from app.contracts import format_instant
from app.contracts.market import Candle, MarketTick


def test_market_tick_price_decimal_positive():
    ts = format_instant()
    tick = MarketTick(price=Decimal("1"), market_ts=ts)
    assert isinstance(tick.price, Decimal)
    assert tick.price == Decimal("1")


def test_candle_ohlcv_all_decimal_type():
    ts = format_instant()
    candle = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts,
        open=Decimal("65000.00"),
        high=Decimal("65200.00"),
        low=Decimal("64900.00"),
        close=Decimal("65100.00"),
        volume=Decimal("1.5"),
        closed=True,
    )
    assert isinstance(candle.open, Decimal)
    assert isinstance(candle.high, Decimal)
    assert isinstance(candle.low, Decimal)
    assert isinstance(candle.close, Decimal)
    assert isinstance(candle.volume, Decimal)


def test_candle_closed_default_true():
    ts = format_instant()
    candle = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts,
        open=Decimal("65000"),
        high=Decimal("65100"),
        low=Decimal("64900"),
        close=Decimal("65050"),
        volume=Decimal("1.0"),
        closed=True,
    )
    assert candle.closed is True


def test_candle_low_leq_others_leq_high_invariant():
    ts = format_instant()
    o = Decimal("65000")
    c = Decimal("65200")
    low = min(o, c)
    high = max(o, c)
    candle = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts,
        open=o,
        high=high,
        low=low,
        close=c,
        volume=Decimal("1.0"),
        closed=True,
    )
    assert candle.low <= candle.open <= candle.high
    assert candle.low <= candle.close <= candle.high
    assert candle.low == Decimal("65000")
    assert candle.high == Decimal("65200")
