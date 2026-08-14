from __future__ import annotations

import csv
import heapq
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from app.ingest.adapters.base import RawFrame


_TS_KEYS = ("raw_timestamp", "timestamp", "market_ts", "book_ts", "open_time")


def _parse_ts_soft(value: Any) -> tuple[bool, datetime | None]:
    if value is None:
        return False, None
    s = str(value).strip()
    if not s:
        return False, None
    if s.endswith("Z"):
        s2 = s[:-1]
    else:
        s2 = s
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s2, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return True, dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return True, dt
    except Exception:
        return False, None


def _frame_sort_key(frame: RawFrame, bundle_priority: int) -> tuple[int, int, Any]:
    for k in _TS_KEYS:
        if k in frame and frame[k] not in (None, ""):
            ok, dt = _parse_ts_soft(frame[k])
            if ok and dt is not None:
                return (0, bundle_priority, dt.timestamp() * 1_000_000)
    row_idx = frame.get("_row_index", 0)
    return (1, bundle_priority, int(row_idx) if isinstance(row_idx, int) else 0)


def _wrap_iter(
    iterator: Iterable[RawFrame],
    bundle_priority: int,
    bundle_id: str,
    bundle_checksum_prefix: str,
    bundle_version: str,
) -> Iterator[tuple[Any, int, int, RawFrame]]:
    seq = 0
    for f in iterator:
        enriched: RawFrame = {
            **f,
            "_bundle_id": bundle_id,
            "_bundle_priority": bundle_priority,
            "_bundle_row_index": f.get("_row_index", 0),
            "_provenance_bundle_id": bundle_id,
            "_provenance_checksum_prefix": bundle_checksum_prefix[:12],
            "_provenance_version": bundle_version,
        }
        key = _frame_sort_key(enriched, bundle_priority)
        yield (key, bundle_priority, seq, enriched)
        seq += 1


def merge_iterators(
    adapter_iterators: list[tuple[Iterator[RawFrame], str, str, str]],
) -> Iterator[RawFrame]:
    """
    Merge N adapter iterators into a single timestamp-ordered deterministic stream.

    adapter_iterators: list of (iterator, bundle_id, bundle_checksum, bundle_version)
    Order within equal timestamps is preserved by the original bundle_priority (list index).
    """
    wrapped: list[Iterator[tuple[Any, int, int, RawFrame]]] = []
    for i, (it, bid, checksum, bversion) in enumerate(adapter_iterators):
        wrapped.append(iter(_wrap_iter(it, i, bid, checksum, bversion)))
    for _, _, _, frame in heapq.merge(*wrapped, key=lambda x: x):
        yield frame
