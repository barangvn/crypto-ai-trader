import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h, INFO_ZERO_BASELINE_EQUITY, INFO_EMPTY_WINDOW


class TestSPTF03RET6Return:
    def test_empty_return_zero(self):
        res = build_rolling_24h(snapshot_samples=[make_snapshot(minutes_delta=-60*48)], end_ts=make_ts(0))
        assert res.rolling_return_pct == 0.0
        assert INFO_EMPTY_WINDOW in res.info_codes

    def test_single_sample_return_zero(self):
        s = make_snapshot(minutes_delta=0, equity=Decimal("1000"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.rolling_return_pct == 0.0

    @pytest.mark.parametrize(
        "start_eq,end_eq,expected_approx",
        [
            (Decimal("1000"), Decimal("1100"), 0.1),
            (Decimal("1000"), Decimal("900"), -0.1),
            (Decimal("10000"), Decimal("10000"), 0.0),
            (Decimal("100"), Decimal("105"), 0.05),
            (Decimal("100"), Decimal("50"), -0.5),
            (Decimal("1"), Decimal("3"), 2.0),
        ],
    )
    def test_return_formula(self, start_eq, end_eq, expected_approx):
        sf = make_snapshot(minutes_delta=-1440, equity=start_eq)
        sl = make_snapshot(minutes_delta=0, equity=end_eq)
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert round(res.rolling_return_pct, 6) == round(expected_approx, 6)

    def test_zero_baseline_return_zero_safe(self):
        sf = make_snapshot(minutes_delta=-1440, equity=Decimal("0"))
        sl = make_snapshot(minutes_delta=0, equity=Decimal("1000"))
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert res.rolling_return_pct == 0.0
        assert INFO_ZERO_BASELINE_EQUITY in res.info_codes

    def test_return_float_type_not_decimal(self):
        sf = make_snapshot(minutes_delta=-1440, equity=Decimal("100"))
        sl = make_snapshot(minutes_delta=0, equity=Decimal("110"))
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert isinstance(res.rolling_return_pct, float)
        assert not isinstance(res.rolling_return_pct, Decimal)

    def test_return_signed_negative(self):
        sf = make_snapshot(minutes_delta=-60, equity=Decimal("1000"))
        sl = make_snapshot(minutes_delta=0, equity=Decimal("750"))
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert res.rolling_return_pct < 0.0
        assert round(res.rolling_return_pct, 2) == -0.25

    def test_20sample_window_end_start_correct(self):
        snaps = []
        for i in range(20):
            eq = Decimal(str(1000 + i * 10))  # 1000, 1010, ... 1190
            snaps.append(make_snapshot(minutes_delta=-60*(19-i), equity=eq))
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert round(res.rolling_return_pct, 4) == round(190 / 1000, 4)
