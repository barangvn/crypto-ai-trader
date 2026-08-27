import hashlib
from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


MATRIX = [
    ("trend_following_v1", MarketRegimeState.BULL, None),
    ("momentum_v1", MarketRegimeState.LOW_VOLATILITY, None),
    ("trend_following_v1", MarketRegimeState.HIGH_VOLATILITY, "stale"),
    ("momentum_v1", MarketRegimeState.SIDEWAYS, "degraded"),
    ("trend_following_v1", MarketRegimeState.TRANSITION_UNCERTAIN, None),
]


class TestDeterminismTenTimes:
    def test_10x_same_sha(self):
        scorer = make_default_scorer()
        for strat_id, regime_state, q_flag in MATRIX:
            sig = make_strategy_signal(
                strategy_id=strat_id, direction=SignalDirection.LONG, signal_strength=0.8, confidence=0.85
            )
            fv = make_feature_vector("bull")
            regime = make_market_regime(regime_state, confidence=0.85, strength=0.8)
            q = None if not q_flag else make_quality(**{q_flag: True})
            shas = set()
            sds = []
            notes = []
            for _ in range(10):
                opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
                shas.add(opp.schema_sha256())
                sds.append(opp.to_sorted_dict())
                notes.append(opp.explainability_note)
            assert len(shas) == 1
            for sd in sds[1:]:
                assert sd == sds[0]
            assert len(set(notes)) == 1

    def test_sha_matches_sorted_dict_256(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(strategy_id="trend_following_v1", direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        import json
        payload = json.dumps(opp.to_sorted_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        assert opp.schema_sha256() == expected
