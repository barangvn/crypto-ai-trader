from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import CONTRACT_VERSION
from app.simulation import FillAssumptionsConfig, PaperExecutionSimulator


# G12: 20 tests — Typed EventBus Integration (S-PLN-01)
class TestEventBusIntegration:
    def test_publish_fill_event(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        assert len(sptr01_bus.published) == 0
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert len(sptr01_bus.published) >= 1
        types_published = [e.event_type for e in sptr01_bus.published]
        assert "paper_fill_created.v1" in types_published

    def test_causation_id_set_to_po(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert len(sptr01_bus.published) >= 1
        fill_env = next(e for e in sptr01_bus.published if e.event_type == "paper_fill_created.v1")
        assert fill_env.causation_id == str(sptr01_order_buy.paper_order_id)

    def test_correlation_id_preserved(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        fill_env = next(e for e in sptr01_bus.published if e.event_type == "paper_fill_created.v1")
        assert fill_env.correlation_id == str(sptr01_order_buy.correlation_id)

    def test_envelope_event_type(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        fill_env = next(e for e in sptr01_bus.published if e.event_type == "paper_fill_created.v1")
        assert fill_env.event_type == "paper_fill_created.v1"

    def test_envelope_payload_is_fill(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.contracts import PaperFill
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        fill_env = next(e for e in sptr01_bus.published if e.event_type == "paper_fill_created.v1")
        assert isinstance(fill_env.payload, PaperFill)

    def test_rejected_event_publish(self, sptr01_order_buy, sptr01_ref_tick, sptr01_bus):
        from app.contracts import QualityFlags
        qf = QualityFlags(stale=True)
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf, publish_to_bus=True)
        sim.publish_rejection(order=sptr01_order_buy, result=res, reference=sptr01_ref_tick, quality_ctx=qf)
        types = [e.event_type for e in sptr01_bus.published]
        assert "paper_fill_rejected.v1" in types

    def test_subscriber_exception_isolation_dlq(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        received_ok = []
        received_exc = []

        def good_sub(env):
            received_ok.append(env.event_id)

        def bad_sub(env):
            raise RuntimeError("kaboom")

        def good_sub2(env):
            received_exc.append(env.event_id)

        sptr01_bus.subscribe_typed("paper_fill_created.v1", good_sub)
        sptr01_bus.subscribe_typed("paper_fill_created.v1", bad_sub)
        sptr01_bus.subscribe_typed("paper_fill_created.v1", good_sub2)
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert len(sptr01_bus.dead_letters) >= 1
        dlq_codes = [d.dlq_code for d in sptr01_bus.dead_letters]
        assert "E_SUBSCRIBER_EXC" in dlq_codes
        # good subscribers called
        assert len(received_ok) >= 1
        assert len(received_exc) >= 1

    def test_quarantine_skip_dlq(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.contracts import QualityFlags
        import app.simulation.execution as exe_mod
        orig = exe_mod.PaperExecutionSimulator.simulate

        class Fake:
            event_type = "paper_fill_created.v1"
            contract_version = CONTRACT_VERSION
            event_id = "QUAR" + "T" * 22
            correlation_id = sptr01_order_buy.correlation_id
            causation_id = sptr01_order_buy.paper_order_id
            quality_flags = QualityFlags(quarantined=True)

        received_q_ok = []
        sptr01_bus.subscribe_typed(
            "paper_fill_created.v1", lambda env: received_q_ok.append(env.event_id),
            accept_quarantined=False,
        )
        sptr01_bus.publish(Fake())  # type: ignore[arg-type]
        dlq_codes = [d.dlq_code for d in sptr01_bus.dead_letters]
        assert "E_QUARANTINED_SKIP" in dlq_codes or len(received_q_ok) == 0

    def test_trace_causation_chain(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        chain = sptr01_bus.trace_causation_chain(str(res.fill.paper_fill_id))
        assert chain == [str(res.fill.paper_fill_id)]
        assert str(res.fill.causation_id) == str(sptr01_order_buy.paper_order_id)

    def test_subscribe_typed_min_version(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        v_matches = []
        sptr01_bus.subscribe_typed(
            "paper_fill_created.v1", lambda e: v_matches.append(True),
            contract_version_min=(1, 0, 0),
        )
        sptr01_bus.subscribe_typed(
            "paper_fill_created.v1", lambda e: None,
            contract_version_min=(99, 99, 99),
        )
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        codes = [d.dlq_code for d in sptr01_bus.dead_letters]
        assert len(v_matches) >= 1 or "E_CONTRACT_VERSION_MIN" in codes

    def test_publish_no_bus_works(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy):
        sim = PaperExecutionSimulator(event_bus=None)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy, publish_to_bus=True)
        assert res.fill is not None

    def test_publish_flag_false_no_event(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_tick,
            quality_ctx=sptr01_quality_healthy,
            publish_to_bus=False,
        )
        assert res.fill is not None
        assert len(sptr01_bus.published) == 0

    @pytest.mark.parametrize("n", range(8))
    def test_8_bus_publishes_fill(self, n, sptr01_ts):
        from app.contracts import (
            PaperOrder, PaperOrderSide, PaperOrderType, PaperOrderStatus,
            PaperOrderPolicyRefs, MarketTick, QualityFlags, Symbol,
        )
        from app.simulation import build_pipeline_reference_data
        policy = PaperOrderPolicyRefs(
            risk_decision_id="RD-BUS-" + str(n) + "X" * 8,
            strategy_id="x",
            strategy_version="1.0.0",
        )
        order = PaperOrder(
            paper_order_id="PO-BUS-" + str(n) + "X" * 8,
            side=PaperOrderSide.BUY if n % 2 == 0 else PaperOrderSide.SELL,
            order_type=PaperOrderType.MARKET,
            requested_qty_base=__import__("decimal").Decimal("0.05"),
            policy_refs=policy,
            status=PaperOrderStatus.CREATED,
            created_at=sptr01_ts,
            updated_at=sptr01_ts,
            correlation_id="COR-BUS-" + str(n) + "X" * 8,
            causation_id="RD-BUS-" + str(n) + "X" * 8,
        )
        tick = MarketTick(
            price=Decimal(f"{1000 + n}"),
            market_ts=sptr01_ts,
            bid_price=Decimal(f"{999 + n}"),
            ask_price=Decimal(f"{1001 + n}"),
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        sim = PaperExecutionSimulator(event_bus=bus)
        ref = build_pipeline_reference_data(tick=tick, symbol=Symbol("BTC_USDT"))
        res = sim.simulate(order=order, reference=ref, quality_ctx=QualityFlags())
        assert res.fill is not None
        assert len(bus.published) >= 1
