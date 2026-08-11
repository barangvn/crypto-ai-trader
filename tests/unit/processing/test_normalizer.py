from __future__ import annotations

from decimal import Decimal

from app.contracts import normalize_symbol, validate_symbol_canonical, validate_instant
from app.processing import Normalizer
from app.contracts import RunMode, SourceType


def test_symbol_normalization_btcusdt_to_btc_usdt():
    result = normalize_symbol("BTCUSDT")
    assert result == "BTC_USDT"


def test_symbol_normalization_slash_form():
    result = normalize_symbol("ETH/USDT")
    assert result == "ETH_USDT"


def test_timestamp_normalizer_produces_z_3digit_ms():
    nm = Normalizer(run_mode=RunMode.PAPER, source_type=SourceType.REPLAY)
    raw_row = {
        "_row_index": 0,
        "raw_symbol": "BTCUSDT",
        "raw_timestamp": "2026-08-10 10:00:00",
        "open": "65000.00",
        "high": "65001.67",
        "low": "64998.33",
        "close": "65000.00",
        "volume": "1.00",
        "trade_count": "100",
        "event_type": "candle",
        "timeframe": "1m",
        "raw_trade_id": "",
        "raw_sequence": "1",
        "spread_bps": "",
    }
    envelope = nm.normalize_one(raw_row, correlation_id="test-corr-1")
    assert validate_instant(envelope.timestamp) is True
    assert envelope.timestamp.endswith("Z")
    assert "." in envelope.timestamp
    ms_part = envelope.timestamp.split(".")[1].replace("Z", "")
    assert len(ms_part) == 3


def test_candle_payload_decimal_types():
    nm = Normalizer(run_mode=RunMode.PAPER, source_type=SourceType.REPLAY)
    raw_row = {
        "_row_index": 0,
        "raw_symbol": "BTCUSDT",
        "raw_timestamp": "2026-08-10 10:00:00",
        "open": "65000.00",
        "high": "65001.67",
        "low": "64998.33",
        "close": "65000.00",
        "volume": "1.00",
        "trade_count": "100",
        "event_type": "candle",
        "timeframe": "1m",
        "raw_trade_id": "",
        "raw_sequence": "1",
        "spread_bps": "",
    }
    envelope = nm.normalize_one(raw_row, correlation_id="test-corr-2")
    payload = envelope.payload
    assert isinstance(payload.open, Decimal)
    assert isinstance(payload.high, Decimal)
    assert isinstance(payload.low, Decimal)
    assert isinstance(payload.close, Decimal)
    assert isinstance(payload.volume, Decimal)


def test_envelope_symbol_canonical():
    nm = Normalizer(run_mode=RunMode.PAPER, source_type=SourceType.REPLAY)
    raw_row = {
        "_row_index": 0,
        "raw_symbol": "BTCUSDT",
        "raw_timestamp": "2026-08-10 10:00:00",
        "open": "65000.00",
        "high": "65001.67",
        "low": "64998.33",
        "close": "65000.00",
        "volume": "1.00",
        "trade_count": "100",
        "event_type": "candle",
        "timeframe": "1m",
        "raw_trade_id": "",
        "raw_sequence": "1",
        "spread_bps": "",
    }
    envelope = nm.normalize_one(raw_row, correlation_id="test-corr-3")
    assert validate_symbol_canonical(envelope.symbol) is True
