from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_strategy_signal,
)
from app.contracts.regime import MarketRegimeState
from app.opportunity.base import (
    DEFAULT_SCORING_WEIGHTS,
    compute_confidence,
    _quality_confidence_multiplier,
)


class TestConfidenceModel:
    def test_perfect_case_yields_high_confidence(self):
        sig = make_strategy_signal(confidence=1.0)
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        c = compute_confidence(sig, regime, None, DEFAULT_SCORING_WEIGHTS)
        assert 0.85 <= c <= 1.0

    def test_all_zeros_confidence_is_zero(self):
        sig = make_strategy_signal(confidence=0.0)
        regime = make_market_regime(MarketRegimeState.BEAR, confidence=0.0)
        c = compute_confidence(sig, regime, None, DEFAULT_SCORING_WEIGHTS)
        assert 0.0 <= c <= 0.15

    def test_quality_stale_degrades_confidence(self):
        sig = make_strategy_signal(confidence=1.0)
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        clean = compute_confidence(sig, regime, None)
        stale_q = make_quality(stale=True)
        stale_c = compute_confidence(sig, regime, stale_q)
        assert stale_c < clean

    def test_invalid_quality_caps_confidence(self):
        sig = make_strategy_signal(confidence=1.0)
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        q = make_quality(invalid=True)
        c = compute_confidence(sig, regime, q)
        assert c <= 0.15 + 1e-9

    def test_quarantined_caps_confidence(self):
        sig = make_strategy_signal(confidence=1.0)
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0)
        q = make_quality(quarantined=True)
        c = compute_confidence(sig, regime, q)
        assert c <= 0.15 + 1e-9

    def test_quality_none_is_clean(self):
        assert _quality_confidence_multiplier(None) == 1.0

    def test_quality_degraded_matches_stale(self):
        q1 = make_quality(stale=True)
        q2 = make_quality(degraded=True)
        assert abs(_quality_confidence_multiplier(q1) - _quality_confidence_multiplier(q2)) < 1e-12

    def test_quality_mult_always_in_zero_one(self):
        flags = [
            {},
            {"stale": True},
            {"missing": True},
            {"duplicate": True},
            {"out_of_order": True},
            {"invalid": True},
            {"quarantined": True},
            {"degraded": True},
            {"stale": True, "duplicate": True, "missing": True},
        ]
        for f in flags:
            q = make_quality(**f)
            m = _quality_confidence_multiplier(q)
            assert 0.0 <= m <= 1.0

    def test_confidence_deterministic(self):
        sig = make_strategy_signal()
        regime = make_market_regime()
        vals = {compute_confidence(sig, regime, None) for _ in range(15)}
        assert len(vals) == 1

    def test_confidence_with_mixed_flags_cumulative(self):
        q_clean = make_quality()
        q_bad = make_quality(missing=True, duplicate=True, out_of_order=True)
        assert _quality_confidence_multiplier(q_bad) < _quality_confidence_multiplier(q_clean)
