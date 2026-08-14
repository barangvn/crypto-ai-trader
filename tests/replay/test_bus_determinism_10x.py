from __future__ import annotations

"""DoD-11: Determinism 10x — aynı 100 event 10 kez publish → her şey derin-eşit."""

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


EVENT_TYPES = ["candle.v1"] * 40 + ["market_tick.v1"] * 30 + ["trade_event.v1"] * 30


def _make_env(idx: int, event_type: str) -> CanonicalEventEnvelope:
    ts = format_instant()
    payload = Candle(
        timeframe="1m", open_time=ts, close_time=ts,
        open=65000 + idx, high=65100 + idx, low=64900 + idx,
        close=65050 + idx, volume=1.0 + idx * 0.01, closed=True,
    )
    return CanonicalEventEnvelope(
        event_id=ULID(f"01930000-0000-7000-8000-{idx:012d}"),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source=f"determ-{idx}",
        timestamp=ts, ingest_ts=ts,
        correlation_id=ULID("01930000-0000-7000-8000-0000000000C1"),
        causation_id=ULID(f"01930000-0000-7000-8000-{idx:012d}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


def _build_fixture_events() -> list[CanonicalEventEnvelope]:
    out: list[CanonicalEventEnvelope] = []
    for i, et in enumerate(EVENT_TYPES):
        out.append(_make_env(i, et))
    return out


def _build_bus_with_subscribers() -> tuple[InMemoryTypedEventBus, list[dict[str, int]]]:
    bus = InMemoryTypedEventBus()
    counters: list[dict[str, int]] = [
        {"n": 0}, {"n": 0}, {"n": 0}, {"n": 0},
    ]

    def cb_candle(e, c=counters[0]):
        c["n"] += 1

    def cb_tick(e, c=counters[1]):
        c["n"] += 1

    def cb_trade(e, c=counters[2]):
        c["n"] += 1

    def cb_all(e, c=counters[3]):
        c["n"] += 1

    bus.subscribe_typed("candle.v1", cb_candle)
    bus.subscribe_typed("market_tick.v1", cb_tick)
    bus.subscribe_typed("trade_event.v1", cb_trade)
    bus.subscribe_typed("*", cb_all)
    return bus, counters


def _signature(bus: InMemoryTypedEventBus, counters_snapshot: list[dict[str, int]]):
    pub_sig = [
        (str(e.event_id), e.event_type, str(e.correlation_id), str(e.causation_id))
        for e in bus.published
    ]
    dlq_sig = [
        (dl.dlq_code, dl.envelope_event_id, dl.subscription_token_id, dl.exc_type_name)
        for dl in bus.dead_letters
    ]
    return (pub_sig, dlq_sig, [c["n"] for c in counters_snapshot])


@pytest.mark.replay
class TestBusDeterminismTenRuns:
    def test_published_list_and_order_deterministic_ten_runs(self) -> None:
        events_template = _build_fixture_events()
        assert len(events_template) == 100
        signatures: list = []
        for run in range(10):
            bus, counters = _build_bus_with_subscribers()
            # Her run için TEMİZ fixtures (aynı event_id & event_type & corr/caus)
            events = _build_fixture_events()
            bus.publish_many(events)
            sig = _signature(bus, counters)
            signatures.append(sig)
        first = signatures[0]
        for idx, other in enumerate(signatures[1:], start=2):
            assert other == first, (
                f"Run {idx} differs from Run 1; "
                f"pub count: {len(other[0])} vs {len(first[0])}; "
                f"counters {other[2]} vs {first[2]}"
            )
        # Fixture büyüklüğünü doğrula
        pub_count, counters_n = len(first[0]), first[2]
        assert pub_count == 100
        assert counters_n == [40, 30, 30, 100]  # type + wildcard

    def test_dlq_deterministic_with_injected_failures(self) -> None:
        """Bazı subscriber'lar raise eder; 10 run DLQ sırası aynı olmalı."""
        signatures: list = []
        for run in range(10):
            bus = InMemoryTypedEventBus()

            def err_cb(e):
                raise ValueError(f"deterministic-boom-{e.event_id}")

            def ok_cb(e):
                return None

            bus.subscribe_typed("candle.v1", err_cb)
            bus.subscribe_typed("candle.v1", ok_cb)
            events = _build_fixture_events()
            bus.publish_many(events)
            dlq_sig = [
                (dl.dlq_code, dl.envelope_event_id, dl.exc_message[:40])
                for dl in bus.dead_letters
            ]
            signatures.append((len(bus.published), dlq_sig))
        for other in signatures[1:]:
            assert other == signatures[0]
        # 40 candle → 40 tane E_SUBSCRIBER_EXC (sadece ilk cb raise, ikincisi OK)
        assert signatures[0][0] == 100
        assert len(signatures[0][1]) == 40
        assert all(x[0] == "E_SUBSCRIBER_EXC" for x in signatures[0][1])
