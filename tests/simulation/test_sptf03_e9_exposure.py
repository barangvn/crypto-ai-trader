import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


class TestSPTF03E9Exposure:
    def test_empty_all_zero(self):
        res = build_rolling_24h(snapshot_samples=[make_snapshot(minutes_delta=-10000)], end_ts=make_ts(0))
        assert res.exposure_max_24h == Decimal("0")
        assert res.exposure_avg_24h == Decimal("0")
        assert res.exposure_end_24h == Decimal("0")

    def test_single_sample_all_same(self):
        s = make_snapshot(minutes_delta=0, exposure=Decimal("100"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.exposure_max_24h == Decimal("100")
        assert res.exposure_avg_24h == Decimal("100")
        assert res.exposure_end_24h == Decimal("100")

    @pytest.mark.parametrize(
        "exp_list,max_e,avg_e,end_e",
        [
            ([100, 50, 150], Decimal("150"), Decimal("100"), Decimal("150")),
            ([50, 100, 150, 200], Decimal("200"), Decimal("125"), Decimal("200")),
            ([1, 2, 3], Decimal("3"), Decimal("2"), Decimal("3")),
            ([0, 0, 0], Decimal("0"), Decimal("0"), Decimal("0")),
            ([200, 100, 50, 25], Decimal("200"), Decimal("93.75"), Decimal("25")),
            ([5, 5, 5, 5, 5, 5], Decimal("5"), Decimal("5"), Decimal("5")),
            ([1000, 0, 1000, 0], Decimal("1000"), Decimal("500"), Decimal("0")),
            ([42], Decimal("42"), Decimal("42"), Decimal("42")),
            ([99, 1], Decimal("99"), Decimal("50"), Decimal("1")),
            ([1, 99], Decimal("99"), Decimal("50"), Decimal("99")),
            ([7, 7, 7], Decimal("7"), Decimal("7"), Decimal("7")),
            ([1000000, 2000000, 1500000], Decimal("2000000"), Decimal("1500000"), Decimal("1500000")),
        ],
    )
    def test_3_exposure_matrix(self, exp_list, max_e, avg_e, end_e):
        snaps = [make_snapshot(minutes_delta=-(len(exp_list)-1-i)*60, exposure=Decimal(str(exp_list[i]))) for i in range(len(exp_list))]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h == max_e
        assert res.exposure_avg_24h == avg_e
        assert res.exposure_end_24h == end_e

    def test_exposure_decimal_nonnegative(self):
        snaps = [make_snapshot(minutes_delta=-(i*30), exposure=Decimal(str(i*5))) for i in range(21)]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h >= 0
        assert res.exposure_avg_24h >= 0
        assert res.exposure_end_24h >= 0

    def test_avg_quantize_8dp(self):
        snaps = [
            make_snapshot(minutes_delta=-60, exposure=Decimal("1")),
            make_snapshot(minutes_delta=-30, exposure=Decimal("1")),
            make_snapshot(minutes_delta=0, exposure=Decimal("2")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        # avg = 4/3 = 1.33333333 quantize 8dp
        assert res.exposure_avg_24h == Decimal("1.33333333")

    def test_exposure_end_is_last_exposure(self):
        snaps = [
            make_snapshot(minutes_delta=-120, exposure=Decimal("100")),
            make_snapshot(minutes_delta=-60, exposure=Decimal("999")),
            make_snapshot(minutes_delta=0, exposure=Decimal("555")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_end_24h == Decimal("555")

    @pytest.mark.parametrize("peak_pos", ["first", "middle", "last"])
    def test_exposure_max_peak_at_different_positions(self, peak_pos):
        base_exp = 100
        peak_exp = 9999
        n = 11
        if peak_pos == "first":
            exp_list = [peak_exp] + [base_exp] * (n - 1)
        elif peak_pos == "middle":
            exp_list = [base_exp] * 5 + [peak_exp] + [base_exp] * 5
        else:  # last
            exp_list = [base_exp] * (n - 1) + [peak_exp]
        snaps = [make_snapshot(minutes_delta=-((n - 1 - i) * 30), exposure=Decimal(str(exp_list[i]))) for i in range(n)]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h == Decimal(str(peak_exp))
        if peak_pos == "last":
            assert res.exposure_end_24h == Decimal(str(peak_exp))

    def test_exposure_large_values_1m_1b(self):
        snaps = [
            make_snapshot(minutes_delta=-120, exposure=Decimal("1000000")),
            make_snapshot(minutes_delta=-60, exposure=Decimal("500000000")),
            make_snapshot(minutes_delta=0, exposure=Decimal("1000000000")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h == Decimal("1000000000")
        assert res.exposure_end_24h == Decimal("1000000000")
        # avg = 1501000000 / 3 = 500333333.33333333
        assert res.exposure_avg_24h == Decimal("500333333.33333333")

    @pytest.mark.parametrize("n", [1, 2, 4, 7, 12, 24, 48, 96])
    def test_exposure_hourly_samples_over_window(self, n):
        snaps = []
        for i in range(n):
            exp = Decimal(str(100 + i * 10))
            snaps.append(make_snapshot(minutes_delta=-((n - 1 - i) * 60), exposure=exp))
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h >= 0
        assert res.exposure_avg_24h >= 0
        assert res.exposure_end_24h >= 0
        # end = son sample'ın exposure (en yüksek, çünkü monotonic artıyor)
        assert res.exposure_end_24h == Decimal(str(100 + (n - 1) * 10))

