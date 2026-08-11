from __future__ import annotations

from decimal import Decimal

from app.contracts import CONTRACT_VERSION, RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Symbol, ULID


def _make_env(event_id_suffix: str, event_type: str = "candle.v1", symbol: str = "BTC_USDT"):
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
    return CanonicalEventEnvelope(
        event_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=Symbol(symbol),
        source="test",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


def test_publish_appends_to_published_log(bus):
    env = _make_env("000000000030")
    bus.publish(env)
    assert len(bus.published) == 1


def test_subscribe_callback_count(bus):
    counter = {"n": 0}

    def cb(evt):
        counter["n"] += 1

    bus.subscribe("candle.v1", cb)
    for i in range(3):
        env = _make_env(f"00000000003{i+1}")
        bus.publish(env)
    assert counter["n"] == 3


def test_subscribe_wildcard_runs_all(bus):
    counter = {"n": 0}

    def cb(evt):
        counter["n"] += 1

    bus.subscribe("*", cb)
    env_a = _make_env("000000000034", event_type="tick.v1")
    env_b = _make_env("000000000035", event_type="candle.v1")
    bus.publish(env_a)
    bus.publish(env_b)
    assert counter["n"] == 2


def test_subscribe_typed_does_not_fire_other_type(bus):
    counter = {"n": 0}

    def cb(evt):
        counter["n"] += 1

    bus.subscribe("tick.v1", cb)
    env = _make_env("000000000036", event_type="candle.v1")
    bus.publish(env)
    assert counter["n"] == 0


def test_correlation_and_causation_ids_preserved(bus):
    env = _make_env("000000000037")
    bus.publish(env)
    assert bus.published[0].correlation_id == env.correlation_id
    assert bus.published[0].causation_id == env.causation_id


def test_deterministic_publish_order_fifo(bus):
    envs = [
        _make_env("000000000038"),
        _make_env("000000000039"),
        _make_env("000000000040"),
    ]
    for e in envs:
        bus.publish(e)
    for i, e in enumerate(envs):
        assert bus.published[i].event_id == e.event_id
