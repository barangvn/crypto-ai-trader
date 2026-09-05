from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from app.contracts import (
    CONTRACT_VERSION,
    Symbol,
    to_sorted_dict,
)

BACKTEST_RUN_VERSION: Literal["1.0.0"] = "1.0.0"
BACKTEST_ASSUMPTIONS_VERSION: Literal["1.0.0"] = "1.0.0"
WINDOW_SPLIT_VERSION: Literal["1.0.0"] = "1.0.0"


def _instant_compare(a: str, b: str) -> int:
    try:
        ai = int(a)
        bi = int(b)
        if ai < bi:
            return -1
        if ai > bi:
            return 1
        return 0
    except (ValueError, TypeError):
        pass
    try:
        fa = float(a)
        fb = float(b)
        if fa < fb:
            return -1
        if fa > fb:
            return 1
        return 0
    except (ValueError, TypeError):
        pass
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def _instant_lte(a: str, b: str) -> bool:
    return _instant_compare(a, b) <= 0


def _instant_gte(a: str, b: str) -> bool:
    return _instant_compare(a, b) >= 0


def _instant_gt(a: str, b: str) -> bool:
    return _instant_compare(a, b) > 0


def _instant_key(a: str) -> tuple[int, int] | tuple[int, float] | tuple[int, str]:
    try:
        return (0, int(a))
    except (ValueError, TypeError):
        pass
    try:
        return (1, float(a))
    except (ValueError, TypeError):
        pass
    return (2, a)


class SplitDataset(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class WindowSplit:
    dataset: SplitDataset
    start_instant: str
    end_instant: str
    event_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.start_instant, str) or not self.start_instant:
            raise ValueError("WindowSplit.start_instant must be non-empty str")
        if not isinstance(self.end_instant, str) or not self.end_instant:
            raise ValueError("WindowSplit.end_instant must be non-empty str")
        if _instant_gt(self.start_instant, self.end_instant):
            raise ValueError("WindowSplit.start_instant must be <= end_instant")
        if not isinstance(self.event_count, int) or self.event_count < 0:
            raise ValueError("WindowSplit.event_count must be non-negative int")
        if self.dataset not in (SplitDataset.TRAIN, SplitDataset.VALIDATION, SplitDataset.TEST):
            raise ValueError("WindowSplit.dataset invalid")

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset.value if isinstance(self.dataset, SplitDataset) else str(self.dataset),
            "start_instant": self.start_instant,
            "end_instant": self.end_instant,
            "event_count": self.event_count,
        }


@dataclass(frozen=True, slots=True)
class BacktestWindowSplit:
    version: Literal["1.0.0"] = WINDOW_SPLIT_VERSION
    train: WindowSplit | None = None
    validation: WindowSplit | None = None
    test: WindowSplit | None = None
    overlap_free: bool = True

    def __post_init__(self) -> None:
        windows: list[WindowSplit] = []
        if self.train is not None:
            windows.append(self.train)
        if self.validation is not None:
            windows.append(self.validation)
        if self.test is not None:
            windows.append(self.test)
        if len(windows) < 1:
            raise ValueError("BacktestWindowSplit requires at least one split")
        windows_sorted = sorted(windows, key=lambda w: _instant_key(w.start_instant))
        for prev, nxt in zip(windows_sorted, windows_sorted[1:]):
            if _instant_gte(prev.end_instant, nxt.start_instant):
                if self.overlap_free:
                    raise ValueError(
                        f"BacktestWindowSplit: overlap detected between "
                        f"{prev.dataset.value} and {nxt.dataset.value}"
                    )

    def split_for_ts(self, instant: str) -> SplitDataset | None:
        for split in (self.train, self.validation, self.test):
            if split is None:
                continue
            if _instant_gte(instant, split.start_instant) and _instant_lte(instant, split.end_instant):
                return split.dataset
        return None

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "overlap_free": self.overlap_free,
            "train": self.train.to_sorted_dict() if self.train is not None else None,
            "validation": self.validation.to_sorted_dict() if self.validation is not None else None,
            "test": self.test.to_sorted_dict() if self.test is not None else None,
        }


@dataclass(frozen=True, slots=True)
class BacktestAssumptions:
    version: Literal["1.0.0"] = BACKTEST_ASSUMPTIONS_VERSION
    initial_equity_quote: Decimal = Decimal("10000")
    quote_currency: str = "USDT"
    universe: tuple[Symbol, ...] = ()
    default_timeframe: str = "1m"
    initial_position_side: str = "flat"

    def compute_hash(self) -> str:
        payload = json.dumps(self.to_sorted_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_sorted_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, Decimal):
                d[f.name] = str(val)
            elif isinstance(val, tuple):
                d[f.name] = list(val)
            else:
                d[f.name] = val
        return d


@dataclass(frozen=True, slots=True)
class BacktestRun:
    run_id: str
    bundle_id: str
    bundle_version: str
    bundle_sha: str
    strategy_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    regime_version: str = "1.0.0"
    opportunity_version: str = "1.0.0"
    risk_version: str = "1.0.0"
    assumptions_hash: str = ""
    assumptions_version: Literal["1.0.0"] = BACKTEST_ASSUMPTIONS_VERSION
    timeframe: str = "1m"
    start_instant: str = ""
    end_instant: str = ""
    train_window: BacktestWindowSplit | None = None
    validation_window: BacktestWindowSplit | None = None
    test_window: BacktestWindowSplit | None = None
    walk_forward_mode: str = "disabled"
    event_count: int = 0
    fill_count: int = 0
    portfolio_snapshot_count: int = 0
    result_hash: str = ""
    engine_version: str = "1.0.0"
    contract_version: str = CONTRACT_VERSION
    run_mode: str = "backtest"
    source_type: str = "replay"

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("BacktestRun.run_id required")
        if not isinstance(self.bundle_id, str) or not self.bundle_id:
            raise ValueError("BacktestRun.bundle_id required")
        if not isinstance(self.bundle_version, str) or not self.bundle_version:
            raise ValueError("BacktestRun.bundle_version required")
        if not isinstance(self.bundle_sha, str) or not self.bundle_sha:
            raise ValueError("BacktestRun.bundle_sha required")
        if not isinstance(self.start_instant, str) or not self.start_instant:
            raise ValueError("BacktestRun.start_instant required")
        if not isinstance(self.end_instant, str) or not self.end_instant:
            raise ValueError("BacktestRun.end_instant required")
        if self.start_instant > self.end_instant:
            raise ValueError("BacktestRun.start must be <= end")

    def compute_provenance_sha(self) -> str:
        parts = [
            self.bundle_id,
            self.bundle_version,
            self.bundle_sha,
            self.strategy_version,
            self.feature_version,
            self.regime_version,
            self.opportunity_version,
            self.risk_version,
            self.assumptions_hash,
            self.timeframe,
            self.start_instant,
            self.end_instant,
            self.engine_version,
            self.contract_version,
        ]
        payload = "|".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_sorted_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if is_dataclass(val):
                raw[f.name] = _nested_sorted_dict(val)
            else:
                raw[f.name] = val
        return raw


def _nested_sorted_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        out: dict[str, Any] = {}
        for f in fields(obj):
            out[f.name] = _nested_sorted_dict(getattr(obj, f.name))
        return out
    if isinstance(obj, list) or isinstance(obj, tuple):
        return [_nested_sorted_dict(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    return obj
