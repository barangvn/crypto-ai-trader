"""Deterministic runner-compatible fixture bundle for the Paper Trading MVP.

Converts a repository CSV fixture (canonical example:
``tests_fixtures/small_3sym_1h_1m_candles.csv``) into
``app.contracts.market.Candle`` events accepted by
``app.backtest.runner.BacktestRunner``.

Contract implemented (duck-typed, as required by the runner):

* ``bundle_id``      — stable identifier.
* ``bundle_version`` — stable version string.
* ``compute_sha256()`` — stable sha256 over the canonical parsed rows.
* ``iter_events()``  — yields ``Candle`` events (``MarketTick``/``Candle`` are
  the only event types the runner consumes).

Fail-closed by design: malformed or unsupported source rows are rejected with
``FixtureBundleError``; values are never silently discarded or fabricated.
Stdlib-only. No network, no credentials, no import side effects.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from app.contracts import Candle, QualityFlags
from app.contracts.types import (
    format_instant,
    normalize_symbol,
    validate_symbol_canonical,
)


FIXTURE_BUNDLE_VERSION: str = "1.0.0"

#: Only ``candle`` rows are supported by this bundle. Any other ``event_type``
#: is rejected explicitly (fail-closed) rather than skipped.
SUPPORTED_EVENT_TYPE: str = "candle"

#: Columns that must be present in the CSV header for a deterministic mapping.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "raw_symbol",
    "raw_timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "event_type",
    "timeframe",
)

_RAW_TS_FORMAT: str = "%Y-%m-%d %H:%M:%S"
_TIMEFRAME_RE = re.compile(r"^(\d+)([mhd])$")
_TIMEFRAME_UNIT_MINUTES: dict[str, int] = {"m": 1, "h": 60, "d": 1440}


class FixtureBundleError(ValueError):
    """Raised (fail-closed) when the fixture cannot be converted deterministically."""


def _parse_timeframe_minutes(raw: str, *, line: int) -> tuple[str, int]:
    tf = (raw or "").strip()
    match = _TIMEFRAME_RE.match(tf)
    if match is None:
        raise FixtureBundleError(
            f"line {line}: unsupported timeframe {raw!r} (expected e.g. '1m', '1h')"
        )
    count = int(match.group(1))
    if count <= 0:
        raise FixtureBundleError(f"line {line}: non-positive timeframe {raw!r}")
    return tf, count * _TIMEFRAME_UNIT_MINUTES[match.group(2)]


def _parse_decimal(raw: str | None, *, field: str, line: int) -> Decimal:
    if raw is None or not str(raw).strip():
        raise FixtureBundleError(f"line {line}: required numeric field {field!r} is empty")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError) as exc:
        raise FixtureBundleError(
            f"line {line}: field {field!r} is not a valid decimal: {raw!r}"
        ) from exc
    if not value.is_finite():
        raise FixtureBundleError(f"line {line}: field {field!r} is not finite: {raw!r}")
    return value


def _parse_trade_count(raw: str | None, *, line: int) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise FixtureBundleError(
            f"line {line}: field 'trade_count' is not a valid integer: {raw!r}"
        ) from exc
    if value < 0:
        raise FixtureBundleError(f"line {line}: negative trade_count {value}")
    return value


def _parse_raw_timestamp(raw: str | None, *, line: int) -> datetime:
    if raw is None or not str(raw).strip():
        raise FixtureBundleError(f"line {line}: required field 'raw_timestamp' is empty")
    try:
        dt = datetime.strptime(str(raw).strip(), _RAW_TS_FORMAT)
    except ValueError as exc:
        raise FixtureBundleError(
            f"line {line}: raw_timestamp {raw!r} does not match {_RAW_TS_FORMAT!r}"
        ) from exc
    return dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class _CanonicalCandle:
    """Canonical, runner-relevant representation of one fixture row."""

    symbol: str
    event_ts: str
    open_time: str
    close_time: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_count: int | None
    timeframe: str
    closed: bool
    source_row_index: int

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "close": str(self.close),
            "close_time": self.close_time,
            "closed": self.closed,
            "event_ts": self.event_ts,
            "high": str(self.high),
            "low": str(self.low),
            "open": str(self.open),
            "open_time": self.open_time,
            "source_row_index": self.source_row_index,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "trade_count": self.trade_count,
            "volume": str(self.volume),
        }


class FixtureBundle:
    """Deterministic, runner-compatible bundle backed by a CSV fixture."""

    def __init__(
        self,
        fixture_path: str | Path,
        *,
        bundle_id: str | None = None,
        bundle_version: str = FIXTURE_BUNDLE_VERSION,
    ) -> None:
        path = Path(fixture_path)
        if not path.is_file():
            raise FixtureBundleError(f"fixture not found: {path}")
        self.fixture_path: Path = path
        self.bundle_id: str = bundle_id or path.stem
        self.bundle_version: str = bundle_version

        records = self._load_records(path)
        if not records:
            raise FixtureBundleError(f"fixture contains no data rows: {path}")

        # Canonical, stable ordering: by event instant, then symbol, then source row.
        records.sort(key=lambda r: (r.event_ts, r.symbol, r.source_row_index))
        self._records: tuple[_CanonicalCandle, ...] = tuple(records)

        timeframes = sorted({r.timeframe for r in self._records})
        if len(timeframes) != 1:
            raise FixtureBundleError(
                f"fixture mixes timeframes {timeframes}; a single timeframe is required"
            )
        self.timeframe: str = timeframes[0]
        self.symbols: tuple[str, ...] = tuple(
            sorted({r.symbol for r in self._records})
        )
        self._sha256: str = self._compute_canonical_sha256()
        self._events: tuple[Candle, ...] = tuple(
            self._build_candle(record, index) for index, record in enumerate(self._records)
        )

    # ------------------------------------------------------------------ loading
    @staticmethod
    def _load_records(path: Path) -> list[_CanonicalCandle]:
        with path.open(mode="r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            missing = [col for col in REQUIRED_COLUMNS if col not in header]
            if missing:
                raise FixtureBundleError(
                    f"{path}: missing required columns {missing}"
                )
            records: list[_CanonicalCandle] = []
            for row_index, row in enumerate(reader):
                line = row_index + 2  # header is line 1
                records.append(FixtureBundle._canonicalize(row, row_index, line))
        return records

    @staticmethod
    def _canonicalize(row: dict[str, Any], row_index: int, line: int) -> _CanonicalCandle:
        event_type = str(row.get("event_type") or "").strip().lower()
        if event_type != SUPPORTED_EVENT_TYPE:
            raise FixtureBundleError(
                f"line {line}: unsupported event_type {event_type!r}; "
                f"only {SUPPORTED_EVENT_TYPE!r} is supported"
            )

        raw_symbol = str(row.get("raw_symbol") or "").strip()
        if not raw_symbol:
            raise FixtureBundleError(f"line {line}: required field 'raw_symbol' is empty")
        symbol = normalize_symbol(raw_symbol)
        if not validate_symbol_canonical(symbol):
            raise FixtureBundleError(
                f"line {line}: symbol {raw_symbol!r} does not normalize to a canonical "
                f"BASE_QUOTE symbol (got {symbol!r})"
            )

        timeframe, timeframe_minutes = _parse_timeframe_minutes(
            str(row.get("timeframe") or ""), line=line
        )
        open_dt = _parse_raw_timestamp(row.get("raw_timestamp"), line=line)
        close_dt = open_dt + timedelta(minutes=timeframe_minutes)

        open_p = _parse_decimal(row.get("open"), field="open", line=line)
        high_p = _parse_decimal(row.get("high"), field="high", line=line)
        low_p = _parse_decimal(row.get("low"), field="low", line=line)
        close_p = _parse_decimal(row.get("close"), field="close", line=line)
        volume = _parse_decimal(row.get("volume"), field="volume", line=line)

        if high_p < low_p:
            raise FixtureBundleError(f"line {line}: high {high_p} < low {low_p}")
        if min(open_p, high_p, low_p, close_p) <= 0:
            raise FixtureBundleError(f"line {line}: non-positive OHLC value")
        if volume < 0:
            raise FixtureBundleError(f"line {line}: negative volume {volume}")

        open_time = format_instant(open_dt)
        return _CanonicalCandle(
            symbol=str(symbol),
            event_ts=str(open_time),
            open_time=str(open_time),
            close_time=str(format_instant(close_dt)),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
            trade_count=_parse_trade_count(row.get("trade_count"), line=line),
            timeframe=timeframe,
            closed=True,
            source_row_index=row_index,
        )

    def _build_candle(self, record: _CanonicalCandle, index: int) -> Candle:
        candle = Candle(
            timeframe=record.timeframe,
            open_time=record.open_time,
            close_time=record.close_time,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            volume=record.volume,
            closed=record.closed,
            quote_volume=None,
            vwap=None,
            trade_count=record.trade_count,
        )
        # The runner/ordering layer reads these attributes dynamically.
        candle.symbol = record.symbol  # type: ignore[attr-defined]
        candle.event_ts = record.event_ts  # type: ignore[attr-defined]
        # ISO-8601 instant: FeatureEngine copies candle_id into FeatureVector.input_refs
        # and RegimeEngine requires those refs to be valid ISO-8601 Instants.
        candle.candle_id = record.open_time  # type: ignore[attr-defined]
        candle.quality_flags = QualityFlags()  # type: ignore[attr-defined]
        return candle

    # ----------------------------------------------------------------- contract
    def _compute_canonical_sha256(self) -> str:
        payload = [record.to_sorted_dict() for record in self._records]
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def compute_sha256(self) -> str:
        """Stable sha256 over the canonical parsed fixture rows."""
        return self._sha256

    def iter_events(self) -> Iterator[Candle]:
        """Yield the canonical candle events in stable order."""
        yield from self._events
