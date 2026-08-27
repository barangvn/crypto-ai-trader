import re
from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


POLICY_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?$")
SYMBOL_REF_RE = re.compile(r"^[A-Z0-9]+_[A-Z0-9]+$")


class TestOpportunityScoreContract:
    def test_required_fields_all_present(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        # Required fields per S-CON-02C
        assert opp.score_id is not None and len(opp.score_id) >= 8
        assert 0.0 <= opp.score_total <= 1.0
        assert 0.0 <= opp.confidence <= 1.0
        assert isinstance(opp.actionable, bool)
        assert isinstance(opp.reject_reasons, list)
        assert isinstance(opp.score_components, dict)
        assert isinstance(opp.expected_edge_bps, (int, float))
        assert isinstance(opp.expected_cost_bps, (int, float))
        assert SYMBOL_REF_RE.match(opp.symbol_ref)
        assert isinstance(opp.regime_ref, str) and opp.regime_ref
        assert isinstance(opp.strategy_ref, str) and opp.strategy_ref
        assert POLICY_VERSION_RE.match(opp.policy_version)
        assert len(opp.correlation_id) >= 8
        assert len(opp.causation_id) >= 8
        assert opp.created_ts.endswith("Z") and "T" in opp.created_ts

    def test_quality_flags_none_acceptable(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.quality_flags is None

    def test_expected_hold_bars_default_zero(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal()
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT")
        assert opp.expected_hold_bars == 0

    def test_eth_symbol_ref_passes_2part(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "ETH_USDT")
        assert SYMBOL_REF_RE.match(opp.symbol_ref)

    def test_schema_sha_64hex(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal()
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT")
        sha = opp.schema_sha256()
        assert re.match(r"^[0-9a-f]{64}$", sha)
