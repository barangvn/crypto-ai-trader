from __future__ import annotations

from dataclasses import replace

import pytest

from tests.opportunity.conftest import (
    DEFAULT_SCORING_WEIGHTS,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_quality_clean,
    make_strategy_signal,
)
from app.opportunity.base import (
    compute_confidence,
    compute_cost_multiplier,
    compute_regime_adjustment,
    compute_strategy_adjustment,
    compute_raw_opportunity_score,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


CONF_STRAT = [0.0, 0.25, 0.50, 0.75, 1.0]
CONF_REGIME = [0.0, 0.33, 0.66, 1.0]
QUALITY_MULT_CASES = [
    (None, 1.0, "clean_none"),
    (make_quality_clean(), 1.0, "clean_default"),
    (make_quality(stale=True), 0.85, "stale_085"),
    (make_quality(degraded=True), 0.85, "degraded_085"),
    (make_quality(missing=True), 1.0, "missing_no_conf_penalty_mult_1"),
    (make_quality(invalid=True), 0.10, "invalid_conf_cap_010"),
    (make_quality(quarantined=True), 0.10, "quarantine_conf_cap_010"),
]


@pytest.mark.parametrize("sc", CONF_STRAT, ids=[f"sc{s}" for s in CONF_STRAT])
@pytest.mark.parametrize("rc", CONF_REGIME, ids=[f"rc{r}" for r in CONF_REGIME])
@pytest.mark.parametrize("quality_tuple", QUALITY_MULT_CASES, ids=[qt[2] for qt in QUALITY_MULT_CASES])
def test_confidence_is_unit_interval_and_deterministic(sc, rc, quality_tuple):
    quality, expected_min_mult, _name = quality_tuple
    sig = make_strategy_signal(confidence=sc)
    regime = make_market_regime(MarketRegimeState.BULL, confidence=rc)
    c1 = compute_confidence(sig, regime, quality, DEFAULT_SCORING_WEIGHTS)
    c2 = compute_confidence(sig, regime, quality, DEFAULT_SCORING_WEIGHTS)
    assert abs(c1 - c2) < 1e-12, "determinism failed"
    assert 0.0 - 1e-9 <= c1 <= 1.0 + 1e-9, f"confidence out of range: {c1}"
    if quality is not None:
        if bool(getattr(quality, "invalid", False)) or bool(getattr(quality, "quarantined", False)):
            assert c1 <= 0.15 + 1e-9, f"invalid/quarantine should cap conf <= 0.15, got {c1}"


REGIME_STATES = list(MarketRegimeState)
REGIME_STATES_VALUES = [s for s in REGIME_STATES]


@pytest.mark.parametrize("state", REGIME_STATES_VALUES, ids=[s.value for s in REGIME_STATES_VALUES])
@pytest.mark.parametrize("confidence", [0.0, 0.49, 0.50, 0.51, 0.95, 1.0])
def test_regime_adjustment_within_zero_one(state, confidence):
    regime = make_market_regime(state, confidence=confidence)
    sig = make_strategy_signal()
    ra = compute_regime_adjustment(sig, regime)
    assert 0.0 <= ra <= 1.0 + 1e-9, f"regime adj out of range state={state}: {ra}"


STRATEGY_VARIANTS = [
    ("trend_following_v1", "str_01_v1", "known_trend"),
    ("momentum_v1", "str_01_v1", "known_momentum"),
    ("random_strategy_unknown", "v1.0.0", "unknown_strategy_penalty"),
]


@pytest.mark.parametrize("sid,sver,_name", STRATEGY_VARIANTS, ids=[n for _, _, n in STRATEGY_VARIANTS])
def test_strategy_adjustment_handles_known_and_unknown(sid, sver, _name):
    sig = make_strategy_signal(strategy_id=sid)
    object.__setattr__(sig, "strategy_version", sver)
    sa = compute_strategy_adjustment(sig)
    assert isinstance(sa, tuple) and len(sa) == 2
    adj_val, ref = sa
    assert 0.0 <= adj_val <= 1.0 + 1e-9, f"strategy adj out of range: {adj_val}"
    if "unknown" in sid:
        assert adj_val <= 0.40, f"unknown strategy expected penalty, got {adj_val}"
    assert ref == f"{sid}:{sver}" or ref.endswith(f":{sver}")


def test_raw_score_boundaries_zero_and_one():
    # Zero strategy strength → raw score should be near 0.5 or clamped region but still 0-1
    sig_zero = make_strategy_signal(signal_strength=0.0)
    reg_bull = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
    fv_bull = make_feature_vector("bull")
    r = compute_raw_opportunity_score(sig_zero, fv_bull, reg_bull, DEFAULT_SCORING_WEIGHTS)
    assert 0.0 <= r <= 1.0, f"raw score zero strength out of range: {r}"
    sig_full = make_strategy_signal(signal_strength=1.0, confidence=1.0)
    r2 = compute_raw_opportunity_score(sig_full, fv_bull, reg_bull, DEFAULT_SCORING_WEIGHTS)
    assert 0.0 <= r2 <= 1.0, f"raw score full strength out of range: {r2}"
    assert r2 >= r - 1e-9, "monotonic: higher strength should not reduce raw"


@pytest.mark.parametrize("net_bps", [-100.0, -10.0, -1.0, -0.01, 0.0, 0.01, 1.0, 10.0, 100.0])
def test_cost_multiplier_boundaries(net_bps):
    mult = compute_cost_multiplier(float(net_bps), DEFAULT_SCORING_WEIGHTS)
    if net_bps > 0:
        assert abs(mult - 1.0) < 1e-9, f"net {net_bps} expected mult 1.0, got {mult}"
    else:
        assert abs(mult - 0.15) < 1e-9, f"net {net_bps} expected mult 0.15, got {mult}"
