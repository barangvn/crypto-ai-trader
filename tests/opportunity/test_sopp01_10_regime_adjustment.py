from tests.opportunity.conftest import (
    make_market_regime,
    make_strategy_signal,
)
from app.contracts.regime import MarketRegimeState
from app.opportunity.base import compute_regime_adjustment


class TestRegimeAdjustment:
    def test_bull_regime_max_confidence_trend(self):
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        sig = make_strategy_signal(strategy_id="trend_following_v1")
        assert compute_regime_adjustment(sig, regime) == pytest.approx(1.0)

    def test_bull_regime_momentum(self):
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        sig = make_strategy_signal(strategy_id="momentum_v1")
        assert compute_regime_adjustment(sig, regime) == pytest.approx(1.0)

    def test_bear_regime_zero_confidence_blend(self):
        regime = make_market_regime(MarketRegimeState.BEAR, confidence=1.0, strength=1.0)
        sig = make_strategy_signal(strategy_id="trend_following_v1")
        assert compute_regime_adjustment(sig, regime) <= 0.0001

    def test_low_confidence_blends_toward_half(self):
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.0)
        sig = make_strategy_signal()
        assert compute_regime_adjustment(sig, regime) == pytest.approx(0.5)

    def test_six_regimes_cover_range(self):
        results = []
        sig_t = make_strategy_signal(strategy_id="trend_following_v1", confidence=1.0)
        for primary in list(MarketRegimeState):
            regime = make_market_regime(primary, confidence=1.0, strength=1.0)
            results.append(compute_regime_adjustment(sig_t, regime))
        # Bull=1, Bear=0 ordered
        assert max(results) >= 0.99
        assert min(results) <= 0.01
        assert 0.2 <= sum(results) / len(results) <= 0.7

    def test_lv_above_hv_trend(self):
        lv = make_market_regime(MarketRegimeState.LOW_VOLATILITY, confidence=1.0, strength=1.0)
        hv = make_market_regime(MarketRegimeState.HIGH_VOLATILITY, confidence=1.0, strength=1.0)
        sig = make_strategy_signal(strategy_id="trend_following_v1", confidence=1.0)
        assert compute_regime_adjustment(sig, lv) > compute_regime_adjustment(sig, hv)

    def test_momentum_slightly_higher_in_sideways(self):
        regime = make_market_regime(MarketRegimeState.SIDEWAYS, confidence=1.0, strength=1.0)
        t = make_strategy_signal(strategy_id="trend_following_v1", confidence=1.0)
        m = make_strategy_signal(strategy_id="momentum_v1", confidence=1.0)
        assert compute_regime_adjustment(m, regime) >= compute_regime_adjustment(t, regime)

    def test_deterministic(self):
        regime = make_market_regime()
        sig = make_strategy_signal()
        assert len({compute_regime_adjustment(sig, regime) for _ in range(12)}) == 1


import pytest
