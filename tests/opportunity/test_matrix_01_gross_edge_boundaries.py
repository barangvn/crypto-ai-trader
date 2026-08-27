from __future__ import annotations

from dataclasses import replace

import pytest

from tests.opportunity.conftest import (
    FIXED_AS_OF,
    FIXED_SYMBOL,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
)
from app.opportunity.base import (
    compute_expected_gross_edge_bps,
    DEFAULT_MARKET_COST_ASSUMPTIONS,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


SCALE_BPS_POINTS = [10.0, 25.0, 50.0, 100.0, 200.0]


@pytest.mark.parametrize("scale_bps", SCALE_BPS_POINTS, ids=[f"scl{s}" for s in SCALE_BPS_POINTS])
def test_gross_edge_scale_bps_multiplies_strength_linearly(scale_bps):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, gross_edge_scale_bps=scale_bps)
    sig_low = make_strategy_signal(signal_strength=0.1)
    sig_high = make_strategy_signal(signal_strength=0.9)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
    g_low = compute_expected_gross_edge_bps(sig_low, fv, regime, costs)
    g_high = compute_expected_gross_edge_bps(sig_high, fv, regime, costs)
    assert g_high >= g_low - 1e-9, "higher strength should not produce lower gross edge"
    ratio = g_high / (g_low + 1e-9)
    assert ratio >= 1.0 - 1e-9, f"monotonicity failed low={g_low} high={g_high}"


@pytest.mark.parametrize("scale_bps", SCALE_BPS_POINTS, ids=[f"det{s}" for s in SCALE_BPS_POINTS])
def test_gross_edge_deterministic_ten_runs_per_scale(scale_bps):
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, gross_edge_scale_bps=scale_bps)
    sig = make_strategy_signal(signal_strength=0.7)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL)
    vals = [compute_expected_gross_edge_bps(sig, fv, regime, costs) for _ in range(10)]
    assert len(set(vals)) == 1, f"gross not deterministic at scale={scale_bps}: {vals}"


SIGNAL_DIRECTIONS = [
    (SignalDirection.LONG, "long"),
    (SignalDirection.FLAT, "flat"),
    (SignalDirection.HOLD, "hold"),
]


@pytest.mark.parametrize("direction,_name", SIGNAL_DIRECTIONS, ids=[n for _, n in SIGNAL_DIRECTIONS])
def test_gross_edge_non_negative_for_all_signal_directions(direction, _name):
    sig = make_strategy_signal(direction=direction)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert gross >= -1e-9, f"direction {direction}: unexpected negative gross edge {gross}"


@pytest.mark.parametrize("direction,_name", SIGNAL_DIRECTIONS, ids=[f"fh{n}" for _, n in SIGNAL_DIRECTIONS])
def test_flat_or_hold_yields_zero_gross(direction, _name):
    if direction.value not in ("flat", "hold"):
        pytest.skip("only flat/hold relevant here")
    sig = make_strategy_signal(direction=direction, signal_strength=1.0)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert abs(gross - 0.0) < 1e-9, f"flat/hold must yield 0 gross, got {gross}"


def test_gross_edge_zero_signal_strength_yields_small_or_zero():
    sig = make_strategy_signal(signal_strength=0.0)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert gross < 10.0, f"zero strength should yield near zero gross, got {gross}"


def test_gross_edge_full_strength_scaled_by_default_scale():
    sig = make_strategy_signal(signal_strength=1.0)
    fv = make_feature_vector("bull", custom_features={"close_raw": 100.0, "ema_14": 105.0, "ema_28": 102.0, "mom_10_pct": 2.0, "volatility_20_bps": 50.0})
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    scale = DEFAULT_MARKET_COST_ASSUMPTIONS.gross_edge_scale_bps
    assert 0.0 < gross <= scale * 1.5 + 1e-9, f"full strength out of band, got {gross} scale={scale}"


def test_long_direction_with_bull_regime_positive_gross():
    sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=1.0, confidence=1.0)
    fv = make_feature_vector("bull", custom_features={"close_raw": 100.0, "ema_14": 105.0, "ema_28": 102.0, "mom_10_pct": 2.0, "volatility_20_bps": 50.0})
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert gross > 0.0, f"bull + long should yield positive gross, got {gross}"


REGIME_FOR_GROSS = list(MarketRegimeState)


@pytest.mark.parametrize("state", REGIME_FOR_GROSS, ids=[s.value for s in REGIME_FOR_GROSS])
def test_gross_edge_never_negative_any_regime(state):
    sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=0.5)
    fv = make_feature_vector("bull")
    regime = make_market_regime(state, confidence=0.9)
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert gross >= -1e-9, f"negative gross in regime {state}: {gross}"


@pytest.mark.parametrize("strength", [0.0, 0.25, 0.5, 0.75, 1.0], ids=[f"st{s}" for s in [0.0, 0.25, 0.5, 0.75, 1.0]])
def test_gross_edge_monotonic_in_strength(strength):
    fv = make_feature_vector("bull", custom_features={"close_raw": 100.0, "ema_14": 105.0, "ema_28": 102.0, "mom_10_pct": 2.0})
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
    costs = replace(DEFAULT_MARKET_COST_ASSUMPTIONS, gross_edge_scale_bps=100.0)
    sig_a = make_strategy_signal(signal_strength=max(0.0, strength - 0.01))
    sig_b = make_strategy_signal(signal_strength=strength)
    g_a = compute_expected_gross_edge_bps(sig_a, fv, regime, costs)
    g_b = compute_expected_gross_edge_bps(sig_b, fv, regime, costs)
    assert g_b >= g_a - 1e-9, f"gross should be monotonic: g({strength-0.01})={g_a}, g({strength})={g_b}"


def test_gross_edge_bear_regime_less_than_bull_same_strength():
    fv = make_feature_vector("bull")
    sig = make_strategy_signal(signal_strength=0.8)
    bull = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
    bear = make_market_regime(MarketRegimeState.BEAR, confidence=0.9)
    g_bull = compute_expected_gross_edge_bps(sig, fv, bull, DEFAULT_MARKET_COST_ASSUMPTIONS)
    g_bear = compute_expected_gross_edge_bps(sig, fv, bear, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert g_bull >= g_bear - 1e-9, f"bull {g_bull} should be >= bear {g_bear}"


ZERO_EDGE_BOUNDARY_STRENGTHS = [0.0, 1e-9, 0.0001]


@pytest.mark.parametrize("strength", ZERO_EDGE_BOUNDARY_STRENGTHS, ids=[f"zb{s}" for s in ZERO_EDGE_BOUNDARY_STRENGTHS])
def test_gross_edge_zero_boundary_strength(strength):
    sig = make_strategy_signal(signal_strength=strength)
    fv = make_feature_vector("bull")
    regime = make_market_regime()
    gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert gross >= 0.0, "negative gross at near-zero strength"
    assert gross <= 5.0, f"too-high gross at strength {strength}: {gross}"


PRECISION_VALUES = [1e-6, 1e-4, 1e-2, 0.9999, 0.999999]


@pytest.mark.parametrize("strength", PRECISION_VALUES, ids=[f"pr{s}" for s in PRECISION_VALUES])
def test_gross_edge_precision_extreme_strengths(strength):
    sig = make_strategy_signal(signal_strength=strength)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
    g1 = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    g2 = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
    assert g1 == g2, "precision repeatability failed"
    assert g1 >= 0.0


def test_full_chain_evaluate_net_edge_matches_gross_minus_costs():
    scorer = make_default_scorer()
    sig = make_strategy_signal(signal_strength=0.8, confidence=0.9)
    fv = make_feature_vector("bull", custom_features={"close_raw": 100.0, "ema_14": 105.0, "ema_28": 102.0, "mom_10_pct": 2.0, "spread_bps": 5.0, "volatility_20_bps": 25.0})
    regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, None, FIXED_AS_OF)
    gross = opp.score_components.get("costs.gross_edge_bps", 0.0)
    total_cost = opp.score_components.get("costs.total_cost_bps", 0.0)
    net = opp.score_components.get("costs.net_edge_bps", 0.0)
    assert abs(net - (gross - total_cost)) < 1e-6, f"net arithmetic: gross={gross} cost={total_cost} net={net}"
    assert abs(opp.expected_edge_bps - net) < 1e-6, "expected_edge_bps != costs.net_edge_bps"
    assert abs(opp.expected_cost_bps - total_cost) < 1e-6, "expected_cost_bps != costs.total_cost_bps"
