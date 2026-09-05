"""S-BKT-02-05: Per-Fold + Aggregate Artifact + SHA Determinism."""

from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.cost_injection import CostModelOverrides
from app.backtest.multi_fold_runner import (
    compute_multifold_sha256,
    run_multifold_walkforward,
    save_multi_fold_backtest_artifact,
    load_multi_fold_backtest_artifact,
    verify_multifold_deterministic,
)
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner
from app.backtest.walk_forward import WalkForwardConfig
from tests.backtest.conftest import SyntheticBundle


def _make_bundle(n=2000, syms=None):
    if syms is None:
        syms = ["BTC_USDT"]
    b = SyntheticBundle(num_candles=n)
    return b


def _runner_factory(
    cost_overrides=None, cost_overrides_fold=None, walk_forward_single_fold=None
):
    asum = BacktestAssumptions()
    return BacktestRunner(
        assumptions=asum,
        cost_overrides=cost_overrides,
        cost_overrides_fold=cost_overrides_fold,
        walk_forward_single_fold=walk_forward_single_fold,
    )


def test_run_multifold_5folds(sbkt_medium_bundle):
    result = run_multifold_walkforward(
        _runner_factory,
        sbkt_medium_bundle,
    )
    assert result.manifest.overall_status in {"PASS", "FAILED"}
    assert len(result.manifest.fold_definitions_sorted_dict) == 5
    assert len(result.per_fold_results) == 5


def test_aggregate_summary_has_fields(sbkt_medium_bundle):
    result = run_multifold_walkforward(_runner_factory, sbkt_medium_bundle)
    s = result.aggregate_summary
    assert s.fold_count == 5
    assert s.pass_count + s.fail_count == 5


def test_per_fold_sha_length(sbkt_medium_bundle):
    result = run_multifold_walkforward(_runner_factory, sbkt_medium_bundle)
    assert len(result.manifest.per_fold_sha256) == 5
    for sha in result.manifest.per_fold_sha256:
        assert isinstance(sha, str) and len(sha) == 64


def test_aggregate_10x_same_sha(sbkt_medium_bundle):
    shas = []
    for _ in range(10):
        result = run_multifold_walkforward(
            _runner_factory, sbkt_medium_bundle, run_id="MF_10X_SHA"
        )
        shas.append(compute_multifold_sha256(result))
    assert len(set(shas)) == 1


def test_save_load_roundtrip(tmp_path, sbkt_medium_bundle):
    result = run_multifold_walkforward(_runner_factory, sbkt_medium_bundle)
    p = tmp_path / "mf_artifact.json"
    sha = save_multi_fold_backtest_artifact(result, p)
    assert p.exists()
    loaded = load_multi_fold_backtest_artifact(p)
    assert loaded["sha256"] == sha


def test_verify_multifold_deterministic_1(tmp_path, sbkt_medium_bundle):
    paths = []
    for i in range(2):
        p = tmp_path / f"mf_{i}.json"
        r = run_multifold_walkforward(
            _runner_factory, sbkt_medium_bundle, run_id="MF_VERIFY"
        )
        save_multi_fold_backtest_artifact(r, p)
        paths.append(p)
    report = verify_multifold_deterministic(paths)
    assert report["file_count"] == 2
    assert report["unique_sha_count"] == 1
    assert report["is_deterministic"] is True
