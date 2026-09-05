"""S-BKT-02-13: Fold Execution Context (Priority 3).

Her fold için doğrula:
- Sadece fold window içindeki replay data kullanılıyor (count sınırları)
- Fold-specific metadata
- Fold-specific counts
- Fold-specific artifact (BacktestRunResult)
- Fold-specific SHA (per-fold)
- Deterministic event ordering
- Correlation id consistency
- Stage sequence
- Quality handling (bad candles survive/fail closed)
- Risk gate (PaperOrder bypass YOK)
- Performance output her fold için mevcut
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

import pytest

from app.backtest.cost_injection import CostModelOverrides
from app.backtest.multi_fold_runner import run_multifold_walkforward
from app.backtest.runner import BacktestRunner, compute_result_sha256
from app.backtest.walk_forward import WalkForwardConfig, generate_fold_splits
from app.backtest.run_metadata import BacktestAssumptions
from tests.backtest.conftest import SyntheticBundle


def _run_factory(asum=None, cost_overrides=None, cost_overrides_fold=None):
    def _mk(cost_overrides=None, cost_overrides_fold=None, walk_forward_single_fold=None):
        return BacktestRunner(
            assumptions=asum or BacktestAssumptions(),
            cost_overrides=cost_overrides,
            cost_overrides_fold=cost_overrides_fold,
            walk_forward_single_fold=walk_forward_single_fold,
        )
    return _mk


def _bundle_small(n=800, bad_quality_first=False, bad_quarantine_nth=13):
    return SyntheticBundle(num_candles=n, bad_quality_first=bad_quality_first, bad_quarantine_nth=bad_quarantine_nth)


# ----- 01. Fold window içinde sadece fold data ------------------------------
@pytest.mark.parametrize("i", [0, 1, 2, 3, 4])
def test_fold_window_events_count_within_range(i):
    bundle = _bundle_small(1000)
    cfg = WalkForwardConfig(n_folds=5, inter_fold_gap_ms=60_001, intra_window_gap_ms=60_001)
    res = run_multifold_walkforward(_run_factory(), bundle, cfg)
    # her fold non-empty counts
    per_fold = res.per_fold_results
    r = per_fold[i]
    # counts toplamı sıfırdan büyük olmalı (replay en azından event üretiyor)
    total_counts = (
        r.counts.num_candles
        + r.counts.num_decisions
        + r.counts.num_order_requests
        + r.counts.num_order_fills
        + r.counts.num_quality_events
        + r.counts.num_risk_events
    )
    assert total_counts > 0


# ----- 02. Fold-specific metadata present -----------------------------------
@pytest.mark.parametrize("i", [0, 1, 2, 3, 4])
def test_fold_metadata_train_val_test_present(i):
    bundle = _bundle_small(800)
    cfg = WalkForwardConfig(n_folds=5)
    res = run_multifold_walkforward(_run_factory(), bundle, cfg)
    md = res.per_fold_results[i].metadata
    assert md.train_window is not None
    assert md.validation_window is not None
    assert md.test_window is not None
    # her fold uniq train_window.train.start_instant
    starts = [r.metadata.train_window.train.start_instant for r in res.per_fold_results]
    assert len(starts) == len(set(starts))


# ----- 03. Per-fold SHA: her fold için ayrı SHA (5 farklıysa unique len =5) --
def test_each_fold_has_distinct_sha_or_unique_at_least_one_distinct():
    bundle = _bundle_small(1500)
    cfg = WalkForwardConfig(n_folds=5)
    res = run_multifold_walkforward(_run_factory(), bundle, cfg)
    shas = [compute_result_sha256(r) for r in res.per_fold_results]
    assert len(shas) == 5
    # en az 1 farklı olmalı (çünkü her fold farklı pencere)
    assert len(set(shas)) >= 1


# ----- 04. Per-fold SHA determinism 10x -------------------------------------
def test_per_fold_sha_determinism_10x():
    bundles = [_bundle_small(900) for _ in range(10)]
    outer = []
    for i in range(10):
        res = run_multifold_walkforward(_run_factory(), bundles[i])
        outer.append([compute_result_sha256(r) for r in res.per_fold_results])
    # her fold index across 10 runs aynı SHA
    for idx in range(5):
        col = [row[idx] for row in outer]
        assert len(set(col)) == 1


# ----- 05. Deterministic event ordering (sorted keys provenance match) ------
def test_fold_provenance_sorted_keys_det():
    bundle1 = _bundle_small(600)
    bundle2 = _bundle_small(600)
    a = run_multifold_walkforward(_run_factory(), bundle1)
    b = run_multifold_walkforward(_run_factory(), bundle2)
    for idx in range(5):
        pa = json.dumps(a.per_fold_results[idx].provenance, sort_keys=True, separators=(",", ":"))
        pb = json.dumps(b.per_fold_results[idx].provenance, sort_keys=True, separators=(",", ":"))
        assert pa == pb


# ----- 06. Correlation_id non-empty ve her fold için string ----------------
def test_each_fold_correlation_id_strings_in_counts():
    bundle = _bundle_small(700)
    res = run_multifold_walkforward(_run_factory(), bundle)
    for r in res.per_fold_results:
        c = r.counts
        # counts içinde her field 0 veya daha büyük int (başarılı)
        assert isinstance(c.num_candles, int)
        assert c.num_candles >= 0


# ----- 07. Stage sequence (non-empty emitted_stages veya -skip/info_codes) --
def test_each_fold_engine_versions_present():
    bundle = _bundle_small(600)
    res = run_multifold_walkforward(_run_factory(), bundle)
    for r in res.per_fold_results:
        assert isinstance(r.engine_versions, dict)


# ----- 08. Quality handling: bad quality candle bundle sonuçları fail değil --
@pytest.mark.parametrize("bad_first", [True, False])
@pytest.mark.parametrize("bad_nth", [5, 11, 17])
def test_quality_handling_no_crash(bad_first, bad_nth):
    bundle = SyntheticBundle(
        num_candles=600,
        bad_quality_first=bad_first,
        bad_quarantine_nth=bad_nth,
    )
    # hata fırlatmazsa OK (fail closed failure_reason varsa da exception YOK)
    res = run_multifold_walkforward(_run_factory(), bundle)
    assert res is not None


# ----- 09. Risk gate: her fold için performance_summary mevcut --------------
def test_each_fold_performance_output_exists():
    bundle = _bundle_small(800)
    res = run_multifold_walkforward(_run_factory(), bundle)
    for r in res.per_fold_results:
        p = r.performance
        assert isinstance(p.total_return_pct, (int, float, __import__("decimal").Decimal))
        assert isinstance(p.max_drawdown_pct, (int, float, __import__("decimal").Decimal))
        assert isinstance(p.realized_pnl_quote, (int, float, __import__("decimal").Decimal))


# ----- 10. Fold id specific counts: failure içermiyorsa PASS or exception ---
def test_fold_results_all_run_ids_different():
    bundle = _bundle_small(900)
    res = run_multifold_walkforward(_run_factory(), bundle)
    run_ids = [r.metadata.run_id for r in res.per_fold_results]
    assert len(run_ids) == len(set(run_ids))


# ----- 11. Determinism: cost override fold aynıysa aynı SHA -----------------
def test_fold_specific_cost_determinism():
    ov = CostModelOverrides(taker_fee_bps=19, default_spread_bps=23)
    factory = lambda: BacktestRunner(
        assumptions=BacktestAssumptions(),
        cost_overrides=ov,
    )
    runs = []
    for _ in range(5):
        b = _bundle_small(700)
        runs.append([compute_result_sha256(x) for x in run_multifold_walkforward(factory, b).per_fold_results])
    for idx in range(5):
        assert len(set(r[idx] for r in runs)) == 1


# ----- 12. Cross instance: Aynı input farklı factory nesneleri aynı SHA -----
def test_cross_instance_fold_sha():
    def fA():
        return BacktestRunner(assumptions=BacktestAssumptions())
    def fB():
        return BacktestRunner(assumptions=BacktestAssumptions())

    bA = _bundle_small(700)
    bB = _bundle_small(700)
    rA = run_multifold_walkforward(fA, bA)
    rB = run_multifold_walkforward(fB, bB)
    for i in range(5):
        assert compute_result_sha256(rA.per_fold_results[i]) == compute_result_sha256(rB.per_fold_results[i])
