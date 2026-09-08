"""S-BKT-03 07: Determinism (10x same input, 2 runner instances, multifold)."""

from __future__ import annotations

import hashlib
import json
import pytest
from decimal import Decimal

from tests.backtest.conftest import SyntheticBundle
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import (
    BacktestRunner,
    compute_result_sha256,
    run_deterministic_check_n_times,
)
from app.backtest.walk_forward import WalkForwardConfig
from app.backtest.multi_fold_runner import (
    run_multifold_walkforward,
    compute_multifold_sha256,
)
from app.backtest.cost_injection import CostModelOverrides

from decimal import Decimal  # noqa: E402 (Drift + Config Decimal)

WF_DEFAULTS = dict(
    train_ratio=Decimal("0.5"),
    validation_ratio=Decimal("0.2"),
    test_ratio=Decimal("0.3"),
    inter_fold_gap_ms=0,
    intra_window_gap_ms=1,
    min_events_per_window=3,
)


def test_sbkt03_DET01_runner_10x_same_sha():
    b = SyntheticBundle(num_candles=120, seed=13, drift=Decimal("0.0003"))
    res = run_deterministic_check_n_times(
        lambda: BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000")),
        b,
        n=10,
    )
    assert res["is_deterministic"] is True, res
    assert res["unique_sha_count"] == 1
    assert res["n_runs"] == 10


def test_sbkt03_DET01_two_separate_runner_class_instances():
    """2 farklı python process'te instance (burada iki ayrı construct) aynı SHA vermeli."""
    b = SyntheticBundle(num_candles=90, seed=17, drift=Decimal("0.0002"))
    class_A = BacktestRunner
    r1 = class_A(assumptions=BacktestAssumptions(initial_equity_quote="10000")).run(b, run_id="X1")
    r2 = class_A(assumptions=BacktestAssumptions(initial_equity_quote="10000")).run(b, run_id="X1")
    assert compute_result_sha256(r1) == compute_result_sha256(r2)
    # V2 fields deterministik
    for k in (
        "total_return_pct",
        "sharpe_ratio_24h",
        "sortino_ratio_24h",
        "profit_factor",
        "stability_index",
        "win_rate_pct",
    ):
        v1 = getattr(r1.performance_v2, k)
        v2 = getattr(r2.performance_v2, k)
        assert v1 == v2, (k, v1, v2)


def test_sbkt03_DET01_cost_override_deterministic():
    b = SyntheticBundle(num_candles=150, seed=21, drift=Decimal("0.0001"))
    ov = CostModelOverrides(taker_fee_bps=Decimal("30"), base_slippage_bps=Decimal("10"))
    r1 = BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"), cost_overrides=ov).run(b, run_id="OVD1")
    r2 = BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"), cost_overrides=ov).run(b, run_id="OVD1")
    assert compute_result_sha256(r1) == compute_result_sha256(r2)
    assert r1.performance_v2.cost_overrides_sha256 == r2.performance_v2.cost_overrides_sha256


def test_sbkt03_DET01_multifold_deterministic():
    b = SyntheticBundle(num_candles=240, seed=29, drift=Decimal("0.0001"))
    wf = WalkForwardConfig(n_folds=4, **WF_DEFAULTS)
    fact = lambda **kw: BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"), **kw)
    r1 = run_multifold_walkforward(fact, b, walk_forward=wf, run_id="MF_D")
    r2 = run_multifold_walkforward(fact, b, walk_forward=wf, run_id="MF_D")
    assert compute_multifold_sha256(r1) == compute_multifold_sha256(r2)
