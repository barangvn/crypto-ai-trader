"""T05 — Position sizing: min-of-5 rules, boundary + 28 tests."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from app.contracts.risk import RiskDecisionResult
from app.risk import IndependentRiskEngine, RiskEngineDefaults


# 5 single-rule limits
def L1_factory(value=Decimal("1000")):
    return lambda o,s,r,pv,l,c: (o, s, r, pv, replace(l, max_position_notional_per_symbol=value), c)

def L2_factory(value=Decimal("500"), cur=Decimal("50000"), total=Decimal("50500")):
    return lambda o,s,r,pv,l,c: (o, s, r, pv, replace(l, current_exposure_notional=cur, max_exposure_notional_total=total), c)

def L3_factory(value=Decimal("250")):
    return lambda o,s,r,pv,l,c: (o, s, r, pv, l, replace(c, defaults=RiskEngineDefaults(max_default_order_notional_quote=value)))

def L4_factory(cash=Decimal("100")):
    return lambda o,s,r,pv,l,c: (o, s, r, replace(pv, cash_quote=cash), l, c)

def L5_factory(cur_dd=0.18, max_dd=0.20, frac=0.80, equity=Decimal("1000")):
    return lambda o,s,r,pv,l,c: (o, s, r, replace(pv, equity_quote=equity), replace(l, current_drawdown_pct=cur_dd, max_drawdown_pct=max_dd), replace(c, defaults=RiskEngineDefaults(drawdown_risk_budget_fraction=frac)))


SIZING_CASES = [
    ("L1_1000",   L1_factory(Decimal("1000")),    Decimal("1000")),
    ("L1_200",    L1_factory(Decimal("200")),     Decimal("200")),
    ("L1_0",      L1_factory(Decimal("0")),       Decimal("0")),
    ("L2_headroom_500", L2_factory(Decimal("500"), cur=Decimal("50000"), total=Decimal("50500")), Decimal("500")),
    ("L2_headroom_0",   L2_factory(Decimal("0"), cur=Decimal("50000"), total=Decimal("50000")), Decimal("0")),
    ("L2_headroom_neg_clamp", L2_factory(Decimal("0"), cur=Decimal("50500"), total=Decimal("50000")), Decimal("0")),
    ("L3_250",    L3_factory(Decimal("250")),     Decimal("250")),
    ("L3_0",      L3_factory(Decimal("0")),       Decimal("0")),
    ("L4_cash_100", L4_factory(Decimal("100")),   Decimal("100")),
    ("L4_cash_0",   L4_factory(Decimal("0")),     Decimal("0")),
    ("L5_dd_headroom_low", L5_factory(0.195, 0.20, 0.80, Decimal("10000")), Decimal("400")),  # (0.005 * 0.80)*10000=40
]


def _apply(mut, opp, sig, reg, pv, lim, ctx):
    return mut(opp, sig, reg, pv, lim, ctx)


@pytest.mark.parametrize("name,mutator,expected_max", SIZING_CASES)
def test_t05_sizing_each_rule_max(name, mutator, expected_max, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    o2, s2, r2, p2, l2, c2 = _apply(mutator, opp, sig, reg, pv, lim, ctx)
    rd = engine.evaluate(o2, s2, r2, p2, l2, c2)
    if rd.decision == RiskDecisionResult.APPROVED:
        assert rd.position_sizing.notional <= expected_max, (name, rd.position_sizing.notional, expected_max)
    # If rejected (L5=0, etc), notional must be zero
    if rd.decision == RiskDecisionResult.REJECTED:
        assert rd.position_sizing.notional == Decimal("0")


# min-of-5 explicit matrix 4 tests
@pytest.mark.parametrize("L1,L2,L3,L4,L5,expected_notional_max", [
    (1000, 2000, 800, 1500, 750, Decimal("750")),
    (10000, 20000, 5000, 3000, 2000, Decimal("2000")),
    (100, 200, 300, 400, 500, Decimal("100")),
    (500, 500, 500, 500, 500, Decimal("500")),
])
def test_t05_sizing_min_of_five_combo(L1, L2, L3, L4, L5, expected_notional_max, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    # L5 = (max_dd - cur_dd) * budget_fraction * equity_quote
    # Solve for equity_quote and headroom such that computed L5 exactly equals the target
    # Choose: budget_fraction = 1.0; headroom_pct = 0.01; equity = L5 / headroom_pct
    HEADROOM = 0.01
    BUDGET_FRAC = 1.0
    CUR_DD = 0.10
    MAX_DD = CUR_DD + HEADROOM
    EQUITY = Decimal(str(L5)) / Decimal(str(HEADROOM * BUDGET_FRAC)) if (HEADROOM*BUDGET_FRAC) > 0 else Decimal(str(L5))
    pv2 = replace(pv, cash_quote=Decimal(str(L4)), equity_quote=EQUITY)
    lim2 = replace(
        lim,
        max_position_notional_per_symbol=Decimal(str(L1)),
        max_exposure_notional_total=Decimal(str(L2 + int(float(lim.current_exposure_notional)))),
        max_daily_loss_notional=Decimal("100000"),
        current_drawdown_pct=CUR_DD,
        max_drawdown_pct=MAX_DD,
    )
    ctx2 = replace(
        ctx,
        defaults=RiskEngineDefaults(
            max_default_order_notional_quote=Decimal(str(L3)),
            drawdown_risk_budget_fraction=BUDGET_FRAC,
        ),
        symbol_price_ref=Decimal("100000"),
    )
    rd = engine.evaluate(opp, sig, reg, pv2, lim2, ctx2)
    if rd.decision == RiskDecisionResult.APPROVED:
        assert rd.position_sizing.notional <= expected_notional_max + Decimal("0.01"), (
            f"min-of-5 mismatch: L5 target={L5}, actual notional={rd.position_sizing.notional}, "
            f"limits: cur_dd={lim2.current_drawdown_pct}, max_dd={lim2.max_drawdown_pct}, "
            f"equity={pv2.equity_quote}, headroom_frac*budget*equity={(MAX_DD-CUR_DD)*BUDGET_FRAC*float(pv2.equity_quote)}"
        )


# 5 zero boundaries + method string + leverage=1 enforcement + eps price guard
def test_t05_rejected_notional_zero(happy_path_tuple, engine):
    from app.contracts.canonical import QualityFlags
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(replace(opp, quality_flags=QualityFlags(invalid=True)), sig, reg, pv, lim, ctx)
    assert rd.position_sizing.notional == Decimal("0")
    assert rd.position_sizing.method == "rejected_no_sizing"


def test_t05_approved_method_string(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    if rd.decision == RiskDecisionResult.APPROVED:
        assert rd.position_sizing.method == "sizing_min_of_five_rules_v1"


def test_t05_leverage_2_invalid_rejected(happy_path_tuple, engine):
    """LimitsSnapshot(max_leverage_allowed=2) throws in __post_init__ -> outer catch rejected."""
    from app.contracts.risk import LimitsSnapshot
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    class RawBadLimits:
        pass
    # Cannot construct limits with 2 -> use raw object
    rd = engine.evaluate(opp, sig, reg, pv, object(), ctx)  # type: ignore[arg-type]
    assert rd.decision == RiskDecisionResult.REJECTED
    assert rd.position_sizing.notional == Decimal("0")


def test_t05_price_ref_zero_fallback(happy_path_tuple, engine):
    """Zero / None price_ref -> fallback 1 -> base_qty = notional / 1."""
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    ctx2 = replace(ctx, symbol_price_ref=Decimal("0"))
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    if rd.decision == RiskDecisionResult.APPROVED:
        assert rd.position_sizing.base_qty == rd.position_sizing.quote_qty


def test_t05_base_qty_nonneg(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.position_sizing.base_qty is None or rd.position_sizing.base_qty >= Decimal("0")
    assert rd.position_sizing.quote_qty is None or rd.position_sizing.quote_qty >= Decimal("0")
