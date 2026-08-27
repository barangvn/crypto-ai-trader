from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
    make_default_scorer,
    FIXED_AS_OF,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


class TestFullChainIntegration:
    def _run(self, strategy_id, variant, regime_state, confidence=0.9, signal_strength=0.8):
        scorer = make_default_scorer()
        sig = make_strategy_signal(
            strategy_id=strategy_id,
            direction=SignalDirection.LONG,
            signal_strength=signal_strength,
            confidence=confidence,
        )
        fv = make_feature_vector(variant)
        regime = make_market_regime(regime_state, confidence=confidence, strength=confidence)
        return scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, FIXED_AS_OF)

    def test_strong_bull_trend_long_good_score(self):
        opp = self._run("trend_following_v1", "bull", MarketRegimeState.BULL, 0.95, 0.9)
        assert opp.score_total >= 0.55
        assert opp.confidence >= 0.75
        assert opp.actionable is True

    def test_bear_regime_flat_near_zero(self):
        opp = self._run("trend_following_v1", "bull", MarketRegimeState.BEAR, 0.95, 0.9)
        assert opp.score_total <= 0.10
        assert opp.actionable is False

    def test_lv_momentum_long_positive(self):
        opp = self._run("momentum_v1", "lv", MarketRegimeState.LOW_VOLATILITY, 0.9, 0.75)
        assert opp.score_total >= 0.20
        assert opp.expected_edge_bps == opp.score_components["costs.net_edge_bps"]

    def test_transition_uncertain_lower_score(self):
        opp_bull = self._run("trend_following_v1", "bull", MarketRegimeState.BULL, 0.85, 0.85)
        opp_tu = self._run("trend_following_v1", "tu", MarketRegimeState.TRANSITION_UNCERTAIN, 0.6, 0.7)
        assert opp_tu.score_total < opp_bull.score_total

    def test_hv_gives_lower_than_lv(self):
        lv = self._run("momentum_v1", "lv", MarketRegimeState.LOW_VOLATILITY, 0.9, 0.8)
        hv = self._run("momentum_v1", "hv", MarketRegimeState.HIGH_VOLATILITY, 0.9, 0.8)
        assert hv.score_total <= lv.score_total
