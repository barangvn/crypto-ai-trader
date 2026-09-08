"""S-BKT-03: Runtime leakage hard assertions.

HARICI ORDERING.PY KULLANILIR. ordering.py HARD-RED, degistirilmez.
- 6 stage (feature / regime / strategy / opportunity / risk / fill) her biri icin
  decision_input_max_ts <= decision_ts + clock.assert_instant_accessible cagrisi.
- Fold overlap: train<val<test, inter-fold N-1 end < inter_gap < N train start.
- Fail-closed: any BK_LEAK_* code -> LookAheadLeakageError raise + no mutation.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .ordering import (
    ReplayClock,
    LookAheadLeakageError,
    assert_no_look_ahead,
)


BK_LEAK_PREFIX = "BK_LEAK_"
STAGES_ORDERED: tuple[str, ...] = (
    "FEATURE",
    "REGIME",
    "STRATEGY",
    "OPPORTUNITY",
    "RISK",
    "FILL",
)


def _code(stage: str, reason: str) -> str:
    return f"{BK_LEAK_PREFIX}{stage}_{reason}"


def max_ts_from_events(events: Iterable[Any], ts_attr: str = "event_ts") -> str:
    best = ""
    for ev in events:
        ts = getattr(ev, ts_attr, None)
        if isinstance(ts, str) and ts > best:
            best = ts
    return best


def enforce_stage_leakage(
    stage: str,
    *,
    decision_ts: str,
    decision_input_max_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    if stage not in STAGES_ORDERED:
        raise ValueError(f"enforce_stage_leakage: invalid stage {stage!r}")
    try:
        assert_no_look_ahead(
            decision_ts=decision_ts,
            decision_input_max_ts=decision_input_max_ts,
            clock=clock,
        )
    except LookAheadLeakageError as exc:
        raise LookAheadLeakageError(
            f"{_code(stage, 'INPUT_AHEAD')}: {exc}"
        ) from exc
    except ValueError as exc:
        raise LookAheadLeakageError(
            f"{_code(stage, 'INPUT_INVALID')}: {exc}"
        ) from exc


def enforce_feature_stage_leakage(
    *,
    decision_ts: str,
    candle_history: Sequence[Any],
    clock: ReplayClock | None = None,
) -> None:
    input_max = max_ts_from_events(candle_history, ts_attr="close_time")
    if not input_max:
        input_max = decision_ts
    enforce_stage_leakage(
        "FEATURE",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def enforce_regime_stage_leakage(
    *,
    decision_ts: str,
    feature_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    input_max = feature_ts if isinstance(feature_ts, str) and feature_ts else decision_ts
    enforce_stage_leakage(
        "REGIME",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def enforce_strategy_stage_leakage(
    *,
    decision_ts: str,
    regime_detected_ts: str,
    feature_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    a = regime_detected_ts if isinstance(regime_detected_ts, str) and regime_detected_ts else ""
    b = feature_ts if isinstance(feature_ts, str) and feature_ts else ""
    input_max = max(decision_ts, a, b) if max(a, b) <= decision_ts else max(a, b)
    enforce_stage_leakage(
        "STRATEGY",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def enforce_opportunity_stage_leakage(
    *,
    decision_ts: str,
    signal_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    input_max = signal_ts if isinstance(signal_ts, str) and signal_ts else decision_ts
    enforce_stage_leakage(
        "OPPORTUNITY",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def enforce_risk_stage_leakage(
    *,
    decision_ts: str,
    opportunity_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    input_max = opportunity_ts if isinstance(opportunity_ts, str) and opportunity_ts else decision_ts
    enforce_stage_leakage(
        "RISK",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def enforce_fill_stage_leakage(
    *,
    decision_ts: str,
    order_ts: str,
    clock: ReplayClock | None = None,
) -> None:
    input_max = order_ts if isinstance(order_ts, str) and order_ts else decision_ts
    enforce_stage_leakage(
        "FILL",
        decision_ts=decision_ts,
        decision_input_max_ts=input_max,
        clock=clock,
    )


def assert_window_train_val_test_ordered(
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    *,
    fold_id: str = "",
) -> None:
    problems: list[str] = []
    if train_end and val_start and not (train_end < val_start):
        problems.append("train_end >= val_start")
    if val_end and test_start and not (val_end < test_start):
        problems.append("val_end >= test_start")
    if train_end and test_start and not (train_end < test_start):
        problems.append("train_end >= test_start")
    if problems:
        msg = "; ".join(problems)
        fid = f" fold={fold_id}" if fold_id else ""
        raise LookAheadLeakageError(
            f"{BK_LEAK_PREFIX}FOLD_WINDOW_INTRA_ORDER{fid}: {msg}"
        )


def assert_interfold_no_overlap(
    prev_test_end: str,
    next_train_start: str,
    *,
    inter_gap_ms: int = 0,
    fold_prev_id: str = "",
    fold_next_id: str = "",
) -> None:
    if not prev_test_end or not next_train_start:
        return
    try:
        from datetime import datetime as _dt, timezone as _tz
        def _ms(s: str) -> float:
            t = _dt.strptime(s.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z")
            return t.timestamp() * 1000.0
        a_ms = _ms(prev_test_end)
        b_ms = _ms(next_train_start)
    except BaseException:
        if not (prev_test_end < next_train_start):
            raise LookAheadLeakageError(
                f"{BK_LEAK_PREFIX}FOLD_INTER_OVERLAP: {fold_prev_id} -> {fold_next_id}"
            )
        return
    if inter_gap_ms and (b_ms - a_ms) < inter_gap_ms:
        raise LookAheadLeakageError(
            f"{BK_LEAK_PREFIX}FOLD_INTER_GAP: gap {(b_ms - a_ms):.1f}ms < required {inter_gap_ms}ms"
        )
    if b_ms <= a_ms:
        raise LookAheadLeakageError(
            f"{BK_LEAK_PREFIX}FOLD_INTER_OVERLAP: {fold_prev_id} end={prev_test_end} >= start={next_train_start} {fold_next_id}"
        )
