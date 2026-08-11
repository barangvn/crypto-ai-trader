from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable
from uuid import uuid7

from app.contracts import (
    CONTRACT_VERSION,
    CanonicalEventEnvelope,
    Candle,
    ClockRef,
    QualityFlags,
    RunMode,
    SchemaRef,
    SourceType,
    format_instant,
    normalize_symbol,
    now_instant,
)
from app.processing.replay_clock import set_clock_ref_for_replay


_CANDLE_OFFSET_SECONDS: int = 60


class Normalizer:
    """
    Normalizes raw provider frames (RawFrame dicts) into canonical
    CanonicalEventEnvelope instances.

    Responsibilities:
      - Symbol canonicalization via contracts.normalize_symbol
      - Timestamp parsing → Instant format (always 3-digit ms + Z)
      - Safe Decimal coercion for numeric fields
      - Payload construction (Candle.v1 is the supported event_type)
      - Envelope build with clock_ref, quality_flags, correlation/causation IDs
      - Replay clock enrichment via set_clock_ref_for_replay
    """

    def __init__(
        self,
        run_mode: str = "paper",
        source_type: str = "replay",
        fixture_source_name: str = "replay.csv_default",
    ) -> None:
        self.run_mode: RunMode = RunMode(run_mode)
        self.source_type: SourceType = SourceType(source_type)
        self.fixture_source_name: str = fixture_source_name

    @staticmethod
    def _parse_raw_ts_to_instant(raw_timestamp: str) -> str:
        """
        Parse a raw timestamp string into canonical Instant format.

        Accepted input variations:
          - "2026-08-10 10:00:00"          (space, no ms)
          - "2026-08-10T10:00:00"          (T separator, no ms)
          - "2026-08-10T10:00:00.123"      (no Z suffix)
          - "2026-08-10T10:00:00.123Z"     (already Instant)

        Always returns: "YYYY-MM-DDTHH:MM:SS.mmmZ"
        """
        s: str = raw_timestamp.strip()
        if not s:
            raise ValueError("raw_timestamp is empty")

        space_norm: str = s.replace(" ", "T", 1)
        no_z: str = space_norm
        if no_z.endswith("Z"):
            no_z = no_z[:-1]

        has_ms: bool = "." in no_z
        fmt: str
        parse_str: str
        if has_ms:
            parts: list[str] = no_z.split(".", 1)
            ms_part: str = parts[1]
            if len(ms_part) > 6:
                ms_part = ms_part[:6]
            parse_str = parts[0] + "." + ms_part
            fmt = "%Y-%m-%dT%H:%M:%S.%f"
        else:
            parse_str = no_z
            fmt = "%Y-%m-%dT%H:%M:%S"

        dt: datetime = datetime.strptime(parse_str, fmt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return format_instant(dt)

    @staticmethod
    def _safe_decimal(
        value: str | int | float | Decimal | None,
    ) -> Decimal | None:
        """
        Safely coerce a value to Decimal.

        Returns None for: None, empty string, NaN, literal "NaN",
        or any value that cannot be parsed as Decimal.
        """
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, str):
            stripped: str = value.strip()
            if stripped == "" or stripped.lower() == "nan":
                return None
            try:
                return Decimal(stripped)
            except (InvalidOperation, ValueError):
                return None
        if isinstance(value, float):
            if math.isnan(value):
                return None
            return Decimal(str(value))
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError, TypeError):
            return None

    def normalize_one(
        self,
        raw_frame: dict,
        *,
        correlation_id: str,
        event_id_factory: Callable[[], str] | None = None,
    ) -> CanonicalEventEnvelope:
        """
        Normalize a single RawFrame dict into a CanonicalEventEnvelope.

        Args:
            raw_frame: Dict with raw provider fields.
            correlation_id: Shared across a batch for traceability.
            event_id_factory: Optional callable to produce event IDs.
                Defaults to uuid7() hex string.

        Returns:
            CanonicalEventEnvelope with Candle payload (for candle.v1 events).
        """
        event_id: str
        if event_id_factory is not None:
            event_id = event_id_factory()
        else:
            event_id = str(uuid7())

        causation_id: str = event_id
        symbol: str = normalize_symbol(raw_frame["raw_symbol"])
        timestamp: str = self._parse_raw_ts_to_instant(raw_frame["raw_timestamp"])
        ingest_ts: str = now_instant()

        event_type_str: str = raw_frame.get("event_type", "candle")
        contract_event_type: str
        payload: Candle | None = None

        if event_type_str == "candle":
            contract_event_type = "candle.v1"

            open_d: Decimal | None = self._safe_decimal(raw_frame.get("open"))
            high_d: Decimal | None = self._safe_decimal(raw_frame.get("high"))
            low_d: Decimal | None = self._safe_decimal(raw_frame.get("low"))
            close_d: Decimal | None = self._safe_decimal(raw_frame.get("close"))
            volume_d: Decimal | None = self._safe_decimal(raw_frame.get("volume"))

            ohlc_non_none: list[Decimal] = [
                x for x in (open_d, high_d, low_d, close_d) if x is not None
            ]
            if len(ohlc_non_none) >= 2:
                min_ohlc: Decimal = min(ohlc_non_none)
                max_ohlc: Decimal = max(ohlc_non_none)
                if low_d is None or low_d > min_ohlc:
                    low_d = min_ohlc
                if high_d is None or high_d < max_ohlc:
                    high_d = max_ohlc

            dt_obj: datetime = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
            close_dt: datetime = dt_obj + timedelta(seconds=_CANDLE_OFFSET_SECONDS)
            close_time: str = format_instant(close_dt)

            trade_count_raw: str | None = raw_frame.get("trade_count")
            trade_count: int | None = None
            if trade_count_raw is not None and str(trade_count_raw).strip() != "":
                try:
                    trade_count = int(float(str(trade_count_raw)))
                except (ValueError, TypeError):
                    trade_count = None

            extra_spread: str | None = raw_frame.get("spread_bps")

            payload = Candle(
                timeframe=raw_frame.get("timeframe", "1m"),
                open_time=timestamp,
                close_time=close_time,
                open=open_d or Decimal("0"),
                high=high_d or Decimal("0"),
                low=low_d or Decimal("0"),
                close=close_d or Decimal("0"),
                volume=volume_d or Decimal("0"),
                closed=True,
                quote_volume=None,
                vwap=None,
                trade_count=trade_count,
            )
        else:
            contract_event_type = f"{event_type_str}.v1"

        envelope: CanonicalEventEnvelope = CanonicalEventEnvelope(
            event_id=event_id,
            event_type=contract_event_type,
            contract_version=CONTRACT_VERSION,
            symbol=symbol,
            source=self.fixture_source_name,
            timestamp=timestamp,
            ingest_ts=ingest_ts,
            correlation_id=correlation_id,
            causation_id=causation_id,
            run_mode=self.run_mode,
            source_type=self.source_type,
            clock_ref=ClockRef(wall=ingest_ts, replay=None),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
            payload=payload,
        )

        if extra_spread is not None and str(extra_spread).strip() != "":
            try:
                envelope.extra["spread_bps"] = float(str(extra_spread))
            except (ValueError, TypeError):
                pass

        raw_seq: str | None = raw_frame.get("raw_sequence")
        if raw_seq is not None and str(raw_seq).strip() != "":
            try:
                envelope.extra["raw_sequence"] = int(str(raw_seq))
            except (ValueError, TypeError):
                pass

        raw_trade_id: str | None = raw_frame.get("raw_trade_id")
        if raw_trade_id is not None and str(raw_trade_id).strip() != "":
            envelope.extra["raw_trade_id"] = str(raw_trade_id)

        return set_clock_ref_for_replay(envelope)

    def normalize_many(
        self,
        raw_frames: Iterable[dict],
        *,
        correlation_id: str,
    ) -> list[CanonicalEventEnvelope]:
        """
        Batch-normalize many RawFrames sharing the same correlation_id.
        """
        return [
            self.normalize_one(frame, correlation_id=correlation_id)
            for frame in raw_frames
        ]
