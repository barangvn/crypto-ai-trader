from __future__ import annotations

from dataclasses import replace

import pytest

from tests.opportunity.conftest import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    DEFAULT_SCORING_WEIGHTS,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_quality_clean,
    make_strategy_signal,
)
from app.opportunity.base import (
    build_explainability_bundle,
    compute_fee_cost_bps,
    compute_net_expected_edge_bps,
    compute_cost_multiplier,
    compute_latency_impact_bps,
    compute_slippage_cost_bps,
    compute_spread_cost_bps,
    compute_strategy_adjustment,
    compute_regime_adjustment,
)
from app.contracts.regime import MarketRegimeState


# Fee: taker * size + network * size. Use precision scenarios.
FEE_SCENARIOS = [
    (0.0, 0.0, 1.0, 0.0, "all_zero"),
    (10.0, 0.5, 1.0, 10.5, "default_taker_and_network"),
    (0.0, 0.5, 1.0, 0.5, "only_network"),
    (5.0, 0.0, 1.0, 5.0, "only_taker"),
    (10.0, 0.5, 2.0, 21.0, "size_x2"),
    (10.0, 0.5, 0.5, 5.25, "size_half"),
]


@pytest.mark.parametrize("taker,net,size,expected,_name", FEE_SCENARIOS, ids=[n for *_, n in FEE_SCENARIOS])
def test_fee_cost_equals_taker_plus_network_times_size(taker, net, size, expected, _name):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, fee_taker_bps=taker, fee_network_bps=net, trade_size_multiplier=size)
    fee = compute_fee_cost_bps(costs)
    assert abs(fee - expected) < 1e-7, f"expected fee {expected}, got {fee}"


def test_fee_precision_small_values_reproducible_10x():
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, fee_taker_bps=0.001, fee_network_bps=0.0001, trade_size_multiplier=1.0)
    vals = [compute_fee_cost_bps(costs) for _ in range(10)]
    assert len(set(vals)) == 1, f"fee not deterministic: {vals}"


# Slippage: monotonic + non-negative (no fixed exponent equation check)
SLIPPAGE_VOL_POINTS = [0.0, 10.0, 20.0, 40.0, 100.0, 250.0]


@pytest.mark.parametrize("vol", SLIPPAGE_VOL_POINTS, ids=[f"vol{v}" for v in SLIPPAGE_VOL_POINTS])
def test_slippage_nonneg_and_monotonic(vol):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, slippage_base_bps=1.0, slippage_vol_exponent=1.5)
    fv = make_feature_vector("bull", custom_features={"volatility_20_bps": vol})
    s = compute_slippage_cost_bps(fv, make_quality_clean(), costs)
    assert s >= 0.0, f"slippage {s} negative at vol={vol}"
    if vol > 0:
        fv_lo = make_feature_vector("bull", custom_features={"volatility_20_bps": vol / 2})
        s_lo = compute_slippage_cost_bps(fv_lo, make_quality_clean(), costs)
        assert s >= s_lo - 1e-9, "monotonic"


# Spread: abnormal 1.3x and min fallback
# Implementation: spread = max(spread_fv_or_fallback, min_spread) * 0.5 * abnormal(1.3 or 1.0)
SPREAD_TABLE = [
    (0.5, 1.0, 1.0, False, 0.5, "below_min_fallback_halfed_without_abnormal"),
    (1.0, 1.0, 1.0, False, 0.5, "at_min_no_abnormal"),
    (10.0, 1.0, 10.0, False, 5.0, "normal_no_abnormal"),
    (99.0, 1.0, 99.0, False, 49.5, "below_abnormal_threshold_no_13x"),
    (100.0, 1.0, 100.0, True, 65.0, "at_100_yes_abnormal_1.3x_65"),
    (200.0, 1.0, 200.0, True, 130.0, "above_200_abnormal_1.3x_130"),
]


@pytest.mark.parametrize("spread_fv,min_spread,_spread_use,abn_exp,expected,_name", SPREAD_TABLE, ids=[e[5] for e in SPREAD_TABLE])
def test_spread_cost_values_and_abnormal(spread_fv, min_spread, _spread_use, abn_exp, expected, _name):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, min_spread_bps=min_spread)
    fv = make_feature_vector("bull", custom_features={"spread_bps": spread_fv})
    out = compute_spread_cost_bps(fv, None, costs)
    # Abnormal independent check
    if spread_fv >= 100.0:
        assert abn_exp is True
    assert abs(out - expected) < 1e-6, f"fv={spread_fv} expected {expected}, got {out}"


# Latency: actual implementation formula; values we check monotonicity + bounds per config
LAT_CASES = [
    (0.0, 1.0, 2.0, "zero_ms"),
    (0.5, 1.0, 2.0, "half_ms"),
    (1.0, 1.0, 2.0, "target_ms"),
    (2.0, 1.0, 2.0, "twice_target"),
    (3.0, 1.0, 2.0, "default_3ms"),
    (5.0, 1.0, 2.0, "high_5ms"),
    (5.0, 2.0, 1.0, "high_target_low_sens"),
]


@pytest.mark.parametrize("lat,target,sens,_name", LAT_CASES, ids=[n for *_, n in LAT_CASES])
def test_latency_impact_positive_and_monotonic(lat, target, sens, _name):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, latency_ms=lat, latency_target_ms=target, latency_sensitivity=sens, gross_edge_scale_bps=50.0)
    fv = make_feature_vector("bull")
    val = compute_latency_impact_bps(fv, costs)
    assert val >= 0.0, f"latency negative {val}"
    # Same target, higher latency >= lower latency
    if lat >= target:
        costs_lo = replace(costs, latency_ms=max(target, lat / 2))
        val_lo = compute_latency_impact_bps(fv, costs_lo)
        assert val >= val_lo - 1e-9, f"monotonic: lat={lat} val={val}, half={lat/2} val_lo={val_lo}"


# Net edge arithmetic: net = gross - sum_4costs
NET_CASES = [
    (100.0, 10.0, 5.0, 5.0, 0.0, 80.0, ">0 → mult 1.0"),
    (10.0, 3.0, 2.0, 1.0, 4.0, 0.0, "exactly_0 → mult 0.15"),
    (5.0, 3.0, 2.0, 1.0, 4.0, -5.0, "negative → mult 0.15"),
]


@pytest.mark.parametrize("g,f,s,sp,l,net_expected,note", NET_CASES, ids=[e[6] for e in NET_CASES])
def test_net_edge_arithmetic_and_cost_multiplier(g, f, s, sp, l, net_expected, note):
    net, total_cost = compute_net_expected_edge_bps(g, f, s, sp, l)
    assert abs(net - net_expected) < 1e-9, f"arith mismatch net={net} expected {net_expected}"
    # mult check: >0 → 1.0, <=0 → 0.15
    mult = compute_cost_multiplier(net, DEFAULT_SCORING_WEIGHTS)
    if net_expected > 0:
        assert abs(mult - 1.0) < 1e-9, f">0 expected mult 1.0, got {mult}"
    else:
        assert abs(mult - 0.15) < 1e-9, f"<=0 expected mult 0.15, got {mult}"


def test_net_edge_deterministic_10x():
    values = [compute_net_expected_edge_bps(50.0, 10.0, 3.0, 2.0, 1.0) for _ in range(10)]
    uniq = {v for v in values}
    assert len(uniq) == 1


# Strategy adjustment: tuple (float, str) return signature
@pytest.mark.parametrize("sid,ver", [
    ("trend_following_v1", "str_01_v1"),
    ("momentum_v1", "str_01_v1"),
    ("totally_unknown_algo", "1.0.0"),
])
def test_strategy_adjustment_returns_tuple(sid, ver):
    sig = make_strategy_signal(strategy_id=sid)
    object.__setattr__(sig, "strategy_version", ver)
    out = compute_strategy_adjustment(sig)
    assert isinstance(out, tuple) and len(out) == 2
    adj_val, ref = out
    assert 0.0 <= adj_val <= 1.0 + 1e-9
    assert f"{sid}" in ref or ref.endswith(f":{ver}") or ref.count(":") >= 1
