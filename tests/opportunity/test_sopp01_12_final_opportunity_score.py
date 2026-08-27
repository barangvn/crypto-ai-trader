from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.opportunity.base import (
    DEFAULT_SCORING_WEIGHTS,
    _quality_score_multiplier,
    compute_final_opportunity_score,
    compute_raw_opportunity_score,
    compute_regime_adjustment,
    compute_strategy_adjustment,
    compute_cost_multiplier,
    compute_confidence,
)


class TestFinalScore:
    def test_perfect_bull_long_actionable_likely(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(
            strategy_id="trend_following_v1",
            direction=SignalDirection.LONG,
            signal_strength=1.0,
            confidence=1.0,
        )
        fv = make_feature_vector("bull", custom_features={"spread_bps": 0.5, "volatility_20_bps": 25.0})
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", created_ts="2026-08-26T10:00:00.000Z")
        assert opp.score_total >= 0.55
        assert opp.actionable is True

    def test_quality_invalid_not_actionable(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        q = make_quality(invalid=True)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert opp.actionable is False
        assert "quality_invalid_data" in opp.reject_reasons
        assert opp.score_total <= 0.20

    def test_quarantined_not_actionable(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        q = make_quality(quarantined=True)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert opp.actionable is False
        assert "quality_quarantined" in opp.reject_reasons
        assert opp.score_total <= 0.20

    def test_bear_regime_score_near_zero(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BEAR, confidence=1.0)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.score_total <= 0.10
        assert "regime_bear_no_long" in opp.reject_reasons

    def test_flat_signal_no_action(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.FLAT)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert "signal_direction_flat" in opp.reject_reasons
        assert opp.actionable is False

    def test_final_score_always_in_unit_interval(self):
        scorer = make_default_scorer()
        for variant in ("bull", "hv", "lv", "sideways"):
            for primary in list(MarketRegimeState):
                for direction in (SignalDirection.LONG, SignalDirection.FLAT, SignalDirection.HOLD):
                    sig = make_strategy_signal(direction=direction)
                    fv = make_feature_vector(variant)
                    regime = make_market_regime(primary)
                    opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
                    assert 0.0 <= opp.score_total <= 1.0
                    assert 0.0 <= opp.confidence <= 1.0

    def test_reject_reasons_sorted(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.FLAT)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BEAR)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.reject_reasons == sorted(opp.reject_reasons)

    def test_compute_final_score_deterministic(self):
        vals = {compute_final_opportunity_score(0.8, 0.9, 0.95, 1.0, 1.0) for _ in range(10)}
        assert len(vals) == 1

    def test_cumulative_product_matches(self):
        assert compute_final_opportunity_score(0.5, 2.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)  # clamp

    def test_expected_costs_match_components(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal()
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert abs(
            opp.expected_cost_bps
            - (
                opp.score_components["costs.fee_bps"]
                + opp.score_components["costs.slippage_bps"]
                + opp.score_components["costs.spread_bps"]
                + opp.score_components["costs.latency_bps"]
            )
        ) < 1e-6
        assert opp.expected_edge_bps == pytest.approx(opp.score_components["costs.net_edge_bps"])
        assert opp.score_total == pytest.approx(opp.score_components["final_score"])


import pytest
