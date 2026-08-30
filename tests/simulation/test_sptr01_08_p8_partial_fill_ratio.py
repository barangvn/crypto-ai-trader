from __future__ import annotations

import pytest
from decimal import Decimal

from app.simulation import FillAssumptionsConfig
from app.simulation.execution import calculate_fill_quantities
from app.simulation.fill_config import PaperFillRejectReason


# G9: 18 tests — P8 Partial Fill
class TestPipelineP8PartialFill:
    def test_full_fill_ratio_one(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0"))
        qty_base, qty_quote, ratio = calculate_fill_quantities(
            requested_qty_base=Decimal("10.0"),
            fill_price=Decimal("100.0"),
            config=cfg,
        )
        assert qty_base == Decimal("10.00000000")
        assert qty_quote == Decimal("1000.00000000")
        assert ratio == Decimal("1.0")

    def test_half_fill(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.5"))
        qty_base, qty_quote, ratio = calculate_fill_quantities(
            requested_qty_base=Decimal("1.0"),
            fill_price=Decimal("100.0"),
            config=cfg,
        )
        assert qty_base == Decimal("0.50000000")
        assert qty_quote == Decimal("50.00000000")
        assert ratio == Decimal("0.5")

    @pytest.mark.parametrize("ratio", [Decimal("0.1"), Decimal("0.25"), Decimal("0.333"), Decimal("0.75"), Decimal("0.99")])
    def test_partial_ratios_positive_bounded(self, ratio):
        cfg = FillAssumptionsConfig(fill_ratio=ratio)
        qty_base, qty_quote, r = calculate_fill_quantities(
            requested_qty_base=Decimal("100.0"),
            fill_price=Decimal("1.0"),
            config=cfg,
        )
        assert qty_base > 0
        assert qty_base <= Decimal("100.0")
        assert qty_quote > 0

    def test_ratio_zero_rejected(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.0"))
        with pytest.raises(ValueError) as exc:
            calculate_fill_quantities(
                requested_qty_base=Decimal("1.0"),
                fill_price=Decimal("100"),
                config=cfg,
            )
        assert PaperFillRejectReason.P8_FILL_RATIO_ZERO.value in str(exc.value)

    def test_ratio_very_small_rejected(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.0000000000001"))
        with pytest.raises(ValueError) as exc:
            calculate_fill_quantities(
                requested_qty_base=Decimal("0.00000001"),
                fill_price=Decimal("1"),
                config=cfg,
            )
        assert PaperFillRejectReason.P8_FILL_QTY_NOT_POSITIVE.value in str(exc.value)

    def test_ratio_over_one_rejected(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0001"))
        with pytest.raises(ValueError) as exc:
            calculate_fill_quantities(
                requested_qty_base=Decimal("1"),
                fill_price=Decimal("1"),
                config=cfg,
            )
        assert PaperFillRejectReason.P8_FILL_RATIO_GT_ONE.value in str(exc.value)

    def test_simulator_partial_half(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.5"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.fill_qty_base == Decimal("0.05000000")
        assert res.fill.fill_qty_base <= sptr01_order_buy.requested_qty_base

    def test_fill_qty_never_exceeds_requested(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0"))
        for qty in [Decimal("0.01"), Decimal("1"), Decimal("1000"), Decimal("0.99999999")]:
            qb, qq, r = calculate_fill_quantities(
                requested_qty_base=qty, fill_price=Decimal("50000.0"), config=cfg,
            )
            assert qb <= qty

    def test_quantize_8dp(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0"))
        qb, qq, r = calculate_fill_quantities(
            requested_qty_base=Decimal("0.123456789"),
            fill_price=Decimal("1.0"),
            config=cfg,
        )
        # 0.123456789 → 8dp → 0.12345678 (ROUND_DOWN)
        assert qb == Decimal("0.12345678")

    def test_full_fill_on_result(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill_ratio_applied == Decimal("1.0")

    def test_partial_fill_on_result(self, sptr01_order_sell, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.333"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_sell, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill_ratio_applied == Decimal("0.333")
        assert res.fill.side == sptr01_order_sell.side

    def test_fill_qty_positive_invariant(self):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("1.0"))
        qb, qq, r = calculate_fill_quantities(
            requested_qty_base=Decimal("999.99999999"),
            fill_price=Decimal("99999.99"),
            config=cfg,
        )
        assert qb > 0
        assert qq > 0
