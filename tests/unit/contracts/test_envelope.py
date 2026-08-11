from __future__ import annotations

from decimal import Decimal

import pytest

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


def test_envelope_required_fields():
    with pytest.raises((TypeError, ValueError)):
        CanonicalEventEnvelope()


def test_envelope_all_15_required_fields_present():
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
        event_id=ULID("01920000-0000-7000-8000-000000000002"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="test-fixture",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID("01920000-0000-7000-8000-000000000002"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )
    assert envelope.event_id
    assert envelope.event_type
    assert envelope.contract_version
    assert envelope.symbol
    assert envelope.source
    assert envelope.timestamp
    assert envelope.ingest_ts
    assert envelope.correlation_id
    assert envelope.causation_id
    assert envelope.run_mode
    assert envelope.source_type
    assert envelope.clock_ref
    assert envelope.quality_flags
    assert envelope.schema_ref
    assert envelope.payload is not None


def test_envelope_timestamp_format():
    ts = Instant("2026-08-10T10:00:00.000Z")
    assert validate_instant(ts) is True


def test_envelope_correlation_and_causation_first_link():
    ts = format_instant()
    envelope = CanonicalEventEnvelope(
        event_id=ULID("01920000-0000-7000-8000-000000000003"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="test-fixture",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-000000000003"),
        causation_id=ULID("01920000-0000-7000-8000-000000000003"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
    )
    assert envelope.causation_id == envelope.event_id


def test_envelope_contract_version_defaults_1_0_0():
    assert CONTRACT_VERSION == "1.0.0"


def test_schema_ref_contracts_md_default_value():
    ref = SchemaRef()
    assert ref.contracts_md == "CONTRACTS.md@1.0.0"
