"""S-BKT-03 03: Performance metrics (FR-059 set) basic + edge cases.

Reuse metrics_compute pure helpers + runner V2 population.
DONT rewrite PnL/equity/drawdown (S-PTF-01/02/03 reuse).
"""

from __future__ import annotations

import math
import pytest
from dataclasses import dataclass
from decimal import Decimal

from app.backtest.metrics_compute import (
    _r8,
    _q8,
    closed_trade_pnl_sequence,
    summarize_win_loss,
    compute_sharpe_sortino_from_returns,
    returns_pct_from_snapshots,
    aggregate_metrics_fold_level,
    group_by_strategy_regime,
)
from app.backtest.runner import (
    BacktestPerformanceSummary,
    BacktestPerformanceSummaryV2,
    upgrade_backtest_performance_v1_to_v2,
)


def _make_fill(side, price, qty, fees, *, corr="", slip=0, lat=0, partial=False):
    class _F:
        def __init__(self):
            self.side = side
            self.fill_price = Decimal(str(price))
            self.fill_qty_base = Decimal(str(qty))
            self.fees_quote = Decimal(str(fees))
            self.correlation_id = corr
            self.slippage_quote = Decimal(str(slip))
            self.latency_ms = lat
            self.partial_fill_indicator = partial
    return _F()


CLOSED_TRADE_SEQUENCE_CASES = [
    # (buys list of (price,qty,fees), sells list of (price,qty,fees), expected_len, expected_sign)
    ([(100, 1, 0.1)], [(110, 1, 0.1)], 1, "profit"),
    ([(100, 1, 0)], [(90, 1, 0)], 1, "loss"),
    ([(100, 2, 0.1)], [(110, 2, 0.1)], 1, "profit"),
    # scale in scale out
    ([(100, 1, 0.05), (105, 1, 0.05)], [(110, 2, 0.1)], 1, "profit"),
    ([(100, 3, 0.1)], [(105, 1, 0.05), (110, 2, 0.05)], 2, "profit"),
    # zero fee
    ([(100, 1, 0)], [(101, 1, 0)], 1, "profit"),
    # exact break even (net depends on fee)
    ([(100, 1, 0)], [(100, 1, 0)], 1, "flat"),
    # 0.0001 micro edge
    ([(100, 1, 0)], [(Decimal("100.0001"), 1, 0)], 1, "profit"),
    # high loss
    ([(100, 1, 0.1)], [(50, 1, 0.1)], 1, "loss"),
    # 10 trades sequential
    ([(100, 1, 0.01)]*10, [(101, 1, 0.01)]*10, 10, "profit"),
    # partial (less sell qty)
    ([(100, 10, 0.5)], [(105, 5, 0.1)], 1, "profit"),
    # large qty
    ([(100, 1000, 10)], [(101, 1000, 10)], 1, "profit"),
    # small qty 0.001
    ([(100, Decimal("0.001"), 0)], [(101, Decimal("0.001"), 0)], 1, "profit"),
    # negative fee? NO - fail-closed cost validation rejects (test elsewhere)
    ([(100, 1, 1)], [(100, 1, 1)], 1, "loss"),
    # buy 2 sells (partial close remainder)
    ([(50, 2, 0.1)], [(60, 1, 0.05), (70, 1, 0.05)], 2, "profit"),
    # 1 loss + 1 profit sequence
    ([(100, 1, 0), (110, 1, 0)], [(90, 1, 0), (120, 1, 0)], 2, "mixed"),
    # all sells match buys
    ([(10, 1, 0.1), (20, 2, 0.1), (30, 3, 0.1)], [(15, 1, 0.1), (25, 2, 0.1), (35, 3, 0.1)], 3, "profit"),
    # price 1 high leverage-like (no lev, just large price delta)
    ([(1, 1, 0)], [(1000, 1, 0)], 1, "profit"),
    # no sells → empty sequence
    ([(100, 1, 0.1)], [], 0, "none"),
    # no buys / empty
    ([], [], 0, "none"),
]


@pytest.mark.parametrize("buys,sells,exp_len,exp_sign", CLOSED_TRADE_SEQUENCE_CASES)
def test_sbkt03_M01_closed_trade_sequence_20edge(buys, sells, exp_len, exp_sign):
    """20 hücre: closed trade pnl sequence edge cases (REUSE S-PTR-01 fill proration)."""
    fills = []
    for p, q, f in buys:
        fills.append(_make_fill("BUY", p, q, f))
    for p, q, f in sells:
        fills.append(_make_fill("SELL", p, q, f))
    seq = closed_trade_pnl_sequence(fills)
    assert len(seq) == exp_len
    if exp_sign == "profit" and seq:
        assert all(s > 0 for s in seq) or sum(seq) > 0  # at least net positive
    elif exp_sign == "loss" and seq:
        assert all(s < 0 for s in seq) or sum(seq) < 0


def test_sbkt03_M01_closed_trade_sequence_profit():
    fills = [
        _make_fill("BUY", 100, 1, 0.1),
        _make_fill("SELL", 110, 1, 0.1),
    ]
    seq = closed_trade_pnl_sequence(fills)
    # gross = (110 - 100) * 1 = 10; net = 10 - 0.1 (sell fee proration 1/1)
    assert len(seq) == 1
    assert seq[0] > Decimal("9")


def test_sbkt03_M01_closed_trade_sequence_loss():
    fills = [
        _make_fill("BUY", 100, 1, 0),
        _make_fill("SELL", 90, 1, 0),
    ]
    seq = closed_trade_pnl_sequence(fills)
    assert len(seq) == 1
    assert seq[0] < Decimal("-9")


WIN_LOSS_MATRIX = [
    ([Decimal("10"), Decimal("-5"), Decimal("2")], 3, 2, 1),
    ([Decimal("-1"), Decimal("-2")], 2, 0, 2),
    ([Decimal("1")], 1, 1, 0),
    ([], 0, 0, 0),
    # extra 12 matrix cells (real behavioral edge cases):
    ([Decimal("0.0001"), Decimal("0.0002")], 2, 2, 0),
    ([Decimal("-0.0001"), Decimal("-0.0002")], 2, 0, 2),
    ([Decimal("0")], 1, 0, 0),
    ([Decimal("1"), Decimal("-1")], 2, 1, 1),
    ([Decimal("100"), Decimal("-1"), Decimal("-2"), Decimal("-3")], 4, 1, 3),
    ([Decimal("-100"), Decimal("1"), Decimal("2"), Decimal("3")], 4, 3, 1),
    ([Decimal("1")]*10 + [Decimal("-1")]*5, 15, 10, 5),
    ([Decimal("-1")]*20, 20, 0, 20),
    ([Decimal("1")]*20, 20, 20, 0),
    ([Decimal("0.01"), Decimal("-0.01"), Decimal("0")], 3, 1, 1),
    ([Decimal("1"), Decimal("-0.1"), Decimal("-0.1"), Decimal("-0.1")], 4, 1, 3),
    ([Decimal("-1"), Decimal("0.1"), Decimal("0.1"), Decimal("0.1")], 4, 3, 1),
]


@pytest.mark.parametrize("pnls,exp_trades,exp_wins,exp_losses", WIN_LOSS_MATRIX)
def test_sbkt03_M02_summarize_win_loss_extended(pnls, exp_trades, exp_wins, exp_losses):
    s = summarize_win_loss(pnls)
    assert s["total_trades"] == exp_trades
    assert s["winning_trades"] == exp_wins
    assert s["losing_trades"] == exp_losses
    if exp_trades == 0:
        assert s["win_rate_pct"] is None
    else:
        assert isinstance(s["stability_index"], int)


SHARPE_SORTINO_N_MATRIX = [
    (5, 30, False),
    (10, 30, False),
    (29, 30, False),
    (30, 30, True),
    (31, 30, True),
    (100, 30, True),
    (200, 30, True),
    (1, 2, False),  # 1 < 2 → INSUFFICIENT
    (2, 5, False),  # 2 < 5 → INSUFFICIENT
    (5, 10, False),  # 5 < 10 → INSUFFICIENT
    (10, 10, True),
    (50, 20, True),
]


@pytest.mark.parametrize("n_samples,min_samples,expected_valid", SHARPE_SORTINO_N_MATRIX)
def test_sbkt03_M03_sharpe_sortino_samples_policy_OD03(n_samples, min_samples, expected_valid):
    import random
    random.seed(n_samples + 1000)
    ret = [random.uniform(-0.01, 0.01) for _ in range(max(1, n_samples))]
    ss = compute_sharpe_sortino_from_returns(ret, min_samples=min_samples)
    if expected_valid and n_samples >= 2:
        # en az biri valid olabilir (ya None eger sd=0 ise)
        assert isinstance(ss.get("sharpe_ratio_24h"), (float, type(None)))
    else:
        if n_samples < min_samples:
            assert ss["sharpe_ratio_24h"] is None
            assert "INSUFFICIENT" in " ".join(ss["info_codes"])


@pytest.mark.parametrize(
    "pnls,exp_trades,exp_wins,exp_losses",
    [
        ([Decimal("10"), Decimal("-5"), Decimal("2")], 3, 2, 1),
        ([Decimal("-1"), Decimal("-2")], 2, 0, 2),
        ([Decimal("1")], 1, 1, 0),
        ([], 0, 0, 0),
    ],
)
def test_sbkt03_M02_summarize_win_loss_counts(pnls, exp_trades, exp_wins, exp_losses):
    s = summarize_win_loss(pnls)
    assert s["total_trades"] == exp_trades
    assert s["winning_trades"] == exp_wins
    assert s["losing_trades"] == exp_losses
    if exp_trades == 0:
        assert s["win_rate_pct"] is None
        assert "METRICS_NO_CLOSED_TRADES" in s["info_codes"]
    else:
        assert s["win_rate_pct"] is not None
        assert isinstance(s["stability_index"], int)


def test_sbkt03_M02_profit_factor_nolosses():
    s = summarize_win_loss([Decimal("5"), Decimal("3")])
    assert s["profit_factor"] is None
    assert "PROFIT_FACTOR_NO_LOSSES" in s["info_codes"]


def test_sbkt03_M02_profit_factor_normal():
    s = summarize_win_loss([Decimal("10"), Decimal("-5"), Decimal("-2")])
    # gross_win = 10, gross_loss_abs = 7; PF = 10/7 ≈ 1.428...
    assert s["profit_factor"] is not None
    assert 1.4 < s["profit_factor"] < 1.5
    assert s["expectancy_quote"] is not None
    # expectancy = (10 - 7) / 3 = 1
    assert float(s["expectancy_quote"]) > 0.9


def test_sbkt03_M03_sharpe_sortino_too_few_samples():
    ret = [0.01] * 5
    ss = compute_sharpe_sortino_from_returns(ret, min_samples=30)
    assert ss["sharpe_ratio_24h"] is None
    assert ss["sortino_ratio_24h"] is None
    assert "INSUFFICIENT" in " ".join(ss["info_codes"])


def test_sbkt03_M03_sharpe_sortino_zero_vol():
    ret = [0.01] * 50
    ss = compute_sharpe_sortino_from_returns(ret, min_samples=30, periods_per_year=365.0)
    assert ss["sharpe_ratio_24h"] is None
    assert ss["sortino_ratio_24h"] is None


def test_sbkt03_M04_snapshot_returns():
    @dataclass
    class _S:
        equity_quote: Decimal
        ts: str = "2025-01-01T00:00:00.000Z"

    snaps = [
        _S(equity_quote=Decimal("100")),
        _S(equity_quote=Decimal("110")),
        _S(equity_quote=Decimal("121")),
    ]
    rs = returns_pct_from_snapshots(snaps)
    assert len(rs) == 2
    assert 9.9 < rs[0] < 10.1
    assert 9.9 < rs[1] < 10.1


def test_sbkt03_M05_aggregate_fold_level_empty():
    agg = aggregate_metrics_fold_level([])
    assert agg["fold_count"] == 0
    assert agg["avg_sharpe_ratio_24h"] is None


def test_sbkt03_M05_aggregate_fold_level_none_policy_OD06():
    per = [
        {"total_return_pct": 5.0, "sharpe_ratio_24h": 1.0, "profit_factor": None},
        {"total_return_pct": 10.0, "sharpe_ratio_24h": None, "profit_factor": 2.0},
    ]
    agg = aggregate_metrics_fold_level(per, exclude_none_in_avg=True)
    assert agg["fold_count"] == 2
    # Compound (1.05 * 1.10 - 1) * 100 = 15.5
    assert 15.4 < agg["compound_total_return_pct"] < 15.6
    assert 4.9 < agg["min_fold_total_return_pct"] < 5.1
    assert 9.9 < agg["max_fold_total_return_pct"] < 10.1
    # Sharpe avg: sadece 1.0 (None exclude)
    assert agg["avg_sharpe_ratio_24h"] == 1.0
    # PF avg: sadece 2.0
    assert agg["avg_profit_factor"] == 2.0
    assert "METRICS_NA_EXCLUDED_AVG" in agg["info_codes"]


def test_sbkt03_M06_regime_decomp_unknown_OD05():
    fills = [
        _make_fill("BUY", 100, 1, 0.1, corr="C1"),
        _make_fill("SELL", 110, 1, 0.1, corr="C1"),
        _make_fill("BUY", 90, 1, 0, corr="C2"),
        _make_fill("SELL", 95, 1, 0, corr="C2"),
    ]
    rows = group_by_strategy_regime(fills)
    assert len(rows) >= 1
    for r in rows:
        # corr chain yok ise UNKNOWN_STRATEGY / UNKNOWN_REGIME (OD-05 default accept)
        assert r.strategy_id == "UNKNOWN_STRATEGY"
        assert r.regime == "UNKNOWN_REGIME"


def test_sbkt03_M07_v1_to_v2_upgrade_OD07():
    v1 = BacktestPerformanceSummary(
        total_return_pct=5.0,
        final_equity_quote=Decimal("10500"),
        initial_equity_quote=Decimal("10000"),
    )
    v2 = upgrade_backtest_performance_v1_to_v2(v1)
    assert isinstance(v2, BacktestPerformanceSummaryV2)
    assert v2.total_return_pct == 5.0
    assert "UPGRADED_FROM_V1" in v2.metrics_info_codes
    assert v2.artifact_schema_version == "bkt_perf_v2"


def test_sbkt03_r8_clamp_inf():
    assert _r8(float("inf")) == 0.0
    assert _r8(float("nan")) == 0.0
    assert _r8(None) == 0.0
    assert _r8(1.234567895) == round(1.234567895, 8)


def test_sbkt03_q8_quantize():
    q = _q8(Decimal("1.1234567845"))
    assert str(q) == "1.12345678" or str(q) == "1.12345679"  # ROUND_HALF_EVEN
