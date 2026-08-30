from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import PaperOrderSide
from app.simulation import FillAssumptionsConfig
from app.simulation.execution import apply_slippage_directional
from app.simulation.fill_config import PaperFillRejectReason


# G7: 18 tests — P6 Slippage Directional Correctness
class TestPipelineP6Slippage:
    def test_zero_slippage_unchanged(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=0.0, max_slippage_bps=100)
        p, bps = apply_slippage_directional(
            side=PaperOrderSide.BUY, price_after_spread=Decimal("100.0"), config=cfg,
        )
        assert p == Decimal("100.0")
        assert bps == 0.0

    def test_positive_small_buy_increases_price(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=2.0, max_slippage_bps=500)
        p, bps = apply_slippage_directional(
            side=PaperOrderSide.BUY, price_after_spread=Decimal("100.0"), config=cfg,
        )
        # 2 bps of 100 = 0.02 → 100.02
        expected = Decimal("100.0") + Decimal("100.0") * Decimal("2") / Decimal("10000")
        assert abs(p - expected) < Decimal("1e-10")
        assert p > Decimal("100.0")

    def test_positive_sell_decreases_price(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=2.0, max_slippage_bps=500)
        p, bps = apply_slippage_directional(
            side=PaperOrderSide.SELL, price_after_spread=Decimal("100.0"), config=cfg,
        )
        expected = Decimal("100.0") - Decimal("100.0") * Decimal("2") / Decimal("10000")
        assert abs(p - expected) < Decimal("1e-10")
        assert p < Decimal("100.0")

    def test_high_slippage_500bps_buy(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=500.0, max_slippage_bps=500.0)
        p, bps = apply_slippage_directional(
            side=PaperOrderSide.BUY, price_after_spread=Decimal("100.0"), config=cfg,
        )
        # 5% = 500 bps up → 105
        assert bps == 500.0
        assert p > Decimal("104.5")

    def test_high_slippage_500bps_sell(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=500.0, max_slippage_bps=500.0)
        p, bps = apply_slippage_directional(
            side=PaperOrderSide.SELL, price_after_spread=Decimal("100.0"), config=cfg,
        )
        assert p < Decimal("96")

    def test_negative_slippage_invalid(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=-1.0)
        with pytest.raises(ValueError) as exc:
            apply_slippage_directional(
                side=PaperOrderSide.BUY, price_after_spread=Decimal("100"), config=cfg,
            )
        assert PaperFillRejectReason.P6_SLIPPAGE_NEGATIVE.value in str(exc.value)

    def test_exceeds_max_invalid(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=501.0, max_slippage_bps=500.0)
        with pytest.raises(ValueError) as exc:
            apply_slippage_directional(
                side=PaperOrderSide.BUY, price_after_spread=Decimal("100"), config=cfg,
            )
        assert PaperFillRejectReason.P6_SLIPPAGE_EXCEEDS_MAX.value in str(exc.value)

    @pytest.mark.parametrize("bps", [0.0, 1.0, 5.0, 50.0, 100.0, 250.0])
    def test_buy_monotonic_increasing(self, bps):
        results = []
        for b in sorted([0.0, 1.0, 5.0, 50.0, 100.0, 250.0]):
            cfg = FillAssumptionsConfig(base_slippage_bps=b, max_slippage_bps=1000.0)
            p, _ = apply_slippage_directional(
                side=PaperOrderSide.BUY, price_after_spread=Decimal("100.0"), config=cfg,
            )
            results.append(p)
        for i in range(1, len(results)):
            assert results[i] >= results[i - 1], f"Buy not monotonic at idx {i}"

    @pytest.mark.parametrize("bps", [0.0, 1.0, 5.0, 50.0, 100.0, 250.0])
    def test_sell_monotonic_decreasing(self, bps):
        results = []
        for b in sorted([0.0, 1.0, 5.0, 50.0, 100.0, 250.0]):
            cfg = FillAssumptionsConfig(base_slippage_bps=b, max_slippage_bps=1000.0)
            p, _ = apply_slippage_directional(
                side=PaperOrderSide.SELL, price_after_spread=Decimal("100.0"), config=cfg,
            )
            results.append(p)
        for i in range(1, len(results)):
            assert results[i] <= results[i - 1], f"Sell not monotonic at idx {i}"

    def test_slippage_determinism_10x(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=3.0, max_slippage_bps=500)
        first, first_bps = apply_slippage_directional(
            side=PaperOrderSide.SELL, price_after_spread=Decimal("777.77"), config=cfg,
        )
        for _ in range(9):
            p, b = apply_slippage_directional(
                side=PaperOrderSide.SELL, price_after_spread=Decimal("777.77"), config=cfg,
            )
            assert p == first and b == first_bps

    def test_buy_sell_opposite_direction(self):
        cfg = FillAssumptionsConfig(base_slippage_bps=50.0, max_slippage_bps=500)
        base = Decimal("1000.0")
        p_buy, _ = apply_slippage_directional(
            side=PaperOrderSide.BUY, price_after_spread=base, config=cfg,
        )
        p_sell, _ = apply_slippage_directional(
            side=PaperOrderSide.SELL, price_after_spread=base, config=cfg,
        )
        assert p_buy > base
        assert p_sell < base

    def test_slippage_on_fill_field(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(base_slippage_bps=7.0, max_slippage_bps=100)
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.slippage_bps == 7.0
