from tests.opportunity.conftest import (
    make_feature_vector,
    make_quality,
)
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    MarketCostAssumptions,
    compute_slippage_cost_bps,
)


class TestSlippageCost:
    def test_default_slippage_positive(self):
        fv = make_feature_vector("bull")
        s = compute_slippage_cost_bps(fv, None, DEFAULT_MARKET_COST_ASSUMPTIONS)
        assert s >= 0.0

    def test_high_vol_higher_slippage_than_low_vol(self):
        hv = make_feature_vector("hv")
        lv = make_feature_vector("lv")
        assert compute_slippage_cost_bps(hv) > compute_slippage_cost_bps(lv)

    def test_abnormal_spread_increases_slippage(self):
        fv = make_feature_vector("bull")
        q_clean = make_quality()
        q_ab = make_quality()
        object.__setattr__(q_ab, "abnormal_spread", True)
        s_clean = compute_slippage_cost_bps(fv, q_clean)
        s_ab = compute_slippage_cost_bps(fv, q_ab)
        assert s_ab > s_clean

    def test_high_spread_feature_bps_triggers_abnormal(self):
        fv_spread = make_feature_vector("bull", custom_features={"spread_bps": 120.0})
        fv_normal = make_feature_vector("bull")
        assert compute_slippage_cost_bps(fv_spread) > compute_slippage_cost_bps(fv_normal)

    def test_slip_base_zero_returns_zero(self):
        fv = make_feature_vector("hv")
        costs = MarketCostAssumptions(slippage_base_bps=0.0)
        assert compute_slippage_cost_bps(fv, None, costs) == 0.0

    def test_vol_exponent_changes_slippage(self):
        fv = make_feature_vector("hv")
        c_low = MarketCostAssumptions(slippage_vol_exponent=1.0)
        c_high = MarketCostAssumptions(slippage_vol_exponent=2.0)
        assert compute_slippage_cost_bps(fv, None, c_high) > compute_slippage_cost_bps(fv, None, c_low)

    def test_always_non_negative(self):
        for variant in ("bull", "hv", "lv", "sideways"):
            fv = make_feature_vector(variant)
            assert compute_slippage_cost_bps(fv) >= 0.0

    def test_deterministic(self):
        fv = make_feature_vector("bull")
        vals = {compute_slippage_cost_bps(fv) for _ in range(10)}
        assert len(vals) == 1
