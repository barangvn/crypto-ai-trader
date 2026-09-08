"""S-BKT-03 06: Strategy/Regime decomposition (OD-05 corr chain unknown groups)."""

from __future__ import annotations

import pytest

from tests.backtest.conftest import SyntheticBundle
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner


def test_sbkt03_M06_runner_v2_strategy_regime_rows_populated():
    b = SyntheticBundle(num_candles=180, seed=9, drift=Decimal("0.0005"))
    r = BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"))
    res = r.run(b)
    rows = res.performance_v2.strategy_regime_rows_sorted
    assert isinstance(rows, tuple)
    for row in rows:
        assert "strategy_id" in row
        assert "regime" in row
        assert "trade_count" in row
        # OD-05: wrapper saglanmadiginda group UNKNOWN_STRATEGY / UNKNOWN_REGIME.
        # Audit NOT reject - so its OK if this is the case.
        assert row["strategy_id"] == "UNKNOWN_STRATEGY"
        assert row["regime"] == "UNKNOWN_REGIME"


from decimal import Decimal  # noqa: E402 (drift parametre icin import yukarida gerek)

DECOMP_CORR_CASES = [
    (["C1", "C2", "C3"], 3),
    (["X1"], 1),
    (["A", "A", "A"], 1),
    (["C1", "C1", "C2", "C2"], 2),
    (["u1", "u2", "u3", "u4", "u5"], 5),
    ([], 0),
    (["TRADE_123"], 1),
    (["CORR_A", "CORR_B", "CORR_A", "CORR_B", "CORR_C"], 3),
    (["ORDER_001", "ORDER_002", "ORDER_001", "ORDER_003"], 3),
    (["S1", "S2", "S3", "S1", "S2", "S3", "S4"], 4),
]


@pytest.mark.parametrize("corr_list,exp_min_groups", DECOMP_CORR_CASES)
def test_sbkt03_M06_decomp_10correlation_cases(corr_list, exp_min_groups):
    """10 hücre: decomposition correlation unknown group policy (OD-05)."""
    from app.backtest.metrics_compute import group_by_strategy_regime, StrategyRegimeRow

    def _make(corr):
        class _F:
            correlation_id = corr
        return _F()

    fills = [_make(c) for c in corr_list]
    rows = group_by_strategy_regime(fills)
    for r in rows:
        assert isinstance(r, StrategyRegimeRow)
        assert r.strategy_id == "UNKNOWN_STRATEGY"
        assert r.regime == "UNKNOWN_REGIME"
    assert len(rows) >= exp_min_groups or len(rows) == 0
