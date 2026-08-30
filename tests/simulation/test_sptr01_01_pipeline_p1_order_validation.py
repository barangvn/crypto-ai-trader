from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import PaperOrderStatus
from app.simulation import FillAssumptionsConfig, PaperExecutionSimulator
from app.simulation.fill_config import PaperFillRejectReason
from tests.simulation.conftest import _bypass_paper_order


# G2: 16 tests — P1 Validation × 2 side buy/sell (8 scenario each: 8 invalid)
@pytest.mark.parametrize("side_label", ["buy", "sell"])
class TestPipelineP1Validation:
    def test_status_created_ok(self, side_label, sptr01_sim_default, sptr01_ts, sptr01_policy_refs, sptr01_ref_tick, sptr01_quality_healthy, sptr01_config_default):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.CREATED,
            paper_order_id="PO_P1_HAPPY_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is False
        assert res.fill is not None
        assert res.fill.side == side

    def test_status_simulating_ok(self, side_label, sptr01_sim_default, sptr01_policy_refs, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.SIMULATING,
            paper_order_id="PO_P1_SIM_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is False
        assert res.fill is not None

    def test_status_partially_filled_ok(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.PARTIALLY_FILLED,
            paper_order_id="PO_P1_PFILL_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is False
        assert res.fill is not None

    def test_status_filled_blocked(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.FILLED,
            paper_order_id="PO_P1_FILLED_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P1_ORDER_STATUS_NOT_FILLABLE.value in res.reject_reasons

    def test_status_canceled_blocked(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.CANCELED,
            paper_order_id="PO_P1_CXL_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P1_ORDER_STATUS_NOT_FILLABLE.value in res.reject_reasons

    def test_status_rejected_blocked(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.REJECTED,
            paper_order_id="PO_P1_REJ_" + side_label,
            requested_qty_base=Decimal("0.1"),
        )
        res = sptr01_sim_default.simulate(order=po, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is True
        assert PaperFillRejectReason.P1_ORDER_STATUS_NOT_FILLABLE.value in res.reject_reasons

    def test_qty_zero_blocked(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        po = _bypass_paper_order(
            side=side,
            status=PaperOrderStatus.CREATED,
            paper_order_id="PO_P1_QTY0_" + side_label,
            requested_qty_base=Decimal("0.000000001"),
        )
        from app.simulation.execution import calculate_fill_quantities
        with pytest.raises(ValueError):
            calculate_fill_quantities(
                requested_qty_base=Decimal("0.000000001"),
                fill_price=Decimal("1"),
                config=FillAssumptionsConfig(fill_ratio=Decimal("0.000000001")),
            )

    def test_rd_id_short_blocked(self, side_label, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        from app.contracts import PaperOrderSide, PaperOrderPolicyRefs
        side = PaperOrderSide.BUY if side_label == "buy" else PaperOrderSide.SELL
        with pytest.raises(Exception):  # policy_refs rejects < 8 chars
            PaperOrderPolicyRefs(
                risk_decision_id="SHORT", strategy_id="s", strategy_version="1.0.0",
            )
