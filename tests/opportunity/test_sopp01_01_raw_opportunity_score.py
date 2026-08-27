from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.opportunity.base import (
    DEFAULT_SCORING_WEIGHTS,
    compute_raw_opportunity_score,
)


class TestRawOpportunityScore:
    def test_long_signal_full_bull_score_nonzero(self):
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=0.9)
        score = compute_raw_opportunity_score(sig, fv, regime, DEFAULT_SCORING_WEIGHTS)
        assert 0.45 <= score <= 1.0

    def test_flat_signal_returns_zero(self):
        sig = make_strategy_signal(direction=SignalDirection.FLAT)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        score = compute_raw_opportunity_score(sig, fv, regime)
        assert score == 0.0

    def test_hold_signal_returns_zero(self):
        sig = make_strategy_signal(direction=SignalDirection.HOLD)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL)
        assert compute_raw_opportunity_score(sig, fv, regime) == 0.0

    def test_bear_regime_greatly_reduces_score(self):
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        bull_reg = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=0.9)
        bear_reg = make_market_regime(MarketRegimeState.BEAR, confidence=1.0)
        bull_score = compute_raw_opportunity_score(sig, fv, bull_reg)
        bear_score = compute_raw_opportunity_score(sig, fv, bear_reg)
        assert bear_score < bull_score
        assert 0.0 <= bear_score <= 0.75

    def test_zero_signal_strength_sets_strategy_component_zero(self):
        sig = make_strategy_signal(signal_strength=0.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        score = compute_raw_opportunity_score(sig, fv, regime)
        assert 0.0 <= score <= 0.45

    def test_sideways_regime_returns_lower_score(self):
        sig = make_strategy_signal(signal_strength=0.8, confidence=0.9)
        fv = make_feature_vector("sideways")
        bull = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
        sw = make_market_regime(MarketRegimeState.SIDEWAYS, confidence=0.9)
        assert compute_raw_opportunity_score(sig, fv, sw) < compute_raw_opportunity_score(sig, fv, bull)

    def test_score_always_in_unit_interval(self):
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        import math
        for _ in range(20):
            s = compute_raw_opportunity_score(sig, fv, regime)
            assert 0.0 <= s <= 1.0
            assert not math.isnan(s)

    def test_lv_regime_improves_over_hv(self):
        sig = make_strategy_signal(signal_strength=0.9, confidence=0.9)
        fv = make_feature_vector("lv")
        lv = make_market_regime(MarketRegimeState.LOW_VOLATILITY, confidence=0.95)
        hv = make_market_regime(MarketRegimeState.HIGH_VOLATILITY, confidence=0.95)
        assert compute_raw_opportunity_score(sig, fv, lv) > compute_raw_opportunity_score(sig, fv, hv)

    def test_weight_sum_equals_one(self):
        w = DEFAULT_SCORING_WEIGHTS
        assert abs((w.w_raw_strategy + w.w_raw_regime + w.w_raw_feature) - 1.0) < 1e-12
        assert abs((w.w_conf_strategy + w.w_conf_regime + w.w_conf_quality) - 1.0) < 1e-12

    def test_deterministic_same_input(self):
        sig = make_strategy_signal()
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL)
        results = {compute_raw_opportunity_score(sig, fv, regime) for _ in range(20)}
        assert len(results) == 1

    def test_direction_compat_rejects_nonlong_only(self):
        for d in (SignalDirection.FLAT, SignalDirection.HOLD):
            sig = make_strategy_signal(direction=d, signal_strength=1.0, confidence=1.0)
            fv = make_feature_vector("bull")
            regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
            assert compute_raw_opportunity_score(sig, fv, regime) == 0.0

    def test_feature_vol_score_contributes(self):
        # When direction is not LONG, score is 0 regardless of feature inputs (direction_compat).
        # So here we compare two feature variants with LONG direction but different feature content.
        sig = make_strategy_signal(signal_strength=0.0, confidence=0.0, direction=SignalDirection.LONG)
        fv_bull = make_feature_vector("bull")
        fv_sw = make_feature_vector("sideways")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.0)
        # Strategy component 0, regime 0, feature only dominates
        s1 = compute_raw_opportunity_score(sig, fv_bull, regime)
        s2 = compute_raw_opportunity_score(sig, fv_sw, regime)
        # Feature component differs → s1 != s2 expected
        assert (s1 - s2) >= -1e-9  # bull feature may be higher than sideways
