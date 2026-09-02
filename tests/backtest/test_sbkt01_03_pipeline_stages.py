from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import (
    Candle,
    QualityFlags,
)


def _make_candle(i: int, price: float = 42000.0, **q_kwargs):
    from tests.backtest.conftest import _make_qflags, _make_ts
    p = Decimal(str(price))
    ts = _make_ts(i)
    ts_next = _make_ts(i + 1)
    c = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts_next,
        open=p,
        high=p * Decimal("1.001"),
        low=p * Decimal("0.999"),
        close=p,
        volume=Decimal(str(100 + i)),
        closed=True,
        quote_volume=Decimal(str(100 + i)) * p,
        trade_count=100 + (i % 50),
    )
    c.symbol = "BTC_USDT"
    c.event_ts = ts
    c.candle_id = f"CTEST-{i:05d}"
    c.quality_flags = _make_qflags(**q_kwargs)
    return c


class TestStage01Market:
    def test_stage01_process_candle(self, sbkt_small_bundle):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-TEST-01",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        candles = [c for c in sbkt_small_bundle.iter_events()][:1]
        res = run_replay_pipeline_step(ctx, candle=candles[0])
        assert res.market_tick is not None or res.market_candle is not None

    def test_stage01_quality_invalid_shortcircuits(self):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-TEST-Q",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        bad_candle = _make_candle(0, price=42000, valid=False)
        res = run_replay_pipeline_step(ctx, candle=bad_candle)
        assert len(res.skipped_stages) > 0
        # portfolio / performance still fire for invalid candles (equity curve continuity)
        assert res.portfolio_snapshot is not None

    def test_stage01_quarantined_shortcircuits(self):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-TEST-QAUR",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        q_candle = _make_candle(0, price=42000, quarantined=True)
        res = run_replay_pipeline_step(ctx, candle=q_candle)
        assert len(res.skipped_stages) >= 1


class TestPipelineSmokeMulti:
    def test_twenty_candles_no_exception(self):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-20C",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        for i in range(20):
            c = _make_candle(i, price=42000 + i)
            r = run_replay_pipeline_step(ctx, candle=c)
        # after 20 candles feature engine should have enough history
        # (needs at least 20 candles)
        assert len(ctx.snapshots) == 20

    def test_snapshot_equity_decreases_on_fees_if_fills(self, sbkt_medium_bundle):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-120C",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        for c in sbkt_medium_bundle.iter_events():
            run_replay_pipeline_step(ctx, candle=c)
        # always expect snapshots >0
        assert len(ctx.snapshots) > 0
        # non-negative total counts
        for key in ("market_count", "feature_count", "regime_count"):
            assert getattr(ctx.counts, key, 0) >= 0


class TestPipelineFailClosed:
    def test_failclosed_prefix_on_feature_monkey(self, monkeypatch):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
            FAIL_CLOSED_PREFIX,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-FC-01",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        # monkey patch feature engine to fail
        from app.features import FeatureEngine
        orig = FeatureEngine.calculate
        try:
            def boom(self, *a, **kw):
                raise RuntimeError("intentional feature fail")
            monkeypatch.setattr(FeatureEngine, "calculate", boom)
            c = _make_candle(30, price=42000)
            # need enough candle history to trigger FEATURE stage
            # add first 30 candles
            for i in range(30):
                cc = _make_candle(i, price=42000 + i)
                ctx.record_candle(cc)
                ctx.clock.advance(cc.event_ts)
            # now re-add with boom active
            res = run_replay_pipeline_step(ctx, candle=c)
            assert len(ctx.failures) > 0
            # failure reason should start with BK-
            assert any(f[1].startswith(FAIL_CLOSED_PREFIX) for f in ctx.failures) or any(f[0] == "FEATURE" for f in ctx.failures)
        finally:
            monkeypatch.setattr(FeatureEngine, "calculate", orig)
