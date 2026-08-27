from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    MarketCostAssumptions,
    compute_fee_cost_bps,
)


class TestFeeCost:
    def test_default_fee_equals_expected(self):
        fee = compute_fee_cost_bps(DEFAULT_MARKET_COST_ASSUMPTIONS)
        assert fee == (10.0 + 0.5) * 1.0

    def test_fee_is_non_negative(self):
        costs = MarketCostAssumptions(fee_taker_bps=0.0, fee_network_bps=0.0)
        assert compute_fee_cost_bps(costs) == 0.0

    def test_size_multiplier_scales_fees(self):
        base = compute_fee_cost_bps(DEFAULT_MARKET_COST_ASSUMPTIONS)
        costs2x = MarketCostAssumptions(trade_size_multiplier=2.0)
        assert compute_fee_cost_bps(costs2x) == pytest.approx(base * 2.0, rel=1e-9)

    def test_deterministic_fee(self):
        vals = {compute_fee_cost_bps(DEFAULT_MARKET_COST_ASSUMPTIONS) for _ in range(10)}
        assert len(vals) == 1

    def test_zero_network_fee_ok(self):
        costs = MarketCostAssumptions(fee_network_bps=0.0)
        assert compute_fee_cost_bps(costs) == costs.fee_taker_bps * costs.trade_size_multiplier


import pytest
