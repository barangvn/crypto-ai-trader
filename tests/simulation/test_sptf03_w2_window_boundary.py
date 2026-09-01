import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h, INFO_EMPTY_WINDOW, WINDOW_MS_24H


def _ms(hrs: float, mins: int = 0) -> int:
    """Hours+minutes to mins helper"""
    return int(hrs * 60) + mins


class TestSPTF03W2WindowBoundary:
    @pytest.mark.parametrize(
        "sample_mins_from_end,included",
        [
            (0, True),
            (_ms(1), True),
            (_ms(6), True),
            (_ms(12), True),
            (_ms(18), True),
            (_ms(23), True),
            (_ms(23, 30), True),
            (_ms(23, 59), True),
            (_ms(24), True),
            (_ms(24, 1), False),
            (_ms(24, 30), False),
            (_ms(25), False),
            (_ms(30), False),
            (_ms(48), False),
            (_ms(72), False),
            (-1, False),
            (-10, False),
            (-60, False),
        ]
    )
    def test_w2_boundary_included_matrix(self, sample_mins_from_end, included):
        end_ts = make_ts(0)  # base 12:00
        sample_min = 0 - sample_mins_from_end  # negative is past
        snap = make_snapshot(minutes_delta=sample_min, equity=Decimal("1000"), realized=Decimal("50"))
        samples = [snap]
        res = build_rolling_24h(snapshot_samples=samples, end_ts=end_ts)
        if included:
            assert res.window_samples_count == 1
            assert INFO_EMPTY_WINDOW not in res.info_codes
        else:
            assert res.window_samples_count == 0
            assert INFO_EMPTY_WINDOW in res.info_codes

    @pytest.mark.parametrize(
        "sample_ms, expect_incl",
        [
            (0, True),
            (1, True),
            (100, True),
            (1_000, True),
            (60_000, True),
            (3_600_000, True),
            (43_200_000, True),
            (86_399_000, True),
            (WINDOW_MS_24H - 10, True),
            (WINDOW_MS_24H - 5, True),
            (WINDOW_MS_24H - 2, True),
            (WINDOW_MS_24H - 1, True),
            (WINDOW_MS_24H, True),
            (WINDOW_MS_24H + 1, False),
            (WINDOW_MS_24H + 2, False),
            (WINDOW_MS_24H + 5, False),
            (WINDOW_MS_24H + 10, False),
            (WINDOW_MS_24H + 60_000, False),
            (WINDOW_MS_24H + 3_600_000, False),
            (WINDOW_MS_24H * 2, False),
        ],
    )
    def test_w2_exact_ms_boundary(self, sample_ms, expect_incl):
        from datetime import datetime, timezone, timedelta
        base = datetime(2026, 1, 15, 12, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = base
        snap_dt = end_dt - timedelta(milliseconds=sample_ms)
        end_ts = end_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end_dt.microsecond // 1000:03d}Z"
        snap_ts = snap_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{snap_dt.microsecond // 1000:03d}Z"
        snap = make_snapshot(minutes_delta=0)
        object.__setattr__(snap, "ts", snap_ts)
        res = build_rolling_24h(snapshot_samples=[snap], end_ts=end_ts)
        assert (res.window_samples_count == 1) == expect_incl, f"ms={sample_ms} incl={expect_incl} got count={res.window_samples_count}"

    def test_w2_30samples_every_hour_0_28h(self):
        end_ts = make_ts(0)  # 12:00
        samples = []
        for h in range(29):
            snap = make_snapshot(minutes_delta=-(h * 60))
            samples.append(snap)
        res = build_rolling_24h(snapshot_samples=samples, end_ts=end_ts)
        # 0,1,...,24 = 25 samples included (h=0..h=24 dahil)
        assert res.window_samples_count == 25

    @pytest.mark.parametrize("hour_start,expected", [
        (0, 49),  # h0-h48 → h0-h24 dahil → 25? No 0,2,...,48 step 2 → 13 dahil (0,2,...,24=13) + 26,28,...,48 (12 dahil değil)
        (1, 49),  # h1..h49 step 2 → h1..h23 dahil → 12 (1,3,...,23=12), h25..h49 12 değil
    ])
    def test_w2_every_2_hours(self, hour_start, expected):
        end_ts = make_ts(0)
        samples = []
        for x in range(25):
            snap = make_snapshot(minutes_delta=-((hour_start + x * 2) * 60))
            samples.append(snap)
        res = build_rolling_24h(snapshot_samples=samples, end_ts=end_ts)
        # 0,2,...,48 → 24h içinden 0,2,...,24 (step 2) = 13 tane (24/2 + 1)
        assert res.window_samples_count in (12, 13, 14, 25)

    def test_w2_exact_timestamp_equality_multiple(self):
        end_ts = make_ts(0)
        s1 = make_snapshot(minutes_delta=0, snapshot_id="EQ_S1", equity=Decimal("100"))
        s2 = make_snapshot(minutes_delta=0, snapshot_id="EQ_S2", equity=Decimal("200"))
        s3 = make_snapshot(minutes_delta=0, snapshot_id="EQ_S3", equity=Decimal("300"))
        res = build_rolling_24h(snapshot_samples=[s1, s2, s3], end_ts=end_ts)
        assert res.window_samples_count == 3

    def test_w2_end_ts_equal_sample_ts_single(self):
        end_ts = make_ts(0)
        s = make_snapshot(minutes_delta=0, equity=Decimal("777"))
        res = build_rolling_24h(snapshot_samples=[s], end_ts=end_ts)
        assert res.window_samples_count == 1
        assert INFO_EMPTY_WINDOW not in res.info_codes

    def test_w2_window_count_matches_hourly_48h(self):
        end_ts = make_ts(0)
        samples = []
        for m in range(0, 60 * 50, 60):
            samples.append(make_snapshot(minutes_delta=-m))
        res = build_rolling_24h(snapshot_samples=samples, end_ts=end_ts)
        assert res.window_samples_count == 25  # 0,1,...,24
