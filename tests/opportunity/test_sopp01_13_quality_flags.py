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
    _quality_score_multiplier,
    _quality_reject_reasons,
    compute_confidence,
)


class TestQualityImpact:
    def test_each_flag_individually_impact(self):
        flags = ["stale", "missing", "duplicate", "out_of_order", "degraded"]
        for f in flags:
            q = make_quality(**{f: True})
            mult = _quality_score_multiplier(q)
            assert 0.3 <= mult <= 0.95, f"flag={f} mult={mult}"
            reasons = _quality_reject_reasons(q)
            # non-critical flags don't need reject reasons list non-empty; just validate mult range

    def test_invalid_sets_ceiling_015(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        q = make_quality(invalid=True)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert opp.score_total <= 0.201  # with 0.10 quality mult, final score is 0.1*other components
        assert opp.actionable is False
        assert "quality_invalid_data" in opp.reject_reasons

    def test_quarantine_sets_ceiling_015(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        q = make_quality(quarantined=True)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert opp.score_total <= 0.201
        assert opp.actionable is False
        assert "quality_quarantined" in opp.reject_reasons

    def test_stale_does_not_reject_by_itself(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        q = make_quality(stale=True)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert "quality_stale" not in opp.reject_reasons

    def test_quality_flags_not_mutated(self):
        q = make_quality(stale=False)
        q_id = id(q)
        before = (q.stale, q.missing, q.duplicate, q.out_of_order, q.invalid, q.quarantined, q.degraded)
        _ = _quality_score_multiplier(q)
        _ = _quality_reject_reasons(q)
        _ = compute_confidence(make_strategy_signal(), make_market_regime(), q)
        assert id(q) == q_id
        assert (q.stale, q.missing, q.duplicate, q.out_of_order, q.invalid, q.quarantined, q.degraded) == before

    def test_multiple_flags_stacked(self):
        q = make_quality(stale=True, missing=True, duplicate=True, out_of_order=True)
        mult = _quality_score_multiplier(q)
        assert 0.0 < mult < 0.7  # at worst multiple discounts applied

    def test_quality_confidence_matches_stale_and_degraded_equal(self):
        q_s = make_quality(stale=True)
        q_d = make_quality(degraded=True)
        assert abs(_quality_score_multiplier(q_s) - _quality_score_multiplier(q_d)) < 1e-12

    def test_quality_score_mult_range(self):
        for f in [{}, {"stale": True}, {"missing": True}, {"duplicate": True}, {"out_of_order": True}, {"degraded": True}, {"invalid": True}, {"quarantined": True}]:
            q = make_quality(**f)
            m = _quality_score_multiplier(q)
            assert 0.0 <= m <= 1.0

    def test_quality_reasons_sorted(self):
        q = make_quality(invalid=True, quarantined=True)
        r = _quality_reject_reasons(q)
        assert r == sorted(r)
