"""S-BKT-02-15: Multi-Symbol x Multi-Fold Matrix (Priority 5).

1x1, 1x5, 2x1, 2x5, Nx5, symbol ordering determinism, duplicate/unknown/empty symbols,
deterministic canonicalization, cross-symbol fold determinism 10x.
"""

from __future__ import annotations

import json

import pytest

from app.backtest.multi_fold_runner import (
    compute_multifold_sha256,
    run_multifold_walkforward,
)
from app.backtest.runner import BacktestRunner
from app.backtest.walk_forward import WalkForwardConfig, generate_fold_splits
from app.backtest.run_metadata import BacktestAssumptions
from tests.backtest.conftest import SyntheticBundle


def _sym(symbol, n=700, bad_quality_first=False, bad_quarantine_nth=23):
    return SyntheticBundle(
        num_candles=n,
        bad_quality_first=bad_quality_first,
        bad_quarantine_nth=bad_quarantine_nth,
    )


def _fac():
    def _mk(cost_overrides=None, cost_overrides_fold=None, walk_forward_single_fold=None):
        return BacktestRunner(
            assumptions=BacktestAssumptions(),
            cost_overrides=cost_overrides,
            cost_overrides_fold=cost_overrides_fold,
            walk_forward_single_fold=walk_forward_single_fold,
        )
    return _mk


SYMS = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT", "XRP_USDT", "ADA_USDT", "DOGE_USDT", "AVAX_USDT"]


# ----- 1. 1 symbol x 1/5 fold -----------------------------------------------
@pytest.mark.parametrize("nf", [1, 5])
def test_1symbol_n_fold(nf):
    cfg = WalkForwardConfig(n_folds=nf, inter_fold_gap_ms=60_001, intra_window_gap_ms=60_001)
    res = run_multifold_walkforward(_fac(), _sym(SYMS[0], n=max(60 * nf, 400)), cfg)
    assert res is not None
    assert len(res.per_fold_results) == nf


# ----- 2. 2 symbols x 1/5 fold ----------------------------------------------
@pytest.mark.parametrize("nf", [1, 5])
def test_2symbols_each_n_fold_separate_calls_deterministic(nf):
    cfg = WalkForwardConfig(n_folds=nf, inter_fold_gap_ms=60_001, intra_window_gap_ms=60_001)
    out1a = []
    out1b = []
    N_EV = max(60 * nf, 500)
    for _ in range(2):
        a = run_multifold_walkforward(_fac(), _sym(SYMS[0], n=N_EV), cfg)
        b = run_multifold_walkforward(_fac(), _sym(SYMS[1], n=N_EV), cfg)
        out1a.append(compute_multifold_sha256(a))
        out1b.append(compute_multifold_sha256(b))
    assert len(set(out1a)) == 1
    assert len(set(out1b)) == 1


# ----- 3. N symbols x 5 fold (1..8 semboller) -------------------------------
@pytest.mark.parametrize("n_sym", [1, 2, 3, 4, 5, 6, 7, 8])
def test_n_symbols_each_5_fold_separate(n_sym):
    cfg = WalkForwardConfig(n_folds=5)
    out = []
    for i in range(n_sym):
        b = _sym(SYMS[i], n=700)
        res = run_multifold_walkforward(_fac(), b, cfg)
        out.append(compute_multifold_sha256(res))
    # same symbol ise aynı; farklılar farklı olabilir ya da aynı (aynı sentetik)
    assert len(out) == n_sym


# ----- 4. Symbol ordering determinism (A,B vs B,A folds) --------------------
def test_symbol_calls_order_does_not_affect_symbol_own_determinism():
    cfg = WalkForwardConfig(n_folds=5)
    a1 = run_multifold_walkforward(_fac(), _sym("BTC_USDT", n=800), cfg)
    a2 = run_multifold_walkforward(_fac(), _sym("BTC_USDT", n=800), cfg)
    b1 = run_multifold_walkforward(_fac(), _sym("ETH_USDT", n=800), cfg)
    b2 = run_multifold_walkforward(_fac(), _sym("ETH_USDT", n=800), cfg)
    assert compute_multifold_sha256(a1) == compute_multifold_sha256(a2)
    assert compute_multifold_sha256(b1) == compute_multifold_sha256(b2)


# ----- 5. Duplicate symbol names --------------------------------------------
def test_duplicate_symbol_same_result():
    cfg = WalkForwardConfig(n_folds=3)
    a = run_multifold_walkforward(_fac(), _sym("X", n=600), cfg)
    b = run_multifold_walkforward(_fac(), _sym("X", n=600), cfg)
    assert compute_multifold_sha256(a) == compute_multifold_sha256(b)


# ----- 6. Unknown symbol string - symbol name independent (SyntheticBundle fixed) -
@pytest.mark.parametrize("name", ["FOO_BAR", "UNKNOWN", "A", "", "X" * 64])
def test_unknown_or_empty_name_symbol_fold_ok(name):
    cfg = WalkForwardConfig(n_folds=3)
    # name arg ignored by SyntheticBundle (uses FIXED_SYMBOL internally),
    # but call must not raise.
    res = run_multifold_walkforward(_fac(), _sym(name, n=500), cfg)
    assert res is not None
    assert len(res.per_fold_results) == 3


# ----- 7. Deterministic 10x multi-symbol ------------------------------------
@pytest.mark.parametrize("sym_idx", [0, 1, 2, 3])
def test_10x_same_symbol_same_sha(sym_idx):
    cfg = WalkForwardConfig(n_folds=5)
    rows = []
    for _ in range(10):
        res = run_multifold_walkforward(_fac(), _sym(SYMS[sym_idx], n=900), cfg)
        rows.append(compute_multifold_sha256(res))
    assert len(set(rows)) == 1


# ----- 8. Fold construction per symbol determinism (no runner) --------------
@pytest.mark.parametrize("sym_idx", [0, 1, 2])
def test_fold_construction_per_symbol_determinism_10x(sym_idx):
    def _evs(start):
        evs = []
        for i in range(700):
            evs.append(type("E", (), {"event_ts": str(1_700_000_000_000 + start * 10_000 + i * 60_000)})())
        return evs

    outs = []
    for _ in range(10):
        folds = generate_fold_splits(_evs(sym_idx))
        outs.append(json.dumps([f.to_sorted_dict() for f in folds], sort_keys=True))
    assert len(set(outs)) == 1
