from __future__ import annotations

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
              corr_id_suffix: str | None = None, cause_id_suffix: str | None = None,
              set_corr: bool = True, contract_version: str = CONTRACT_VERSION):
    ts = format_instant()
    payload = Candle(
        timeframe="1m", open_time=ts, close_time=ts,
        open=65000, high=65100, low=64900, close=65050,
        volume=1.0, closed=True,
    )
    corr_suffix = corr_id_suffix if corr_id_suffix is not None else "000000000001"
    caus_suffix = cause_id_suffix if cause_id_suffix is not None else event_id_suffix
    corr_val = ULID(f"01920000-0000-7000-8000-{corr_suffix}") if set_corr else None
    return CanonicalEventEnvelope(
        event_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        event_type=event_type,
        contract_version=contract_version,
        symbol=Symbol("BTC_USDT"),
        source="test",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=corr_val,  # type: ignore[arg-type]
        causation_id=ULID(f"01920000-0000-7000-8000-{caus_suffix}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


def _uid(suffix: str) -> str:
    return f"01920000-0000-7000-8000-{suffix}"


# ============ Grup 3 — Correlation / Causation (AC-15..AC-20) ============


def test_AC15_correlation_copied_from_parent_causation_set():
    """AC-15: E2 correlation None iken parent E1'den C1 kopyalanır.
    causation_id=E1.event_id. trace [E2,E1]."""
    bus = InMemoryTypedEventBus()
    e1_id_suffix = "000000000301"
    e1_corr_suffix = "0000000000C1"
    e1 = _make_env(e1_id_suffix, corr_id_suffix=e1_corr_suffix)
    # İlk halkada causation_id == kendi event_id olmalı (CONTRACTS §1)
    e1.causation_id = e1.event_id
    bus.publish(e1)

    e2 = _make_env("000000000302", set_corr=False)
    # correlation_id = None iken, parent'tan alınmalı
    bus.publish_with_causation(e2, parent_event_id=str(e1.event_id))

    assert len(bus.published) == 2
    assert str(e2.correlation_id) == str(e1.correlation_id)
    assert str(e2.causation_id) == str(e1.event_id)

    chain = bus.trace_causation_chain(str(e2.event_id))
    assert chain == [str(e2.event_id), str(e1.event_id)]


def test_AC16_causation_depth_32_exceeded_33rd_event_blocked():
    """AC-16: max_depth=32 (default). 33. event → E_CAUSATION_DEPTH DLQ,
    published 33. yok."""
    bus = InMemoryTypedEventBus()
    first = _make_env("000000000400")
    first.causation_id = first.event_id
    bus.publish(first)
    prev_id = str(first.event_id)
    for i in range(1, 32):
        suffix = f"0000000004{i:02d}"
        child = _make_env(suffix)
        bus.publish_with_causation(child, parent_event_id=prev_id)
        prev_id = str(child.event_id)
    assert len(bus.published) == 32
    assert len(bus.dead_letters) == 0

    # 33. event: ancestors sayısı 32 olacak, depth 32 ≥ 32 → aborts
    last = _make_env("000000000499")
    bus.publish_with_causation(last, parent_event_id=prev_id)
    assert len(bus.published) == 32  # 33. publish edilmedi
    assert len(bus.dead_letters) >= 1
    codes = [dl.dlq_code for dl in bus.dead_letters]
    assert "E_CAUSATION_DEPTH" in codes, f"Expected E_CAUSATION_DEPTH in {codes}"


def test_AC17_cycle_detection_prevents_publish():
    """AC-17: E1→E2→E3→ELT(E1 id collides with ancestor) → CYCLE → DLQ E_CYCLE_DETECTED."""
    bus = InMemoryTypedEventBus()
    e1 = _make_env("000000000501")
    e1.causation_id = e1.event_id
    bus.publish(e1)
    e2 = _make_env("000000000502")
    bus.publish_with_causation(e2, str(e1.event_id))
    e3 = _make_env("000000000503")
    bus.publish_with_causation(e3, str(e2.event_id))
    assert len(bus.published) == 3

    # Aynı event_id ile ELT = E1 event_id (id çakışması) — E3'ün çocuğu
    elt = _make_env("000000000501")  # ⚠️ Aynı id
    elt.causation_id = e3.event_id
    bus.publish_with_causation(elt, str(e3.event_id))
    assert len(bus.published) == 3  # ELT publish edilmedi
    codes = [dl.dlq_code for dl in bus.dead_letters]
    assert "E_CYCLE_DETECTED" in codes


def test_AC18_missing_parent_id_still_publishes_tolerant():
    """AC-18: parent bulunamaz (OLMAYAN-EVENT-99999) → publish YAPILIR, no DLQ."""
    bus = InMemoryTypedEventBus()
    env = _make_env("000000000510")
    bus.publish_with_causation(env, parent_event_id="OLMAYAN-EVENT-999999")
    assert len(bus.published) == 1
    assert str(env.causation_id) == "OLMAYAN-EVENT-999999"
    assert len(bus.dead_letters) == 0  # tolerans


def test_AC19_two_parallel_causation_chains_independent():
    """AC-19: C1 zinciri A→B→C, C2 zinciri X→Y→Z. trace'ler karışmaz."""
    bus = InMemoryTypedEventBus()
    corr_a = "000000000C01"
    corr_x = "000000000C02"

    a = _make_env("000000000601", corr_id_suffix=corr_a)
    a.causation_id = a.event_id
    bus.publish(a)
    b = _make_env("000000000602", corr_id_suffix=corr_a)
    bus.publish_with_causation(b, str(a.event_id))
    c = _make_env("000000000603", corr_id_suffix=corr_a)
    bus.publish_with_causation(c, str(b.event_id))

    x = _make_env("000000000611", corr_id_suffix=corr_x)
    x.causation_id = x.event_id
    bus.publish(x)
    y = _make_env("000000000612", corr_id_suffix=corr_x)
    bus.publish_with_causation(y, str(x.event_id))
    z = _make_env("000000000613", corr_id_suffix=corr_x)
    bus.publish_with_causation(z, str(y.event_id))

    chain_c = bus.trace_causation_chain(str(c.event_id))
    chain_z = bus.trace_causation_chain(str(z.event_id))
    assert chain_c == [str(c.event_id), str(b.event_id), str(a.event_id)]
    assert chain_z == [str(z.event_id), str(y.event_id), str(x.event_id)]
    # Ortak eleman YOK
    assert set(chain_c).isdisjoint(set(chain_z))
    # Correlation id'ler doğru
    assert str(c.correlation_id) != str(z.correlation_id)


def test_AC20_correlation_propagated_down_through_chain():
    """AC-20: E1→E2 (C1). EX corr_id=None, publish_with_causation(EX,E2).
    EX corr_id = C1 olmalı; zincir [EX,E2,E1]."""
    bus = InMemoryTypedEventBus()
    corr_c1 = "000000000C11"
    e1 = _make_env("000000000701", corr_id_suffix=corr_c1)
    e1.causation_id = e1.event_id
    bus.publish(e1)
    e2 = _make_env("000000000702", corr_id_suffix=corr_c1)
    bus.publish_with_causation(e2, str(e1.event_id))
    ex = _make_env("000000000703", set_corr=False)
    bus.publish_with_causation(ex, str(e2.event_id))
    assert str(ex.correlation_id) == str(e1.correlation_id), (
        "EX correlation_id E1'den gelmeli (C1 zinciri)"
    )
    chain = bus.trace_causation_chain(str(ex.event_id))
    assert chain == [str(ex.event_id), str(e2.event_id), str(e1.event_id)]


def test_trace_causation_chain_missing_leaf_returns_empty():
    """Yardımcı: Olmayan leaf için boş liste."""
    bus = InMemoryTypedEventBus()
    assert bus.trace_causation_chain("missing-id") == []


def test_trace_causation_chain_single_root_event():
    """Root event (causation_id == kendi.event_id) için tek elemanlı zincir."""
    bus = InMemoryTypedEventBus()
    e1 = _make_env("000000000750")
    e1.causation_id = e1.event_id
    bus.publish(e1)
    chain = bus.trace_causation_chain(str(e1.event_id))
    assert chain == [str(e1.event_id)]
