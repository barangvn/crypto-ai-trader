"""T09 — CAP-9: Winner hint non-binding. 7 tests."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    champion_challenger_equal_metrics,
    challenger_better_metrics,
    challenger_mixed_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.contracts.model import CCWinnerEnum  # noqa: E402


def test_hint_strictly_challenger_wins(tmp_path):
    """Critical 6 all strictly better challenger → challenger_promoted."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.winner_hint == CCWinnerEnum.CHALLENGER_PROMOTED


def test_hint_mixed_inconclusive(tmp_path):
    """Mixed (some pro, some against) → inconclusive_rerun."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_mixed_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.winner_hint == CCWinnerEnum.INCONCLUSIVE_RERUN


def test_hint_equal_metrics_inconclusive(tmp_path):
    c, t = champion_challenger_equal_metrics()
    fix = make_engine_with_fixtures(tmp_path, c, t)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.winner_hint == CCWinnerEnum.INCONCLUSIVE_RERUN


def test_hint_champion_keeps(tmp_path):
    """Champion strictly better 6 critical → champion_keeps."""
    # Swap champion/challenger: build challenger metrics worse across 6 critical
    from tests.evaluation.conftest import _base_metrics_template

    worse_challenger = _base_metrics_template(
        return_pct=Decimal("0.08000000"),
        max_drawdown_pct=0.15,
        sharpe_ratio=1.0,
        sortino_ratio=1.5,
        profit_factor=1.1,
        total_fees_quote=Decimal("350.00000000"),
        avg_slippage_bps=5.0,
        trade_count=200,
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), worse_challenger)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.winner_hint == CCWinnerEnum.CHAMPION_KEEPS


def test_hint_is_non_binding_enum(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.payload.winner_hint, CCWinnerEnum)


def test_hint_one_tie_in_critical_inconclusive(tmp_path):
    """One tie among 6 critical = not strict all; tie_count>=1 → inconclusive."""
    from tests.evaluation.conftest import _base_metrics_template
    champ = champion_metrics()
    # Return same (tie) + challenger otherwise slightly better on 5 → tie_count=1 → inconclusive
    chall = _base_metrics_template(
        return_pct=champ["return_pct"],
        max_drawdown_pct=0.06,
        sharpe_ratio=1.9,
        sortino_ratio=2.5,
        profit_factor=1.6,
        total_fees_quote=Decimal("210.00000000"),
        avg_slippage_bps=2.0,
        trade_count=260,
    )
    fix = make_engine_with_fixtures(tmp_path, champ, chall)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.winner_hint == CCWinnerEnum.INCONCLUSIVE_RERUN


def test_hint_never_sets_promotion_gate_result(tmp_path):
    """OD-03: gate_result.passed NEVER set by S-MDL-02 (gate_result constructed with passed=False)."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # payload.cce_contract.promotion_gate_result.passed must be False (default)
    assert r.payload.cce_contract is not None
    # promotion_gate_result passed=False default (set in build_cce_payload: PromotionGateResult(passed=False)
    assert r.payload.cce_contract.promotion_gate_result.passed is False
