"""S-BKT-03 01: Runtime leakage hard assertions (6 stage wrappers + direct data-flow).

- TUM 6 stage (FEATURE / REGIME / STRATEGY / OPPORTUNITY / RISK / FILL)
  enforce_stage_leakage cagrisi.
- decision_input_max_ts > decision_ts => LookAheadLeakageError.
- Boundary: input max == decision_ts PASS; input max = decision_ts + 1ms FAIL.
- Exact ts boundary: input max = close_time < decision_ts (allowed) PASS.
- Future timestamp injection: clock max_allowed_future_ts korumasi.
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from decimal import Decimal

from app.backtest.ordering import ReplayClock, LookAheadLeakageError
from app.backtest.leakage_asserts import (
    enforce_stage_leakage,
    enforce_feature_stage_leakage,
    enforce_regime_stage_leakage,
    enforce_strategy_stage_leakage,
    enforce_opportunity_stage_leakage,
    enforce_risk_stage_leakage,
    enforce_fill_stage_leakage,
    max_ts_from_events,
    STAGES_ORDERED,
    BK_LEAK_PREFIX,
)


STAGES_EXTRA = (
    "FEATURE",
    "REGIME",
    "STRATEGY",
    "OPPORTUNITY",
    "RISK",
    "FILL",
)


DEC_TS = "2025-01-01T00:05:00.000Z"
DEC_TS_PAST = "2025-01-01T00:04:00.000Z"
DEC_TS_PLUS_1 = "2025-01-01T00:05:00.001Z"
DEC_TS_MINUS_1 = "2025-01-01T00:04:59.999Z"

STAGE_BOUNDARY_TIMESTAMPS = [
    ("2025-01-01T00:00:00.000Z", False),
    ("2025-01-01T00:01:00.000Z", False),
    ("2025-01-01T00:02:30.500Z", False),
    ("2025-01-01T00:03:00.000Z", False),
    ("2025-01-01T00:04:00.000Z", False),
    (DEC_TS_MINUS_1, False),
    (DEC_TS, False),
    (DEC_TS_PLUS_1, True),
    ("2025-01-01T00:05:00.002Z", True),
    ("2025-01-01T00:05:01.000Z", True),
    ("2025-01-01T00:10:00.000Z", True),
    ("2025-02-01T00:00:00.000Z", True),
]


@pytest.mark.parametrize("stage", STAGES_EXTRA)
@pytest.mark.parametrize("input_ts,raises", STAGE_BOUNDARY_TIMESTAMPS)
def test_sbkt03_L01_stage_wide_boundary_matrix(stage, input_ts, raises):
    """6 stage × 12 timestamp = 72 hücre: exact boundary + wide future matrix."""
    if raises:
        with pytest.raises(LookAheadLeakageError) as ei:
            enforce_stage_leakage(
                stage,
                decision_ts=DEC_TS,
                decision_input_max_ts=input_ts,
            )
        assert BK_LEAK_PREFIX in str(ei.value)
        assert stage in str(ei.value)
    else:
        enforce_stage_leakage(
            stage,
            decision_ts=DEC_TS,
            decision_input_max_ts=input_ts,
        )


@pytest.mark.parametrize("stage", STAGES_EXTRA)
@pytest.mark.parametrize(
    "input_ts,raises",
    [
        (DEC_TS_PAST, False),
        (DEC_TS_MINUS_1, False),
        (DEC_TS, False),
        (DEC_TS_PLUS_1, True),
        ("2025-01-01T00:06:00.000Z", True),
    ],
)
def test_sbkt03_L01_stage_exact_boundary(stage, input_ts, raises):
    if raises:
        with pytest.raises(LookAheadLeakageError) as ei:
            enforce_stage_leakage(
                stage,
                decision_ts=DEC_TS,
                decision_input_max_ts=input_ts,
            )
        assert BK_LEAK_PREFIX in str(ei.value)
        assert stage in str(ei.value)
    else:
        enforce_stage_leakage(
            stage,
            decision_ts=DEC_TS,
            decision_input_max_ts=input_ts,
        )


def test_sbkt03_L01_invalid_stage_code_raises():
    with pytest.raises(ValueError):
        enforce_stage_leakage(
            "INVALID",
            decision_ts=DEC_TS,
            decision_input_max_ts=DEC_TS_PAST,
        )


FEATURE_CANDLE_TIMESTAMPS = [
    ("2025-01-01T00:00:00.000Z", False),
    ("2025-01-01T00:01:00.000Z", False),
    ("2025-01-01T00:02:00.000Z", False),
    ("2025-01-01T00:03:00.000Z", False),
    ("2025-01-01T00:03:30.000Z", False),
    ("2025-01-01T00:04:00.000Z", False),
    (DEC_TS_MINUS_1, False),
    (DEC_TS, False),
    (DEC_TS_PLUS_1, True),
    ("2025-01-01T00:05:01.000Z", True),
    ("2025-01-01T00:10:00.000Z", True),
    ("2026-01-01T00:00:00.000Z", True),
]


@pytest.mark.parametrize("hist_ts,raises", FEATURE_CANDLE_TIMESTAMPS)
def test_sbkt03_L01_feature_candle_wide_matrix(hist_ts, raises):
    """Feature stage candle close_time × 12 boundary timestamp = 12 hücre."""
    @dataclass
    class _C:
        close_time: str

    clock = ReplayClock()
    clock.advance(DEC_TS)
    if raises:
        with pytest.raises(LookAheadLeakageError):
            enforce_feature_stage_leakage(
                decision_ts=DEC_TS,
                candle_history=[_C(close_time=hist_ts)],
                clock=clock,
            )
    else:
        enforce_feature_stage_leakage(
            decision_ts=DEC_TS,
            candle_history=[_C(close_time=hist_ts)],
            clock=clock,
        )


@pytest.mark.parametrize(
    "hist_ts,raises",
    [
        (DEC_TS_PAST, False),
        (DEC_TS, False),
        (DEC_TS_PLUS_1, True),
    ],
)
def test_sbkt03_L01_feature_candle_close_time(hist_ts, raises):
    @dataclass
    class _C:
        close_time: str

    clock = ReplayClock()
    clock.advance(DEC_TS)
    if raises:
        with pytest.raises(LookAheadLeakageError):
            enforce_feature_stage_leakage(
                decision_ts=DEC_TS,
                candle_history=[_C(close_time=hist_ts)],
                clock=clock,
            )
    else:
        enforce_feature_stage_leakage(
            decision_ts=DEC_TS,
            candle_history=[_C(close_time=hist_ts)],
            clock=clock,
        )


def test_sbkt03_L01_clock_locked_access_fail():
    clock = ReplayClock()
    clock.advance(DEC_TS_PAST)
    clock.frozen = True
    with pytest.raises(LookAheadLeakageError):
        enforce_feature_stage_leakage(
            decision_ts=DEC_TS,
            candle_history=[],
            clock=clock,
        )


def test_sbkt03_L01_regime_featurets_ahead_raises():
    with pytest.raises(LookAheadLeakageError) as ei:
        enforce_regime_stage_leakage(
            decision_ts=DEC_TS,
            feature_ts=DEC_TS_PLUS_1,
        )
    assert "REGIME" in str(ei.value)


@pytest.mark.parametrize(
    "r_ts,f_ts,raises",
    [
        (DEC_TS_PAST, DEC_TS_PAST, False),
        (DEC_TS_PAST, DEC_TS, False),
        (DEC_TS_PLUS_1, DEC_TS_PAST, True),
        (DEC_TS_PAST, DEC_TS_PLUS_1, True),
    ],
)
def test_sbkt03_L01_strategy_composite(r_ts, f_ts, raises):
    if raises:
        with pytest.raises(LookAheadLeakageError):
            enforce_strategy_stage_leakage(
                decision_ts=DEC_TS,
                regime_detected_ts=r_ts,
                feature_ts=f_ts,
            )
    else:
        enforce_strategy_stage_leakage(
            decision_ts=DEC_TS,
            regime_detected_ts=r_ts,
            feature_ts=f_ts,
        )


def test_sbkt03_L01_opp_signal_ahead():
    with pytest.raises(LookAheadLeakageError):
        enforce_opportunity_stage_leakage(
            decision_ts=DEC_TS,
            signal_ts=DEC_TS_PLUS_1,
        )


def test_sbkt03_L01_risk_opp_ahead():
    with pytest.raises(LookAheadLeakageError):
        enforce_risk_stage_leakage(
            decision_ts=DEC_TS,
            opportunity_ts=DEC_TS_PLUS_1,
        )


def test_sbkt03_L01_fill_order_ahead():
    with pytest.raises(LookAheadLeakageError):
        enforce_fill_stage_leakage(
            decision_ts=DEC_TS,
            order_ts=DEC_TS_PLUS_1,
        )


def test_sbkt03_L01_max_ts_from_events_skips_non_str():
    @dataclass
    class _E:
        event_ts: str
    @dataclass
    class _E2:
        event_ts: object

    arr = [_E(event_ts=DEC_TS_PAST), _E2(event_ts=None), _E2(event_ts=123)]
    assert max_ts_from_events(arr, "event_ts") == DEC_TS_PAST


def test_sbkt03_L01_future_clock_access_raises():
    """runtime data akışında future ts erişim (LookAheadLeakageError)."""
    clock = ReplayClock()
    clock.advance(DEC_TS)
    assert clock.decision_ts == DEC_TS
    # Normal input max <= decision ts → pass
    enforce_stage_leakage(
        "FEATURE",
        decision_ts=DEC_TS,
        decision_input_max_ts=DEC_TS,
        clock=clock,
    )
    # Input max ts > clock.decision_ts → raise
    with pytest.raises(LookAheadLeakageError):
        enforce_stage_leakage(
            "REGIME",
            decision_ts=DEC_TS,
            decision_input_max_ts=DEC_TS_PLUS_1,
            clock=clock,
        )
