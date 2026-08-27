from tests.opportunity.conftest import (
    make_feature_vector,
    make_quality,
)
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    MarketCostAssumptions,
    compute_spread_cost_bps,
)


class TestSpreadCost:
    def test_spread_from_feature(self):
        fv = make_feature_vector("bull", custom_features={"spread_bps": 6.0})
        s = compute_spread_cost_bps(fv, None, DEFAULT_MARKET_COST_ASSUMPTIONS)
        assert s == 6.0 * 0.5

    def test_spread_below_min_uses_min(self):
        costs = MarketCostAssumptions(min_spread_bps=5.0)
        fv = make_feature_vector("bull", custom_features={"spread_bps": 2.0})
        s = compute_spread_cost_bps(fv, None, costs)
        assert s == 5.0 * 0.5

    def test_missing_spread_uses_min(self):
        feats = make_feature_vector("bull").features
        feats.pop("spread_bps", None)
        fv = make_feature_vector("bull", custom_features=feats)
        costs = MarketCostAssumptions(min_spread_bps=2.0)
        assert compute_spread_cost_bps(fv, None, costs) == 2.0 * 0.5

    def test_nan_spread_uses_min(self):
        fv = make_feature_vector("bull", custom_features={"spread_bps": float("nan")})
        costs = MarketCostAssumptions(min_spread_bps=3.0)
        s = compute_spread_cost_bps(fv, None, costs)
        assert s == 3.0 * 0.5

    def test_abnormal_spread_flag_13x(self):
        fv = make_feature_vector("bull", custom_features={"spread_bps": 10.0})
        q = make_quality()
        object.__setattr__(q, "abnormal_spread", True)
        normal = compute_spread_cost_bps(fv, None)
        ab = compute_spread_cost_bps(fv, q)
        assert ab == pytest.approx(normal * 1.3, rel=1e-9)

    def test_never_negative(self):
        for v in ("bull", "hv", "lv", "sideways"):
            assert compute_spread_cost_bps(make_feature_vector(v)) >= 0.0

    def test_deterministic(self):
        fv = make_feature_vector("bull")
        assert len({compute_spread_cost_bps(fv) for _ in range(10)}) == 1


import pytest
