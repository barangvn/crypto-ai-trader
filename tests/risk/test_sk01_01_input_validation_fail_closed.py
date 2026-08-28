"""T01 — Input validation + fail-closed + exception injection (AD-19).

Total parametrize: 19 × matrix + 7 exception injection + 2 extra = 37 tests.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.contracts.opportunity import OpportunityScore
from app.contracts.risk import RiskDecisionResult
from app.risk import IndependentRiskEngine, RiskContext, evaluate_risk


def _bypass_opp_post_init(opp: OpportunityScore, **overrides: Any) -> OpportunityScore:
    """Construct OpportunityScore bypassing __post_init__ validation — allows
    creating intentionally malformed instances to test Risk Engine's
    outer fail-closed catch even when upstream validation is somehow bypassed."""
    raw = object.__new__(OpportunityScore)
    for fld in opp.__dataclass_fields__:
        object.__setattr__(raw, fld, getattr(opp, fld))
    for k, v in overrides.items():
        object.__setattr__(raw, k, v)
    return raw


def _bypass_opp_del_attr(opp: OpportunityScore, attr: str) -> OpportunityScore:
    """OpportunityScore with one attribute deleted → triggers AttributeError inside engine."""
    from dataclasses import fields as _flds
    raw = object.__new__(OpportunityScore)
    for f in _flds(type(opp)):
        if f.name != attr:
            object.__setattr__(raw, f.name, getattr(opp, f.name))
    return raw


def _bypass_any_del_attr(obj, attr: str):
    """Any dataclass with one attribute deleted → AttributeError inside engine."""
    from dataclasses import fields as _flds
    raw = object.__new__(type(obj))
    for f in _flds(type(obj)):
        if f.name != attr:
            object.__setattr__(raw, f.name, getattr(obj, f.name))
    return raw


# 19 fail-closed scenarios (each rejected)
FAIL_CLOSED_CASES = [
    ("malformed_opp_None",          lambda o,s,r,pv,l,c: (None, s, r, pv, l, c),  ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_opp_wrong_type",    lambda o,s,r,pv,l,c: (object(), s, r, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_signal_None",       lambda o,s,r,pv,l,c: (o, None, r, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_regime_wrong",      lambda o,s,r,pv,l,c: (o, s, object(), pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_limits_None",       lambda o,s,r,pv,l,c: (o, s, r, pv, None, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_ctx_None",          lambda o,s,r,pv,l,c: (o, s, r, pv, l, None), ["INTERNAL_CALCULATION_ERROR"]),
    ("invalid_score_oor_hi",        lambda o,s,r,pv,l,c: (_bypass_opp_post_init(o, score_total=1.5), s, r, pv, l, c), ["OPPORTUNITY_INVALID"]),
    ("invalid_score_oor_lo",        lambda o,s,r,pv,l,c: (_bypass_opp_post_init(o, score_total=-0.1), s, r, pv, l, c), ["OPPORTUNITY_INVALID"]),
    ("score_not_actionable",        lambda o,s,r,pv,l,c: (replace(o, actionable=False), s, r, pv, l, c), ["OPPORTUNITY_NOT_ACTIONABLE"]),
    ("score_expected_edge_missing", lambda o,s,r,pv,l,c: (_bypass_opp_post_init(o, expected_edge_bps=None), s, r, pv, l, c), ["OPPORTUNITY_EXPECTED_EDGE_MISSING"]),
    ("portf_view_missing",          lambda o,s,r,pv,l,c: (o, s, r, None, l, c),   ["PORTFOLIO_VIEW_MISSING"]),
    ("net_edge_non_positive",       lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=-5.0), s, r, pv, l, c), ["EXPECTED_NET_EDGE_NON_POSITIVE"]),
    ("net_edge_zero",               lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=0.0), s, r, pv, l, c), ["EXPECTED_NET_EDGE_NON_POSITIVE"]),
    ("malformed_signal_raw",        lambda o,s,r,pv,l,c: (o, object(), r, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("malformed_regime_none",       lambda o,s,r,pv,l,c: (o, s, None, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("opp_no_score_id_attr",        lambda o,s,r,pv,l,c: (_bypass_opp_del_attr(o, "score_id"), s, r, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("sig_no_strategy_id_attr",     lambda o,s,r,pv,l,c: (o, _bypass_any_del_attr(s, "strategy_id"), r, pv, l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("pv_no_ts_attr",               lambda o,s,r,pv,l,c: (o, s, r, _bypass_any_del_attr(pv, "ts"), l, c), ["INTERNAL_CALCULATION_ERROR"]),
    ("lim_no_max_pos_attr",         lambda o,s,r,pv,l,c: (o, s, r, pv, _bypass_any_del_attr(l, "max_position_notional_per_symbol"), c), ["INTERNAL_CALCULATION_ERROR"]),
]


@pytest.mark.parametrize("name,mutator,expected_subset", FAIL_CLOSED_CASES)
def test_t01_fail_closed_matrix(name, mutator, expected_subset, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = mutator(*happy_path_tuple)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.REJECTED, name
    assert rd.position_sizing.notional == Decimal("0"), name
    for rc in expected_subset:
        assert rc in rd.reason_codes, (name, rc, rd.reason_codes)


# 5 different exception injections via patched attributes
EXCEPTION_ATTR_INJECTION = [
    ("opp_to_sorted_dict_type_error", "to_sorted_dict"),  # opp_score.score_total attribute -> inject via opp_score attribute
    ("score_components_keyerr", "score_components"),
]

@pytest.mark.parametrize("exc_name", ["AttributeError", "TypeError", "ValueError", "KeyError", "ZeroDivisionError", "IndexError", "OverflowError"])
def test_t01_exception_injections_fail_closed(exc_name, happy_path_tuple):
    """Monkey patch a helper used only within inner -> ensure outer catch fails closed."""
    class BoomEngine(IndependentRiskEngine):
        def _evaluate_inner(self, *a, **k):
            # Raise different exception types
            if exc_name == "AttributeError":
                class X: pass
                X().missing_attr_xyz
            elif exc_name == "TypeError":
                None + 5  # type: ignore[operator]
            elif exc_name == "ValueError":
                raise ValueError("boom")
            elif exc_name == "KeyError":
                {}["missing_key_xyz"]
            elif exc_name == "ZeroDivisionError":
                1/0
            elif exc_name == "IndexError":
                [][999]
            elif exc_name == "OverflowError":
                raise OverflowError("math range")
            else:
                raise RuntimeError("nope")

    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = BoomEngine().evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.REJECTED, exc_name
    assert "INTERNAL_CALCULATION_ERROR" in rd.reason_codes, exc_name
    assert rd.position_sizing.notional == Decimal("0"), exc_name


def test_t01_pure_shortcut_ok(happy_path_tuple, clean_ctx):
    """evaluate_risk shortcut: approved clean happy path."""
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = evaluate_risk(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.APPROVED
    assert rd.position_sizing.notional > Decimal("0")


def test_t01_base_exception_is_fail_closed(happy_path_tuple):
    """Unusual Exception subclass also caught by outer fail-closed."""
    class BoomEngine(IndependentRiskEngine):
        def _evaluate_inner(self, *a, **k):
            raise RuntimeError("unexpected generic runtime boom")

    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = BoomEngine().evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.REJECTED
    assert "INTERNAL_CALCULATION_ERROR" in rd.reason_codes
    assert rd.position_sizing.notional == Decimal("0")


def test_t01_approved_notional_gt_zero_contract(happy_path_tuple):
    """AD-11 RiskDecision contract: approved must have notional > 0."""
    from app.contracts.exceptions import ContractSchemaError
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = evaluate_risk(opp, sig, reg, pv, lim, ctx)
    assert rd.decision == RiskDecisionResult.APPROVED
    assert rd.position_sizing.notional > Decimal("0")
    # try to mutate approved->0 via replace → should trigger contract __post_init__
    from dataclasses import replace as _r
    from app.contracts.risk import RiskDecision
    bad_sz = _r(rd.position_sizing, notional=Decimal("0"))
    raised = False
    try:
        _r(rd, position_sizing=bad_sz)
    except ContractSchemaError:
        raised = True
    assert raised, "APPROVED with notional=0 must raise ContractSchemaError"
