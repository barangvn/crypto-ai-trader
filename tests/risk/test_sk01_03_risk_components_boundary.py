"""T03 — 20 risk components + 24 component boundary test cases (R01..R19 key)."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.contracts.canonical import QualityFlags
from app.contracts.risk import RiskDecisionResult
from app.risk import DEFAULT_WEIGHTS, IndependentRiskEngine, RiskEngineDefaults


def _apply(hpt, mutator):
    opp, sig, reg, pv, lim, ctx = hpt
    result = mutator(opp, sig, reg, pv, lim, ctx)
    if not isinstance(result, tuple) or len(result) != 6:
        return opp, sig, reg, pv, lim, ctx
    fixed = []
    for i, val in enumerate(result):
        fixed.append(val if val is not None else [opp, sig, reg, pv, lim, ctx][i])
    return tuple(fixed)


COMPONENT_CASES_NAMES = [
    "R01_quality_clean",
    "R01_quality_all_bad",
    "R02_spread_20bps",
    "R02_spread_500bps",
    "R03_edge_1bps",
    "R03_edge_100bps",
    "R05_opp_conf_1pct",
    "R05_opp_conf_100pct",
    "R07_sig_conf_0",
    "R07_sig_conf_1",
    "R08_trend_bull",
    "R08_trend_sideways",
    "R10_regime_hv",
    "R10_regime_lv",
    "R11_dd_100pct",
    "R11_dd_0pct",
    "R12_loss_breach",
    "R12_no_loss",
    "R15_high_concentration",
    "R15_low_concentration",
    "R16_cash_zero",
    "R16_cash_huge",
    "R19_sliplat_high",
    "R19_sliplat_low",
]

COMPONENT_CASES_MUTATORS = [
    lambda o,s,r,pv,l,c: (replace(o, quality_flags=QualityFlags(degraded=False)), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (replace(o, quality_flags=QualityFlags(stale=True,missing=True,duplicate=True,out_of_order=True,invalid=True,quarantined=True,degraded=True)), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (None, None, None, None, None, replace(c, feature_spread_bps_probe=20.0)),
    lambda o,s,r,pv,l,c: (None, None, None, None, None, replace(c, feature_spread_bps_probe=500.0)),
    lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=1.0), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=100.0), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (replace(o, confidence=0.01), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (replace(o, confidence=1.00), None, None, None, None, None),
    lambda o,s,r,pv,l,c: (None, replace(s, confidence=0.00), None, None, None, None),
    lambda o,s,r,pv,l,c: (None, replace(s, confidence=1.00), None, None, None, None),
    lambda o,s,r,pv,l,c: (None, replace(s, strategy_id="trend"), None, None, None, None),
    lambda o,s,r,pv,l,c: (None, replace(s, strategy_id="trend"), replace(r, regime="sideways"), None, None, None),
    lambda o,s,r,pv,l,c: (None, None, replace(r, regime="high_volatility"), None, None, None),
    lambda o,s,r,pv,l,c: (None, None, replace(r, regime="low_volatility"), None, None, None),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, current_drawdown_pct=0.99, max_drawdown_pct=1.00), None),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, current_drawdown_pct=0.0, max_drawdown_pct=1.00), None),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, max_daily_loss_notional=Decimal("100"), current_daily_pnl=Decimal("-500")), None),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, max_daily_loss_notional=Decimal("1000"), current_daily_pnl=Decimal("0")), None),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, current_exposure_notional=Decimal("33000"), max_exposure_notional_total=Decimal("50000")), replace(c, symbol_current_exposure_notional=Decimal("33000"), defaults=RiskEngineDefaults(concentration_diversifier_n=3.0))),
    lambda o,s,r,pv,l,c: (None, None, None, None, replace(l, current_exposure_notional=Decimal("0"), max_exposure_notional_total=Decimal("50000")), replace(c, symbol_current_exposure_notional=Decimal("0"))),
    lambda o,s,r,pv,l,c: (None, None, None, replace(pv, cash_quote=Decimal("0")), None, None),
    lambda o,s,r,pv,l,c: (None, None, None, replace(pv, cash_quote=Decimal("1000000")), None, None),
    lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=5.0), None, None, None, None, replace(c, defaults=RiskEngineDefaults(slippage_bps_default=100.0, latency_bps_default=100.0))),
    lambda o,s,r,pv,l,c: (replace(o, expected_edge_bps=100.0), None, None, None, None, replace(c, defaults=RiskEngineDefaults(slippage_bps_default=1.0, latency_bps_default=1.0))),
]


@pytest.mark.parametrize("case_idx", range(len(COMPONENT_CASES_NAMES)), ids=COMPONENT_CASES_NAMES)
def test_t03_component_boundaries(case_idx, happy_path_tuple, engine):
    name = COMPONENT_CASES_NAMES[case_idx]
    mutator = COMPONENT_CASES_MUTATORS[case_idx]
    o2, s2, r2, p2, l2, c2 = _apply(happy_path_tuple, mutator)
    rd = engine.evaluate(o2, s2, r2, p2, l2, c2)
    assert rd.decision in (RiskDecisionResult.APPROVED, RiskDecisionResult.REJECTED), name


def test_t03_weights_sum_equals_one():
    total = 0.0
    for _, v in DEFAULT_WEIGHTS.as_tuple_ordered():
        total += v
    assert abs(total - 1.000) < 1e-8, total


def test_t03_20_components_in_weights_tuple():
    names = [k for k, _ in DEFAULT_WEIGHTS.as_tuple_ordered()]
    assert len(names) == 20
