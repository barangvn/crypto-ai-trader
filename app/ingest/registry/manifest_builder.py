from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import ReplayBundleManifest


_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


def _canonical_symbol(raw: str) -> str:
    raw = raw.strip().upper()
    if "/" in raw:
        base, q = raw.split("/", 1)
        return f"{base.strip().upper()}_{q.strip().upper()}"
    if "_" in raw:
        return raw
    for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
        if raw.endswith(quote) and len(raw) > len(quote):
            return f"{raw[: -len(quote)]}_{quote}"
    return raw


def _to_utc_z(ts_str: str) -> str:
    ts_str = ts_str.strip()
    if ts_str.endswith("Z"):
        return ts_str
    try:
        if "." in ts_str:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        else:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return ts_str
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def compute_sha256(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def count_csv_rows(path: Path, encoding: str = "utf-8") -> int:
    count = 0
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for _ in reader:
            count += 1
    return count


def inspect_csv(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    headers: list[str] = []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        for row in reader:
            rows.append(dict(row))
    symbols: set[str] = set()
    timeframes: set[str] = set()
    event_types: set[str] = set()
    timestamps: list[str] = []
    for r in rows:
        raw_sym = r.get("raw_symbol") or r.get("symbol")
        if raw_sym:
            symbols.add(_canonical_symbol(raw_sym))
        tf = r.get("timeframe")
        if tf:
            timeframes.add(tf)
        et = r.get("event_type")
        if et:
            event_types.add(et)
        ts = r.get("raw_timestamp") or r.get("timestamp") or r.get("market_ts") or r.get("book_ts") or r.get("open_time")
        if ts:
            timestamps.append(_to_utc_z(ts))
    timestamps_sorted = sorted(timestamps) if timestamps else []
    return {
        "headers": headers,
        "expected_rows": len(rows),
        "symbols": sorted(symbols),
        "timeframes": sorted(timeframes),
        "event_types": sorted(event_types),
        "first_ts": timestamps_sorted[0] if timestamps_sorted else "",
        "last_ts": timestamps_sorted[-1] if timestamps_sorted else "",
    }


def build_manifest(
    csv_path: Path,
    bundle_id: str | None = None,
    bundle_version: str = "1.0.0",
    display_name: str | None = None,
    extra_tags: list[str] | None = None,
    notes: str | None = None,
    encoding: str = "utf-8",
) -> ReplayBundleManifest:
    csv_path = Path(csv_path)
    info = inspect_csv(csv_path, encoding=encoding)
    stem = csv_path.stem
    bid = bundle_id or stem
    dname = display_name or stem.replace("_", " ").title()
    tags: list[str] = []
    lower = stem.lower()
    if "edge_" in lower:
        tags.append("edge")
        rest = lower.split("edge_", 1)[1]
        for part in rest.split("_"):
            if part:
                tags.append(part)
    elif "small_" in lower:
        tags.append("happy")
    tags.extend(extra_tags or [])
    ev_type = info["event_types"][0] if len(info["event_types"]) == 1 else (info["event_types"][0] if info["event_types"] else "candle")
    return ReplayBundleManifest(
        bundle_id=bid,
        bundle_version=bundle_version,
        display_name=dname,
        fixture_path=str(csv_path).replace("\\", "/"),
        event_type=ev_type,
        symbols=info["symbols"],
        timeframes=info["timeframes"],
        expected_rows=info["expected_rows"],
        expected_first_ts=info["first_ts"],
        expected_last_ts=info["last_ts"],
        checksum_sha256=compute_sha256(csv_path),
        tags=sorted(set(tags)),
        notes=notes,
    )
