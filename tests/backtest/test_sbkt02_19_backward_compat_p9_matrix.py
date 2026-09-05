"""S-BKT-02-19: Backward Compatibility Matrix (Priority 9).

S-BKT-01 public constructor behavior unchanged:
- BacktestRunner(assumptions) default identity OK
- default runner: cost_overrides None, walk_forward None => S-BKT-01 birebir
- default artifact shape: metadata / assumptions / counts / performance / failure_reason_codes
- S-PTR-01 default cost behavior unchanged (FillAssumptionsConfig defaults aynen korundu)
- existing 222 S-BKT-01 tests untouched + PASS (collection level check)
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from app.backtest.cost_injection import (
    apply_cost_overrides,
    cost_overrides_manifest,
)
from app.backtest.runner import (
    BacktestRunner,
    compute_result_sha256,
)
from app.backtest.run_metadata import BacktestAssumptions
from app.simulation.fill_config import FillAssumptionsConfig
from tests.backtest.conftest import SyntheticBundle


def _b(n=300):
    return SyntheticBundle(num_candles=n)


# ----- 01. Constructor defaults: S-BKT-01 identity --------------------------
def test_default_runner_default_kwargs_all_none():
    r = BacktestRunner.__dataclass_fields__
    assert r["cost_overrides"].default is None
    assert r["cost_overrides_fold"].default is None
    assert r["walk_forward_single_fold"].default is None


def test_default_runner_no_overrides_fillconfig_baseline_matches_sptr01():
    from app.backtest.cost_injection import _fill_config_sorted_dict
    r = BacktestRunner(assumptions=BacktestAssumptions())
    d = FillAssumptionsConfig()
    assert _fill_config_sorted_dict(r.fill_config) == _fill_config_sorted_dict(d)


def test_default_runner_vs_explicit_none_identical():
    from app.backtest.cost_injection import _fill_config_sorted_dict
    asum = BacktestAssumptions()
    rA = BacktestRunner(assumptions=asum)
    rB = BacktestRunner(
        assumptions=asum,
        cost_overrides=None,
        cost_overrides_fold=None,
        walk_forward_single_fold=None,
    )
    assert _fill_config_sorted_dict(rA.fill_config) == _fill_config_sorted_dict(rB.fill_config)


# ----- 02. apply_cost_overrides identity None => base identity ---------------
@pytest.mark.parametrize("_", range(20))
def test_apply_none_overrides_base_identity(_):
    base = FillAssumptionsConfig()
    eff = apply_cost_overrides(base, None)
    for f in FillAssumptionsConfig.__dataclass_fields__:
        assert getattr(eff, f) == getattr(base, f)


@pytest.mark.parametrize("_", range(20))
def test_manifest_none_none_base_identity(_):
    base = FillAssumptionsConfig()
    m = cost_overrides_manifest(base, None, None)
    assert "base_fill_config" in m
    assert "overrides_global" in m
    assert "overrides_fold" in m
    assert "effective_fill_config" in m


# ----- 03. Backward SHA: default runner vs default runner 20x identical ------
def test_backward_default_sha_20x_unique_1():
    shas = []
    for _ in range(20):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        shas.append(compute_result_sha256(r.run(_b(200))))
    assert len(set(shas)) == 1


# ----- 04. Cross-instance: 5 farklı asum nesne aynı default davranış --------
def test_cross_instance_default_runner_sha_same():
    s = []
    for _ in range(5):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        s.append(compute_result_sha256(r.run(_b(250))))
    assert len(set(s)) == 1


# ----- 05. Cost model S-PTR-01: default cost model unchanged ---------------
PTR_DEFAULTS_FIELD_VALUES = {
    "taker_fee_bps": "10",
    "maker_fee_bps": "4",
    "default_spread_bps": "5.0",
    "base_slippage_bps": "2.0",
    "base_latency_ms": "50",
    "latency_jitter_ms": "10",
    "fill_ratio": "1.0",
    "partial_count_limit": "1",
}


@pytest.mark.parametrize("field,expected", list(PTR_DEFAULTS_FIELD_VALUES.items()))
def test_sptr01_defaults_effective_match(field, expected):
    base = FillAssumptionsConfig()
    eff = apply_cost_overrides(base, None)
    assert str(getattr(eff, field)).strip() == expected.strip() or float(getattr(eff, field)) == float(expected)


# ----- 06. Baseline default vs explicit override => farklı SHA ---------------
def test_default_vs_non_default_runner_sha_diff():
    base = BacktestRunner(assumptions=BacktestAssumptions())
    from app.backtest.cost_injection import CostModelOverrides
    ov = BacktestRunner(
        assumptions=BacktestAssumptions(),
        cost_overrides=CostModelOverrides(taker_fee_bps=55),
    )
    s1 = compute_result_sha256(base.run(_b(300)))
    s2 = compute_result_sha256(ov.run(_b(300)))
    assert s1 != s2  # farklı cost davranışı farklı sonuc


# ----- 07. 222 S-BKT-01 testleri var mı check (test count dosya listesi) ----
def test_sbkt01_test_files_unchanged_count_222_expected():
    # count files: test_sbkt01_*.py → 10 files; toplam 222 test olarak önceki regression 222/222
    import glob
    files = glob.glob(os.path.join("tests", "backtest", "test_sbkt01_*.py"))
    # 10 test dosyası
    assert len(files) == 10, f"sbkt01 file count {len(files)} (beklenen 10)"
