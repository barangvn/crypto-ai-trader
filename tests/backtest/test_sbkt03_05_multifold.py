"""S-BKT-03 05: Multi-fold performance (per-fold metrics + aggregate canonical deterministic)."""

from __future__ import annotations

import json
import pytest
from decimal import Decimal

from tests.backtest.conftest import SyntheticBundle
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner
from app.backtest.walk_forward import WalkForwardConfig
from app.backtest.multi_fold_runner import (
    MultiFoldAggregateSummary,
    run_multifold_walkforward,
    compute_multifold_sha256,
)
from decimal import Decimal  # noqa: E402 (config arg Decimal)


WF_DEFAULTS = dict(
    train_ratio=Decimal("0.5"),
    validation_ratio=Decimal("0.2"),
    test_ratio=Decimal("0.3"),
    inter_fold_gap_ms=0,
    intra_window_gap_ms=1,
    min_events_per_window=3,
)


def _factory(**kw):
    def _f(**inner):
        merge = {**kw, **inner}
        return BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"), **merge)
    return _f


def test_sbkt03_M04_multifold_2fold_perfold_and_aggregate():
    b = SyntheticBundle(num_candles=200, seed=3, drift=Decimal("0.0001"))
    wf = WalkForwardConfig(n_folds=2, **WF_DEFAULTS)
    res = run_multifold_walkforward(
        _factory(),
        b,
        walk_forward=wf,
        run_id="MFTEST05",
    )
    agg: MultiFoldAggregateSummary = res.aggregate_summary
    assert agg.fold_count == 2
    assert agg.pass_count + agg.fail_count == 2
    # V2 per-fold metrics list populated (S-BKT-03 yeni)
    assert len(agg.per_fold_metrics_sorted) == 2
    for fm in agg.per_fold_metrics_sorted:
        assert "fold_run_id" in fm
        assert "total_return_pct" in fm
        assert "max_drawdown_pct" in fm
        assert "cost_overrides_sha256" in fm
    # aggregate fold metrics canonical deterministik
    sha1 = compute_multifold_sha256(res)
    sha2 = compute_multifold_sha256(res)
    assert sha1 == sha2 and len(sha1) == 64


def test_sbkt03_M04_multifold_deterministic_two_runs():
    b = SyntheticBundle(num_candles=240, seed=7, drift=Decimal("0.0002"))
    wf = WalkForwardConfig(n_folds=3, **WF_DEFAULTS)
    r1 = run_multifold_walkforward(_factory(), b, walk_forward=wf, run_id="DET_A")
    r2 = run_multifold_walkforward(_factory(), b, walk_forward=wf, run_id="DET_A")
    assert compute_multifold_sha256(r1) == compute_multifold_sha256(r2)
    agg1 = r1.aggregate_summary
    agg2 = r2.aggregate_summary
    # aggregate V2 numeric alanlar ayni olmali
    for k in ("avg_sharpe_ratio_24h", "avg_sortino_ratio_24h", "compound_total_return_pct", "min_fold_total_return_pct", "max_fold_total_return_pct"):
        assert getattr(agg1, k) == getattr(agg2, k), k


def test_sbkt03_M04_aggregate_info_codes_OD06():
    """N/A fold'lar avg'den exclude → code METRICS_NA_EXCLUDED_AVG."""
    b = SyntheticBundle(num_candles=120, seed=5, drift=Decimal("0.0001"))
    wf = WalkForwardConfig(n_folds=3, **WF_DEFAULTS)
    r = run_multifold_walkforward(_factory(), b, walk_forward=wf, run_id="AGG_CODES")
    # en az 1 fold trades az ise None olabilir; code kontrol (present ise dogru format).
    for code in r.aggregate_summary.aggregate_info_codes:
        assert isinstance(code, str)
        if "EXCLUDED" in code:
            assert code == "METRICS_NA_EXCLUDED_AVG"
