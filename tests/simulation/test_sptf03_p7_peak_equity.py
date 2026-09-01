import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


class TestSPTF03P7RollingPeak:
    def test_empty_window_peak_zero(self):
        res = build_rolling_24h(snapshot_samples=[make_snapshot(minutes_delta=-10000)], end_ts=make_ts(0))
        assert res.rolling_peak_equity_quote == Decimal("0")

    def test_single_sample_peak_self(self):
        s = make_snapshot(minutes_delta=-10, equity=Decimal("100"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.rolling_peak_equity_quote == Decimal("100")

    @pytest.mark.parametrize(
        "eq_list,expected_peak",
        [
            ([100, 120, 90, 150, 130], Decimal("150")),
            ([50, 60, 70, 80], Decimal("80")),  # monoton artan peak = last
            ([80, 70, 60, 50], Decimal("80")),  # monoton azalan peak = first
            ([10, 50, 20, 50, 30], Decimal("50")),  # tie -> max
        ],
    )
    def test_peak_matrix(self, eq_list, expected_peak):
        snaps = []
        for idx, eq in enumerate(eq_list):
            snaps.append(make_snapshot(minutes_delta=-(len(eq_list)-1-idx)*60, equity=Decimal(str(eq))))
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.rolling_peak_equity_quote == expected_peak

    def test_peak_vs_session_peak_separated_acp04(self):
        # Session peak (PortfolioSnapshot.peak_equity_quote) = 5000
        # Rolling window peak = 150 (window içindeki max)
        s1 = make_snapshot(minutes_delta=-60, equity=Decimal("100"), peak=Decimal("5000"))
        s2 = make_snapshot(minutes_delta=-30, equity=Decimal("150"), peak=Decimal("5000"))
        s3 = make_snapshot(minutes_delta=0, equity=Decimal("120"), peak=Decimal("5000"))
        res = build_rolling_24h(snapshot_samples=[s1, s2, s3], end_ts=make_ts(0))
        assert res.rolling_peak_equity_quote == Decimal("150")
        # Snapshot peak alanı değişmedi session peak 5000
        for s in [s1, s2, s3]:
            assert s.peak_equity_quote == Decimal("5000")
        # İkisi AYRIMI
        assert res.rolling_peak_equity_quote != s3.peak_equity_quote

    def test_100sample_window_peak_middle(self):
        eq = []
        for i in range(100):
            if i == 49:
                eq.append(Decimal("9999"))
            else:
                eq.append(Decimal(str(1000 + i)))
        snaps = [make_snapshot(minutes_delta=-(99-i)*5, equity=eq[i]) for i in range(100)]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.rolling_peak_equity_quote == Decimal("9999")
