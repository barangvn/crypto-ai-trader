"""S-BKT-03 02: Fold overlap leakage (train < val < test; inter-fold isolation)."""

from __future__ import annotations

import pytest

from app.backtest.ordering import LookAheadLeakageError
from app.backtest.leakage_asserts import (
    assert_window_train_val_test_ordered,
    assert_interfold_no_overlap,
    BK_LEAK_PREFIX,
)


T_END = "2025-01-01T00:10:00.000Z"
V_START = "2025-01-01T00:10:00.001Z"
V_END = "2025-01-01T00:20:00.000Z"
TST_START = "2025-01-01T00:20:00.001Z"
TST_END = "2025-01-01T00:30:00.000Z"
FOLD_B_START = "2025-01-02T00:00:00.000Z"


def test_sbkt03_L02_window_pass():
    assert_window_train_val_test_ordered(T_END, V_START, V_END, TST_START, fold_id="F1")


WINDOW_VIOLATIONS_MATRIX = [
    ("2025-01-01T00:10:00.001Z", V_START, V_END, TST_START),
    (T_END, T_END, V_END, TST_START),
    (T_END, V_START, TST_START, TST_START),
    (T_END, V_START, "2025-01-01T00:25:00.000Z", "2025-01-01T00:15:00.000Z"),
    # extra 10 varied violations (14 total cells):
    # --- FIXED 2026-09-05: prev .000001Z cases WERE valid (.000001 < .001 = PASS) → changed to REAL violations:
    ("2025-01-01T00:10:00.002Z", V_START, V_END, TST_START),  # train_end(00:10.002) > val_start(00:10.001)
    ("2025-01-01T00:11:00.000Z", V_START, V_END, TST_START),
    (T_END, "2025-01-01T00:09:00.000Z", V_END, TST_START),
    (T_END, "2024-12-31T23:59:00.000Z", V_END, TST_START),
    (T_END, V_START, "2025-01-01T00:19:59.999Z", "2025-01-01T00:19:59.999Z"),
    (T_END, V_START, "2025-01-01T00:30:00.000Z", "2025-01-01T00:25:00.000Z"),
    (T_END, V_START, "2025-01-01T00:35:00.000Z", "2025-01-01T00:30:00.000Z"),
    (T_END, V_START, "2025-01-01T00:20:00.002Z", TST_START),  # val_end(00:20.002) > test_start(00:20.001)
    ("2025-01-01T00:09:59.999Z", V_START, V_END, "2025-01-01T00:19:59.999Z"),
    (T_END, V_START, V_END, V_START),  # test_start == val_start (00:10.001) << val_end → overlap
]


@pytest.mark.parametrize("te,vs,ve,ts", WINDOW_VIOLATIONS_MATRIX)
def test_sbkt03_L02_window_violations_extended(te, vs, ve, ts):
    with pytest.raises(LookAheadLeakageError) as ei:
        assert_window_train_val_test_ordered(te, vs, ve, ts)
    assert BK_LEAK_PREFIX in str(ei.value)
    assert "FOLD_WINDOW_INTRA" in str(ei.value)


@pytest.mark.parametrize(
    "te,vs,ve,ts",
    [
        ("2025-01-01T00:10:00.001Z", V_START, V_END, TST_START),  # train end > val start exact (tie raise)
        (T_END, T_END, V_END, TST_START),  # val start == train end (tie raise strict)
        (T_END, V_START, TST_START, TST_START),  # val end == test start exact tie
        (T_END, V_START, "2025-01-01T00:25:00.000Z", "2025-01-01T00:15:00.000Z"),  # test start < val end (cross contamination)
    ],
)
def test_sbkt03_L02_window_violations(te, vs, ve, ts):
    with pytest.raises(LookAheadLeakageError) as ei:
        assert_window_train_val_test_ordered(te, vs, ve, ts)
    assert BK_LEAK_PREFIX in str(ei.value)
    assert "FOLD_WINDOW_INTRA" in str(ei.value)


def test_sbkt03_L02_interfold_pass_no_gap():
    assert_interfold_no_overlap(TST_END, FOLD_B_START)


def test_sbkt03_L02_interfold_overlap_raises():
    # fold A.test_end == fold B.train_start → tie raise (no gap, contamination)
    with pytest.raises(LookAheadLeakageError) as ei:
        assert_interfold_no_overlap(TST_END, TST_END, fold_prev_id="A", fold_next_id="B")
    assert "FOLD_INTER" in str(ei.value)


def test_sbkt03_L02_interfold_gap_required_pass():
    # Gap: 1 day ms
    gap_ms = 86400_000  # 24h
    assert_interfold_no_overlap(
        TST_END,
        "2025-01-02T00:30:00.000Z",
        inter_gap_ms=gap_ms,
    )


def test_sbkt03_L02_interfold_gap_required_violation():
    gap_ms = 86400_000 * 2  # 48h required
    with pytest.raises(LookAheadLeakageError) as ei:
        assert_interfold_no_overlap(TST_END, FOLD_B_START, inter_gap_ms=gap_ms)
    assert "FOLD_INTER_GAP" in str(ei.value)


INTERFOLD_GAP_MATRIX = [
    (0, "2025-01-01T00:30:00.001Z", True),
    (0, "2025-01-01T00:30:00.000Z", False),  # tie → raise
    (0, "2025-01-01T00:29:59.999Z", False),  # overlap → raise
    (60_000, "2025-01-01T00:31:00.000Z", True),
    (60_000, "2025-01-01T00:30:59.999Z", False),  # < 60s gap → raise
    (3600_000, "2025-01-01T01:30:00.000Z", True),
    (3600_000, "2025-01-01T01:29:59.999Z", False),
    (86400_000, "2025-01-02T00:30:00.000Z", True),
]


@pytest.mark.parametrize("gap_ms,next_start,passes", INTERFOLD_GAP_MATRIX)
def test_sbkt03_L02_interfold_gap_8cases(gap_ms, next_start, passes):
    """8 hücre: inter-fold isolation various gaps."""
    if passes:
        assert_interfold_no_overlap(TST_END, next_start, inter_gap_ms=gap_ms)
    else:
        with pytest.raises(LookAheadLeakageError):
            assert_interfold_no_overlap(TST_END, next_start, inter_gap_ms=gap_ms)


def test_sbkt03_L02_empty_ts_noop():
    assert_interfold_no_overlap("", "")
    assert_window_train_val_test_ordered("", "", "", "")
