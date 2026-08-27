from app.opportunity.base import compute_net_expected_edge_bps


class TestNetEdge:
    def test_net_edge_basic_subtraction(self):
        gross, fee, slip, spread, lat = 100.0, 10.0, 3.0, 2.0, 1.0
        net, total_cost = compute_net_expected_edge_bps(gross, fee, slip, spread, lat)
        assert total_cost == pytest.approx(16.0)
        assert net == pytest.approx(84.0)

    def test_negative_net_when_costs_exceed_gross(self):
        net, tc = compute_net_expected_edge_bps(5.0, 4.0, 1.0, 1.0, 0.5)
        assert net < 0.0
        assert tc == 6.5

    def test_zero_gross_positive_costs_yields_negative(self):
        net, tc = compute_net_expected_edge_bps(0.0, 1.0, 0.5, 0.2, 0.1)
        assert net == pytest.approx(-1.8)
        assert tc == 1.8

    def test_all_zero(self):
        net, tc = compute_net_expected_edge_bps(0.0, 0.0, 0.0, 0.0, 0.0)
        assert net == 0.0 and tc == 0.0

    def test_negative_cost_clamped_to_zero(self):
        # negative cost provided externally is invalid; clamp happens inside total_cost
        net, tc = compute_net_expected_edge_bps(50.0, -1.0, -0.5, -0.2, -0.1)
        assert tc >= 0.0

    def test_deterministic(self):
        vals = {compute_net_expected_edge_bps(42.0, 1.0, 2.0, 3.0, 4.0) for _ in range(10)}
        assert len(vals) == 1


import pytest
