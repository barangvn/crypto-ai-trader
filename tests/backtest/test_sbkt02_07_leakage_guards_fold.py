"""S-BKT-02-07: Fold Leakage Guards + Future Data."""

from __future__ import annotations

import pytest

from app.backtest.walk_forward import (
    WalkForwardConfig,
    WalkForwardFoldDefinition,
    WindowSplit,
    generate_fold_splits,
    validate_no_inter_fold_overlap,
)
from tests.backtest.conftest import SyntheticBundle


def _events_numeric(n=500, step_ms=60_000, start_ms=1_700_000_000_000):
    """Sayısal (int milisaniye) timestamp'li basit event tuple listesi."""
    evs = []
    for i in range(n):
        ts = str(start_ms + i * step_ms)
        evs.append(type("E", (), {"event_ts": ts})())
    return evs


def _events(n=500):
    return list(SyntheticBundle(num_candles=n).iter_events())


def test_fold_test_not_leaking_future():
    evs = _events_numeric(1000)
    folds = generate_fold_splits(evs)
    assert folds[0].test.end_instant < folds[1].train.start_instant


def test_inter_fold_gap_sets_boundary():
    evs = _events_numeric(1200, step_ms=60_000)
    cfg = WalkForwardConfig(n_folds=3, inter_fold_gap_ms=3_600_000)
    folds = generate_fold_splits(evs, cfg)
    gap = int(folds[1].train.start_instant) - int(folds[0].test.end_instant)
    assert gap >= 3_600_000


def test_no_overlap_forced_intra():
    evs = _events_numeric(500)
    folds = generate_fold_splits(evs)
    for f in folds:
        assert f.train.end_instant < f.validation.start_instant
        assert f.validation.end_instant < f.test.start_instant


def test_fold_timestamp_boundaries():
    evs = _events_numeric(1000)
    cfg = WalkForwardConfig(n_folds=2, intra_window_gap_ms=60_001)
    folds = generate_fold_splits(evs, cfg)
    for f in folds:
        v_start = int(f.validation.start_instant)
        t_end = int(f.train.end_instant)
        assert v_start - t_end >= cfg.intra_window_gap_ms
