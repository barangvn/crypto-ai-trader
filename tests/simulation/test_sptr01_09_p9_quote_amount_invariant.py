from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import ContractSchemaError
from app.simulation import FillAssumptionsConfig, PaperExecutionSimulator


# G10: 10 tests — P9 Quote Amount Invariant (price × qty = quote)
class TestPipelineP9QuoteInvariant:
    def test_invariant_full_fill_buy(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        expected = f.fill_price * f.fill_qty_base
        diff = abs(f.fill_qty_quote - expected)
        assert diff <= Decimal("1e-12"), f"diff={diff} expected={expected}"

    def test_invariant_full_fill_sell(self, sptr01_order_sell, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_sell, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        expected = f.fill_price * f.fill_qty_base
        diff = abs(f.fill_qty_quote - expected)
        assert diff <= Decimal("1e-12")

    def test_invariant_partial_fill(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        cfg = FillAssumptionsConfig(fill_ratio=Decimal("0.3333"))
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        expected = f.fill_price * f.fill_qty_base
        diff = abs(f.fill_qty_quote - expected)
        assert diff <= Decimal("1e-12")

    def test_invariant_zero_spread_zero_slippage(self, sptr01_order_buy, sptr01_tick_no_bidask, sptr01_quality_healthy, sptr01_bus):
        cfg = FillAssumptionsConfig(
            default_spread_bps=0.0, base_slippage_bps=0.0,
            base_latency_ms=0, latency_jitter_ms=0,
        )
        from app.simulation import build_pipeline_reference_data
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=ref, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        expected = f.fill_price * f.fill_qty_base
        diff = abs(f.fill_qty_quote - expected)
        assert diff <= Decimal("1e-12")

    def test_invariant_ob_ref(self, sptr01_order_buy, sptr01_ref_ob, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_ob, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        diff = abs(f.fill_qty_quote - f.fill_price * f.fill_qty_base)
        assert diff <= Decimal("1e-12")

    def test_invariant_candle_ref(self, sptr01_order_sell, sptr01_ref_candle, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_sell, reference=sptr01_ref_candle, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        f = res.fill
        diff = abs(f.fill_qty_quote - f.fill_price * f.fill_qty_base)
        assert diff <= Decimal("1e-12")

    def test_direct_contract_validation_catches_bad_quote(self, sptr01_ts):
        from app.contracts import PaperFill, PaperOrderSide, Instant, ULID
        with pytest.raises(ContractSchemaError) as exc:
            PaperFill(
                paper_fill_id=ULID("F1" + "A" * 24),
                paper_order_id=ULID("PO" + "B" * 24),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("100.0"),
                fill_qty_base=Decimal("2.0"),
                fill_qty_quote=Decimal("999.99"),  # should be 200
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("CAU" * 8 + "AB"),
            )
        assert "invariant" in str(exc.value).lower()

    def test_fee_non_negative(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.fees_quote >= 0

    def test_fill_qty_base_strictly_positive(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.fill_qty_base > 0
