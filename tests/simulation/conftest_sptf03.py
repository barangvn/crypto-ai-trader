import pytest
from decimal import Decimal
from typing import List, Optional

from app.contracts.portfolio import PortfolioSnapshot, Position, PositionSide
from app.contracts.canonical import QualityFlags
from app.contracts.types import Symbol, ULID


def make_ts(minutes_from_base: int, base_str: str = "2026-01-15T12:00:00.000Z") -> str:
    """Generate UTC Instant Z — minutes_from_base. base = 2026-01-15T12:00:00Z."""
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    dt = base + timedelta(minutes=minutes_from_base)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def make_snapshot(
    *,
    minutes_delta: int,
    realized: Decimal = Decimal("0"),
    fees_total: Decimal = Decimal("0"),
    equity: Decimal = Decimal("10000"),
    exposure: Decimal = Decimal("0"),
    cash: Decimal = Decimal("10000"),
    unrealized: Decimal = Decimal("0"),
    drawdown: float = 0.0,
    peak: Optional[Decimal] = None,
    snapshot_id: Optional[ULID] = None,
    corr: ULID = "CORR_TEST_SPTF03_0001",
    caus: ULID = "CAUS_TEST_SPTF03_0001",
    positions: Optional[List[Position]] = None,
    account_ref: str = "ACC_TEST",
) -> PortfolioSnapshot:
    def _pad_ulidish(val: str, prefix: str) -> str:
        if not isinstance(val, str):
            val = str(val)
        if len(val) >= 8:
            return val
        # Sadece eksikse minimum 8 karaktere pad'le — zaten prefix varsa dokunma
        need = 8 - len(val)
        if need > 0:
            val = val + ("_" * need)
        return val
    if peak is None:
        peak = equity
    sid_raw = snapshot_id or f"SNAP_{minutes_delta:06d}_{abs(hash((minutes_delta, str(realized))))}"
    # Snapshot id de ≥8 olmalı
    if isinstance(sid_raw, str) and len(sid_raw) < 8:
        sid = sid_raw.ljust(8, "_")
    else:
        sid = sid_raw
    corr_padded = _pad_ulidish(corr, "CORR_")
    caus_padded = _pad_ulidish(caus, "CAUS_")
    return PortfolioSnapshot(
        snapshot_id=sid,
        account_ref=account_ref,
        ts=make_ts(minutes_delta),
        cash_quote=cash,
        equity_quote=equity,
        realized_pnl_quote_24h=realized,
        unrealized_pnl_quote=unrealized,
        fees_quote_total=fees_total,
        exposure_notional=exposure,
        drawdown_pct=drawdown,
        peak_equity_quote=peak,
        correlation_id=corr_padded,
        causation_id=caus_padded,
        positions_snapshot=positions,
    )


def make_quality_flags(
    *,
    invalid: bool = False,
    quarantined: bool = False,
    missing: bool = False,
    stale: bool = False,
    degraded: bool = False,
    duplicate: bool = False,
    out_of_order: bool = False,
) -> QualityFlags:
    return QualityFlags(
        invalid=invalid,
        quarantined=quarantined,
        missing=missing,
        stale=stale,
        degraded=degraded,
        duplicate=duplicate,
        out_of_order=out_of_order,
    )


def attach_quality(snap: PortfolioSnapshot, qf: QualityFlags) -> PortfolioSnapshot:
    """Attach quality_flags attribute (frozen dataclass QualityFlags S-CON-02A frozen; not PortfolioSnapshot own field)."""
    object.__setattr__(snap, "quality_flags", qf)
    return snap
