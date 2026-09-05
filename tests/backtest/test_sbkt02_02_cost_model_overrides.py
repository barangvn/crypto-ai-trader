"""S-BKT-02-02: Cost Model Individual Overrides + Combinations + Fail-Closed."""

from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.cost_injection import (
    CostModelOverrides,
    apply_cost_overrides,
    validate_cost_overrides,
)
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner, compute_result_sha256
from app.simulation.fill_config import FillAssumptionsConfig


def test_fee_only_override_changes_only_fee():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(taker_fee_bps=Decimal("50"))
    out = apply_cost_overrides(d, ov)
    assert format(out.taker_fee_bps, "f") == format(Decimal("50"), "f")
    assert out.maker_fee_bps == d.maker_fee_bps
    assert out.default_spread_bps == d.default_spread_bps
    assert out.base_slippage_bps == d.base_slippage_bps
    assert out.base_latency_ms == d.base_latency_ms
    assert out.fill_ratio == d.fill_ratio


def test_spread_only_override():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(default_spread_bps=Decimal("500"))
    out = apply_cost_overrides(d, ov)
    assert float(out.default_spread_bps) == 500.0
    assert out.taker_fee_bps == d.taker_fee_bps


def test_slippage_only_override():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(base_slippage_bps=Decimal("99"))
    out = apply_cost_overrides(d, ov)
    assert float(out.base_slippage_bps) == 99.0
    assert out.default_spread_bps == d.default_spread_bps


def test_latency_only_override():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(base_latency_ms=Decimal("500"))
    out = apply_cost_overrides(d, ov)
    assert float(out.base_latency_ms) == 500.0
    assert out.base_slippage_bps == d.base_slippage_bps


def test_partial_fill_only_override():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(fill_ratio=Decimal("0.5"), partial_count_limit=7)
    out = apply_cost_overrides(d, ov)
    assert format(out.fill_ratio, "f") == format(Decimal("0.5"), "f")
    assert out.partial_count_limit == 7


@pytest.mark.parametrize(
    "kwargs, err_type",
    [
        ({"taker_fee_bps": Decimal("-1")}, ValueError),
        ({"default_spread_bps": Decimal("-5")}, ValueError),
        ({"base_slippage_bps": Decimal("-2")}, ValueError),
        ({"base_latency_ms": Decimal("-1")}, ValueError),
        ({"fill_ratio": Decimal("1.1")}, ValueError),
        ({"fill_ratio": Decimal("-0.1")}, ValueError),
        ({"partial_count_limit": 0}, ValueError),
        ({"partial_count_limit": -10}, ValueError),
    ],
)
def test_invalid_override_fail_closed(kwargs, err_type):
    ov = CostModelOverrides(**kwargs)
    with pytest.raises(err_type):
        validate_cost_overrides(ov)


def test_invalid_override_type_fail_closed():
    with pytest.raises(TypeError):
        validate_cost_overrides("not an override object")  # type: ignore[arg-type]


def test_override_combination():
    d = FillAssumptionsConfig()
    ov = CostModelOverrides(
        taker_fee_bps=Decimal("25"),
        default_spread_bps=Decimal("100"),
        fill_ratio=Decimal("0.9"),
    )
    out = apply_cost_overrides(d, ov)
    assert format(out.taker_fee_bps, "f") == "25"
    assert float(out.default_spread_bps) == 100.0
    assert format(out.fill_ratio, "f") == "0.9"
    # unchanged
    assert out.base_slippage_bps == d.base_slippage_bps


def test_runner_constructor_accepts_overrides():
    asum = BacktestAssumptions()
    ov = CostModelOverrides(taker_fee_bps=Decimal("12"))
    r = BacktestRunner(assumptions=asum, cost_overrides=ov)
    assert format(r.fill_config.taker_fee_bps, "f") == "12"


def test_override_sha_deterministic(sbkt_small_bundle):
    asum = BacktestAssumptions()
    ov = CostModelOverrides(
        default_spread_bps=Decimal("75"),
        base_latency_ms=Decimal("150"),
    )
    shas = []
    for _ in range(10):
        r = BacktestRunner(assumptions=asum, cost_overrides=ov)
        shas.append(compute_result_sha256(r.run(sbkt_small_bundle, run_id="SBKT02_OV_DET")))
    assert len(set(shas)) == 1
