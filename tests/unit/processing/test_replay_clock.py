from __future__ import annotations

from decimal import Decimal

from app.contracts import (
    CONTRACT_VERSION,
    RunMode,
    SourceType,
    format_instant,
    validate_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Instant, Symbol, ULID
from app.processing import Normalizer, set_clock_ref_for_replay


def test_source_type_replay_sets_clock_ref_replay():
    ts = format_instant()
    payload = Candle(
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
    envelope = CanonicalEventEnvelope(
        event_id=ULID("01920000-0000-7000-8000-000000000020"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="test-fixture",
        timestamp=ts,
        ingest_ts=format_instant(),
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID("01920000-0000-7000-8000-000000000020"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=format_instant()),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )
    set_clock_ref_for_replay(envelope)
    assert envelope.clock_ref.replay is not None
    assert envelope.clock_ref.replay == envelope.timestamp


def test_source_type_not_replay_wont_break():
    ts = format_instant()
    payload = Candle(
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
    envelope = CanonicalEventEnvelope(
        event_id=ULID("01920000-0000-7000-8000-000000000021"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="test-fixture",
        timestamp=ts,
        ingest_ts=format_instant(),
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID("01920000-0000-7000-8000-000000000021"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.LIVE_WS,
        clock_ref=ClockRef(wall=format_instant()),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )
    set_clock_ref_for_replay(envelope)
    assert envelope.source_type == SourceType.LIVE_WS
    assert envelope.clock_ref.replay is None


def test_clock_ref_wall_different_from_replay_after_normalize():
    import time
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
    envelope = nm.normalize_one(raw_row, correlation_id="test-corr-clock")
    set_clock_ref_for_replay(envelope)
    assert validate_instant(envelope.clock_ref.wall)
    assert validate_instant(envelope.clock_ref.replay)
    assert envelope.clock_ref.replay == envelope.timestamp
    assert isinstance(envelope.clock_ref.wall, str)
    assert isinstance(envelope.clock_ref.replay, str)
