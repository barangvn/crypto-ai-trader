from decimal import Decimal

import pytest

from app.contracts.model import (
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    PromotionGateResult,
)
from app.gate import (
    GateInvariantError,
    build_promotion_gate_result,
    default_thresholds_v1,
    enforce_winner_gate_invariant,
    inject_gate_into_champion_challenger,
)
from tests.gate.conftest import _make_payload


def test_enforce_invariant_challenger_with_gate_pass_ok():
    gate = PromotionGateResult(
        passed=True,
        reasons=[],
        thresholds_used_version="t/w",
    )
    enforce_winner_gate_invariant(CCWinnerEnum.CHALLENGER_PROMOTED, gate)


def test_enforce_invariant_challenger_without_gate_pass_raises():
    gate = PromotionGateResult(
        passed=False, reasons=["HARD_RETURN_NOT_POSITIVE"],
        thresholds_used_version="t/w",
    )
    with pytest.raises(GateInvariantError):
        enforce_winner_gate_invariant(CCWinnerEnum.CHALLENGER_PROMOTED, gate)


def test_enforce_invariant_champion_keeps_with_gate_pass_raises():
    gate = PromotionGateResult(passed=True, reasons=[], thresholds_used_version="t/w")
    with pytest.raises(GateInvariantError):
        enforce_winner_gate_invariant(CCWinnerEnum.CHAMPION_KEEPS, gate)


def test_enforce_invariant_champion_keeps_gate_fail_ok():
    gate = PromotionGateResult(
        passed=False, reasons=["EVAL_STALE"],
        thresholds_used_version="t/w",
    )
    enforce_winner_gate_invariant(CCWinnerEnum.CHAMPION_KEEPS, gate)


def test_enforce_invariant_rerun_gate_fail_ok():
    gate = PromotionGateResult(passed=False, reasons=["WINNER_HINT_INCONCLUSIVE_RERUN"], thresholds_used_version="t/w")
    enforce_winner_gate_invariant(CCWinnerEnum.INCONCLUSIVE_RERUN, gate)


def test_inject_gate_contract_constructor_succeeds_for_valid():
    from tests.gate.conftest import _base_metrics_template
    cm = _base_metrics_template(
        return_pct=Decimal("0.12"), max_drawdown_pct=0.08, sharpe_ratio=1.6,
        sortino_ratio=2.0, profit_factor=1.5, total_fees_quote=Decimal("200"),
        avg_slippage_bps=5.0, trade_count=100, regime_coverage_count=5,
        window_days=300, oos_flag=True,
    )
    payload = _make_payload(
        winner_hint=CCWinnerEnum.CHALLENGER_PROMOTED, comparable=True,
        challenger_metrics=cm,
    )
    gate = PromotionGateResult(passed=True, reasons=[], thresholds_used_version="t-v/w-v")
    result = inject_gate_into_champion_challenger(
        cce_payload=payload, gate=gate,
        final_winner=CCWinnerEnum.CHALLENGER_PROMOTED,
        approval_refs=["a1", "a2"],
    )
    assert isinstance(result, ChampionChallengerEvaluation)
    assert result.winner is CCWinnerEnum.CHALLENGER_PROMOTED
    assert result.promotion_gate_result.passed is True
    assert result.approval_refs == ["a1", "a2"]


def test_inject_gate_champion_keeps_failed():
    from tests.gate.conftest import _base_metrics_template
    cm = _base_metrics_template(
        return_pct=Decimal("0.12"), max_drawdown_pct=0.08, sharpe_ratio=1.6,
        sortino_ratio=2.0, profit_factor=1.5, total_fees_quote=Decimal("200"),
        avg_slippage_bps=5.0, trade_count=100, regime_coverage_count=5,
        window_days=300, oos_flag=True,
    )
    payload = _make_payload(
        winner_hint=CCWinnerEnum.CHAMPION_KEEPS, comparable=True,
        challenger_metrics=cm,
    )
    gate = PromotionGateResult(passed=False, reasons=["HARD_RETURN_NOT_POSITIVE"],
        thresholds_used_version="t-v/w-v"
    )
    result = inject_gate_into_champion_challenger(
        cce_payload=payload, gate=gate,
        final_winner=CCWinnerEnum.CHAMPION_KEEPS,
        approval_refs=[],
    )
    assert isinstance(result, ChampionChallengerEvaluation)
    assert result.winner is CCWinnerEnum.CHAMPION_KEEPS
    assert result.promotion_gate_result.passed is False
