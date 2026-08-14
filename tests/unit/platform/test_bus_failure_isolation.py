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
from app.platform.event_bus import InMemoryTypedEventBus


def _make_env(event_id_suffix: str, event_type: str = "candle.v1",
              qf: QualityFlags | None = None, contract_version: str = CONTRACT_VERSION):
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


# ============ Grup 4 — Subscriber Failure Isolation (AC-21..AC-24) ============


def test_AC21_typed_cb_exception_isolated_other_cbs_continue():
    """AC-21: cb1 OK, cb2 raise, cb3 OK → cb1+cb3 çağrılır. DLQ 1 tane E_SUBSCRIBER_EXC.
    Exception publish çağıranına YAYILMAZ."""
    bus = InMemoryTypedEventBus()
    trace: list[str] = []

    def cb1(e):
        trace.append("cb1")

    def cb2(e):
        trace.append("cb2")
        raise ValueError("simulate bad subscriber")

    def cb3(e):
        trace.append("cb3")

    bus.subscribe_typed("candle.v1", cb1)
    bus.subscribe_typed("candle.v1", cb2)
    bus.subscribe_typed("candle.v1", cb3)
    env = _make_env("000000000801")
    try:
        bus.publish(env)
    except Exception:
        pytest.fail("Typed subscriber exceptions MUST NOT propagate to publisher")
    assert trace == ["cb1", "cb2", "cb3"]
    assert len(bus.dead_letters) == 1
    dl = bus.dead_letters[0]
    assert dl.dlq_code == "E_SUBSCRIBER_EXC"
    assert dl.exc_type_name == "ValueError"
    assert "simulate bad subscriber" in (dl.exc_message or "")
    assert dl.envelope_event_id == str(env.event_id)


def test_AC22_compat_cb_exception_propagates_stops_chain():
    """AC-22: compat (eski subscribe) raise → publish çağıranına yayılır.
    Önceki typed çağrılmış olabilir ama sonraki cb'ler durur."""
    bus = InMemoryTypedEventBus()
    trace: list[str] = []

    def t1(e):
        trace.append("typed_before")

    def compat_cb(e):
        trace.append("compat")
        raise ValueError("legacy boom")

    def t2(e):
        trace.append("typed_after")

    bus.subscribe_typed("candle.v1", t1)
    # ÖNEMLİ: compat, typed subscriber'lardan ÖNCE (publish sıralamasına göre)
    # Sıra: compat type_cbs loop, sonra compat wildcard loop, SONRA typed dispatch.
    # Yani compat type_cb içinde raise → typed subscribers çağrılmaz.
    bus2 = InMemoryTypedEventBus()
    bus2.subscribe("candle.v1", compat_cb)
    bus2.subscribe_typed("candle.v1", t2)
    env = _make_env("000000000802")
    with pytest.raises(ValueError, match="legacy boom"):
        bus2.publish(env)
    # Compat raise olduğu için t2 (typed) çağrılmadı
    # (sıra: compat type_cb → raise → typed dispatch'e ULAŞILMADI)
    assert "compat" in trace
    assert "typed_after" not in trace


def test_AC23_quarantined_event_typed_subscribers_filtered_accept_flag():
    """AC-23: S1 accept_quarantined=True (aldı), S2/S3 default=False (almadı).
    DLQ'da 2× E_QUARANTINED_SKIP."""
    bus = InMemoryTypedEventBus()
    counters: dict[str, int] = {"S1": 0, "S2": 0, "S3": 0}
    bus.subscribe_typed(
        "candle.v1",
        lambda e, c=counters: c.update(S1=c["S1"] + 1),
        accept_quarantined=True,
    )
    bus.subscribe_typed("candle.v1", lambda e, c=counters: c.update(S2=c["S2"] + 1))
    bus.subscribe_typed("candle.v1", lambda e, c=counters: c.update(S3=c["S3"] + 1))
    qf = QualityFlags(quarantined=True, reasons=[{"code": "test_q"}])
    env = _make_env("000000000803", qf=qf)
    bus.publish(env)
    assert counters == {"S1": 1, "S2": 0, "S3": 0}
    assert len(bus.published) == 1  # published log korur
    skip_codes = [dl.dlq_code for dl in bus.dead_letters if dl.dlq_code == "E_QUARANTINED_SKIP"]
    assert len(skip_codes) == 2


def test_AC24_mixed_dlq_records_counted_correctly():
    """AC-24: 1 cb hatası + 1 cycle + 1 depth + 2 quarantine → her koddan en az 1."""
    # --- 1 subscriber failure (E_SUBSCRIBER_EXC) ---
    bus_fail = InMemoryTypedEventBus()

    def bad_cb(e):
        raise RuntimeError("fail-1")

    bus_fail.subscribe_typed("candle.v1", bad_cb)
    bus_fail.publish(_make_env("000000000950", event_type="candle.v1"))
    assert any(dl.dlq_code == "E_SUBSCRIBER_EXC" for dl in bus_fail.dead_letters)

    # --- 1 cycle (E_CYCLE_DETECTED) ---
    bus_cycle = InMemoryTypedEventBus()
    e1 = _make_env("000000000961")
    e1.causation_id = e1.event_id
    bus_cycle.publish(e1)
    collide = _make_env("000000000961")  # aynı id
    bus_cycle.publish_with_causation(collide, str(e1.event_id))
    assert any(dl.dlq_code == "E_CYCLE_DETECTED" for dl in bus_cycle.dead_letters)

    # --- 1 depth (E_CAUSATION_DEPTH) ---
    bus_depth = InMemoryTypedEventBus()
    first = _make_env("DEADBEEF0000")
    first.causation_id = first.event_id
    bus_depth.publish(first)
    prev = str(first.event_id)
    # 31 tane daha ekle → 32 event. 33. event için ancestors sayısı 32
    for i in range(1, 32):
        child = _make_env(f"CAFEBABE{i:04d}")
        bus_depth.publish_with_causation(child, prev)
        prev = str(child.event_id)
    assert len(bus_depth.published) == 32
    too_deep = _make_env("FFFFFFFFFFFF")
    bus_depth.publish_with_causation(too_deep, prev)
    assert len(bus_depth.published) == 32  # 33. yayınlanmadı
    dlq_codes_depth = [dl.dlq_code for dl in bus_depth.dead_letters]
    assert "E_CAUSATION_DEPTH" in dlq_codes_depth, (
        "Expected E_CAUSATION_DEPTH in bus_depth dead_letters, got: "
        f"{dlq_codes_depth}"
    )

    # --- 2 quarantine skip (E_QUARANTINED_SKIP) ---
    bus_q = InMemoryTypedEventBus()
    bus_q.subscribe_typed("c.v1", lambda e: None)
    bus_q.subscribe_typed("c.v1", lambda e: None)
    qf = QualityFlags(quarantined=True)
    bus_q.publish(_make_env("000000000998", event_type="c.v1", qf=qf))
    q_skips = [dl for dl in bus_q.dead_letters if dl.dlq_code == "E_QUARANTINED_SKIP"]
    assert len(q_skips) == 2

    # Birlikte 4 kod da doğru şekilde üretildi
    all_codes = set()
    for b in (bus_fail, bus_cycle, bus_depth, bus_q):
        for dl in b.dead_letters:
            all_codes.add(dl.dlq_code)
    for required in [
        "E_SUBSCRIBER_EXC",
        "E_CYCLE_DETECTED",
        "E_CAUSATION_DEPTH",
        "E_QUARANTINED_SKIP",
    ]:
        assert required in all_codes, f"Missing {required} in combined codes: {all_codes}"


def test_dlq_fifo_order_preserved():
    """Yardımcı: DLQ kayıtları first-fail-first-record sırasında (FIFO)."""
    bus = InMemoryTypedEventBus()
    records: list[str] = []

    def err_a(e):
        raise RuntimeError("A")

    def err_b(e):
        raise RuntimeError("B")

    def err_c(e):
        raise RuntimeError("C")

    bus.subscribe_typed("a.v1", err_a)
    bus.subscribe_typed("b.v1", err_b)
    bus.subscribe_typed("c.v1", err_c)
    for tag in ["a", "b", "c"]:
        env = _make_env(f"00000000085{tag}", event_type=f"{tag}.v1")
        bus.publish(env)
    msgs = [dl.exc_message for dl in bus.dead_letters]
    assert len(msgs) == 3
    assert "A" in msgs[0]
    assert "B" in msgs[1]
    assert "C" in msgs[2]
