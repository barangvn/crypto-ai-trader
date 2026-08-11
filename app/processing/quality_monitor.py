from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable

from app.contracts import (
    CanonicalEventEnvelope,
    Candle,
    QualityFlags,
    now_instant,
    validate_instant,
)


class DataQualityMonitor:
    """
    Data Quality Monitor / Validator (AD-5, 9 CHECKS).

    Stateful per-session validator that enforces data-quality invariants
    on CanonicalEventEnvelope instances. Tracks per-symbol timestamps,
    sequence numbers, and dedup keys across calls.

    Thresholds (test-only defaults):
      - stale_threshold_ms: 5 minutes (5 * 60 * 1000)
      - spread_bps_threshold: 5000 bps
    """

    def __init__(
        self,
        *,
        stale_threshold_ms: int = 5 * 60 * 1000,
        spread_bps_threshold: float = 5000.0,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self.stale_threshold_ms: int = stale_threshold_ms
        self.spread_bps_threshold: float = spread_bps_threshold
        self._now_provider: Callable[[], str] = now_provider or now_instant
        self.last_ts_by_symbol: dict[str, str] = {}
        self.last_seq_by_symbol: dict[str, int] = {}
        self.seen_dedup_keys: set[str] = set()

    @staticmethod
    def _add_reason(
        qf: QualityFlags,
        code: str,
        message: str,
        context: dict | None = None,
    ) -> None:
        reason: dict[str, Any] = {"code": code, "message": message}
        if context:
            reason["context"] = context
        qf.reasons.append(reason)

    def _now(self) -> str:
        return self._now_provider()

    @staticmethod
    def _parse_instant_to_dt(instant: str) -> datetime:
        dt: datetime = datetime.strptime(instant, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.replace(tzinfo=timezone.utc)

    def validate_one(
        self,
        envelope: CanonicalEventEnvelope,
    ) -> tuple[CanonicalEventEnvelope, bool]:
        """
        Run 9 quality checks on a single envelope.

        Returns (modified_envelope, is_quarantined_bool).
        Caller MUST NOT publish to canonical bus when is_quarantined=True.
        """
        qf: QualityFlags = envelope.quality_flags
        payload: Any = envelope.payload
        symbol: str = envelope.symbol or ""

        # Check 9 (done first so Check 4 can reuse): timestamp format zero/null
        if not validate_instant(envelope.timestamp):
            qf.invalid = True
            qf.quarantined = True
            self._add_reason(
                qf,
                "INVALID_TIMESTAMP_FORMAT",
                "Envelope timestamp is not a valid Instant string",
                {"timestamp": envelope.timestamp},
            )

        # Check 1: invalid_price / invalid_price_range (Candle payload)
        if isinstance(payload, Candle):
            ohlc: list[tuple[str, Decimal | None]] = [
                ("open", payload.open),
                ("high", payload.high),
                ("low", payload.low),
                ("close", payload.close),
            ]
            bad_price: bool = False
            for name, val in ohlc:
                if val is None or val <= Decimal("0"):
                    bad_price = True
                    break
            if bad_price:
                qf.invalid = True
                qf.quarantined = True
                self._add_reason(
                    qf,
                    "INVALID_PRICE",
                    "Candle OHLC contains non-positive or None values",
                    {"open": str(payload.open), "high": str(payload.high),
                     "low": str(payload.low), "close": str(payload.close)},
                )
            else:
                if not (payload.low <= payload.open <= payload.high and
                        payload.low <= payload.close <= payload.high and
                        payload.low <= payload.high):
                    qf.invalid = True
                    qf.quarantined = True
                    self._add_reason(
                        qf,
                        "INVALID_PRICE_RANGE",
                        "Candle violates low <= OHLC <= high invariant",
                        {"open": str(payload.open), "high": str(payload.high),
                         "low": str(payload.low), "close": str(payload.close)},
                    )

        # Check 2: invalid_volume (Candle)
        if isinstance(payload, Candle):
            if payload.volume is None or payload.volume <= Decimal("0"):
                qf.invalid = True
                qf.quarantined = True
                self._add_reason(
                    qf,
                    "INVALID_VOLUME",
                    "Candle volume is non-positive or None",
                    {"volume": str(payload.volume)},
                )

        # Check 3: abnormal_spread
        spread_bps: float | None = None
        if "spread_bps" in envelope.extra:
            try:
                spread_bps = float(envelope.extra["spread_bps"])
            except (ValueError, TypeError):
                spread_bps = None
        if spread_bps is None and hasattr(payload, "spread_bps"):
            try:
                attr_val: Any = getattr(payload, "spread_bps")
                if attr_val is not None:
                    spread_bps = float(attr_val)
            except (ValueError, TypeError):
                spread_bps = None
        if spread_bps is not None and spread_bps > self.spread_bps_threshold:
            qf.degraded = True
            self._add_reason(
                qf,
                "ABNORMAL_SPREAD",
                "Spread exceeds configured threshold",
                {"spread_bps": spread_bps, "threshold": self.spread_bps_threshold},
            )

        # Check 4: timestamp drift (future drift) + re-validate format
        if validate_instant(envelope.timestamp):
            now_str: str = self._now()
            if validate_instant(now_str):
                now_dt: datetime = self._parse_instant_to_dt(now_str)
                ts_dt: datetime = self._parse_instant_to_dt(envelope.timestamp)
                delta_future_ms: float = (ts_dt - now_dt).total_seconds() * 1000.0
                if delta_future_ms > 1000.0:
                    qf.invalid = True
                    qf.quarantined = True
                    self._add_reason(
                        qf,
                        "FUTURE_TIMESTAMP_DRIFT",
                        "Event timestamp is in the future",
                        {"event_ts": envelope.timestamp, "now": now_str,
                         "delta_ms": int(delta_future_ms)},
                    )

        # Check 5: stale data
        if validate_instant(envelope.timestamp) and validate_instant(self._now()):
            now_dt2: datetime = self._parse_instant_to_dt(self._now())
            ts_dt2: datetime = self._parse_instant_to_dt(envelope.timestamp)
            delta_ms: float = (now_dt2 - ts_dt2).total_seconds() * 1000.0
            if delta_ms > self.stale_threshold_ms:
                qf.stale = True
                qf.staleness_ms = int(delta_ms)
                self._add_reason(
                    qf,
                    "STALE_DATA",
                    "Event is older than stale threshold",
                    {"delta_ms": int(delta_ms),
                     "threshold_ms": self.stale_threshold_ms},
                )

        # Check 6: out_of_order (timestamp + sequence)
        last_ts: str | None = self.last_ts_by_symbol.get(symbol)
        if last_ts is not None and validate_instant(last_ts) and validate_instant(envelope.timestamp):
            last_dt: datetime = self._parse_instant_to_dt(last_ts)
            curr_dt: datetime = self._parse_instant_to_dt(envelope.timestamp)
            if curr_dt < last_dt:
                qf.out_of_order = True
                qf.quarantined = True
                self._add_reason(
                    qf,
                    "OUT_OF_ORDER_TIMESTAMP",
                    "Event timestamp is before previously seen timestamp for symbol",
                    {"symbol": symbol, "last_ts": last_ts,
                     "current_ts": envelope.timestamp},
                )
        raw_seq: Any = envelope.extra.get("raw_sequence")
        if raw_seq is None and hasattr(payload, "sequence"):
            raw_seq = getattr(payload, "sequence")
        seq_int: int | None = None
        if raw_seq is not None:
            try:
                seq_int = int(raw_seq)
            except (ValueError, TypeError):
                seq_int = None
        last_seq: int | None = None
        if seq_int is not None:
            last_seq = self.last_seq_by_symbol.get(symbol)
            if last_seq is not None and seq_int < last_seq:
                qf.out_of_order = True
                qf.quarantined = True
                self._add_reason(
                    qf,
                    "OUT_OF_ORDER_SEQUENCE",
                    "Event sequence is before previously seen sequence for symbol",
                    {"symbol": symbol, "last_seq": last_seq,
                     "current_seq": seq_int},
                )

        # Check 7: duplicate
        dedup_key: str
        open_time_attr: str | None = None
        if isinstance(payload, Candle):
            open_time_attr = payload.open_time
        elif payload is not None and hasattr(payload, "open_time"):
            try:
                open_time_attr = str(getattr(payload, "open_time"))
            except Exception:
                open_time_attr = None
        dedup_key = (
            f"{envelope.source}|{envelope.event_type}|"
            f"{symbol}|{open_time_attr or envelope.timestamp}"
        )
        extra_trade_id: Any = envelope.extra.get("raw_trade_id")
        if extra_trade_id is None and payload is not None and hasattr(payload, "trade_id"):
            try:
                extra_trade_id = getattr(payload, "trade_id")
            except Exception:
                extra_trade_id = None
        if extra_trade_id is not None:
            dedup_key += f"|{extra_trade_id}"
        is_duplicate: bool = dedup_key in self.seen_dedup_keys
        if is_duplicate:
            qf.duplicate = True
            qf.quarantined = True
            qf.dedup_key = dedup_key
            self._add_reason(
                qf,
                "DUPLICATE_EVENT",
                "Event dedup key matches a previously seen event",
                {"dedup_key": dedup_key},
            )

        # Check 8: missing (sequence gap + candle gap)
        if seq_int is not None:
            expected: int = seq_int
            if last_seq is not None:
                expected = last_seq + 1
            if seq_int > expected:
                qf.missing = True
                qf.expected_sequence = expected
                qf.actual_sequence = seq_int
                self._add_reason(
                    qf,
                    "MISSING_SEQUENCE_GAP",
                    "Sequence number jumped; events may be missing",
                    {"symbol": symbol, "expected": expected,
                     "actual": seq_int},
                )
        if isinstance(payload, Candle) and last_ts is not None:
            if validate_instant(last_ts) and validate_instant(envelope.timestamp):
                ldt: datetime = self._parse_instant_to_dt(last_ts)
                cdt: datetime = self._parse_instant_to_dt(envelope.timestamp)
                gap_sec: float = (cdt - ldt).total_seconds()
                if gap_sec > 120.0:
                    qf.missing = True
                    self._add_reason(
                        qf,
                        "MISSING_CANDLE_GAP",
                        "Timestamp gap between successive candles exceeds 2x timeframe",
                        {"symbol": symbol, "last_ts": last_ts,
                         "current_ts": envelope.timestamp,
                         "gap_seconds": int(gap_sec)},
                    )

        # Post-check: ensure quarantined if any hard-fail flags
        hard_fail: bool = qf.invalid or qf.duplicate or qf.out_of_order
        if hard_fail and not qf.quarantined:
            qf.quarantined = True

        any_flag: bool = (
            qf.stale or qf.missing or qf.duplicate or qf.out_of_order
            or qf.invalid or qf.quarantined or qf.degraded
        )
        if any_flag:
            qf.degraded = True

        # --- STATE UPDATES (after all validation checks) ---
        if symbol:
            self.last_ts_by_symbol[symbol] = envelope.timestamp
            if seq_int is not None:
                self.last_seq_by_symbol[symbol] = seq_int
        if not is_duplicate:
            self.seen_dedup_keys.add(dedup_key)

        return envelope, qf.quarantined

    def validate_many(
        self,
        envelopes: Iterable[CanonicalEventEnvelope],
    ) -> tuple[list[CanonicalEventEnvelope], list[CanonicalEventEnvelope]]:
        """
        Batch-validate envelopes.

        Returns (publishable[], quarantined[]).
        """
        publishable: list[CanonicalEventEnvelope] = []
        quarantined: list[CanonicalEventEnvelope] = []
        for env in envelopes:
            modified_env, is_q = self.validate_one(env)
            if is_q:
                quarantined.append(modified_env)
            else:
                publishable.append(modified_env)
        return publishable, quarantined
