from __future__ import annotations

"""AC-27: conftest offline blocker aktifken 100 event publish + 3 cb failure — hiç network çağrısı yok."""

import pytest

from app.contracts import CONTRACT_VERSION, RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Symbol, ULID
from app.platform.event_bus import InMemoryTypedEventBus


def _make_env(idx: int) -> CanonicalEventEnvelope:
    ts = format_instant()
    return CanonicalEventEnvelope(
        event_id=ULID(f"01940000-0000-7000-8000-{idx:012d}"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source=f"net-{idx}",
        timestamp=ts, ingest_ts=ts,
        correlation_id=ULID("01940000-0000-7000-8000-0000000000C1"),
        causation_id=ULID(f"01940000-0000-7000-8000-{idx:012d}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=Candle(
            timeframe="1m", open_time=ts, close_time=ts,
            open=idx, high=idx + 1, low=idx, close=idx,
            volume=1.0, closed=True,
        ),
    )


@pytest.mark.failure_injection
class TestBusNetworkSafety:
    def test_bus_one_hundred_events_publish_works_offline(self) -> None:
        bus = InMemoryTypedEventBus()
        counters: dict[str, int] = {"ok": 0}
        bus.subscribe_typed("candle.v1", lambda e, c=counters: c.update(ok=c["ok"] + 1))
        events = [_make_env(i) for i in range(100)]
        count = bus.publish_many(events)
        assert count == 100
        assert len(bus.published) == 100
        assert counters["ok"] == 100

    def test_bus_with_failing_subscribers_offline(self) -> None:
        bus = InMemoryTypedEventBus()

        def bad_cb_1(e):
            raise RuntimeError("network-blocked-run-fail-1")

        def bad_cb_2(e):
            raise RuntimeError("network-blocked-run-fail-2")

        def bad_cb_3(e):
            raise RuntimeError("network-blocked-run-fail-3")

        bus.subscribe_typed("candle.v1", bad_cb_1)
        bus.subscribe_typed("candle.v1", bad_cb_2)
        bus.subscribe_typed("candle.v1", bad_cb_3)

        events = [_make_env(i) for i in range(10)]
        count = bus.publish_many(events)
        assert count == 10
        assert len(bus.published) == 10
        # 10 event × 3 failing cb = 30 DLQ kaydı
        assert len(bus.dead_letters) == 30
        codes = {dl.dlq_code for dl in bus.dead_letters}
        assert codes == {"E_SUBSCRIBER_EXC"}
        # Network çağrısı olmadığı için conftest socket blocker RuntimeError tetiklenmemeli
        # (Bu testin geçmesi = offline block var ama bus onu çağırmamış)
