from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.ordering import (
    assert_no_look_ahead,
    LookAheadLeakageError,
    ReplayClock,
)


class TestLeakageStatic:
    """Static-style tests for look-ahead invariants that do not need runtime."""

    def test_decision_input_after_decision_raises(self):
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead(
                "2025-01-01T00:00:00.000Z",
                "2025-01-01T00:00:00.001Z",
            )

    def test_t_plus_one_not_allowed(self):
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead(
                "2025-01-01T00:00:00.000Z",
                "2025-01-01T00:01:00.000Z",  # t + 1 min
            )

    @pytest.mark.parametrize("offset_ms", [1, 5, 100, 500, 999])
    def test_any_future_offset_raises(self, offset_ms):
        ts = "2025-01-01T00:00:00.000Z"
        future = f"2025-01-01T00:00:00.{offset_ms:03d}Z"
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead(ts, future)

    def test_equal_ok(self):
        assert_no_look_ahead("2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.000Z")

    @pytest.mark.parametrize("back_ms", [1, 1000, 60_000, 3600_000])
    def test_past_inputs_ok(self, back_ms):
        sec = 1735689600  # 2025-01-01 00:00:00 UTC
        dec_ts = sec * 1000 + 3600_000  # 01:00:00
        inp_ms = dec_ts - back_ms
        s1 = __import__("datetime").datetime.utcfromtimestamp(dec_ts // 1000).strftime("%Y-%m-%dT%H:%M:%S") + f".{dec_ts % 1000:03d}Z"
        s2 = __import__("datetime").datetime.utcfromtimestamp(inp_ms // 1000).strftime("%Y-%m-%dT%H:%M:%S") + f".{inp_ms % 1000:03d}Z"
        assert_no_look_ahead(s1, s2)

    def test_clock_blocks_future_decision(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:05:00.000Z")
        # Clock says max allowed future is 00:05.
        # Decision ts = 00:10 is future relative to clock, but also decision_input_max_ts > clock
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead(
                "2025-01-01T00:10:00.000Z",
                "2025-01-01T00:09:00.000Z",
                clock=rc,
            )


class TestLeakageRuntime:
    """Tests through the pipeline ensuring decision_input_max_ts never exceeds decision_ts."""

    def test_pipeline_records_max_input_ts(self, sbkt_medium_bundle):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock
        from app.simulation import FillAssumptionsConfig

        ctx = BacktestPipelineContext(
            run_id="R-LEAK-01",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        for c in sbkt_medium_bundle.iter_events():
            result = run_replay_pipeline_step(ctx, candle=c)
            # Decision ts >= max_input_ts invariant
            dec_ts = ctx.clock.decision_ts
            max_inp = ctx.clock.input_max_ts
            # ordering module guarantees monoticity, this is structural check
            assert max_inp <= dec_ts or max_inp == "" or dec_ts == ""

    def test_clock_not_monotonic_caught(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:10:00.000Z")
        with pytest.raises(LookAheadLeakageError):
            rc.advance("2025-01-01T00:09:59.999Z")


class TestOOSTrainValTestSplit:
    def test_split_overlap_zero(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        ws = result.window_split
        # train end < val start OR equal (but no intersection)
        assert ws.train.end_instant <= ws.validation.start_instant
        assert ws.validation.end_instant <= ws.test.start_instant

    def test_split_sum_count_close_to_total(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        ws = result.window_split
        total_split = ws.train.event_count + ws.validation.event_count + ws.test.event_count
        # allow max 2 rounding error
        assert abs(total_split - sbkt_medium_bundle.num_candles) <= 2

    def test_test_not_empty(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        assert result.window_split.test.event_count > 0

    def test_test_split_classification(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions, SplitDataset

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        ws = result.window_split
        assert ws.train.dataset == SplitDataset.TRAIN
        assert ws.validation.dataset == SplitDataset.VALIDATION
        assert ws.test.dataset == SplitDataset.TEST


class TestWalkForwardFoundation:
    def test_runner_supports_walk_forward_mode_flag(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions(), use_walk_forward=True)
        result = r.run(sbkt_medium_bundle)
        assert result.metadata.walk_forward_mode == "enabled" or result.metadata.walk_forward_mode != "disabled"

    def test_runner_disabled_walkforward_default(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        assert result.metadata.walk_forward_mode == "disabled"

    def test_window_split_version_present(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        assert result.window_split.version == "1.0.0"

    def test_metadata_windows_non_null_with_walkforward(self, sbkt_medium_bundle):
        from app.backtest.runner import BacktestRunner
        from app.backtest.run_metadata import BacktestAssumptions

        r = BacktestRunner(assumptions=BacktestAssumptions(), use_walk_forward=True)
        result = r.run(sbkt_medium_bundle)
        # runner must still set main metadata.train_window, validation_window, test_window
        assert result.metadata.train_window is not None
        assert result.metadata.validation_window is not None
        assert result.metadata.test_window is not None
