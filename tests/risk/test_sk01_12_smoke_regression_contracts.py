"""T12 — Smoke & regression: import risk.py contracts, unchanged pyproject, smoke evaluate = 5 tests."""
from __future__ import annotations

import pathlib

import pytest


def test_t12_import_contracts_risk_unchanged():
    """S-CON-02B contract imports still work (no signature changes)."""
    from app.contracts.risk import (
        KillSwitchStateSpec,
        LimitsSnapshot,
        PositionSizingSpec,
        RiskDecision,
        RiskDecisionResult,
    )
    assert "approved" in set(v.value for v in RiskDecisionResult)
    assert "rejected" in set(v.value for v in RiskDecisionResult)
    # Enum member names UPPERCASE (contract guarantee)
    assert "APPROVED" in set(v.name for v in RiskDecisionResult)
    assert "REJECTED" in set(v.name for v in RiskDecisionResult)


def test_t12_smoke_evaluate_risk_call(happy_path_tuple):
    from app.risk import evaluate_risk
    from app.contracts.risk import RiskDecisionResult
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = evaluate_risk(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.APPROVED, rd.reason_codes
    assert rd.position_sizing.notional > 0


def test_t12_risk_decision_enum_2_values_only():
    """AD-11: only approved + rejected values — no third state."""
    from app.contracts.risk import RiskDecisionResult
    vals = [e.value for e in RiskDecisionResult]
    assert sorted(vals) == ["approved", "rejected"]


def test_t12_pyproject_unchanged_deps():
    txt = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = []' in txt or '"dependencies" = []' in txt


def test_t12_approved_has_valid_until(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    # valid_until must be ISO8601 Z instant
    assert rd.valid_until.endswith("Z")
    # valid_until > ctx.as_of
    assert rd.valid_until >= (ctx.as_of or opp.created_ts)
