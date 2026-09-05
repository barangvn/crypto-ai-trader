"""S-BKT-02-06: Multi-Symbol × Multi-Fold Determinism."""

from __future__ import annotations

from tests.backtest.conftest import SyntheticBundle
from app.backtest.multi_fold_runner import (
    compute_multifold_sha256,
    run_multifold_walkforward,
)
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import BacktestRunner


def _runner_factory(**kw):
    return BacktestRunner(assumptions=BacktestAssumptions(), **kw)


def test_three_symbol_multifold():
    evs = []
    for sym in ["BTC_USDT", "ETH_USDT", "SOL_USDT"]:
        b = SyntheticBundle(num_candles=800)
        evs.extend(list(b.iter_events()))
    # make a pseudo-bundle
    class MBundle:
        bundle_id = "MSB_MULTISYM"
        version = "1.0.0"
        sha = "0" * 64
        symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]

        def iter_events(self):
            return iter(evs)

        def compute_sha256(self):
            return self.sha

    res = run_multifold_walkforward(_runner_factory, MBundle())
    assert res.aggregate_summary.fold_count == 5


def test_multisymbol_multifold_sha_10x():
    evs = []
    for sym in ["BTC_USDT", "ETH_USDT"]:
        b = SyntheticBundle(num_candles=500)
        evs.extend(list(b.iter_events()))

    class M:
        bundle_id = "MSB_2SYM"
        version = "1.0.0"
        sha = "abcd1234" * 16
        symbols = ["BTC_USDT", "ETH_USDT"]

        def iter_events(self):
            return iter(evs)

        def compute_sha256(self):
            return self.sha

    shas = []
    for _ in range(10):
        r = run_multifold_walkforward(_runner_factory, M(), run_id="MSYM_10X")
        shas.append(compute_multifold_sha256(r))
    assert len(set(shas)) == 1
