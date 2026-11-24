"""Paper Trading MVP — determinism acceptance tests (AC-02).

Ten independent runs with identical inputs must produce identical
``compute_result_sha256`` values. Differences are never concealed through
silent normalization: raw sha strings and raw rendered summaries are compared
for exact equality.
"""
from __future__ import annotations

from pathlib import Path

from app.backtest import BacktestRunner, compute_result_sha256, run_deterministic_check_n_times
from app.backtest.run_metadata import BacktestAssumptions
from app.paper.__main__ import build_paper_summary
from app.paper.fixture_bundle import FixtureBundle
from app.paper.summary import render_summary_json


REPO_ROOT: Path = Path(__file__).resolve().parents[2]
FIXTURE_PATH: Path = REPO_ROOT / "tests_fixtures" / "small_3sym_1h_1m_candles.csv"

RUNS = 10


def _runner_factory() -> BacktestRunner:
    return BacktestRunner(assumptions=BacktestAssumptions())


class TestAC02Determinism:
    def test_ac02_ten_runs_identical_result_sha(self) -> None:
        shas = []
        for _ in range(RUNS):
            result = _runner_factory().run(FixtureBundle(FIXTURE_PATH))
            shas.append(compute_result_sha256(result))
        assert len(shas) == RUNS
        assert len(set(shas)) == 1, f"non-deterministic result shas: {sorted(set(shas))}"

    def test_ac02_helper_reports_single_unique_sha(self) -> None:
        report = run_deterministic_check_n_times(
            _runner_factory, FixtureBundle(FIXTURE_PATH), n=RUNS
        )
        assert report["n_runs"] == RUNS
        assert report["unique_sha_count"] == 1
        assert report["is_deterministic"] is True
        assert len(report["sha_list"]) == 1

    def test_ac02_bundle_sha_stable_across_builds(self) -> None:
        shas = {FixtureBundle(FIXTURE_PATH).compute_sha256() for _ in range(RUNS)}
        assert len(shas) == 1

    def test_ac02_summary_json_identical_across_ten_runs(self) -> None:
        rendered = {
            render_summary_json(build_paper_summary(env="test", fixture_path=FIXTURE_PATH))
            for _ in range(RUNS)
        }
        assert len(rendered) == 1
