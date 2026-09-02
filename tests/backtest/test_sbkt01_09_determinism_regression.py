from __future__ import annotations

import json
import pytest

from app.backtest.runner import (
    BacktestRunner,
    compute_result_sha256,
    run_deterministic_check_n_times,
    save_backtest_artifact,
    load_backtest_artifact,
)
from app.backtest.run_metadata import BacktestAssumptions


class TestDeterminismFull:
    def test_10x_runner_same_inputs_same_sha(self, sbkt_medium_bundle):
        """10 runs of identical runner + bundle → 1 unique SHA."""
        def factory():
            return BacktestRunner(assumptions=BacktestAssumptions())
        rep = run_deterministic_check_n_times(factory, sbkt_medium_bundle, n=10)
        assert rep["n_runs"] == 10
        assert rep["unique_sha_count"] == 1, f"non-deterministic! SHAs: {rep['sha_list']}"

    def test_10x_sha_list_singleton(self, sbkt_medium_bundle):
        def factory():
            return BacktestRunner(assumptions=BacktestAssumptions())
        rep = run_deterministic_check_n_times(factory, sbkt_medium_bundle, n=10)
        assert len(rep["sha_list"]) == 1

    def test_run_twice_same_run_id_same_sha(self, sbkt_small_bundle):
        """Two calls with same run_id → deterministic. (Random ULID for correlation is seeded from run_id/counter in pipeline)."""
        runner1 = BacktestRunner(assumptions=BacktestAssumptions())
        runner2 = BacktestRunner(assumptions=BacktestAssumptions())
        r1 = runner1.run(sbkt_small_bundle, run_id="RID-SAME-111")
        r2 = runner2.run(sbkt_small_bundle, run_id="RID-SAME-111")
        assert compute_result_sha256(r1) == compute_result_sha256(r2)

    def test_artifact_json_keys_sorted(self, sbkt_small_bundle, tmp_path):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        p = tmp_path / "det.json"
        save_backtest_artifact(r, p)
        parsed = json.loads(p.read_text(encoding="utf-8"))
        # verify top-level keys sorted in raw JSON string (preserve sort order from json.dumps)
        raw = p.read_text(encoding="utf-8")
        top_order = [key for key in json.JSONDecoder().raw_decode(raw)[0]]
        assert top_order == sorted(top_order), "JSON artifact top-level keys NOT sorted!"

    def test_save_artifact_twice_same_bytes(self, sbkt_small_bundle, tmp_path):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        p1 = tmp_path / "a1.json"
        p2 = tmp_path / "a2.json"
        save_backtest_artifact(r, p1)
        save_backtest_artifact(r, p2)
        assert p1.read_bytes() == p2.read_bytes()

    def test_result_hash_in_metadata(self, sbkt_small_bundle):
        r = BacktestRunner(assumptions=BacktestAssumptions()).run(sbkt_small_bundle)
        # result_hash in metadata
        assert r.metadata.result_hash is not None
        assert len(r.metadata.result_hash) == 64


class TestDeterminismEventLevel:
    @pytest.mark.parametrize("n", [2, 5, 10])
    def test_counts_equal_across_runs(self, sbkt_medium_bundle, n):
        """Run n times, verify all 19 counts identical."""
        runs = []
        for i in range(n):
            runner = BacktestRunner(assumptions=BacktestAssumptions())
            result = runner.run(sbkt_medium_bundle, run_id="RID-DET-COUNTS")
            runs.append(result.counts)
        first = runs[0]
        from dataclasses import asdict
        d0 = asdict(first)
        for other in runs[1:]:
            assert asdict(other) == d0


class TestRegressionBaselinePreserved:
    def test_prior_modules_importable(self):
        from app.features import FeatureEngine  # S-FEA-01
        from app.regime import RegimeEngine  # S-REG-01
        from app.strategies import TrendFollowingStrategy, MomentumStrategy  # S-STR-01
        from app.opportunity import DeterministicOpportunityScorer  # S-OPP-01
        from app.risk import IndependentRiskEngine, evaluate_risk  # S-RSK-01
        from app.risk.gate import RiskDecisionToPaperOrderGate  # S-RSK-02
        from app.simulation import PaperExecutionSimulator, FillAssumptionsConfig  # S-PTR-01
        from app.simulation.portfolio import apply_fill, build_portfolio_snapshot, build_rolling_24h  # S-PTF-01/02/03
        from app.platform.event_bus import InMemoryTypedEventBus  # S-PLN-01
        assert True

    def test_baseline_feature_engine_still_works(self):
        from app.features import FeatureEngine
        from app.contracts import Candle
        from decimal import Decimal
        candles = []
        p0 = 100.0
        for i in range(25):
            ts_s = f"2025-01-01T00:{i:02d}:00.000Z"
            ts_e = f"2025-01-01T00:{i+1:02d}:00.000Z"
            candles.append(Candle(
                timeframe="1m",
                open_time=ts_s,
                close_time=ts_e,
                open=Decimal(str(p0 + i)),
                high=Decimal(str(p0 + i + 2)),
                low=Decimal(str(p0 + i - 2)),
                close=Decimal(str(p0 + i + 0.5)),
                volume=Decimal("100"),
                closed=True,
            ))
        fv = FeatureEngine().calculate("BTC_USDT", candles, timeframe="1m")
        assert fv is not None
