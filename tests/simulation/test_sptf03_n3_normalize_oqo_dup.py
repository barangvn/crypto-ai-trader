import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h, INFO_DUP_SNAPSHOT_ID_DROPPED


class TestSPTF03N3Normalize:
    def test_oos_reverse_sorted(self):
        # reversed: new to old → sort sonrası düzgün ASC
        s1 = make_snapshot(minutes_delta=0, realized=Decimal("100"))
        s2 = make_snapshot(minutes_delta=-60, realized=Decimal("50"))
        s3 = make_snapshot(minutes_delta=-120, realized=Decimal("10"))
        # reverse (S1, S2, S3) → sıralama ASC: s3,s2,s1
        samples_r = [s1, s2, s3]
        res = build_rolling_24h(snapshot_samples=samples_r, end_ts=make_ts(0))
        assert res.window_samples_count == 3
        assert res.rolling_realized_pnl_quote_24h == Decimal("90")  # 100-10
        # original list unchanged
        assert samples_r[0] is s1

    def test_oo0_mixed(self):
        s_a = make_snapshot(minutes_delta=-60)  # 1 saat önce (2)
        s_b = make_snapshot(minutes_delta=0)    # şimdi (3)
        s_c = make_snapshot(minutes_delta=-180) # 3 saat önce (1)
        mix = [s_b, s_c, s_a]
        res = build_rolling_24h(snapshot_samples=mix, end_ts=make_ts(0))
        assert res.window_samples_count == 3

    def test_dup_timestamp_ulid_tiebreak(self):
        # aynı dakika, farklı snapshot_id → sıralama snapshot_id ASC
        s_x = make_snapshot(minutes_delta=-10, snapshot_id="SNAP_A_1000")
        s_y = make_snapshot(minutes_delta=-10, snapshot_id="SNAP_B_0500")
        lst = [s_x, s_y]
        res = build_rolling_24h(snapshot_samples=lst, end_ts=make_ts(0))
        assert res.window_samples_count == 2

    def test_dup_same_snapshot_id_keep_first(self):
        snap_id = "SNAP_DUP_00001"
        s1 = make_snapshot(minutes_delta=-10, snapshot_id=snap_id, realized=Decimal("10"))
        s2 = make_snapshot(minutes_delta=-10, snapshot_id=snap_id, realized=Decimal("9999"))  # ikinci drop
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        assert res.window_samples_count == 1
        assert res.rolling_realized_pnl_quote_24h == Decimal("0")  # tek sample delta 0
        assert INFO_DUP_SNAPSHOT_ID_DROPPED in res.info_codes

    def test_missing_samples_no_interpolation(self):
        # 0, -60, -600 (=10 saat — 0-24 dahil), -1440 (= 24 saat) — missing 1-59. dk aralıkları NO interpolasyon
        snaps = [
            make_snapshot(minutes_delta=0, realized=Decimal("100")),
            make_snapshot(minutes_delta=-60, realized=Decimal("50")),
            make_snapshot(minutes_delta=-1440, realized=Decimal("10")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.window_samples_count == 3
        assert res.rolling_realized_pnl_quote_24h == Decimal("90")  # 100 - 10

    @pytest.mark.parametrize("order", [[0,1,2],[2,1,0],[1,0,2]])
    def test_any_order_deterministic_result(self, order):
        base = [
            make_snapshot(minutes_delta=0, realized=Decimal("5")),
            make_snapshot(minutes_delta=-120, realized=Decimal("3")),
            make_snapshot(minutes_delta=-360, realized=Decimal("1")),
        ]
        samples = [base[i] for i in order]
        res = build_rolling_24h(snapshot_samples=samples, end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("4")  # 5 - 1
