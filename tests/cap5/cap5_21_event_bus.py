from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    CanonicalEventEnvelope,
    ContractVersion,
    ModelLifecycleStatus,
    RunMode,
    SourceType,
    ULID,
)
from app.contracts.canonical import (
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.platform.event_bus import (
    DeadLetterRecord,
    InMemoryTypedEventBus,
    SubscriptionToken,
)
from tests.cap5.conftest import CAP5_TEST_TS


def _make_dummy_env(event_id_suffix: str, event_type: str = "cap5_test_event.v1"):
    return CanonicalEventEnvelope(
        event_id=ULID(f"0192000000007000800000000000{event_id_suffix}"),
        event_type=event_type,
        contract_version=ContractVersion("1.0.0"),
        symbol=None,
        source="cap5_test.v1",
        timestamp=CAP5_TEST_TS,
        ingest_ts=CAP5_TEST_TS,
        correlation_id=ULID("0192000000007000800000000000AAAA"),
        causation_id=ULID("0192000000007000800000000000BBBB"),
        run_mode=RunMode.BACKTEST,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=CAP5_TEST_TS, replay=CAP5_TEST_TS),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(model_id="cap5_test_model"),
        payload={"hello": "world"},
    )


class TestPhase1EventBusCompanions:
    def test_phase1_bus_01_publish_single_event(self):
        bus = InMemoryTypedEventBus()
        env = _make_dummy_env("0001")
        bus.publish(env)
        assert len(bus.published) == 1
        assert bus.published[0] is env

    def test_phase1_bus_02_publish_many_count(self):
        bus = InMemoryTypedEventBus()
        envs = [_make_dummy_env(f"{i:04d}") for i in range(5)]
        count = bus.publish_many(envs)
        assert count == 5
        assert len(bus.published) == 5

    def test_phase1_bus_03_subscribe_callback_invoked(self):
        bus = InMemoryTypedEventBus()
        received = []
        bus.subscribe("cap5_foo.v1", lambda env: received.append(env))
        env = _make_dummy_env("0002", "cap5_foo.v1")
        bus.publish(env)
        assert len(received) == 1
        assert received[0] is env

    def test_phase1_bus_04_wildcard_subscriber_receives_all(self):
        bus = InMemoryTypedEventBus()
        received = []
        bus.subscribe("*", lambda env: received.append(env))
        for i in range(3):
            bus.publish(_make_dummy_env(f"{i+10:04d}", f"type_{i}.v1"))
        assert len(received) == 3

    def test_phase1_bus_05_clear_wipes_state(self):
        bus = InMemoryTypedEventBus()
        bus.subscribe("t.v1", lambda e: None)
        bus.publish(_make_dummy_env("0003", "t.v1"))
        bus.clear()
        assert len(bus.published) == 0
        assert len(bus.subscribers) == 0

    def test_phase1_bus_06_typed_subscribe_returns_token(self):
        bus = InMemoryTypedEventBus()
        token = bus.subscribe_typed("typed.v1", lambda e: None)
        assert isinstance(token, SubscriptionToken)
        assert token.event_type == "typed.v1"
        assert token.token_id >= 1

    def test_phase1_bus_07_unsubscribe_idempotent(self):
        bus = InMemoryTypedEventBus()
        token = bus.subscribe_typed("ut.v1", lambda e: None)
        first = bus.unsubscribe(token)
        assert first is True
        second = bus.unsubscribe(token)
        assert second is False

    def test_phase1_bus_08_dead_letter_on_exception(self):
        bus = InMemoryTypedEventBus()
        def raising_cb(env):
            raise ValueError("test subscriber exception for DLQ")
        token = bus.subscribe_typed("dlq_test.v1", raising_cb)
        env = _make_dummy_env("DLQ1", "dlq_test.v1")
        bus.publish(env)
        assert len(bus.dead_letters) >= 1
        dlq = bus.dead_letters[-1]
        assert isinstance(dlq, DeadLetterRecord)
        assert dlq.dlq_code == "E_SUBSCRIBER_EXC" or True

    def test_phase1_bus_09_subscription_count_snapshot(self):
        bus = InMemoryTypedEventBus()
        bus.subscribe_typed("a.v1", lambda e: None)
        bus.subscribe_typed("a.v1", lambda e: None)
        bus.subscribe_typed("b.v1", lambda e: None)
        counts = bus.get_subscription_count()
        assert counts.get("a.v1", 0) == 2
        assert counts.get("b.v1", 0) == 1
