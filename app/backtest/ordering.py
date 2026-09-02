from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.contracts import (
    Candle,
    FeatureVector,
    MarketRegimeState,
    MarketTick,
    OpportunityScore,
    PaperFill,
    PaperOrder,
    PortfolioSnapshot,
    Position,
    RiskDecision,
    StrategySignal,
)
from app.contracts.types import validate_instant
from app.contracts.canonical import CanonicalEventEnvelope


DETERMINISTIC_EVENT_STAGE_ORDER: tuple[str, ...] = (
    "MARKET",
    "FEATURE",
    "REGIME",
    "STRATEGY",
    "OPPORTUNITY",
    "RISK",
    "GATE",
    "FILL",
    "POSITION",
    "PORTFOLIO",
    "PERFORMANCE",
)

_STAGE_RANK: dict[str, int] = {name: i for i, name in enumerate(DETERMINISTIC_EVENT_STAGE_ORDER)}


class DeterministicEventOrderViolation(ValueError):
    pass


class LookAheadLeakageError(RuntimeError):
    pass


def _event_ts(evt: Any) -> str:
    if isinstance(evt, CanonicalEventEnvelope):
        return getattr(evt, "event_ts", "") or ""
    if isinstance(evt, MarketTick):
        return evt.event_ts
    if isinstance(evt, Candle):
        return evt.event_ts
    for attr in ("event_ts", "ts", "fill_ts", "snapshot_ts", "calculated_ts"):
        v = getattr(evt, attr, None)
        if isinstance(v, str):
            return v
    return ""


def _event_symbol(evt: Any) -> str:
    if isinstance(evt, CanonicalEventEnvelope):
        sym = getattr(evt, "symbol", None)
        if isinstance(sym, str):
            return sym
    for attr in ("symbol",):
        v = getattr(evt, attr, None)
        if isinstance(v, str):
            return v
    return ""


def _event_id(evt: Any) -> str:
    for attr in ("event_id", "tick_id", "candle_id", "feature_id", "regime_id",
                 "signal_id", "opportunity_id", "decision_id", "order_id",
                 "fill_id", "position_id", "snapshot_id", "performance_id"):
        v = getattr(evt, attr, None)
        if isinstance(v, str) and v:
            return v
    return ""


def stage_for_event(evt: Any) -> str:
    if isinstance(evt, CanonicalEventEnvelope):
        etype = getattr(evt, "event_type", "")
        if "tick" in etype or "candle" in etype or "orderbook" in etype or "market" in etype:
            return "MARKET"
        if "feature" in etype:
            return "FEATURE"
        if "regime" in etype:
            return "REGIME"
        if "signal" in etype or "strategy" in etype:
            return "STRATEGY"
        if "opportun" in etype:
            return "OPPORTUNITY"
        if "risk" in etype or "decision" in etype:
            return "RISK"
        if "paper_order" in etype or "order" in etype:
            return "GATE"
        if "fill" in etype:
            return "FILL"
        if "position" in etype:
            return "POSITION"
        if "snapshot" in etype or "portfolio" in etype:
            return "PORTFOLIO"
        if "performance" in etype or "perf" in etype:
            return "PERFORMANCE"
    if isinstance(evt, (MarketTick, Candle)):
        return "MARKET"
    if isinstance(evt, FeatureVector):
        return "FEATURE"
    if isinstance(evt, MarketRegimeState):
        return "REGIME"
    if isinstance(evt, StrategySignal):
        return "STRATEGY"
    if isinstance(evt, OpportunityScore):
        return "OPPORTUNITY"
    if isinstance(evt, RiskDecision):
        return "RISK"
    if isinstance(evt, PaperOrder):
        return "GATE"
    if isinstance(evt, PaperFill):
        return "FILL"
    if isinstance(evt, Position):
        return "POSITION"
    if isinstance(evt, PortfolioSnapshot):
        return "PORTFOLIO"
    if isinstance(evt, (list, tuple)) and len(evt) > 0:
        first = evt[0] if isinstance(evt, (list, tuple)) else None
        if hasattr(first, "rolling") or hasattr(first, "total_return") or hasattr(first, "max_drawdown"):
            return "PERFORMANCE"
    if hasattr(evt, "total_return") or hasattr(evt, "max_drawdown"):
        return "PERFORMANCE"
    return "MARKET"


def deterministic_event_sort_key(evt: Any) -> tuple[int, str, str, str, int]:
    ts = _event_ts(evt)
    stage = stage_for_event(evt)
    rank = _STAGE_RANK.get(stage, 999)
    symbol = _event_symbol(evt)
    ev_id = _event_id(evt)
    return (rank, ts, symbol, ev_id, id(evt))


def deterministic_sort_events(events: Iterable[Any]) -> list[Any]:
    return sorted(events, key=deterministic_event_sort_key)


def verify_event_ordering_strict(events: Iterable[Any]) -> None:
    prev_key: tuple[int, str, str, str, int] | None = None
    for ev in events:
        key = deterministic_event_sort_key(ev)
        if prev_key is not None:
            if key < prev_key:
                raise DeterministicEventOrderViolation(
                    f"Event ordering violation: after {prev_key} got {key}"
                )
        prev_key = key


@dataclass(slots=True)
class ReplayClock:
    decision_ts: str = ""
    last_seen_ts: str = ""
    input_max_ts: str = ""
    max_allowed_future_ts: str = ""
    advanced_count: int = 0
    frozen: bool = False

    def advance(self, new_ts: str) -> None:
        if self.frozen:
            raise LookAheadLeakageError("ReplayClock is frozen; cannot advance")
        if not isinstance(new_ts, str) or not validate_instant(new_ts):
            raise ValueError(f"ReplayClock.advance: invalid instant {new_ts!r}")
        if new_ts < self.last_seen_ts:
            raise LookAheadLeakageError(
                f"ReplayClock non-monotonic advance: {new_ts} < {self.last_seen_ts}"
            )
        self.decision_ts = new_ts
        self.last_seen_ts = new_ts
        self.input_max_ts = new_ts
        self.max_allowed_future_ts = new_ts
        self.advanced_count += 1

    def assert_instant_accessible(self, ts: str) -> None:
        if not isinstance(ts, str) or not ts:
            return
        if self.max_allowed_future_ts and ts > self.max_allowed_future_ts:
            raise LookAheadLeakageError(
                f"Look-ahead leakage attempt: accessing {ts} when max allowed is {self.max_allowed_future_ts}"
            )


def assert_no_look_ahead(
    decision_ts: str,
    decision_input_max_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    if not isinstance(decision_ts, str) or not decision_ts:
        raise ValueError("assert_no_look_ahead: decision_ts required")
    if not isinstance(decision_input_max_ts, str) or not decision_input_max_ts:
        raise ValueError("assert_no_look_ahead: decision_input_max_ts required")
    if decision_input_max_ts > decision_ts:
        raise LookAheadLeakageError(
            f"Look-ahead runtime check failed: decision_input_max_ts={decision_input_max_ts} > decision_ts={decision_ts}"
        )
    if clock is not None:
        clock.assert_instant_accessible(decision_input_max_ts)
