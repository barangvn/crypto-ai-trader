from __future__ import annotations

import pytest
from decimal import Decimal
from typing import Any, Callable, Iterable

from app.contracts import (
    Candle,
    MarketTick,
    QualityFlags,
    Symbol,
)

FIXED_CORR_ID = "CORR-SBKT01-FIXED-000000000001"
FIXED_SYMBOL = "BTC_USDT"
START_TS = "2025-01-01T00:00:00.000Z"
ONE_MIN_MS = 60_000


def _make_qflags(
    *,
    valid: bool = True,
    quarantined: bool = False,
    stale: bool = False,
    duplicate: bool = False,
    out_of_order: bool = False,
    missing: bool = False,
    degraded: bool = False,
    reason_codes: tuple[str, ...] = (),
) -> QualityFlags:
    return QualityFlags(
        invalid=(not valid),
        quarantined=quarantined,
        stale=stale,
        duplicate=duplicate,
        out_of_order=out_of_order,
        missing=missing,
        degraded=degraded,
        reasons=[{"code": c} for c in reason_codes],
    )


def _make_ts(minute_offset: int) -> str:
    base_ms = 1735689600000 + minute_offset * ONE_MIN_MS
    sec = base_ms // 1000
    ms = base_ms % 1000
    ymdhms = __import__("datetime").datetime.utcfromtimestamp(sec).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{ymdhms}.{ms:03d}Z"


class SyntheticBundle:
    def __init__(
        self,
        *,
        num_candles: int = 60,
        start_price: Decimal = Decimal("42000"),
        drift: Decimal = Decimal("0.001"),
        include_ticks: bool = False,
        bundle_id: str = "sbkt-syn-001",
        bundle_version: str = "1.0.0",
        bad_quality_first: bool = False,
        bad_quarantine_nth: int | None = None,
        seed: int = 42,
    ) -> None:
        self.bundle_id = bundle_id
        self.bundle_version = bundle_version
        self.num_candles = num_candles
        self._candles: list[Candle] = []
        self._ticks: list[MarketTick] = []
        p = start_price
        import hashlib
        for i in range(num_candles):
            h = hashlib.sha256(f"{seed}|{i}".encode()).digest()
            delta = (int.from_bytes(h[:4], "big", signed=True) / 2**31) * float(drift) * 100
            open_p = p
            close_p = p * Decimal(str(1 + delta / float(start_price)))
            high_p = max(open_p, close_p) * Decimal("1.002")
            low_p = min(open_p, close_p) * Decimal("0.998")
            volume = Decimal(str(100 + (int.from_bytes(h[4:6], "big") % 500)))
            ts = _make_ts(i)
            ts_next = _make_ts(i + 1)
            quality_kwargs: dict[str, Any] = dict(valid=True)
            if bad_quality_first and i == 0:
                quality_kwargs = dict(valid=False, reason_codes=("BKT-Q-BAD",))
            if bad_quarantine_nth is not None and i % bad_quarantine_nth == 0:
                quality_kwargs = dict(valid=True, quarantined=True, reason_codes=("BKT-Q-QAUR",))
            c = Candle(
                timeframe="1m",
                open_time=ts,
                close_time=ts_next,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                closed=True,
                quote_volume=volume * open_p,
                trade_count=100 + (i % 50),
            )
            c.symbol = FIXED_SYMBOL
            c.event_ts = ts
            c.candle_id = f"C-{bundle_id}-{i:05d}"
            c.quality_flags = _make_qflags(**quality_kwargs)
            self._candles.append(c)
            p = close_p

        self._events: list = list(self._candles) + list(self._ticks)

    class _Manifest:
        def __init__(self, sha):
            self.content_sha256 = sha

    @property
    def manifest(self):
        import hashlib
        all_ids = "".join(c.candle_id for c in self._candles)
        return SyntheticBundle._Manifest(hashlib.sha256(all_ids.encode()).hexdigest())

    @property
    def bundle_sha(self) -> str:
        return self.manifest.content_sha256

    def compute_sha256(self) -> str:
        return self.manifest.content_sha256

    def iter_events(self) -> Iterable:
        for e in self._events:
            yield e


@pytest.fixture
def sbkt_small_bundle():
    return SyntheticBundle(num_candles=30)


@pytest.fixture
def sbkt_medium_bundle():
    return SyntheticBundle(num_candles=120)


@pytest.fixture
def sbkt_bad_quality_bundle():
    return SyntheticBundle(num_candles=60, bad_quality_first=True, bad_quarantine_nth=10)


@pytest.fixture
def sbkt_fixed_corr_id():
    return FIXED_CORR_ID
