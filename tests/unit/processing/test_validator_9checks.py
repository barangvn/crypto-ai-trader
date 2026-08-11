from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.contracts import CONTRACT_VERSION, RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Instant, Symbol, ULID
from app.processing import DataQualityMonitor, Normalizer, set_clock_ref_for_replay


def _make_envelope(
    *,
    timestamp: Instant,
    open_time: Instant,
    symbol: str = "BTC_USDT",
    open: Decimal = Decimal("65000"),
    high: Decimal = Decimal("65100"),
    low: Decimal = Decimal("64900"),
    close: Decimal = Decimal("65050"),
    volume: Decimal = Decimal("1.0"),
    raw_sequence: int | None = None,
    spread_bps: float | None = None,
    source: str = "test",
    event_type: str = "candle.v1",
) -> CanonicalEventEnvelope:
    ts = format_instant()
    payload = Candle(
        timeframe="1m",
        open_time=open_time,
        close_time=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        closed=True,
    )
    extra = {}
    if raw_sequence is not None:
        extra["raw_sequence"] = raw_sequence
    if spread_bps is not None:
        extra["spread_bps"] = spread_bps
    return CanonicalEventEnvelope(
        event_id=ULID("01920000-0000-7000-8000-000000000010"),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=Symbol(symbol),
        source=source,
        timestamp=timestamp,
        ingest_ts=ts,
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID("01920000-0000-7000-8000-000000000010"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=timestamp),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        extra=extra,
        payload=payload,
    )


def test_check_stale():
    qm = DataQualityMonitor()
    old_dt = datetime.now(timezone.utc) - timedelta(days=400)
    old_ts = format_instant(old_dt)
    env = _make_envelope(timestamp=old_ts, open_time=old_ts)
    qm.validate_one(env)
    assert env.quality_flags.stale is True
    assert env.quality_flags.degraded is True


def test_check_missing_sequence_gap():
    dt_base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    ts1 = format_instant(dt_base)
    ts3 = format_instant(dt_base + timedelta(minutes=2))
    dt_now = dt_base + timedelta(minutes=3)
    now_ts = format_instant(dt_now)

    def now_provider() -> str:
        return now_ts

    qm = DataQualityMonitor(
        stale_threshold_ms=1000 * 60 * 60 * 24,
        now_provider=now_provider,
    )
    env1 = _make_envelope(
        timestamp=ts1, open_time=ts1, raw_sequence=1,
    )
    env1.event_id = ULID("01920000-0000-7000-8000-000000000011")
    env2 = _make_envelope(
        timestamp=ts3, open_time=ts3, raw_sequence=3,
    )
    env2.event_id = ULID("01920000-0000-7000-8000-000000000012")
    qm.validate_one(env1)
    qm.validate_one(env2)
    assert env2.quality_flags.duplicate is False
    assert env2.quality_flags.invalid is False
    assert env2.quality_flags.stale is False
    assert env2.quality_flags.out_of_order is False
    assert env2.quality_flags.missing is True
    reason_codes = [r.get("code") for r in env2.quality_flags.reasons]
    assert any("SEQUENCE_GAP" in c for c in reason_codes if isinstance(c, str))


def test_check_duplicate_event():
    qm = DataQualityMonitor()
    ts = format_instant()
    env1 = _make_envelope(timestamp=ts, open_time=ts)
    env1.event_id = ULID("01920000-0000-7000-8000-000000000013")
    env2 = _make_envelope(timestamp=ts, open_time=ts)
    env2.event_id = ULID("01920000-0000-7000-8000-000000000014")
    qm.validate_one(env1)
    qm.validate_one(env2)
    assert env2.quality_flags.duplicate is True
    assert env2.quality_flags.quarantined is True


def test_check_out_of_order_timestamp():
    qm = DataQualityMonitor()
    dt_a = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    dt_b = dt_a - timedelta(minutes=1)
    ts_a = format_instant(dt_a)
    ts_b = format_instant(dt_b)
    env_a = _make_envelope(timestamp=ts_a, open_time=ts_a)
    env_a.event_id = ULID("01920000-0000-7000-8000-000000000015")
    env_b = _make_envelope(timestamp=ts_b, open_time=ts_b)
    env_b.event_id = ULID("01920000-0000-7000-8000-000000000016")
    qm.validate_one(env_a)
    qm.validate_one(env_b)
    assert env_b.quality_flags.out_of_order is True
    assert env_b.quality_flags.quarantined is True


def test_check_invalid_price_negative():
    qm = DataQualityMonitor()
    ts = format_instant()
    env = _make_envelope(
        timestamp=ts, open_time=ts, open=Decimal("-1"),
    )
    qm.validate_one(env)
    assert env.quality_flags.invalid is True
    assert env.quality_flags.quarantined is True


def test_check_invalid_volume_negative_or_zero():
    qm = DataQualityMonitor()
    ts = format_instant()
    env_zero = _make_envelope(
        timestamp=ts, open_time=ts, volume=Decimal(0),
    )
    qm.validate_one(env_zero)
    assert env_zero.quality_flags.invalid is True
    assert env_zero.quality_flags.quarantined is True

    qm2 = DataQualityMonitor()
    env_neg = _make_envelope(
        timestamp=ts, open_time=ts, volume=Decimal("-1"),
    )
    qm2.validate_one(env_neg)
    assert env_neg.quality_flags.invalid is True
    assert env_neg.quality_flags.quarantined is True


def test_check_abnormal_spread():
    qm = DataQualityMonitor()
    ts = format_instant()
    env = _make_envelope(
        timestamp=ts, open_time=ts, spread_bps=6000,
    )
    qm.validate_one(env)
    assert env.quality_flags.degraded is True
    reason_codes = [r.get("code") for r in env.quality_flags.reasons]
    assert "ABNORMAL_SPREAD" in reason_codes


def test_check_timestamp_format_or_future_drift():
    qm = DataQualityMonitor()
    future_dt = datetime(2100, 1, 1, tzinfo=timezone.utc)
    future_ts = format_instant(future_dt)
    env = _make_envelope(timestamp=future_ts, open_time=future_ts)
    qm.validate_one(env)
    assert env.quality_flags.invalid is True
    assert env.quality_flags.quarantined is True


def test_check_high_less_than_low():
    qm = DataQualityMonitor()
    ts = format_instant()
    env = _make_envelope(
        timestamp=ts,
        open_time=ts,
        high=Decimal("64000"),
        low=Decimal("65000"),
    )
    qm.validate_one(env)
    assert env.quality_flags.invalid is True
    reason_codes = [r.get("code") for r in env.quality_flags.reasons]
    assert "INVALID_PRICE_RANGE" in reason_codes
