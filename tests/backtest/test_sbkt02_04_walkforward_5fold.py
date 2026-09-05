"""S-BKT-02-04: 5-Fold Walk-Forward Creation, Boundaries, Overlap, Chronological."""

from __future__ import annotations

import pytest

from app.backtest.walk_forward import (
    WalkForwardConfig,
    generate_fold_splits,
    validate_no_inter_fold_overlap,
)
from tests.backtest.conftest import SyntheticBundle


def _dummy_events(n=300, symbol="BTC_USDT"):
    b = SyntheticBundle(num_candles=n)
    return list(b.iter_events())


def test_5fold_len():
    evs = _dummy_events(300)
    folds = generate_fold_splits(evs)
    assert len(folds) == 5


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
def test_nfold_len_various(n):
    evs = _dummy_events(n * 60)
    cfg = WalkForwardConfig(n_folds=n)
    folds = generate_fold_splits(evs, cfg)
    assert len(folds) == n


def test_5fold_chronological():
    evs = _dummy_events(500)
    folds = generate_fold_splits(evs)
    prev_start = None
    for f in folds:
        start = f.train.start_instant
        if prev_start is not None:
            assert start > prev_start
        prev_start = start


def test_5fold_overlap_free_intra():
    evs = _dummy_events(500)
    folds = generate_fold_splits(evs)
    for f in folds:
        assert f.train.end_instant < f.validation.start_instant
        assert f.validation.end_instant < f.test.start_instant


def test_5fold_overlap_free_inter():
    evs = _dummy_events(1000)
    cfg = WalkForwardConfig(n_folds=5, inter_fold_gap_ms=3600_000)
    folds = generate_fold_splits(evs, cfg)
    validate_no_inter_fold_overlap(folds)


def test_fold_ordering_deterministic_10x():
    evs = _dummy_events(500)
    cfg = WalkForwardConfig()
    sets_ids = []
    for _ in range(10):
        folds = generate_fold_splits(list(evs), cfg)
        sets_ids.append(tuple(f.fold_id + f.train.start_instant for f in folds))
    assert len(set(sets_ids)) == 1


def test_invalid_overlap_raises():
    from app.backtest.walk_forward import WalkForwardFoldDefinition, WindowSplit, SplitDataset

    bad = [
        WalkForwardFoldDefinition(
            fold_id="F001",
            fold_index=0,
            train=WindowSplit(SplitDataset.TRAIN, "1", "100", 10),
            validation=WindowSplit(SplitDataset.VALIDATION, "200", "300", 10),
            test=WindowSplit(SplitDataset.TEST, "301", "600", 29),
            segment_start_idx=0,
            segment_end_idx=50,
        ),
        WalkForwardFoldDefinition(
            fold_id="F002",
            fold_index=1,
            train=WindowSplit(SplitDataset.TRAIN, "400", "650", 25),  # overlap F001 test 301-600
            validation=WindowSplit(SplitDataset.VALIDATION, "700", "750", 5),
            test=WindowSplit(SplitDataset.TEST, "751", "900", 15),
            segment_start_idx=50,
            segment_end_idx=100,
        ),
    ]
    with pytest.raises(ValueError):
        validate_no_inter_fold_overlap(bad)


def test_small_events_raises():
    evs = _dummy_events(20)
    cfg = WalkForwardConfig(n_folds=5)
    with pytest.raises(ValueError):
        generate_fold_splits(evs, cfg)


def test_zero_length_window_raises():
    evs = _dummy_events(30)
    cfg = WalkForwardConfig(n_folds=10)
    with pytest.raises(ValueError):
        generate_fold_splits(evs, cfg)


@pytest.mark.parametrize("sym", ["BTC_USDT", "ETH_USDT", "SOL_USDT"])
def test_multisymbol_5fold(sym):
    evs = _dummy_events(800, symbol=sym)
    folds = generate_fold_splits(evs)
    assert len(folds) == 5
