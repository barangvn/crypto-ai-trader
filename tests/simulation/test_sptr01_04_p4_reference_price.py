from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import PaperOrderSide, MarketTick, Candle, OrderBookSnapshot, Symbol
from app.simulation import FillAssumptionsConfig, build_pipeline_reference_data
from app.simulation.execution import select_reference_price
from app.simulation.fill_config import PaperFillRejectReason


# G5: 18 tests — P4 Reference Price
class TestPipelineP4ReferencePrice:
    def test_ob_ask_for_buy(self, sptr01_orderbook):
        ref = build_pipeline_reference_data(orderbook=sptr01_orderbook)
        cfg = FillAssumptionsConfig()
        price, src, spread_bps = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        assert price == Decimal("50010.0")
        assert src == "OB_ASK"
        assert spread_bps is not None
        assert spread_bps > 0

    def test_ob_bid_for_sell(self, sptr01_orderbook):
        ref = build_pipeline_reference_data(orderbook=sptr01_orderbook)
        cfg = FillAssumptionsConfig()
        price, src, spread_bps = select_reference_price(side=PaperOrderSide.SELL, ref=ref, config=cfg)
        assert price == Decimal("49990.0")
        assert src == "OB_BID"

    def test_tick_ask_for_buy(self, sptr01_tick_btc):
        ref = build_pipeline_reference_data(tick=sptr01_tick_btc)
        cfg = FillAssumptionsConfig()
        price, src, _ = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        assert price == Decimal("50010.0")
        assert src == "TICK_ASK"

    def test_tick_bid_for_sell(self, sptr01_tick_btc):
        ref = build_pipeline_reference_data(tick=sptr01_tick_btc)
        cfg = FillAssumptionsConfig()
        price, src, _ = select_reference_price(side=PaperOrderSide.SELL, ref=ref, config=cfg)
        assert price == Decimal("49990.0")
        assert src == "TICK_BID"

    def test_tick_mid_fallback_no_bidask(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig()
        price_b, src_b, _ = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        assert price_b == Decimal("50000.0")
        assert src_b == "TICK_PRICE"
        price_s, src_s, _ = select_reference_price(side=PaperOrderSide.SELL, ref=ref, config=cfg)
        assert price_s == Decimal("50000.0")
        assert src_s == "TICK_PRICE"

    def test_candle_close_fallback(self, sptr01_candle_closed):
        ref = build_pipeline_reference_data(candle=sptr01_candle_closed)
        cfg = FillAssumptionsConfig()
        price_b, src_b, _ = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        assert price_b == Decimal("50000.0")
        assert src_b == "CANDLE_CLOSE"
        price_s, _, _ = select_reference_price(side=PaperOrderSide.SELL, ref=ref, config=cfg)
        assert price_s == Decimal("50000.0")

    def test_candle_notclosed_rejected(self, sptr01_order_buy, sptr01_quality_healthy, sptr01_bus, sptr01_candle_notclosed):
        from app.simulation import PaperExecutionSimulator
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        ref = build_pipeline_reference_data(candle=sptr01_candle_notclosed)
        res = sim.simulate(order=sptr01_order_buy, reference=ref, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P4_CANDLE_NOT_CLOSED.value in res.reject_reasons

    def test_no_reference_rejected(self, sptr01_order_buy, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        ref = build_pipeline_reference_data()
        res = sim.simulate(order=sptr01_order_buy, reference=ref, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P4_NO_MARKET_REFERENCE.value in res.reject_reasons

    def test_orderbook_crossed_rejected(self, sptr01_order_buy, sptr01_orderbook_crossed, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        ref = build_pipeline_reference_data(orderbook=sptr01_orderbook_crossed)
        res = sim.simulate(order=sptr01_order_buy, reference=ref, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P4_BID_ASK_CROSS.value in res.reject_reasons

    def test_priority_ob_over_tick_over_candle(self, sptr01_orderbook, sptr01_tick_btc, sptr01_candle_closed):
        ref = build_pipeline_reference_data(
            orderbook=sptr01_orderbook, tick=sptr01_tick_btc, candle=sptr01_candle_closed,
        )
        cfg = FillAssumptionsConfig()
        price_b, src_b, _ = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        assert src_b == "OB_ASK"
        assert price_b == Decimal("50010.0")

    @pytest.mark.parametrize("side", [PaperOrderSide.BUY, PaperOrderSide.SELL])
    def test_deterministic_same_result(self, sptr01_tick_btc, side):
        ref = build_pipeline_reference_data(tick=sptr01_tick_btc)
        cfg = FillAssumptionsConfig()
        p1, s1, b1 = select_reference_price(side=side, ref=ref, config=cfg)
        p2, s2, b2 = select_reference_price(side=side, ref=ref, config=cfg)
        assert p1 == p2
        assert s1 == s2
        assert b1 == b2
