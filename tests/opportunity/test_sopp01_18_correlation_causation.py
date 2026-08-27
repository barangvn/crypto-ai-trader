import re
from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")


class TestCorrelationCausation:
    def test_opp_correlation_id_equals_signal(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, correlation_id="CORR_ABC_123_XYZ")
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.correlation_id == sig.correlation_id

    def test_opp_causation_id_non_empty_ulidish(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, correlation_id="01920000-0000-7000-8000-000000000AAA")
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.causation_id is not None
        assert ULIDISH_RE.match(opp.causation_id)

    def test_causation_id_uses_signal_id_when_available(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(
            direction=SignalDirection.LONG,
            signal_id="SIG_DIRECT_ID_001",
        )
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.causation_id == "SIG_DIRECT_ID_001"

    def test_10x_same_corr_and_caus(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_id="PARENT_SIG_888")
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
        corrs = set()
        caus = set()
        for _ in range(10):
            opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
            corrs.add(opp.correlation_id)
            caus.add(opp.causation_id)
        assert len(corrs) == 1
        assert len(caus) == 1

    def test_quality_preserves_corr_caus_unchanged(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(signal_id="PARENT_SIG_1")
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp1 = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        q = make_quality(stale=True, missing=True)
        opp2 = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", q, "2026-08-26T10:00:00.000Z")
        assert opp1.correlation_id == opp2.correlation_id
