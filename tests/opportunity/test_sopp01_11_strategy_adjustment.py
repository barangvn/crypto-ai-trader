from tests.opportunity.conftest import make_strategy_signal
from app.opportunity.base import compute_strategy_adjustment


class TestStrategyAdjustment:
    def test_trend_id_highest_when_high_conf(self):
        sig = make_strategy_signal(strategy_id="trend_following_v1", confidence=1.0)
        adj, ref = compute_strategy_adjustment(sig)
        assert adj == pytest.approx(1.0)
        assert "trend_following_v1" in ref
        assert "str_01_v1" in ref

    def test_momentum_slightly_lower(self):
        sig_mom = make_strategy_signal(strategy_id="momentum_v1", confidence=1.0)
        sig_trend = make_strategy_signal(strategy_id="trend_following_v1", confidence=1.0)
        adj_mom, _ = compute_strategy_adjustment(sig_mom)
        adj_trend, _ = compute_strategy_adjustment(sig_trend)
        assert adj_mom < adj_trend
        assert adj_mom == pytest.approx(0.95, rel=1e-9)

    def test_unknown_gets_low_penalty(self):
        sig = make_strategy_signal(strategy_id="unknown_v1", confidence=1.0)
        adj, ref = compute_strategy_adjustment(sig)
        assert 0.25 <= adj <= 0.45
        assert "unknown_v1" in ref

    def test_zero_confidence_halves(self):
        sig = make_strategy_signal(strategy_id="trend_following_v1", confidence=0.0)
        adj, _ = compute_strategy_adjustment(sig)
        assert adj == pytest.approx(0.5)

    def test_strategy_ref_contains_version(self):
        sig = make_strategy_signal(strategy_id="momentum_v1")
        _, ref = compute_strategy_adjustment(sig)
        assert "momentum_v1:str_01_v1" == ref

    def test_deterministic(self):
        sig = make_strategy_signal(strategy_id="trend_following_v1")
        vals = {compute_strategy_adjustment(sig) for _ in range(10)}
        assert len(vals) == 1


import pytest
