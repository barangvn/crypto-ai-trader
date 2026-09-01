import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


class TestSPTF03DD8Drawdown:
    def test_empty_dd_zero(self):
        res = build_rolling_24h(snapshot_samples=[make_snapshot(minutes_delta=-99999)], end_ts=make_ts(0))
        assert res.rolling_drawdown_pct == 0.0

    def test_single_sample_eq_peak_end_dd_zero(self):
        s = make_snapshot(minutes_delta=-10, equity=Decimal("100"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.rolling_drawdown_pct == 0.0

    @pytest.mark.parametrize(
        "eq_list,expected_dd",
        [
            ([100, 120, 90, 150, 130], 0.13333333333333333),  # peak 150, end 130 → (150-130)/150
            ([150, 120, 90, 60], 0.6),  # peak 150 end 60 → (150-60)/150 = 0.6
            ([100, 200], 0.0),  # end peak
            ([200, 100], 0.5),
        ],
    )
    def test_dd_matrix(self, eq_list, expected_dd):
        snaps = [make_snapshot(minutes_delta=-(len(eq_list)-1-i)*60, equity=Decimal(str(eq_list[i]))) for i in range(len(eq_list))]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert round(res.rolling_drawdown_pct, 6) == round(expected_dd, 6)

    def test_rolling_dd_in_0_1_range_clamped(self):
        # negatif olmamalı; >1 olmamalı
        s1 = make_snapshot(minutes_delta=-30, equity=Decimal("1"))
        s2 = make_snapshot(minutes_delta=0, equity=Decimal("0"))
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        assert 0.0 <= res.rolling_drawdown_pct <= 1.0

    def test_session_dd_vs_rolling_dd_separated_acdd06(self):
        # Snapshot drawdown session lifetime = 0.35
        # Rolling window drawdown = 0.2
        s1 = make_snapshot(minutes_delta=-60, equity=Decimal("150"), drawdown=0.35)
        s2 = make_snapshot(minutes_delta=0, equity=Decimal("120"), drawdown=0.35)
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        # peak window = 150, end 120 → (150-120)/150 = 0.2
        assert round(res.rolling_drawdown_pct, 2) == 0.2
        # snapshot drawdownlar değişmedi
        assert s1.drawdown_pct == 0.35
        assert s2.drawdown_pct == 0.35
        assert res.rolling_drawdown_pct != s2.drawdown_pct

    def test_peak_zero_guard_divbyzero(self):
        s1 = make_snapshot(minutes_delta=-60, equity=Decimal("0"))
        s2 = make_snapshot(minutes_delta=0, equity=Decimal("0"))
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        assert res.rolling_drawdown_pct == 0.0
