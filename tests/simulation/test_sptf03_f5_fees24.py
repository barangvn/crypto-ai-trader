import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h, INFO_NEGATIVE_FEES_DELTA_CLAMPED


class TestSPTF03F5Fees24h:
    def test_empty(self):
        res = build_rolling_24h(snapshot_samples=[], end_ts=make_ts(0))
        assert res.rolling_fees_quote_24h == Decimal("0")

    def test_single_sample_zero(self):
        s = make_snapshot(minutes_delta=0, fees_total=Decimal("100"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.rolling_fees_quote_24h == Decimal("0")

    @pytest.mark.parametrize(
        "first,last,expected",
        [
            (Decimal("10"), Decimal("25"), Decimal("15")),
            (Decimal("0"), Decimal("10.5"), Decimal("10.5")),
            (Decimal("100.1"), Decimal("100.1"), Decimal("0")),
        ],
    )
    def test_fees_delta(self, first, last, expected):
        sf = make_snapshot(minutes_delta=-1440, fees_total=first)
        sl = make_snapshot(minutes_delta=0, fees_total=last)
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert res.rolling_fees_quote_24h == expected

    def test_negative_fees_delta_clamp_adn03(self):
        sf = make_snapshot(minutes_delta=-120, fees_total=Decimal("100"))  # ilk fee 100
        sl = make_snapshot(minutes_delta=0, fees_total=Decimal("50"))    # son 50 — düşmüş
        res = build_rolling_24h(snapshot_samples=[sf, sl], end_ts=make_ts(0))
        assert res.rolling_fees_quote_24h == Decimal("0")
        assert INFO_NEGATIVE_FEES_DELTA_CLAMPED in res.info_codes

    def test_no_double_count_dup(self):
        s1 = make_snapshot(minutes_delta=-10, snapshot_id="SNAP_DUP_FEE", fees_total=Decimal("10"))
        s2 = make_snapshot(minutes_delta=-10, snapshot_id="SNAP_DUP_FEE", fees_total=Decimal("1000"))  # drop
        sl = make_snapshot(minutes_delta=0, snapshot_id="SNAP_END", fees_total=Decimal("20"))
        res = build_rolling_24h(snapshot_samples=[s1, s2, sl], end_ts=make_ts(0))
        # s1 ilk tutulan, s2 drop → delta = 20-10 = 10
        assert res.rolling_fees_quote_24h == Decimal("10")

    def test_30samples_fees_monotonic(self):
        # i=0 → minutes_delta = -(30-0)*30 = -900 (eski)
        # i=30 → minutes_delta = 0 (yeni, fees 60)
        # ilk sample fees 0, son sample fees 60 → delta 60
        snaps = [make_snapshot(minutes_delta=-(30-i)*30, fees_total=Decimal(str(i*2))) for i in range(31)]  # 0,2,4...60
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.rolling_fees_quote_24h == Decimal("60")
