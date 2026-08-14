from __future__ import annotations

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
from app.platform.event_bus import InMemoryTypedEventBus, SubscriptionToken


def _make_env(event_id_suffix: str, event_type: str = "candle.v1",
              contract_version: str = CONTRACT_VERSION, qf: QualityFlags | None = None):
    ts = format_instant()
    payload = Candle(
        timeframe="1m", open_time=ts, close_time=ts,
        open=65000, high=65100, low=64900, close=65050,
        volume=1.0, closed=True,
    )
    return CanonicalEventEnvelope(
        event_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        event_type=event_type,
        contract_version=contract_version,
        symbol=Symbol("BTC_USDT"),
        source="test",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=qf if qf is not None else QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


# ============ Grup 2 — Typed Bus + Subscriber Lifecycle (AC-07..AC-14) ============


def test_AC07_subscribe_typed_two_callbacks_registration_order():
    """AC-07: 2 farklı cb, subscribe_typed ile kaydedilince registration order çağrılır."""
    bus = InMemoryTypedEventBus()
    order: list[str] = []

    def cb_a(e):
        order.append("A")

    def cb_b(e):
        order.append("B")

    t_a = bus.subscribe_typed("candle.v1", cb_a)
    t_b = bus.subscribe_typed("candle.v1", cb_b)
    assert isinstance(t_a, SubscriptionToken)
    assert isinstance(t_b, SubscriptionToken)
    assert t_a.token_id < t_b.token_id  # monotonic
    env = _make_env("000000000200")
    bus.publish(env)
    assert order == ["A", "B"]


def test_AC08_subscribe_typed_wrong_event_type_not_delivered():
    """AC-08: yanlış event_type teslim edilmez, DLQ'da yanlış tip için kayıt YOKTUR."""
    bus = InMemoryTypedEventBus()
    counter = {"n": 0}

    def cb(e):
        counter["n"] += 1

    bus.subscribe_typed("market_tick.v1", cb)
    env = _make_env("000000000201", event_type="candle.v1")
    bus.publish(env)
    assert counter["n"] == 0
    # Filter başarılı = DLQ yok
    assert len(bus.dead_letters) == 0


def test_AC09_contract_version_min_passes_when_equal():
    """AC-09: envelope contract_version == contract_version_min → teslim edilir."""
    bus = InMemoryTypedEventBus()
    counter = {"n": 0}

    def cb(e):
        counter["n"] += 1

    bus.subscribe_typed("candle.v1", cb, contract_version_min=(1, 0, 0))
    env = _make_env("000000000202", contract_version="1.0.0")
    bus.publish(env)
    assert counter["n"] == 1
    assert len(bus.dead_letters) == 0


def test_AC10_contract_version_min_too_low_yields_dlq():
    """AC-10: envelope 1.5.0 ama min 2.0.0 → E_CONTRACT_VERSION_MIN DLQ."""
    bus = InMemoryTypedEventBus()
    counter = {"n": 0}

    def cb(e):
        counter["n"] += 1

    tok = bus.subscribe_typed("candle.v1", cb, contract_version_min=(2, 0, 0))
    env = _make_env("000000000203", contract_version="1.5.0")
    bus.publish(env)
    assert counter["n"] == 0
    assert len(bus.dead_letters) == 1
    dl = bus.dead_letters[0]
    assert dl.dlq_code == "E_CONTRACT_VERSION_MIN"
    assert dl.subscription_token_id == tok.token_id
    assert str(env.event_id) == dl.envelope_event_id


def test_AC11_typed_wildcard_subscriber_receives_all_types():
    """AC-11: wildcard typed 3 farklı event tipi için 3 kez çağrılır.
    Her event için type → wildcard order."""
    bus = InMemoryTypedEventBus()
    types_seen: list[str] = []
    order: list[str] = []

    def type_cb(e):
        types_seen.append("type:" + e.event_type)
        order.append("type")

    def wild_cb(e):
        types_seen.append("wild:" + e.event_type)
        order.append("wild")

    bus.subscribe_typed("candle.v1", type_cb)
    bus.subscribe_typed("*", wild_cb)
    for i, et in enumerate(["candle.v1", "market_tick.v1", "paper_order.v1"]):
        env = _make_env(f"0000000002{i+10:02d}", event_type=et)
        bus.publish(env)
    assert types_seen.count("wild:candle.v1") == 1
    assert types_seen.count("wild:market_tick.v1") == 1
    assert types_seen.count("wild:paper_order.v1") == 1
    # candle.v1 → type:wild, diğerleri → sadece wild
    assert order == ["type", "wild", "wild", "wild"]


def test_AC12_unsubscribe_then_double_unsubscribe_idempotent():
    """AC-12: ilk unsubscribe True, ikinci False; artık cb çağrılmaz."""
    bus = InMemoryTypedEventBus()
    counter = {"n": 0}

    def cb(e):
        counter["n"] += 1

    tok = bus.subscribe_typed("candle.v1", cb)
    env1 = _make_env("000000000220")
    bus.publish(env1)
    assert counter["n"] == 1

    r1 = bus.unsubscribe(tok)
    assert r1 is True
    env2 = _make_env("000000000221")
    bus.publish(env2)
    assert counter["n"] == 1  # artık çağrılmadı

    r2 = bus.unsubscribe(tok)
    assert r2 is False  # double unsubscribe idempotent, no raise

    r3 = bus.unsubscribe("not-even-a-token")  # type: ignore[arg-type]
    assert r3 is False


def test_AC13_unicode_and_weird_event_types_accepted_by_bus_string_equality():
    """AC-13: bus event_type ismine takılmaz, sadece string eşitliği yapar."""
    bus = InMemoryTypedEventBus()
    counter_unicode = {"n": 0}
    counter_slash = {"n": 0}

    unicode_type = "weird-ÜNİCODE-⛄-chars.v1"
    slash_type = "my/../slash.dot.notation"

    bus.subscribe_typed(unicode_type, lambda e: counter_unicode.update(n=counter_unicode["n"] + 1))
    bus.subscribe_typed(slash_type, lambda e: counter_slash.update(n=counter_slash["n"] + 1))

    env_u = _make_env("000000000230", event_type=unicode_type)
    env_s = _make_env("000000000231", event_type=slash_type)
    bus.publish(env_u)
    bus.publish(env_s)
    assert counter_unicode["n"] == 1
    assert counter_slash["n"] == 1


def test_AC14_contract_version_min_tuple_shape_validated():
    """AC-14: yanlış tuple boyutu → ValueError; negatif sayı → ValueError."""
    bus = InMemoryTypedEventBus()
    with pytest.raises(ValueError):
        bus.subscribe_typed("c.v1", lambda e: None, contract_version_min=(0,))
    with pytest.raises(ValueError):
        bus.subscribe_typed("c.v1", lambda e: None, contract_version_min=(1, 2, 3, 4))
    with pytest.raises(ValueError):
        bus.subscribe_typed("c.v1", lambda e: None, contract_version_min=(1, -2, 3))
    with pytest.raises(ValueError):
        bus.subscribe_typed("c.v1", lambda e: None, contract_version_min=("a", "b", "c"))  # type: ignore[arg-type]
