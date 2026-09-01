import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


class TestSPTF03M10MultiSymbol:
    def test_corr_preservation_per_sample(self):
        s1 = make_snapshot(minutes_delta=-60, corr="CORR_BTC_SPTF03_M10_001", caus="CAUS_BTC_SPTF03_M10_001")
        s2 = make_snapshot(minutes_delta=-30, corr="CORR_ETH_SPTF03_M10_002", caus="CAUS_ETH_SPTF03_M10_002")
        s3 = make_snapshot(minutes_delta=0, corr="CORR_SOL_SPTF03_M10_003", caus="CAUS_SOL_SPTF03_M10_003")
        res = build_rolling_24h(snapshot_samples=[s1, s2, s3], end_ts=make_ts(0))
        assert res.correlation_id == "CORR_SOL_SPTF03_M10_003"
        assert res.causation_id.startswith("SNAP_") or res.causation_id != ""

    def test_multiple_account_ref(self):
        s_a = make_snapshot(minutes_delta=-60, account_ref="A")
        s_b = make_snapshot(minutes_delta=-30, account_ref="B")
        s_c = make_snapshot(minutes_delta=0, account_ref="C")
        res = build_rolling_24h(snapshot_samples=[s_a, s_b, s_c], end_ts=make_ts(0))
        assert res.window_samples_count == 3

    @pytest.mark.parametrize("n", [1, 2, 3, 5, 10, 20, 48, 100, 200, 288])
    def test_sample_count_deterministic(self, n):
        snaps = [make_snapshot(minutes_delta=-(n-i-1)*5, equity=Decimal(str(1000+i))) for i in range(n)]
        end_ts = make_ts(0)
        # 10 runs same
        res = None
        for i in range(10):
            r = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
            if res is None:
                res = r
            assert r.window_samples_count == res.window_samples_count
            assert r.rolling_return_pct == res.rolling_return_pct
            assert r.rolling_peak_equity_quote == res.rolling_peak_equity_quote
            assert r.rolling_drawdown_pct == res.rolling_drawdown_pct

    def test_exposure_three_symbols_sum(self):
        snaps = [
            make_snapshot(minutes_delta=-60, exposure=Decimal("1000")),
            make_snapshot(minutes_delta=-30, exposure=Decimal("500")),
            make_snapshot(minutes_delta=0, exposure=Decimal("1500")),
        ]
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.exposure_max_24h == Decimal("1500")
        assert res.exposure_avg_24h == Decimal("1000")
        assert res.exposure_end_24h == Decimal("1500")

    @pytest.mark.parametrize("seed", list(range(20)))
    def test_seeded_random_equity_fees_deterministic(self, seed):
        import hashlib
        snaps = []
        for i in range(50):
            h = hashlib.sha256(f"{seed}-{i}-equity".encode()).hexdigest()[:10]
            eq = Decimal(str(int(h, 16) % 10000 + 1))
            hf = hashlib.sha256(f"{seed}-{i}-fee".encode()).hexdigest()[:10]
            fe = Decimal(str(int(hf, 16) % 500))
            snaps.append(make_snapshot(minutes_delta=-(49-i)*6, equity=eq, fees_total=fe))
        r1 = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        for _ in range(5):
            r2 = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
            assert r1.rolling_return_pct == r2.rolling_return_pct
            assert r1.rolling_fees_quote_24h == r2.rolling_fees_quote_24h
            assert r1.rolling_realized_pnl_quote_24h == r2.rolling_realized_pnl_quote_24h
            assert r1.rolling_peak_equity_quote == r2.rolling_peak_equity_quote
            assert r1.rolling_drawdown_pct == r2.rolling_drawdown_pct
            assert r1.exposure_max_24h == r2.exposure_max_24h
            assert r1.exposure_avg_24h == r2.exposure_avg_24h
            assert r1.exposure_end_24h == r2.exposure_end_24h
