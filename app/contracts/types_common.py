from __future__ import annotations

from typing import Literal, NewType


from ._validation import (
    CONTRACT_VERSION_STR,
    RUN_MODE_VALUES,
    SOURCE_TYPE_VALUES,
)


ContractVersionStr = NewType("ContractVersionStr", str)
CONTRACT_VERSION: ContractVersionStr = ContractVersionStr(CONTRACT_VERSION_STR)

Instant = NewType("Instant", str)
ULID_SORTABLE = NewType("ULID_SORTABLE", str)
SymbolCanonical = NewType("SymbolCanonical", str)
ContractEventName = NewType("ContractEventName", str)

RunModeE = Literal["paper", "backtest", "live"]
SourceTypeE = Literal[
    "live_ws",
    "historical_rest",
    "replay",
    "simulated",
    "synthetic",
    "static_fixture",
]


__all__ = [
    "ContractVersionStr",
    "CONTRACT_VERSION",
    "Instant",
    "ULID_SORTABLE",
    "SymbolCanonical",
    "ContractEventName",
    "RunModeE",
    "SourceTypeE",
]
