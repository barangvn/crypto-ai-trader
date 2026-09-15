from decimal import Decimal

import pytest

from app.contracts.model import (
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    PromotionGateResult,
)
from app.gate import (
    GateInvariantError,
    PromotionGate,
    enforce_winner_gate_invariant,
    inject_gate_into_champion_challenger,
)
from tests.gate.conftest import (
    DEFAULT_EVAL_TS,
    DEFAULT_WINDOW_END,
    _make_payload,
    _base_metrics_template,
)


def test_inject_gate_result_type_champion_keeps():
    cm = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.6, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )
    payload = _make_payload(CCWinnerEnum.CHAMPION_KEEPS, True, cm)
    gate = PromotionGateResult(passed=False, reasons=["HARD_RETURN_NOT_POSITIVE"],
        thresholds_used_version="t-v/w-v")
    out = inject_gate_into_champion_challenger(
        payload, gate, CCWinnerEnum.CHAMPION_KEEPS, ["a1"]
    )
    assert isinstance(out, ChampionChallengerEvaluation)
    assert out.winner is CCWinnerEnum.CHAMPION_KEEPS
    assert out.promotion_gate_result.passed is False
    assert out.approval_refs == ["a1"]


def test_inject_gate_result_challenger_promoted():
    cm = _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=2.0,
        sortino_ratio=2.8, profit_factor=1.8, total_fees_quote=Decimal("150"),
        avg_slippage_bps=3.0, trade_count=300, regime_coverage_count=8,
        window_days=365, oos_flag=True,
    )
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, cm)
    gate = PromotionGateResult(passed=True, reasons=[], thresholds_used_version="tv/wv")
    out = inject_gate_into_champion_challenger(
        payload, gate, CCWinnerEnum.CHALLENGER_PROMOTED, ["a1", "a2"]
    )
    assert isinstance(out, ChampionChallengerEvaluation)
    assert out.winner is CCWinnerEnum.CHALLENGER_PROMOTED
    assert out.promotion_gate_result.passed is True
    assert sorted(out.approval_refs) == ["a1", "a2"]
    assert out.evaluation_period_days == 365


def test_inject_gate_enforces_invariant_on_winner_vs_gate_pass():
    cm = _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=2.0,
        sortino_ratio=2.8, profit_factor=1.8, total_fees_quote=Decimal("150"),
        avg_slippage_bps=3.0, trade_count=300, regime_coverage_count=8,
        window_days=365, oos_flag=True,
    )
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, cm)
    gate_failed = PromotionGateResult(passed=False, reasons=["EVAL_STALE"],
        thresholds_used_version="tv/wv")
    with pytest.raises(GateInvariantError):
        enforce_winner_gate_invariant(CCWinnerEnum.CHALLENGER_PROMOTED, gate_failed)


def test_inject_gate_payload_evidence_refs_carried():
    cm = _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=2.0,
        sortino_ratio=2.8, profit_factor=1.8, total_fees_quote=Decimal("150"),
        avg_slippage_bps=3.0, trade_count=300, regime_coverage_count=8,
        window_days=365, oos_flag=True,
    )
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, cm, evidence_refs=["e1", "e2"])
    gate = PromotionGateResult(passed=True, reasons=[], thresholds_used_version="tv/wv")
    out = inject_gate_into_champion_challenger(
        payload, gate, CCWinnerEnum.CHALLENGER_PROMOTED, ["a1"]
    )
    assert out.champion_ref.model_id == "champ_m01"
    assert out.challenger_ref.model_id == "chllngr_m01"
    assert out.champion_ref.version == "1"
    assert out.challenger_ref.version == "1"


def test_evaluate_returns_cce_contract_when_payload_present():
    from tests.gate.conftest import DummyCompareResult, _make_metric_deltas, _make_model_eval
    champion = _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.6, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )
    challenger = _base_metrics_template(
        return_pct=Decimal("0.25"), max_drawdown_pct=0.04, sharpe_ratio=3.0,
        sortino_ratio=4.0, profit_factor=2.5, total_fees_quote=Decimal("100"),
        avg_slippage_bps=1.0, trade_count=400, regime_coverage_count=9,
        window_days=365, oos_flag=True, stability=0.95, fees_per_trade=0.00005,
    )
    deltas = _make_metric_deltas(champion, challenger)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger, DEFAULT_EVAL_TS)
    cr = DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=deltas,
        champion_eval=_make_model_eval(champion),
    )
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert result["passed"] is True
    assert result["final_winner"] == "challenger_promoted"
    assert "cce_contract" in result
    contract = result["cce_contract"]
    assert isinstance(contract, ChampionChallengerEvaluation)
    assert contract.winner is CCWinnerEnum.CHALLENGER_PROMOTED
    assert contract.promotion_gate_result.passed is True
