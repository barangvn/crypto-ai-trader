from __future__ import annotations

"""CAP-2: 7 quality bayrağı publish/subscribe yoluyla değişmeden korunur."""

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


def _quality_sets() -> list[QualityFlags]:
    return [
        # Clean
        QualityFlags(),
        # Stale + missing (degraded=True otomatik)
        QualityFlags(
            stale=True,
            missing=True,
            reasons=[{"code": "S1"}, {"code": "M1"}],
            staleness_ms=1500,
            dedup_key="K-abc",
        ),
        # Duplicate + out_of_order + quarantined
        QualityFlags(
            duplicate=True,
            out_of_order=True,
            quarantined=True,
            reasons=[{"code": "D1"}, {"code": "OOO1"}, {"code": "Q1"}],
            expected_sequence=10,
            actual_sequence=11,
        ),
    ]


def _make_env(idx: int, qf: QualityFlags) -> CanonicalEventEnvelope:
    import copy

    qf_copy = copy.deepcopy(qf)
    ts = format_instant()
    payload = Candle(
        timeframe="1m", open_time=ts, close_time=ts,
        open=1, high=2, low=0, close=1, volume=1, closed=True,
    )
    return CanonicalEventEnvelope(
        event_id=ULID(f"01920000-0000-7000-8000-000000000B{idx:02d}"),
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=Symbol("BTC_USDT"),
        source="qtest",
        timestamp=ts, ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-0000000000C1"),
        causation_id=ULID(f"01920000-0000-7000-8000-000000000B{idx:02d}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=qf_copy,
        schema_ref=SchemaRef(),
        payload=payload,
    )


def _same_flags(a: QualityFlags, b: QualityFlags) -> None:
    assert a.stale == b.stale
    assert a.missing == b.missing
    assert a.duplicate == b.duplicate
    assert a.out_of_order == b.out_of_order
    assert a.invalid == b.invalid
    assert a.quarantined == b.quarantined
    assert a.degraded == b.degraded
    assert a.staleness_ms == b.staleness_ms
    assert a.dedup_key == b.dedup_key
    assert a.expected_sequence == b.expected_sequence
    assert a.actual_sequence == b.actual_sequence
    assert a.reasons == b.reasons


def test_cap2_quality_flags_unmodified_through_bus():
    """3 farklı kalite seti → publish → subscriber gördüğü ve published log
    içindeki zarfların kalite bayrakları aynen korunur."""
    bus = InMemoryTypedEventBus()
    sets = _quality_sets()
    originals = []
    envs = []
    for i, qf in enumerate(sets):
        originals.append((i, qf))
        envs.append(_make_env(i, qf))

    seen_by_subscriber: list[CanonicalEventEnvelope] = []

    def subscriber(e):
        import copy
        seen_by_subscriber.append(copy.deepcopy(e))

    bus.subscribe_typed("candle.v1", subscriber, accept_quarantined=True)
    bus.subscribe_typed("*", subscriber, accept_quarantined=True)

    for env in envs:
        bus.publish(env)

    # Published log + subscriber her 3 event için 2 kez (type + wildcard) = 6 kayıt
    assert len(bus.published) == 3
    assert len(seen_by_subscriber) == 6

    for i, qf in originals:
        _same_flags(qf, bus.published[i].quality_flags)

    # İlk 3 subscriber (type subscriber) hepsini görmeli
    for i in range(3):
        _same_flags(bus.published[i].quality_flags, seen_by_subscriber[i * 2].quality_flags)
        _same_flags(bus.published[i].quality_flags, seen_by_subscriber[i * 2 + 1].quality_flags)


def test_quarantine_typed_subscriber_skips_but_log_preserves_qf():
    """accept_quarantined=false olan subscriber quarantined'i atlasa da
    published log'daki kalite bayrakları değişmez."""
    bus = InMemoryTypedEventBus()
    qf = QualityFlags(quarantined=True, reasons=[{"code": "Q"}])
    env = _make_env(0, qf)
    before = {
        "stale": qf.stale, "missing": qf.missing, "duplicate": qf.duplicate,
        "out_of_order": qf.out_of_order, "invalid": qf.invalid,
        "quarantined": qf.quarantined, "degraded": qf.degraded,
        "reasons": list(qf.reasons),
    }
    t_skip = bus.subscribe_typed("candle.v1", lambda e: None)  # accept_quarantined=False default
    bus.publish(env)
    assert len(bus.published) == 1
    after = bus.published[0].quality_flags
    assert before["quarantined"] is True and after.quarantined is True
    assert before["degraded"] is True and after.degraded is True
    assert before["reasons"] == after.reasons
    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0].dlq_code == "E_QUARANTINED_SKIP"
    assert bus.dead_letters[0].subscription_token_id == t_skip.token_id
