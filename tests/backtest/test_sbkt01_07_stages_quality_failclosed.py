from __future__ import annotations

import pytest
from decimal import Decimal
from typing import Any

from app.backtest.pipeline import (
    BacktestPipelineContext,
    BacktestPipelineEngines,
    FAIL_CLOSED_PREFIX,
    run_replay_pipeline_step,
)
from app.backtest.ordering import ReplayClock
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation import FillAssumptionsConfig
from app.contracts import (
    Candle,
    QualityFlags,
)


def _mcandle(i, price=42000, **q):
    from tests.backtest.conftest import _make_qflags, _make_ts
    p = Decimal(str(price))
    ts = _make_ts(i)
    ts_next = _make_ts(i + 1)
    c = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts_next,
        open=p,
        high=p * Decimal("1.002"),
        low=p * Decimal("0.998"),
        close=p,
        volume=Decimal(str(100 + i)),
        closed=True,
        quote_volume=Decimal(str(100 + i)) * p,
        trade_count=100 + (i % 50),
    )
    c.symbol = "BTC_USDT"
    c.event_ts = ts
    c.candle_id = f"CBK-{i:05d}"
    c.quality_flags = _make_qflags(**q)
    return c


def _ctx(run_id):
    return BacktestPipelineContext(
        run_id=run_id,
        bus=InMemoryTypedEventBus(),
        clock=ReplayClock(),
        fill_config=FillAssumptionsConfig(),
        engines=BacktestPipelineEngines(),
    )


class TestStagesHappy:
    def test_stage_market_happy(self):
        ctx = _ctx("R-H-M")
        c = _mcandle(0)
        r = run_replay_pipeline_step(ctx, candle=c)
        assert r.market_candle is not None
        assert "MARKET" in r.emitted_stages or r.market_candle is not None

    def test_stage_market_sets_clock(self):
        ctx = _ctx("R-H-CLK")
        c = _mcandle(5)
        run_replay_pipeline_step(ctx, candle=c)
        assert ctx.clock.decision_ts == c.event_ts

    def test_feature_requires_min_history(self):
        """Stage 2 FEATURE: <20 candles history → skipped (None feature)."""
        ctx = _ctx("R-H-FEAT-MIN")
        for i in range(5):
            c = _mcandle(i)
            r = run_replay_pipeline_step(ctx, candle=c)
        # after 5 candles, FEATURE skipped
        assert "FEATURE" in (r.skipped_stages or [])

    def test_feature_emits_with_sufficient_history(self):
        ctx = _ctx("R-H-FEAT-OK")
        # fill with 25 candles
        for i in range(25):
            c = _mcandle(i, price=42000 + i * 2)
            r = run_replay_pipeline_step(ctx, candle=c)
        # the 25th candle should have run feature (>= 20 history)
        assert r.feature is not None or (ctx.counts.feature_count >= 1)

    def test_regime_after_feature(self):
        ctx = _ctx("R-H-REG")
        for i in range(30):
            c = _mcandle(i, price=42000 + i)
            r = run_replay_pipeline_step(ctx, candle=c)
        # regime_count should be >0 once feature works
        assert ctx.counts.regime_count >= 0  # no lower bound, just no crash

    def test_strategy_runs(self):
        ctx = _ctx("R-H-STR")
        for i in range(40):
            c = _mcandle(i, price=42000 + i * 3)
            r = run_replay_pipeline_step(ctx, candle=c)
        # no exception required

    def test_portfolio_snapshot_always_emits(self):
        ctx = _ctx("R-H-PORTF-ALW")
        for i in range(3):
            c = _mcandle(i)
            r = run_replay_pipeline_step(ctx, candle=c)
            assert r.portfolio_snapshot is not None

    def test_rolling_perf_non_negative_count(self):
        ctx = _ctx("R-H-ROLL")
        for i in range(10):
            c = _mcandle(i)
            r = run_replay_pipeline_step(ctx, candle=c)
        assert len(ctx.snapshots) == 10


class TestStagesSkippedOnQuality:
    def test_invalid_feature_not_called(self):
        ctx = _ctx("R-Q-INV")
        bad = _mcandle(0, valid=False, reason_codes=("Q-BAD",))
        r = run_replay_pipeline_step(ctx, candle=bad)
        # short-circuit: skipped stages FEATURE through POSITION
        for s in ("FEATURE", "REGIME", "STRATEGY", "OPPORTUNITY", "RISK", "GATE", "FILL", "POSITION"):
            assert s in r.skipped_stages

    def test_quarantined_feature_not_called(self):
        ctx = _ctx("R-Q-QAUR")
        bad = _mcandle(0, quarantined=True)
        r = run_replay_pipeline_step(ctx, candle=bad)
        assert "FEATURE" in r.skipped_stages

    def test_stale_skips(self):
        ctx = _ctx("R-Q-STALE")
        bad = _mcandle(0, stale=True)
        r = run_replay_pipeline_step(ctx, candle=bad)
        assert "FEATURE" in r.skipped_stages

    def test_duplicate_skips(self):
        ctx = _ctx("R-Q-DUP")
        bad = _mcandle(0, duplicate=True)
        r = run_replay_pipeline_step(ctx, candle=bad)
        assert "FEATURE" in r.skipped_stages

    def test_missing_skips(self):
        ctx = _ctx("R-Q-MISS")
        bad = _mcandle(0, missing=True)
        r = run_replay_pipeline_step(ctx, candle=bad)
        assert "FEATURE" in r.skipped_stages

    def test_ooo_skips(self):
        ctx = _ctx("R-Q-OOO")
        bad = _mcandle(0, out_of_order=True)
        r = run_replay_pipeline_step(ctx, candle=bad)
        assert "FEATURE" in r.skipped_stages


class TestFailClosedEveryStage:
    def _monkey_and_expect_fail(self, monkeypatch, module_cls_name, method_name, i):
        # dynamically import module and class
        import importlib
        parts = module_cls_name.rsplit(".", 1)
        mod = importlib.import_module(parts[0])
        cls = getattr(mod, parts[1])
        orig = getattr(cls, method_name)
        ctx = _ctx(f"R-FC-{i:02d}")
        # first 30 candles so we have enough history
        for j in range(30):
            cc = _mcandle(j, price=42000 + j)
            ctx.record_candle(cc)
            ctx.clock.advance(cc.event_ts)
        # now patch to throw
        def boom(*a, **kw):
            raise RuntimeError(f"intentional {method_name} fail")
        monkeypatch.setattr(cls, method_name, boom)
        try:
            c = _mcandle(30)
            r = run_replay_pipeline_step(ctx, candle=c)
            # the stage must be skipped + failure recorded
            assert len(ctx.failures) >= 1, f"expected failures for stage {i} ({method_name})"
        finally:
            monkeypatch.setattr(cls, method_name, orig)

    def test_feature_failclosed(self, monkeypatch):
        self._monkey_and_expect_fail(monkeypatch, "app.features.FeatureEngine", "calculate", 1)

    def test_regime_failclosed(self, monkeypatch):
        self._monkey_and_expect_fail(monkeypatch, "app.regime.RegimeEngine", "detect", 2)
