from tests.opportunity.conftest import make_feature_vector
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    MarketCostAssumptions,
    compute_latency_impact_bps,
)


class TestLatencyImpact:
    def test_latency_increases_with_ratio(self):
        fv = make_feature_vector("bull")
        c1 = MarketCostAssumptions(latency_ms=1.0)
        c2 = MarketCostAssumptions(latency_ms=100.0)
        assert compute_latency_impact_bps(fv, c2) >= compute_latency_impact_bps(fv, c1)

    def test_sensitivity_multiplies(self):
        fv = make_feature_vector("hv")
        c_low = MarketCostAssumptions(latency_sensitivity=0.5)
        c_high = MarketCostAssumptions(latency_sensitivity=4.0)
        assert compute_latency_impact_bps(fv, c_high) >= compute_latency_impact_bps(fv, c_low)

    def test_zero_vol_returns_zeroish(self):
        fv = make_feature_vector("bull", custom_features={"volatility_20_bps": 0.001})
        c = DEFAULT_MARKET_COST_ASSUMPTIONS
        assert compute_latency_impact_bps(fv, c) >= 0.0

    def test_never_negative(self):
        for v in ("bull", "hv", "lv", "sideways"):
            assert compute_latency_impact_bps(make_feature_vector(v)) >= 0.0

    def test_deterministic(self):
        fv = make_feature_vector("bull")
        assert len({compute_latency_impact_bps(fv) for _ in range(10)}) == 1

    def test_gross_scale_affects(self):
        fv = make_feature_vector("bull")
        c1 = MarketCostAssumptions(gross_edge_scale_bps=25.0)
        c2 = MarketCostAssumptions(gross_edge_scale_bps=100.0)
        ratio = compute_latency_impact_bps(fv, c2) / max(compute_latency_impact_bps(fv, c1), 1e-9)
        assert abs(ratio - 4.0) < 0.2
