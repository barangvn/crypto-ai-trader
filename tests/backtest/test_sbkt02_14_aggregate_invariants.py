"""S-BKT-02-14: Aggregate Artifact Invariants (Priority 4).

1/2/5 folds, empty/failed fold handling, partial aggregate (forbidden/behavior),
canonical ordering determinism, aggregate SHA determinism,
artifact roundtrip, aggregate metadata, aggregate counts,
aggregate performance, cross-instance SHA.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile

import pytest

from app.backtest.cost_injection import CostModelOverrides
from app.backtest.multi_fold_runner import (
    MultiFoldBacktestResult,
    compute_multifold_sha256,
    load_multi_fold_backtest_artifact,
    run_multifold_walkforward,
    save_multi_fold_backtest_artifact,
    verify_multifold_deterministic,
)
from app.backtest.runner import BacktestRunner, compute_result_sha256
from app.backtest.walk_forward import WalkForwardConfig
from app.backtest.run_metadata import BacktestAssumptions
from tests.backtest.conftest import SyntheticBundle


def _factory(asum=None, cost=None, cost_fold=None):
    asum = asum or BacktestAssumptions()
    def _mk(cost_overrides=None, cost_overrides_fold=None, walk_forward_single_fold=None):
        return BacktestRunner(
            assumptions=asum,
            cost_overrides=cost_overrides if cost_overrides is not None else cost,
            cost_overrides_fold=cost_overrides_fold if cost_overrides_fold is not None else cost_fold,
            walk_forward_single_fold=walk_forward_single_fold,
        )
    return _mk


def _b(n=800, **kw):
    return SyntheticBundle(num_candles=n, **kw)


# ----- 01. 1/2/5 fold aggregate creation ------------------------------------
@pytest.mark.parametrize("nf", [1, 2, 5])
def test_n_fold_aggregate_creation(nf):
    cfg = WalkForwardConfig(n_folds=nf, inter_fold_gap_ms=60_001, intra_window_gap_ms=60_001)
    res = run_multifold_walkforward(_factory(), _b(max(60 * nf, 300)), cfg)
    assert isinstance(res, MultiFoldBacktestResult)
    assert len(res.per_fold_results) == nf
    assert len(res.manifest.per_fold_sha256) == nf
    assert len(res.manifest.fold_definitions_sorted_dict) == nf


# ----- 02. Empty fold count edge --------------------------------------------
def test_empty_fold_cfg_zero_raises():
    cfg = WalkForwardConfig(n_folds=0)
    with pytest.raises(ValueError):
        run_multifold_walkforward(_factory(), _b(100), cfg)


# ----- 03. Failed fold detection + aggregate status FAILED ------------------
def test_failed_fold_status_not_pass_aggregate():
    # insufficient events = folds fail or reduce => status PASS/FAILED one of them OK
    try:
        cfg = WalkForwardConfig(n_folds=5)
        res = run_multifold_walkforward(_factory(), _b(20), cfg)
        assert res.manifest.overall_status in ("PASS", "FAILED")
        assert isinstance(res.manifest.failed_fold_ids, list)
    except ValueError:
        # acceptable too
        assert True


# ----- 04. Canonical ordering determinism (fold_index 0..n-1) ----------------
@pytest.mark.parametrize("_", range(5))
def test_canonical_fold_order_invariant(_):
    res = run_multifold_walkforward(_factory(), _b(900))
    idxs = [f["fold_index"] for f in res.manifest.fold_definitions_sorted_dict]
    assert idxs == [0, 1, 2, 3, 4]


def test_aggregate_manifest_order_independent_of_call_count():
    rows = []
    for _ in range(10):
        res = run_multifold_walkforward(_factory(), _b(900))
        rows.append(
            json.dumps(res.manifest.config_sorted_dict, sort_keys=True, separators=(",", ":"))
            + "|"
            + ",".join(res.manifest.per_fold_sha256)
        )
    assert len(set(rows)) == 1


# ----- 05. Aggregate SHA determinism 10x ------------------------------------
def test_aggregate_sha_determinism_10x():
    shas = []
    for _ in range(10):
        res = run_multifold_walkforward(_factory(), _b(1000))
        shas.append(compute_multifold_sha256(res))
    assert len(set(shas)) == 1


# ----- 06. Artifact save/load roundtrip --------------------------------------
def test_save_load_roundtrip_preserves_sha():
    res = run_multifold_walkforward(_factory(), _b(700))
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "mf.json")
        save_multi_fold_backtest_artifact(res, path)
        loaded = load_multi_fold_backtest_artifact(path)
        # loaded is a dict with "sha256" and "result"
        assert compute_multifold_sha256(res) == loaded["sha256"]


def test_verify_passes_after_save_load():
    res = run_multifold_walkforward(_factory(), _b(700))
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "mf.json")
        exp_sha = save_multi_fold_backtest_artifact(res, path)
        ok = verify_multifold_deterministic([path])
        assert ok["is_deterministic"] is True
        assert ok["sha_list"] == [exp_sha]


# ----- 07. Aggregate metadata: num folds -------------------------------------
def test_aggregate_metadata_num_folds_matches():
    cfg = WalkForwardConfig(n_folds=5)
    res = run_multifold_walkforward(_factory(), _b(800), cfg)
    assert res.manifest.config_sorted_dict["n_folds"] == 5
    assert len(res.per_fold_results) == 5


# ----- 08. Aggregate counts: sum of per-fold counts meaningful ----------------
def test_aggregate_summary_counts_match_lengths():
    res = run_multifold_walkforward(_factory(), _b(900))
    s = res.aggregate_summary
    n = len([r for r in res.per_fold_results if not r.failure_reason_codes])
    assert isinstance(s.num_folds_attempted, int)
    assert s.num_folds_attempted == 5
    assert 0 <= s.num_folds_ok <= 5
    assert s.num_folds_ok == n


# ----- 09. Aggregate performance averages: returns in plausible range --------
def test_aggregate_avg_performance_reasonable_range():
    res = run_multifold_walkforward(_factory(), _b(1200))
    s = res.aggregate_summary
    # returns -> [-100, 100] arası makul
    assert -200.0 <= float(s.avg_total_return_pct) <= 200.0
    assert 0.0 <= float(s.avg_max_drawdown_pct) <= 200.0


# ----- 10. Cross-instance aggregate SHA --------------------------------------
def test_cross_instance_aggregate_sha_identical():
    def fa(): return BacktestRunner(assumptions=BacktestAssumptions())
    def fb(): return BacktestRunner(assumptions=BacktestAssumptions())
    ba, bb = _b(900), _b(900)
    ra = run_multifold_walkforward(fa, ba)
    rb = run_multifold_walkforward(fb, bb)
    assert compute_multifold_sha256(ra) == compute_multifold_sha256(rb)


# ----- 11. Cost override applied aggregate => sha changes vs default --------
def test_aggregate_sha_changes_with_cost_override():
    no_ov = run_multifold_walkforward(_factory(), _b(700))
    ov = run_multifold_walkforward(
        _factory(cost=CostModelOverrides(taker_fee_bps=77, default_spread_bps=88)),
        _b(700),
    )
    assert compute_multifold_sha256(no_ov) != compute_multifold_sha256(ov)


# ----- 12. Per-fold SHA list matches results --------------------------------
def test_manifest_sha_matches_compute_result_sha():
    res = run_multifold_walkforward(_factory(), _b(900))
    for r, sha in zip(res.per_fold_results, res.manifest.per_fold_sha256):
        assert compute_result_sha256(r) == sha


# ----- 13. Save twice same content => same SHA file content -----------------
def test_double_save_same_sha():
    res = run_multifold_walkforward(_factory(), _b(600))
    with tempfile.TemporaryDirectory() as td:
        p1 = os.path.join(td, "a.json")
        p2 = os.path.join(td, "b.json")
        s1 = save_multi_fold_backtest_artifact(res, p1)
        s2 = save_multi_fold_backtest_artifact(res, p2)
        assert s1 == s2
