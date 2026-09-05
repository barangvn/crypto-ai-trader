"""S-BKT-02-03: Injection Metadata Deterministic Provenance."""

from __future__ import annotations

from decimal import Decimal

from app.backtest.cost_injection import CostModelOverrides, cost_overrides_manifest
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner, compute_result_sha256
from app.simulation.fill_config import FillAssumptionsConfig


def test_injection_metadata_sorted_keys():
    base = FillAssumptionsConfig()
    ov = CostModelOverrides(taker_fee_bps=Decimal("15"), fill_ratio=Decimal("0.7"))
    m1 = cost_overrides_manifest(base, ov)
    m2 = cost_overrides_manifest(base, ov)
    import json

    r1 = json.dumps(m1, sort_keys=True, separators=(",", ":"))
    r2 = json.dumps(m2, sort_keys=True, separators=(",", ":"))
    assert r1 == r2


def test_provenance_manifest_included(sbkt_small_bundle):
    asum = BacktestAssumptions()
    ov = CostModelOverrides(default_spread_bps=Decimal("333"))
    r = BacktestRunner(assumptions=asum, cost_overrides=ov)
    res = r.run(sbkt_small_bundle, run_id="PROV_INCL")
    m = res.provenance["cost_model_manifest"]
    eff = m["effective_fill_config"]
    assert float(eff["default_spread_bps"]) == 333.0


def test_override_vs_default_provenance_diff(sbkt_small_bundle):
    asum = BacktestAssumptions()
    r0 = BacktestRunner(assumptions=asum)
    r1 = BacktestRunner(
        assumptions=asum, cost_overrides=CostModelOverrides(taker_fee_bps=Decimal("77"))
    )
    s0 = compute_result_sha256(r0.run(sbkt_small_bundle, run_id="PROV_DIFF"))
    s1 = compute_result_sha256(r1.run(sbkt_small_bundle, run_id="PROV_DIFF"))
    assert s0 != s1
