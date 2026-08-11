from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import NewType


Instant = NewType("Instant", str)
Symbol = NewType("Symbol", str)
ULID = NewType("ULID", str)
ContractVersion = NewType("ContractVersion", str)


class RunMode(StrEnum):
    PAPER = "paper"
    BACKTEST = "backtest"
    LIVE = "live"


class SourceType(StrEnum):
    LIVE_WS = "live_ws"
    HISTORICAL_REST = "historical_rest"
    REPLAY = "replay"
    SIMULATED = "simulated"
    SYNTHETIC = "synthetic"


_INSTANT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)

_SYMBOL_CANONICAL_RE = re.compile(r"^[A-Z0-9]+_[A-Z0-9]+$")

_COMMON_QUOTES = ("USDT", "BUSD", "USDC", "BTC", "ETH")

_EXPLICIT_MAP: dict[str, str] = {
    "BTCUSDT": "BTC_USDT",
    "ETHUSDT": "ETH_USDT",
    "SOLUSDT": "SOL_USDT",
}


def format_instant(dt: datetime | None = None) -> Instant:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    ms = int(dt.microsecond / 1000)
    formatted = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"
    return Instant(formatted)


def validate_instant(s: str) -> bool:
    return bool(_INSTANT_RE.match(s))


def normalize_symbol(raw: str) -> Symbol:
    if not raw:
        return Symbol("")
    s = raw.strip().upper()
    if s in _EXPLICIT_MAP:
        return Symbol(_EXPLICIT_MAP[s])
    if "/" in s:
        return Symbol(s.replace("/", "_"))
    if "_" in s:
        return Symbol(s)
    for quote in _COMMON_QUOTES:
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return Symbol(f"{base}_{quote}")
    return Symbol(s)


def validate_symbol_canonical(s: str) -> bool:
    if not s:
        return False
    parts = s.split("_")
    if len(parts) != 2:
        return False
    return bool(_SYMBOL_CANONICAL_RE.match(s))
