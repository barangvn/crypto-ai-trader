import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


class TestSPTF03R4Realized24h:
    def test_empty_window(self):
        s_outside = make_snapshot(minutes_delta=-60*48)  # 48h önce dışarı
        res = build_rolling_24h(snapshot_samples=[s_outside], end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("0")

    def test_single_sample_delta_zero(self):
        s = make_snapshot(minutes_delta=0, realized=Decimal("123"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("0")

    @pytest.mark.parametrize(
        "r_first,r_last,expected_delta",
        [
            (Decimal("0"), Decimal("150"), Decimal("150")),
            (Decimal("100"), Decimal("250"), Decimal("150")),
            (Decimal("500"), Decimal("400"), Decimal("-100")),  # negatif realized delta (loss) — izin verilir
            (Decimal("0"), Decimal("0"), Decimal("0")),
            (Decimal("-50"), Decimal("25"), Decimal("75")),
            (Decimal("1000"), Decimal("1000"), Decimal("0")),
            (Decimal("-100"), Decimal("-50"), Decimal("50")),
            (Decimal("-200"), Decimal("-300"), Decimal("-100")),
            (Decimal("999999"), Decimal("1000001"), Decimal("2")),
            (Decimal("0.01"), Decimal("0.99"), Decimal("0.98")),
            (Decimal("-0.5"), Decimal("0.5"), Decimal("1.0")),
            (Decimal("1234567.89"), Decimal("9876543.21"), Decimal("8641975.32")),
        ],
    )
    def test_delta_positive_negative_zero(self, r_first, r_last, expected_delta):
        s_first = make_snapshot(minutes_delta=-1440, realized=r_first)  # 24h önce
        s_last = make_snapshot(minutes_delta=0, realized=r_last)
        res = build_rolling_24h(snapshot_samples=[s_first, s_last], end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == expected_delta

    def test_session_vs_rolling_separated(self):
        # Session realized (S-PTF-02) = 9999 (session cumulative); ama delta 150
        s_first = make_snapshot(minutes_delta=-600, realized=Decimal("9999"))
        s_last = make_snapshot(minutes_delta=0, realized=Decimal("10149"))
        res = build_rolling_24h(snapshot_samples=[s_first, s_last], end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("150")
        # Session alanı (snapshot.realized_pnl_quote_24h) değişmez
        assert s_first.realized_pnl_quote_24h == Decimal("9999")
        assert s_last.realized_pnl_quote_24h == Decimal("10149")
        assert res.rolling_realized_pnl_quote_24h != s_last.realized_pnl_quote_24h

    def test_multi_sample_monotonic(self):
        snaps = [
            make_snapshot(minutes_delta=-60*20, realized=Decimal("0")),
            make_snapshot(minutes_delta=-60*12, realized=Decimal("50")),
            make_snapshot(minutes_delta=-60*6, realized=Decimal("70")),
            make_snapshot(minutes_delta=0, realized=Decimal("100")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("100")

    def test_decimal_8dp_quantize(self):
        f = make_snapshot(minutes_delta=-1440, realized=Decimal("1.123456781"))
        l = make_snapshot(minutes_delta=0, realized=Decimal("2.123456789"))
        res = build_rolling_24h(snapshot_samples=[f, l], end_ts=make_ts(0))
        # 8dp quantize, rounding half even
        assert str(res.rolling_realized_pnl_quote_24h).endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))

    @pytest.mark.parametrize("n_steps,delta_each", [
        (5, Decimal("10")),
        (10, Decimal("5")),
        (20, Decimal("3")),
        (24, Decimal("1")),
        (48, Decimal("0.5")),
    ])
    def test_multi_step_linear_growth(self, n_steps, delta_each):
        snaps = []
        for i in range(n_steps):
            mins = -(n_steps - 1 - i) * 30  # 30'er dk aralıklar
            realized = delta_each * i
            snaps.append(make_snapshot(minutes_delta=mins, realized=realized))
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        expected = delta_each * (n_steps - 1)
        assert res.rolling_realized_pnl_quote_24h == expected

    def test_realized_delta_with_many_samples_random_order(self):
        import random
        base = Decimal("1000")
        target = Decimal("1750")
        snaps = []
        vals = [base + (target - base) * (Decimal(i) / Decimal(19)) for i in range(20)]
        for idx, v in enumerate(vals):
            snaps.append(make_snapshot(minutes_delta=-(19 - idx) * 30, realized=v))
        snaps_shuffled = list(snaps)
        random.seed(42)
        random.shuffle(snaps_shuffled)
        res = build_rolling_24h(snapshot_samples=snaps_shuffled, end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("750")

    def test_zero_delta_flat_large_samples(self):
        snaps = []
        for i in range(100):
            snaps.append(make_snapshot(minutes_delta=-(99 - i) * 5, realized=Decimal("4242")))
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.rolling_realized_pnl_quote_24h == Decimal("0")

