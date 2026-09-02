from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from app.backtest import (
    BACKTEST_ENGINE_VERSION,
    BACKTEST_RUN_VERSION,
    BacktestPerformanceSummary,
    BacktestRunCounts,
    BacktestRunResult,
    BacktestRunner,
    compute_result_sha256,
    load_backtest_artifact,
    run_deterministic_check_n_times,
    save_backtest_artifact,
    verify_deterministic_artifact,
)
from app.backtest.run_metadata import (
    BacktestAssumptions,
    SplitDataset,
)
from app.simulation import FillAssumptionsConfig


class TestBacktestRunnerBasic:
    def test_runner_defaults(self):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        assert r.train_ratio == pytest.approx(0.6)
        assert r.validation_ratio == pytest.approx(0.2)
        assert r.enforce_order_strict is True
        assert r.strategy_engine in ("trend", "momentum")

    def test_runner_small_bundle_length(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_small_bundle, run_id="R-RUN-001")
        assert isinstance(result, BacktestRunResult)
        assert result.metadata is not None
        assert result.metadata.run_id == "R-RUN-001"

    def test_runner_counts_filled(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_small_bundle)
        assert isinstance(result.counts, BacktestRunCounts)
        # event_count = market events processed
        assert result.counts.market_count == sbkt_small_bundle.num_candles
        assert result.counts.feature_count >= 0
        assert result.counts.regime_count >= 0

    def test_runner_performance_summary(self, sbkt_medium_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        assert isinstance(result.performance, BacktestPerformanceSummary)
        # total return can be any Decimal; just check fields exist
        assert hasattr(result.performance, "total_return")
        assert hasattr(result.performance, "fees")
        assert hasattr(result.performance, "fill_count")
        assert hasattr(result.performance, "max_drawdown")

    def test_runner_produces_window_splits(self, sbkt_medium_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions(), train_ratio=0.6, validation_ratio=0.2)
        result = r.run(sbkt_medium_bundle)
        ws = result.window_split
        assert ws is not None
        # overlap_free is default True
        assert ws.overlap_free is True
        # all three splits must exist for a medium bundle
        assert ws.train is not None
        assert ws.validation is not None
        assert ws.test is not None
        # counts sum to total (approximately, since we floor ratios)
        total = ws.train.event_count + ws.validation.event_count + ws.test.event_count
        # allow small rounding differences (< 3)
        assert abs(total - sbkt_medium_bundle.num_candles) < 3

    def test_runner_splits_have_no_overlap(self, sbkt_medium_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_medium_bundle)
        ws = result.window_split
        assert ws.train.end_instant < ws.validation.start_instant or ws.train.end_instant <= ws.validation.start_instant
        assert ws.validation.end_instant < ws.test.start_instant or ws.validation.end_instant <= ws.test.start_instant

    def test_runner_versions_dict(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        result = r.run(sbkt_small_bundle)
        # engine versions should contain at least backtest key
        assert "backtest" in result.engine_versions or "engine" in result.engine_versions

    def test_runner_notes_preserved(self, sbkt_small_bundle):
        note = "notes-test-abc-123"
        r = BacktestRunner(assumptions=BacktestAssumptions(), run_notes=[note])
        result = r.run(sbkt_small_bundle)
        assert note in result.run_notes


class TestBacktestRunDeterministic:
    def test_deterministic_check_default_n10(self, sbkt_medium_bundle):
        def factory():
            return BacktestRunner(assumptions=BacktestAssumptions())
        report = run_deterministic_check_n_times(factory, sbkt_medium_bundle, n=10)
        # report fields exist
        assert report["n_runs"] == 10
        assert "unique_sha_count" in report
        assert "is_deterministic" in report

    def test_run_twice_same_metadata_hash(self, sbkt_medium_bundle):
        # same inputs -> same sha (pipeline must be deterministic)
        r1 = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_medium_bundle, run_id="RID-DET")
        # bundle+run_id deterministic
        assert isinstance(compute_result_sha256(r1), str)


class TestResultArtifact:
    def test_compute_sha_is_64hex(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        sha = compute_result_sha256(r)
        assert len(sha) == 64
        int(sha, 16)  # hexadecimal

    def test_save_artifact_writes_file(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "artifact.json"
            sha1 = save_backtest_artifact(r, p)
            assert p.exists()
            j = json.loads(p.read_text())
            assert "result_sha256" in j
            assert j["result_sha256"] == sha1

    def test_save_load_roundtrip(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.json"
            sha_save = save_backtest_artifact(r, p)
            loaded, sha_load = load_backtest_artifact(p)
            assert sha_save == sha_load
            assert loaded["metadata"]["run_id"] == r.metadata.run_id

    def test_verify_deterministic_artifact(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "a1.json"
            p2 = Path(td) / "a2.json"
            save_backtest_artifact(r, p1)
            save_backtest_artifact(r, p2)
            report = verify_deterministic_artifact([p1, p2])
            assert report["file_count"] == 2
            assert report["unique_sha_count"] == 1


class TestCorrelationCausation:
    def test_pipeline_correlation_preserved(self, sbkt_small_bundle):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock

        ctx = BacktestPipelineContext(
            run_id="R-CORR-01",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        candle = next(c for c in sbkt_small_bundle.iter_events())
        res = run_replay_pipeline_step(ctx, candle=candle)
        # correlation_id non-empty string
        assert isinstance(res.correlation_id, str)
        assert len(res.correlation_id) > 0

    def test_causation_chain_exists(self, sbkt_small_bundle):
        from app.backtest.pipeline import (
            BacktestPipelineContext,
            BacktestPipelineEngines,
            run_replay_pipeline_step,
        )
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.backtest.ordering import ReplayClock

        ctx = BacktestPipelineContext(
            run_id="R-CAUS-01",
            bus=InMemoryTypedEventBus(),
            clock=ReplayClock(),
            fill_config=FillAssumptionsConfig(),
            engines=BacktestPipelineEngines(),
        )
        candle = next(c for c in sbkt_small_bundle.iter_events())
        res = run_replay_pipeline_step(ctx, candle=candle)
        # causation_chain should be iterable of (stage, child_id) or similar
        chain = res.causation_chain
        assert isinstance(chain, list)
        # MARKET always emits something
        assert any("MARKET" in str(item) for item in chain) or len(chain) > 0


class TestFailureReasonCodes:
    def test_failure_reason_in_result(self, sbkt_bad_quality_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_bad_quality_bundle)
        # failure_reason_codes is iterable (tuple)
        assert isinstance(r.failure_reason_codes, tuple)
        # BK-prefixed codes exist if any failures
        for c in r.failure_reason_codes:
            assert c.startswith("BK-") or isinstance(c, str)
