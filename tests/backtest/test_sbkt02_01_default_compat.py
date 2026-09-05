"""S-BKT-02-01: Default Injection Baseline Compatibility (Backward).

Kural: cost_overrides=None + walk_forward=None => S-BKT-01 100% SHA identical.
"""

from __future__ import annotations

import pytest

from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner, compute_result_sha256


def test_default_no_override_fill_config_equals_defaults():
    asum = BacktestAssumptions()
    r = BacktestRunner(assumptions=asum)
    from app.backtest.cost_injection import _fill_config_sorted_dict
    from app.simulation.fill_config import FillAssumptionsConfig

    d = FillAssumptionsConfig()
    assert _fill_config_sorted_dict(r.fill_config) == _fill_config_sorted_dict(d)


def test_default_vs_none_runner_same_fill_config():
    asum = BacktestAssumptions()
    r1 = BacktestRunner(assumptions=asum, cost_overrides=None)
    r2 = BacktestRunner(assumptions=asum)
    from app.backtest.cost_injection import _fill_config_sorted_dict

    assert _fill_config_sorted_dict(r1.fill_config) == _fill_config_sorted_dict(r2.fill_config)


def test_10x_default_sha_identical(sbkt_small_bundle):
    asum = BacktestAssumptions()
    shas = []
    for _ in range(10):
        r = BacktestRunner(assumptions=asum)
        res = r.run(sbkt_small_bundle, run_id="SBKT02_DEFAULT_10X")
        shas.append(compute_result_sha256(res))
    assert len(set(shas)) == 1


def test_cross_instance_default_sha(sbkt_small_bundle):
    asum = BacktestAssumptions()
    r1 = BacktestRunner(assumptions=asum)
    r2 = BacktestRunner(assumptions=asum)
    s1 = compute_result_sha256(r1.run(sbkt_small_bundle, run_id="CROSS_DEFAULT"))
    s2 = compute_result_sha256(r2.run(sbkt_small_bundle, run_id="CROSS_DEFAULT"))
    assert s1 == s2


def test_provenance_contains_cost_model_manifest_default(sbkt_small_bundle):
    asum = BacktestAssumptions()
    r = BacktestRunner(assumptions=asum)
    res = r.run(sbkt_small_bundle, run_id="PROV_MANIFEST")
    assert "cost_model_manifest" in res.provenance
    m = res.provenance["cost_model_manifest"]
    assert "effective_fill_config" in m
    assert "overrides_global" in m
    assert m["overrides_global"] == {}
