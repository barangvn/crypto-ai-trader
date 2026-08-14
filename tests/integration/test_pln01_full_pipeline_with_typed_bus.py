from __future__ import annotations

"""Integration: S-RDH-02 replay pipeline sonuna typed bus + downstream subscriber."""

from pathlib import Path

import pytest

from app.contracts import RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Symbol, ULID
from app.platform.event_bus import InMemoryTypedEventBus


CONTRACT_VERSION = "1.0.0"


def test_pln01_full_pipeline_emits_envelopes_to_typed_subscribers(
    run_pipeline, small_fixture_path
):
    """Full pipeline: adapter → normalizer → validator → bus → typed subscribers."""
    bus = InMemoryTypedEventBus()

    counters: dict[str, int] = {"candle": 0, "wildcard": 0, "accept_q": 0, "skip_q": 0}
    t_candle = bus.subscribe_typed(
        "candle.v1",
        lambda e, c=counters: c.update(candle=c["candle"] + 1),
    )
    t_wild = bus.subscribe_typed(
        "*",
        lambda e, c=counters: c.update(wildcard=c["wildcard"] + 1),
    )
    t_quar_accept = bus.subscribe_typed(
        "candle.v1",
        lambda e, c=counters: c.update(accept_q=c["accept_q"] + 1),
        accept_quarantined=True,
    )
    t_quar_skip = bus.subscribe_typed(
        "candle.v1",
        lambda e, c=counters: c.update(skip_q=c["skip_q"] + 1),
        accept_quarantined=False,
    )

    published, quarantined, bus_out = run_pipeline(small_fixture_path, bus_instance=bus)
    assert bus_out is bus
    assert len(published) > 0
    # Her publish edilen zarf için 3 tane tip cb çağrıldı (candle + wildcard + accept_q + skip_q)
    # quarantine edilmeyen varsayılan clean veriler için 4 subscriber da çalışır
    expected_count = len(published)
    assert counters["candle"] == expected_count, f"candle count mismatch: {counters}"
    assert counters["wildcard"] == expected_count
    assert counters["accept_q"] == expected_count
    assert counters["skip_q"] == expected_count
    assert len(bus.dead_letters) == 0  # clean veride DLQ yok


def test_pln01_downstream_propagates_correlation():
    """Integration: 1 event → 2 downstream publish_with_causation → 3'lü zincir."""
    bus = InMemoryTypedEventBus()

    ts = format_instant()
    payload = Candle(
        timeframe="1m", open_time=ts, close_time=ts,
        open=1, high=2, low=0, close=1, volume=1, closed=True,
    )
    corr_ulid = ULID("01920000-0000-7000-8000-000000000C99")

    emitted: list[CanonicalEventEnvelope] = []

    def on_candle(e):
        feat = CanonicalEventEnvelope(
            event_id=ULID("01920000-0000-7000-8000-000000000A02"),
            event_type="feature_vector.v1",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="feature",
            timestamp=ts, ingest_ts=ts,
            correlation_id=None,  # type: ignore[arg-type]
            causation_id=None,  # type: ignore[arg-type]
            run_mode=RunMode.PAPER,
            source_type=SourceType.REPLAY,
            clock_ref=ClockRef(wall=ts, replay=ts),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
            payload=None,
        )
        bus.publish_with_causation(feat, str(e.event_id))
        emitted.append(feat)

        regime = CanonicalEventEnvelope(
            event_id=ULID("01920000-0000-7000-8000-000000000A03"),
            event_type="regime.v1",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="regime",
            timestamp=ts, ingest_ts=ts,
            correlation_id=None,  # type: ignore[arg-type]
            causation_id=None,  # type: ignore[arg-type]
            run_mode=RunMode.PAPER,
            source_type=SourceType.REPLAY,
            clock_ref=ClockRef(wall=ts, replay=ts),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
            payload=None,
        )
        bus.publish_with_causation(regime, str(feat.event_id))
        emitted.append(regime)

    candle_id = ULID("01920000-0000-7000-8000-000000000A01")
    bus.subscribe_typed("candle.v1", on_candle)
    env = CanonicalEventEnvelope(
        event_id=candle_id,
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="manual",
        timestamp=ts, ingest_ts=ts,
        correlation_id=corr_ulid,
        causation_id=candle_id,  # ilk halka
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )
    bus.publish(env)

    assert len(emitted) == 2
    for e in emitted:
        assert str(e.correlation_id) == str(corr_ulid), f"Corruption mismatch for {e.event_type}"

    chain = bus.trace_causation_chain(str(emitted[1].event_id))
    assert len(chain) == 3
    assert chain[0] == str(emitted[1].event_id)
    assert chain[1] == str(emitted[0].event_id)
    assert chain[2] == str(candle_id)
