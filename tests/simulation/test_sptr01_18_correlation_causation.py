from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    QualityFlags,
    Symbol,
    ULID,
)
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation import (
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    build_pipeline_reference_data,
)


class TestCorrelationCausation:
    def test_18_01_correlation_preserved_buy_ob(self, sptr01_order_buy, sptr01_ref_ob, sptr01_bus, sptr01_config_default):
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)
        result = sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_ob,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert result.fill is not None
        assert str(result.fill.correlation_id) == str(sptr01_order_buy.correlation_id)

    def test_18_02_correlation_preserved_sell_tick(self, sptr01_order_sell, sptr01_ref_tick, sptr01_bus, sptr01_config_default):
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)
        result = sim.simulate(
            order=sptr01_order_sell,
            reference=sptr01_ref_tick,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert result.fill is not None
        assert str(result.fill.correlation_id) == str(sptr01_order_sell.correlation_id)

    def test_18_03_correlation_preserved_candle_ref(self, sptr01_order_buy, sptr01_ref_candle, sptr01_bus, sptr01_config_default):
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)
        result = sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_candle,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert result.fill is not None
        assert str(result.fill.correlation_id) == str(sptr01_order_buy.correlation_id)

    def test_18_04_causation_id_equals_paper_order_id_exact(self, sptr01_order_buy, sptr01_ref_ob, sptr01_bus, sptr01_config_default):
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)
        result = sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_ob,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert result.fill is not None
        assert str(result.fill.causation_id) == str(sptr01_order_buy.paper_order_id)

    def test_18_05_different_corr_ids_produce_distinct_fill_ids(self, sptr01_ts, sptr01_policy_refs, sptr01_ref_ob, sptr01_bus, sptr01_config_default):
        from app.contracts import PaperOrder, PaperOrderSide, PaperOrderStatus, PaperOrderType
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)
        fills_ids = set()
        for i in range(3):
            cid = f"COR{i:024d}"
            poid = f"POX{i:024d}"
            order = PaperOrder(
                paper_order_id=poid,
                side=PaperOrderSide.BUY,
                order_type=PaperOrderType.MARKET,
                requested_qty_base=Decimal("0.1"),
                policy_refs=sptr01_policy_refs,
                status=PaperOrderStatus.CREATED,
                created_at=sptr01_ts,
                updated_at=sptr01_ts,
                correlation_id=cid,
                causation_id="RD" + "0" * 23 + str(i),
            )
            r = sim.simulate(order=order, reference=sptr01_ref_ob, quality_ctx=QualityFlags(), publish_to_bus=False)
            assert r.fill is not None
            fills_ids.add(str(r.fill.paper_fill_id))
        assert len(fills_ids) == 3

    def test_18_06_event_envelope_correlation_match(self, sptr01_order_buy, sptr01_ref_ob, sptr01_config_default):
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        received = []

        def _h(ev):
            received.append(ev)
            return None

        bus.subscribe_typed("paper_fill_created.v1", _h)
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=bus)
        sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_ob,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert len(received) == 1
        ev = received[0]
        assert str(ev.correlation_id) == str(sptr01_order_buy.correlation_id)

    def test_18_07_event_envelope_causation_match(self, sptr01_order_sell, sptr01_ref_tick, sptr01_config_default):
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        received = []

        def _h(ev):
            received.append(ev)
            return None

        bus.subscribe_typed("paper_fill_created.v1", _h)
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=bus)
        sim.simulate(
            order=sptr01_order_sell,
            reference=sptr01_ref_tick,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert len(received) == 1
        ev = received[0]
        assert str(ev.causation_id) == str(sptr01_order_sell.paper_order_id)

    def test_18_08_trace_causation_chain_from_bus(self, sptr01_order_buy, sptr01_ref_ob, sptr01_config_default):
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        sim = PaperExecutionSimulator(config=sptr01_config_default, event_bus=bus)
        result = sim.simulate(
            order=sptr01_order_buy,
            reference=sptr01_ref_ob,
            quality_ctx=QualityFlags(),
            publish_to_bus=True,
        )
        assert result.fill is not None
        chain = bus.trace_causation_chain(str(result.fill.paper_fill_id))
        ids_str = [str(x) for x in chain]
        assert ids_str == [str(result.fill.paper_fill_id)]
        assert str(result.fill.causation_id) == str(sptr01_order_buy.paper_order_id)
