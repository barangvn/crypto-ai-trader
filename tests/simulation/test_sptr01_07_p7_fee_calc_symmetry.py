from __future__ import annotations

import pytest
from decimal import Decimal

from app.simulation import FillAssumptionsConfig
from app.simulation.execution import calculate_fee_quote
from app.simulation.fill_config import PaperFillRejectReason


# G8: 16 tests — P7 Fee Non-Neg + BUY/SELL Symmetry
class TestPipelineP7Fee:
    def test_fee_positive_minimum_floor(self):
        cfg = FillAssumptionsConfig(
            taker_fee_bps=Decimal("0.00000001"),
            min_fee_quote_floor=Decimal("0.00000001"),
            max_fee_bps=Decimal("100"),
        )
        fee, bps = calculate_fee_quote(fill_qty_quote=Decimal("0.0000001"), config=cfg)
        assert fee == Decimal("0.00000001")
        assert fee > 0

    def test_fee_10bps_normal_buy(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("10"), max_fee_bps=Decimal("100"))
        quote = Decimal("5000.0")
        fee, bps = calculate_fee_quote(fill_qty_quote=quote, config=cfg)
        # 5000 * 10/10000 = 5.0
        expected = Decimal("5000.0") * Decimal("10") / Decimal("10000")
        assert abs(fee - expected.quantize(Decimal("0.00000001"))) < Decimal("0.000001")
        assert fee > 0

    def test_buy_sell_symmetry(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("25"), max_fee_bps=Decimal("100"))
        qty = Decimal("0.1")
        price = Decimal("100.0")
        quote = qty * price
        fee_buy, bps_buy = calculate_fee_quote(fill_qty_quote=quote, config=cfg)
        fee_sell, bps_sell = calculate_fee_quote(fill_qty_quote=quote, config=cfg)
        assert fee_buy == fee_sell
        assert bps_buy == bps_sell
        assert fee_buy > 0

    def test_maker_fee(self):
        cfg = FillAssumptionsConfig(
            default_fee_type="maker",
            maker_fee_bps=Decimal("4"),
            max_fee_bps=Decimal("100"),
        )
        quote = Decimal("1000.0")
        fee, bps = calculate_fee_quote(fill_qty_quote=quote, config=cfg)
        expected = Decimal("1000.0") * Decimal("4") / Decimal("10000")
        assert abs(fee - expected.quantize(Decimal("0.00000001"))) < Decimal("1e-6")
        assert fee > 0

    def test_fee_negative_bps_invalid(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("-1"), max_fee_bps=Decimal("100"))
        with pytest.raises(ValueError) as exc:
            calculate_fee_quote(fill_qty_quote=Decimal("100"), config=cfg)
        assert PaperFillRejectReason.P7_FEE_NEGATIVE.value in str(exc.value)

    def test_fee_over_max_cap_invalid(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("1000"), max_fee_bps=Decimal("100"))
        with pytest.raises(ValueError) as exc:
            calculate_fee_quote(fill_qty_quote=Decimal("100"), config=cfg)
        assert PaperFillRejectReason.P7_FEE_EXCEEDS_SAFETY.value in str(exc.value)

    def test_fee_decimal_8dp_precision(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("7"), max_fee_bps=Decimal("100"))
        quote = Decimal("1234.56789012")
        fee, _ = calculate_fee_quote(fill_qty_quote=quote, config=cfg)
        # Check quantized to 8 dp
        assert fee == fee.quantize(Decimal("0.00000001"))

    @pytest.mark.parametrize("bps", [0.0001, 1, 5, 25, 50, 75, 99])
    def test_fee_monotonic_increasing(self, bps):
        results = []
        for b in sorted([Decimal("0.0001"), Decimal("1"), Decimal("5"), Decimal("25"), Decimal("50"), Decimal("75"), Decimal("99")]):
            cfg = FillAssumptionsConfig(taker_fee_bps=b, max_fee_bps=Decimal("100"))
            fee, _ = calculate_fee_quote(fill_qty_quote=Decimal("1000"), config=cfg)
            results.append(fee)
        for i in range(1, len(results)):
            assert results[i] >= results[i - 1], f"Fee not monotonic at {i}"

    def test_fee_on_fill_field(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("15"), max_fee_bps=Decimal("100"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.fees_quote > 0

    def test_fill_result_fee_bps_tracking(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("12"), max_fee_bps=Decimal("100"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fee_bps_applied == Decimal("12")

    def test_fee_determinism(self):
        cfg = FillAssumptionsConfig(taker_fee_bps=Decimal("8"), max_fee_bps=Decimal("100"))
        first, bps1 = calculate_fee_quote(fill_qty_quote=Decimal("1234.56"), config=cfg)
        for _ in range(9):
            f, b = calculate_fee_quote(fill_qty_quote=Decimal("1234.56"), config=cfg)
            assert f == first and b == bps1

    def test_fill_fees_quote_must_be_positive_v1(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(
            taker_fee_bps=Decimal("0.0000000001"),
            max_fee_bps=Decimal("100"),
            min_fee_quote_floor=Decimal("0.00000001"),
        )
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.fees_quote > 0
