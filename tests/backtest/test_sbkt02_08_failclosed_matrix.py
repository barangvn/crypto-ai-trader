"""S-BKT-02-08: Fail-Closed Matrix (Invalid config / Fold Fail / Negative boundary)."""

from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.cost_injection import CostModelOverrides, validate_cost_overrides
from app.backtest.walk_forward import WalkForwardConfig, generate_fold_splits
from tests.backtest.conftest import SyntheticBundle


def test_negative_fee_fail():
    with pytest.raises(ValueError):
        validate_cost_overrides(CostModelOverrides(taker_fee_bps=Decimal("-0.5")))


def test_fill_ratio_gt_1_fail():
    with pytest.raises(ValueError):
        validate_cost_overrides(CostModelOverrides(fill_ratio=Decimal("2.0")))


def test_partial_count_0_fail():
    with pytest.raises(ValueError):
        validate_cost_overrides(CostModelOverrides(partial_count_limit=0))


def test_walkforward_n_folds_0_fail():
    cfg = WalkForwardConfig(n_folds=0)
    evs = list(SyntheticBundle(num_candles=100).iter_events())
    with pytest.raises(ValueError):
        generate_fold_splits(evs, cfg)


def test_walkforward_ratios_zero_fail():
    from decimal import Decimal as D

    cfg = WalkForwardConfig(train_ratio=D("0"))
    evs = list(SyntheticBundle(num_candles=100).iter_events())
    with pytest.raises(ValueError):
        generate_fold_splits(evs, cfg)


def test_small_events_multifold_fail():
    cfg = WalkForwardConfig(n_folds=10)
    evs = list(SyntheticBundle(num_candles=30).iter_events())
    with pytest.raises(ValueError):
        generate_fold_splits(evs, cfg)
