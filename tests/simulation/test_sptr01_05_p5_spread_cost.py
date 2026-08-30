from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import PaperOrderSide
from app.simulation import FillAssumptionsConfig, build_pipeline_reference_data
from app.simulation.execution import apply_spread_cost
from app.simulation.fill_config import PaperFillRejectReason


# G6: 12 tests — P5 Spread Cost
class TestPipelineP5Spread:
    def test_zero_spread(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=0.0)
        price_actual, _, _ = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("100.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=0.0,
        )
        assert price_actual == Decimal("100.0")

    def test_small_spread_5bps_buy(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=5.0)
        price, bps_applied, _ = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("100.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        # half spread = 2.5 bps for buy: 100.0 + 0.025 = 100.025
        expected = Decimal("100.0") + Decimal("100.0") * Decimal(str(5.0 / 2.0)) / Decimal("10000")
        assert abs(price - expected) < Decimal("1e-9")
        assert bps_applied == 5.0

    def test_small_spread_5bps_sell(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=5.0)
        price, _, _ = apply_spread_cost(
            side=PaperOrderSide.SELL,
            reference_price=Decimal("100.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        expected = Decimal("100.0") - Decimal("100.0") * Decimal(str(5.0 / 2.0)) / Decimal("10000")
        assert abs(price - expected) < Decimal("1e-9")

    def test_spread_normal_100bps(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=100.0)
        price, _, _ = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("100.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        # half spread: 50 bps up
        assert price > Decimal("100.0")
        assert price < Decimal("101.5")

    def test_spread_high_1000bps(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=1000.0)
        price, bps, src = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("100.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        assert bps == 1000.0
        assert src == "DEFAULT_ASSUMPTION"

    def test_spread_negative_invalid(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig()
        with pytest.raises(ValueError) as exc:
            apply_spread_cost(
                side=PaperOrderSide.BUY,
                reference_price=Decimal("100.0"),
                ref=ref,
                config=cfg,
                actual_spread_bps=-5.0,
            )
        assert PaperFillRejectReason.P5_SPREAD_NEGATIVE.value in str(exc.value)

    def test_spread_default_negative_invalid(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=-1.0)
        with pytest.raises(ValueError) as exc:
            apply_spread_cost(
                side=PaperOrderSide.BUY,
                reference_price=Decimal("100.0"),
                ref=ref,
                config=cfg,
                actual_spread_bps=None,
            )
        assert PaperFillRejectReason.P5_SPREAD_NEGATIVE.value in str(exc.value)

    def test_spread_actual_from_ob_preferred(self, sptr01_tick_btc, sptr01_orderbook):
        ref = build_pipeline_reference_data(orderbook=sptr01_orderbook, tick=sptr01_tick_btc)
        cfg = FillAssumptionsConfig(default_spread_bps=0.0)
        from app.simulation.execution import select_reference_price
        ref_price, _, actual_spread = select_reference_price(side=PaperOrderSide.BUY, ref=ref, config=cfg)
        price, bps, src = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=ref_price,
            ref=ref,
            config=cfg,
            actual_spread_bps=actual_spread,
        )
        assert src == "ACTUAL_BID_ASK"
        assert bps == pytest.approx(4.0, rel=0.1)  # bid=49990, ask=50010, mid=50000 → 20/50000*10000 = 4 bps

    def test_spread_buy_higher_cost(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=10.0)
        p_buy, _, _ = apply_spread_cost(
            side=PaperOrderSide.BUY, reference_price=Decimal("100"), ref=ref, config=cfg, actual_spread_bps=None,
        )
        p_sell, _, _ = apply_spread_cost(
            side=PaperOrderSide.SELL, reference_price=Decimal("100"), ref=ref, config=cfg, actual_spread_bps=None,
        )
        assert p_buy > Decimal("100")
        assert p_sell < Decimal("100")

    def test_spread_monotonicity_increasing(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        prices = []
        for bps in [0, 5, 50, 100, 500]:
            cfg = FillAssumptionsConfig(default_spread_bps=float(bps))
            p, _, _ = apply_spread_cost(
                side=PaperOrderSide.BUY,
                reference_price=Decimal("100.0"),
                ref=ref,
                config=cfg,
                actual_spread_bps=None,
            )
            prices.append(p)
        for i in range(1, len(prices)):
            assert prices[i] >= prices[i - 1], f"Spread not monotonic at {i}"

    def test_spread_determinism(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig(default_spread_bps=7.0)
        p1, b1, s1 = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("500.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        p2, b2, s2 = apply_spread_cost(
            side=PaperOrderSide.BUY,
            reference_price=Decimal("500.0"),
            ref=ref,
            config=cfg,
            actual_spread_bps=None,
        )
        assert p1 == p2 and b1 == b2 and s1 == s2

    def test_spread_over_10000_rejected(self, sptr01_tick_no_bidask):
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        cfg = FillAssumptionsConfig()
        with pytest.raises(ValueError):
            apply_spread_cost(
                side=PaperOrderSide.BUY,
                reference_price=Decimal("1"),
                ref=ref,
                config=cfg,
                actual_spread_bps=50000.0,
            )
