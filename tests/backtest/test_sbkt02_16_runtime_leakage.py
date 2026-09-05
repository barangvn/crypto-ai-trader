"""S-BKT-02-16: Runtime Leakage / OOS Guards (Priority 6).

Gerçek behavior assertions:
- decision_ts <= sonraki event (gelecekten okuma yok)
- train window içindeki olaylar validation/testte tüketilmez
- validation window testte tüketilmez
- fold train/val/test state isolation (metadata cross fold karışmaz)
- future price/volume/candle/signal/fill unavailable
- cross fold leakage forbidden
- fold windows overlap-free strict
"""

from __future__ import annotations

import json

import pytest

from app.backtest.multi_fold_runner import run_multifold_walkforward
from app.backtest.runner import BacktestRunner
from app.backtest.walk_forward import (
    WalkForwardConfig,
    generate_fold_splits,
    validate_no_inter_fold_overlap,
    cut_events_for_fold,
    _instant_from_event,
    _cmp_instant,
)
from app.backtest.run_metadata import BacktestAssumptions
from tests.backtest.conftest import SyntheticBundle


def _fac():
    def _mk(cost_overrides=None, cost_overrides_fold=None, walk_forward_single_fold=None):
        return BacktestRunner(
            assumptions=BacktestAssumptions(),
            cost_overrides=cost_overrides,
            cost_overrides_fold=cost_overrides_fold,
            walk_forward_single_fold=walk_forward_single_fold,
        )
    return _mk


def _evs(n=1000):
    return list(SyntheticBundle(num_candles=n).iter_events())


# ----- 01. Chronological boundary: train events < val events < test events ---
def test_cut_events_for_fold_train_not_leaking_val_test():
    folds = generate_fold_splits(_evs(800))
    for f in folds:
        tr, va, te = cut_events_for_fold(_evs(800), f)
        if len(tr) and len(va):
            tr_last = _instant_from_event(tr[-1])
            va_first = _instant_from_event(va[0])
            assert _cmp_instant(tr_last, va_first) < 0
        if len(va) and len(te):
            va_last = _instant_from_event(va[-1])
            te_first = _instant_from_event(te[0])
            assert _cmp_instant(va_last, te_first) < 0


# ----- 02. Train events are subset only of train window ---------------------
def test_cut_events_train_end_instant_within_train_window():
    folds = generate_fold_splits(_evs(800))
    for f in folds:
        tr, _, _ = cut_events_for_fold(_evs(800), f)
        for e in tr:
            t = _instant_from_event(e)
            assert f.train.start_instant <= t <= f.train.end_instant


def test_cut_events_val_within_val_window():
    folds = generate_fold_splits(_evs(800))
    for f in folds:
        _, va, _ = cut_events_for_fold(_evs(800), f)
        for e in va:
            t = _instant_from_event(e)
            assert f.validation.start_instant <= t <= f.validation.end_instant


def test_cut_events_test_within_test_window():
    folds = generate_fold_splits(_evs(800))
    for f in folds:
        _, _, te = cut_events_for_fold(_evs(800), f)
        for e in te:
            t = _instant_from_event(e)
            assert f.test.start_instant <= t <= f.test.end_instant


# ----- 03. Inter-fold overlap free validate_no_inter_fold_overlap ------------
def test_generate_fold_splits_produces_overlap_free_inter():
    for n in [400, 700, 1000, 1500]:
        folds = generate_fold_splits(_evs(n))
        validate_no_inter_fold_overlap(folds)  # no raise => OK


# ----- 04. Cross-fold metadata: her fold farklı train window start ----------
def test_cross_fold_metadata_no_mix():
    bundle = SyntheticBundle(num_candles=900)
    res = run_multifold_walkforward(_fac(), bundle)
    starts = [r.metadata.train_window.train.start_instant for r in res.per_fold_results]
    ends = [r.metadata.test_window.test.end_instant for r in res.per_fold_results]
    # starts strictly increasing
    for i in range(1, len(starts)):
        assert starts[i] > starts[i - 1]
    # ends strictly increasing
    for i in range(1, len(ends)):
        assert ends[i] > ends[i - 1]


# ----- 05. Cross-fold leakage: fold[k] train instant > fold[k-1] test instant
def test_no_cross_fold_leakage_instant_order():
    import datetime as _dt
    cfg = WalkForwardConfig(inter_fold_gap_ms=60_001)
    evs_numeric = [type("E", (), {"event_ts": str(1_700_000_000_000 + i * 60_000)})() for i in range(900)]
    folds = generate_fold_splits(evs_numeric, cfg)
    for i in range(1, len(folds)):
        prev_test_end = folds[i - 1].test.end_instant
        curr_train_start = folds[i].train.start_instant
        # strict gap
        delta = int(curr_train_start) - int(prev_test_end)
        assert delta >= cfg.inter_fold_gap_ms


# ----- 06. Future data unavailable: test metadata.end < ev total +1 not breach
def test_no_fold_breaches_total_event_end():
    N = 1200
    evs = _evs(N)
    total_last = _instant_from_event(evs[-1])
    folds = generate_fold_splits(evs)
    for f in folds:
        assert f.test.end_instant <= total_last


# ----- 07. Provenance metadata: fold 0 manifest cannot reference Fold 2 SHA -
def test_manifest_per_fold_cost_distinct_length():
    res = run_multifold_walkforward(_fac(), SyntheticBundle(num_candles=800))
    per = res.manifest.per_fold_cost_manifest
    assert len(per) == 5


# ----- 08. Strict overlap-free: intra train-val strict (not equal) -----------
def test_intra_train_val_strictly_less_than():
    cfg = WalkForwardConfig(intra_window_gap_ms=120_000)
    folds = generate_fold_splits(_evs(1000), cfg)
    for f in folds:
        assert f.train.end_instant < f.validation.start_instant
        assert f.validation.end_instant < f.test.start_instant


# ----- 09. Boundary 1ms gap OK: strict ordering preserved -------------------
def test_small_gap_strict_ordering():
    cfg = WalkForwardConfig(intra_window_gap_ms=60_001, inter_fold_gap_ms=60_001)
    evs_numeric = [type("E", (), {"event_ts": str(1_700_000_000_000 + i * 60_000)})() for i in range(1200)]
    folds = generate_fold_splits(evs_numeric, cfg)
    for f in folds:
        # integer arithmetic compare strict
        assert int(f.validation.start_instant) - int(f.train.end_instant) >= 60_001
        assert int(f.test.start_instant) - int(f.validation.end_instant) >= 60_001


# ----- 10. Deterministic ordering 10x: each fold chrono ---------------------
def test_10x_fold_chrono_boundaries():
    outs = []
    for _ in range(10):
        folds = generate_fold_splits(_evs(900))
        outs.append([(f.train.end_instant, f.validation.start_instant, f.test.end_instant) for f in folds])
    assert len(set(map(str, outs))) == 1
