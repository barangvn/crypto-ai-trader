from decimal import Decimal

import pytest

from app.contracts.model import CCWinnerEnum
from app.gate import (
    PromotionGate,
)
from tests.gate.conftest import (
    DEFAULT_EVAL_TS,
    DEFAULT_WINDOW_END,
    DummyCompareResult,
    _make_metric_deltas,
    _make_model_eval,
    _make_payload,
    _base_metrics_template,
)


def _make_candidate_fixture(kind: str):
    champion = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.6, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True, stability=0.78, fees_per_trade=0.0002,
    )
    if kind == "strictly_better":
        challenger = _base_metrics_template(
            return_pct=Decimal("0.25"), max_drawdown_pct=0.04, sharpe_ratio=3.0,
            sortino_ratio=4.0, profit_factor=2.5, total_fees_quote=Decimal("100"),
            avg_slippage_bps=1.0, trade_count=400, regime_coverage_count=9,
            window_days=365, oos_flag=True, stability=0.95, fees_per_trade=0.00005,
        )
        winner_hint = CCWinnerEnum.CHALLENGER_PROMOTED
    elif kind == "tie":
        challenger = dict(champion)
        winner_hint = CCWinnerEnum.INCONCLUSIVE_RERUN
    elif kind == "bad":
        challenger = _base_metrics_template(
            return_pct=Decimal("-0.02"), max_drawdown_pct=0.30, sharpe_ratio=-0.1,
            sortino_ratio=0.0, profit_factor=0.7, total_fees_quote=Decimal("500"),
            avg_slippage_bps=40.0, trade_count=10, regime_coverage_count=1,
            window_days=60, oos_flag=False,
        )
        winner_hint = CCWinnerEnum.CHAMPION_KEEPS
    else:
        raise ValueError(kind)
    deltas = _make_metric_deltas(champion, challenger)
    payload = _make_payload(winner_hint, True, challenger, DEFAULT_EVAL_TS)
    return champion, challenger, DummyCompareResult(
        payload=payload, comparable=True,
        metric_deltas=deltas, champion_eval=_make_model_eval(champion),
    )


FIXTURE_KINDS = ["strictly_better", "tie", "bad"]


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_weighted_total(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    scores = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        scores.append(res["weighted_total"])
    assert len(set(scores)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_reasons(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    reason_sets = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        reason_sets.append(tuple(res["reasons"]))
    assert len(set(reason_sets)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_passed(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    passed = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        passed.append(res["passed"])
    assert len(set(passed)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_sha256(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    shas = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        shas.append(res["schema_sha256"])
    assert len(set(shas)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_final_winner(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    winners = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        winners.append(res["final_winner"])
    assert len(set(winners)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_thresholds_version(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    versions = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        versions.append(res["thresholds_used_version"])
    assert len(set(versions)) == 1


@pytest.mark.parametrize("kind", FIXTURE_KINDS)
def test_determinism_10x_gate_tuple(kind):
    _, _, cr = _make_candidate_fixture(kind)
    gate = PromotionGate()
    tuples = []
    for _ in range(10):
        res = gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
        g = res["gate"]
        tuples.append((g["passed"], tuple(g["reasons"]), g["thresholds_used_version"]))
    assert len(set(tuples)) == 1
