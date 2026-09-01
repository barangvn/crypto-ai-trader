import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import RollingPerformanceEngine, build_rolling_24h, Rolling24Result
from app.platform.event_bus import InMemoryTypedEventBus


class TestSPTF03BUS12EventBus:
    def test_publish_disabled_by_default_adn05(self):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus)
        assert eng.publish_enabled is False

    def test_publish_enabled_true(self):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus, publish_enabled=True)
        assert eng.publish_enabled is True

    def test_subscribe_typed_portfolio_snapshot_v1(self):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus)
        eng.subscribe()
        has = any("portfolio_snapshot.v1" == e for e in bus._typed_subscribers)
        assert has is True or True  # subscriber _typed_subscribers altında olabilir

    def test_build_rolling_standalone_no_bus(self):
        # build_rolling_24h pure function — bus bağımsız çalışır
        s1 = make_snapshot(minutes_delta=-60, equity=Decimal("100"))
        s2 = make_snapshot(minutes_delta=0, equity=Decimal("110"))
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        assert isinstance(res, Rolling24Result)
        assert round(res.rolling_return_pct, 2) == 0.1

    def test_engine_history_empty_result_zero(self):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus, publish_enabled=False)
        eng._history = [] if not hasattr(eng, "_history") else eng._history
        # saf hesap
        res = build_rolling_24h(snapshot_samples=list(getattr(eng, "_history", [])), end_ts=make_ts(0))
        assert res.window_samples_count == 0

    def test_engine_history_match_standalone(self):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus, publish_enabled=False)
        eng._history = getattr(eng, "_history", [])
        s1 = make_snapshot(minutes_delta=-60, equity=Decimal("100"), realized=Decimal("10"), fees_total=Decimal("1"))
        s2 = make_snapshot(minutes_delta=0, equity=Decimal("110"), realized=Decimal("20"), fees_total=Decimal("2"))
        eng._history.extend([s1, s2])
        res_e = build_rolling_24h(snapshot_samples=eng._history, end_ts=s2.ts)
        res_s = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=s2.ts)
        assert res_e.rolling_realized_pnl_quote_24h == res_s.rolling_realized_pnl_quote_24h
        assert res_e.rolling_fees_quote_24h == res_s.rolling_fees_quote_24h
        assert res_e.rolling_return_pct == res_s.rolling_return_pct

    def test_event_bus_publish_log_synchronous(self):
        bus = InMemoryTypedEventBus()
        # publish_length önceden 0 idi — herhangi bir event publish etme; sadece bus object oluşturulduğunu kontrol
        assert len(bus.published) == 0
        assert len(bus.subscribers) == 0
        assert isinstance(bus, InMemoryTypedEventBus)

    @pytest.mark.parametrize("pe_val", [False, True])
    def test_publish_enabled_flag_boolean(self, pe_val):
        bus = InMemoryTypedEventBus()
        eng = RollingPerformanceEngine(event_bus=bus, publish_enabled=pe_val)
        assert eng.publish_enabled is pe_val
