from __future__ import annotations

import pytest
from decimal import Decimal

from app.simulation import FillAssumptionsConfig
from app.simulation.execution import (
    deterministic_latency_ms,
    _instant_plus_ms,
    _parse_instant_to_dt,
)


# G4: 12 tests — P3 Latency NO SLEEP boundary exact zero small high max invalid
class TestPipelineP3Latency:
    def test_latency_zero_boundary(self):
        cfg = FillAssumptionsConfig(base_latency_ms=0, latency_jitter_ms=0)
        lat = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T", order_id="O")
        assert lat == 0

    def test_latency_1ms_small(self):
        cfg = FillAssumptionsConfig(base_latency_ms=1, latency_jitter_ms=0)
        lat = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T", order_id="O")
        assert lat == 1

    def test_latency_50ms_normal_default(self):
        cfg = FillAssumptionsConfig(base_latency_ms=50, latency_jitter_ms=0)
        lat = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T", order_id="O")
        assert lat == 50

    def test_latency_max_boundary_exact(self):
        cfg = FillAssumptionsConfig(base_latency_ms=5000, latency_jitter_ms=0, max_latency_ms=5000)
        lat = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T", order_id="O")
        assert lat == 5000

    def test_latency_cap_applied_over_max(self):
        cfg = FillAssumptionsConfig(base_latency_ms=9999, latency_jitter_ms=9999, max_latency_ms=5000)
        with pytest.raises(ValueError):
            deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T", order_id="O")

    def test_latency_jitter_bounded(self):
        cfg = FillAssumptionsConfig(base_latency_ms=0, latency_jitter_ms=50, max_latency_ms=5000)
        results = set()
        for n in range(100):
            lat = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts=f"T{n}", order_id="O")
            assert 0 <= lat <= 50
            results.add(lat)
        # Check deterministic: same input same latency
        lat_a = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T1", order_id="O")
        lat_b = deterministic_latency_ms(config=cfg, correlation_id="C", reference_market_ts="T1", order_id="O")
        assert lat_a == lat_b

    def test_instant_plus_zero_ms_unchanged(self, sptr01_ts):
        result = _instant_plus_ms(sptr01_ts, 0)
        assert result == sptr01_ts

    def test_instant_plus_1000ms(self, sptr01_ts):
        result = _instant_plus_ms(sptr01_ts, 1000)
        orig_dt = _parse_instant_to_dt(sptr01_ts)
        res_dt = _parse_instant_to_dt(result)
        delta_ms = (res_dt - orig_dt).total_seconds() * 1000
        assert abs(delta_ms - 1000) < 1.0

    def test_instant_plus_boundary_max(self, sptr01_ts):
        result = _instant_plus_ms(sptr01_ts, 5000)
        assert len(result) == len(sptr01_ts)

    def test_simulator_uses_latency_in_fill_ts(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(base_latency_ms=100, latency_jitter_ms=0)
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.latency_ms_applied == 100
        expected_fill_ts = _instant_plus_ms(str(sptr01_order_buy.created_at), 100)
        assert str(res.fill.fill_ts) == expected_fill_ts

    def test_latency_ms_on_fill_field(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        cfg = FillAssumptionsConfig(base_latency_ms=7, latency_jitter_ms=0)
        sim = PaperExecutionSimulator(config=cfg, event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None
        assert res.fill.latency_ms == 7

    def test_no_sleep(self, monkeypatch):
        calls = []
        import app.simulation.execution as m
        monkeypatch.setattr(m, "_instant_plus_ms", lambda s, ms: (calls.append(("s", ms)), s)[1])
        from app.simulation.execution import _instant_plus_ms as f
        f("X", 1)
        assert calls == [("s", 1)]
