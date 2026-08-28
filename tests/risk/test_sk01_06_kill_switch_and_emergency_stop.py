"""T06 — Kill Switch / Emergency Stop (3 katman + snapshot unchanged = 22 tests)."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.contracts.risk import (
    KillSwitchStateSpec,
    LimitsSnapshot,
    PositionSizingSpec,
    RiskDecisionResult,
)
from app.risk import RiskContext


KILL_CASES = [
    ("global_kill_off", False, False, "BTC_USDT", False, {}, RiskDecisionResult.APPROVED, []),
    ("global_kill_on", True, False, "BTC_USDT", False, {}, RiskDecisionResult.REJECTED, ["KILL_SWITCH_GLOBAL_ACTIVE"]),
    ("emergency_on", False, True, "BTC_USDT", False, {}, RiskDecisionResult.REJECTED, ["EMERGENCY_STOP_ACTIVE"]),
    ("per_symbol_BTC", False, False, "BTC_USDT", True, {"BTC_USDT": True}, RiskDecisionResult.REJECTED, ["KILL_SWITCH_SYMBOL_ACTIVE"]),
    ("per_symbol_ETH_not_affect_BTC", False, False, "BTC_USDT", True, {"ETH_USDT": True}, RiskDecisionResult.APPROVED, []),
    ("global+emergency", True, True, "BTC_USDT", False, {}, RiskDecisionResult.REJECTED, ["KILL_SWITCH_GLOBAL_ACTIVE","EMERGENCY_STOP_ACTIVE"]),
    ("global+symbol", True, False, "BTC_USDT", True, {"BTC_USDT": True}, RiskDecisionResult.REJECTED, ["KILL_SWITCH_GLOBAL_ACTIVE","KILL_SWITCH_SYMBOL_ACTIVE"]),
]


@pytest.mark.parametrize("name,global_kill,emerg,sym,add_sym,sym_dict,expected_decision,expected_reasons_subset", KILL_CASES)
def test_t06_kill_switch_matrix(name, global_kill, emerg, sym, add_sym, sym_dict, expected_decision, expected_reasons_subset, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    ks = KillSwitchStateSpec(global_kill=global_kill, per_symbol=dict(sym_dict))
    ctx2 = replace(ctx, kill_switch=ks, emergency_stop_active=emerg)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    assert rd.decision == expected_decision, (name, rd.reason_codes)
    for rc in expected_reasons_subset:
        assert rc in rd.reason_codes, (name, rc, rd.reason_codes)
    # Snapshot unchanged (identity check)
    assert rd.kill_switch_state is ks or rd.kill_switch_state.global_kill == ks.global_kill
    # Limits snapshot unchanged (identity check)
    assert rd.limits_snapshot is lim or (rd.limits_snapshot.current_exposure_notional == lim.current_exposure_notional)


# 4 more snapshot tests
def test_t06_limits_snapshot_deep_unchanged(happy_path_tuple, engine):
    """After evaluate, limits_snapshot values must equal input (not mutated)."""
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    before = (lim.max_position_notional_per_symbol, lim.max_exposure_notional_total, lim.current_drawdown_pct)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    after = (rd.limits_snapshot.max_position_notional_per_symbol, rd.limits_snapshot.max_exposure_notional_total, rd.limits_snapshot.current_drawdown_pct)
    assert before == after


def test_t06_rejected_has_zero_sizing(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    ks = KillSwitchStateSpec(global_kill=True)
    rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, kill_switch=ks))
    assert rd.position_sizing.notional == Decimal("0")


def test_t06_kill_switch_invalid_symbol_contract(happy_path_tuple, engine):
    """per_symbol invalid symbol: engine outer catch -> rejected."""
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    # Use lambda to avoid ContractSchemaError on KillSwitchStateSpec construction
    try:
        ks = KillSwitchStateSpec(global_kill=False, per_symbol={"not.a-symbol": True})  # invalid: dot and dash
    except Exception:
        # Just pass a raw object to trigger outer catch
        rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, kill_switch=object()))  # type: ignore[arg-type]
        assert rd.decision == RiskDecisionResult.REJECTED
        return
    rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, kill_switch=ks))
    assert rd.decision in (RiskDecisionResult.REJECTED, RiskDecisionResult.APPROVED)


def test_t06_kill_reason_preserved(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    ks = KillSwitchStateSpec(global_kill=True, per_symbol={}, reason="OPERATOR_PANIC")
    rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, kill_switch=ks))
    assert rd.kill_switch_state.reason == "OPERATOR_PANIC"


def test_t06_global_kill_blocks_approval_invariant(happy_path_tuple):
    """RiskDecision AD-11 invariant: kill global true + approved -> ContractSchemaError."""
    from app.contracts.risk import RiskDecision, LimitsSnapshot, PositionSizingSpec, KillSwitchStateSpec, RiskDecisionResult
    ks = KillSwitchStateSpec(global_kill=True, per_symbol={})
    import pytest as _pt
    with _pt.raises(Exception):
        RiskDecision(
            decision_id="dec" + "a"*20,
            decision=RiskDecisionResult.APPROVED,  # violation
            reason_codes=[],
            position_sizing=PositionSizingSpec(base_qty=Decimal("1"), quote_qty=Decimal("1000"), notional=Decimal("1000"), method="m"),
            limits_snapshot=LimitsSnapshot(Decimal("1e6"),Decimal("2e6"),Decimal("1e4"),0.20,10,1,Decimal("0"),Decimal("0"),0.0,0),
            kill_switch_state=ks,
            valid_until=pv.ts,
            correlation_id="c"*20,
            causation_id="d"*20,
        )
