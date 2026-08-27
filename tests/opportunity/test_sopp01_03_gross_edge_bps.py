from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    MarketCostAssumptions,
    compute_expected_gross_edge_bps,
)


class TestGrossEdgeBps:
    def test_flat_direction_returns_zero(self):
        sig = make_strategy_signal(direction=SignalDirection.FLAT)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL)
        assert compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS) == 0.0

    def test_hold_direction_returns_zero(self):
        sig = make_strategy_signal(direction=SignalDirection.HOLD)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        assert compute_expected_gross_edge_bps(sig, fv, regime) == 0.0

    def test_strong_bull_gross_edge_positive(self):
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=0.9)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
        gross = compute_expected_gross_edge_bps(sig, fv, regime, DEFAULT_MARKET_COST_ASSUMPTIONS)
        assert gross > 0.0
        assert gross <= 50.0 * 0.9 * 1.0 * 1.0 * 1.0 + 1e-6

    def test_zero_signal_strength_gross_zero(self):
        sig = make_strategy_signal(signal_strength=0.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        assert compute_expected_gross_edge_bps(sig, fv, regime) == 0.0

    def test_bear_regime_gross_zero_or_low(self):
        sig = make_strategy_signal(signal_strength=0.9)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BEAR, confidence=0.95)
        assert compute_expected_gross_edge_bps(sig, fv, regime) <= 0.5

    def test_scale_bps_increases_gross(self):
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=0.99)
        c1 = DEFAULT_MARKET_COST_ASSUMPTIONS
        c2 = MarketCostAssumptions(gross_edge_scale_bps=100.0)
        g1 = compute_expected_gross_edge_bps(sig, fv, regime, c1)
        g2 = compute_expected_gross_edge_bps(sig, fv, regime, c2)
        assert g2 >= g1 * 1.9

    def test_high_vol_factor_increases_gross(self):
        sig = make_strategy_signal(signal_strength=0.9)
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.95)
        low_vol_fv = make_feature_vector("lv")
        high_vol_fv = make_feature_vector("hv")
        g_low = compute_expected_gross_edge_bps(sig, low_vol_fv, regime)
        g_high = compute_expected_gross_edge_bps(sig, high_vol_fv, regime)
        assert g_high >= g_low

    def test_gross_edge_never_negative(self):
        for _ in range(20):
            sig = make_strategy_signal(signal_strength=0.3)
            fv = make_feature_vector("sideways")
            regime = make_market_regime(MarketRegimeState.SIDEWAYS, confidence=0.4)
            assert compute_expected_gross_edge_bps(sig, fv, regime) >= 0.0

    def test_deterministic_same(self):
        sig = make_strategy_signal()
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        vals = {compute_expected_gross_edge_bps(sig, fv, regime) for _ in range(12)}
        assert len(vals) == 1
