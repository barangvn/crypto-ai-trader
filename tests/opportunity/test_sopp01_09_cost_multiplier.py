from app.opportunity.base import (
    DEFAULT_SCORING_WEIGHTS,
    compute_cost_multiplier,
)


class TestCostMultiplier:
    def test_positive_net_uses_positive_mult(self):
        assert compute_cost_multiplier(12.5, DEFAULT_SCORING_WEIGHTS) == 1.0

    def test_zero_net_uses_negative_mult(self):
        assert compute_cost_multiplier(0.0, DEFAULT_SCORING_WEIGHTS) == DEFAULT_SCORING_WEIGHTS.net_negative_multiplier

    def test_negative_net_uses_negative_mult(self):
        assert compute_cost_multiplier(-7.0, DEFAULT_SCORING_WEIGHTS) == DEFAULT_SCORING_WEIGHTS.net_negative_multiplier

    def test_positive_is_higher_than_negative(self):
        pos = compute_cost_multiplier(1.0)
        neg = compute_cost_multiplier(-1.0)
        assert pos > neg

    def test_deterministic(self):
        assert len({compute_cost_multiplier(10.0) for _ in range(15)}) == 1
        assert len({compute_cost_multiplier(-1.0) for _ in range(15)}) == 1
