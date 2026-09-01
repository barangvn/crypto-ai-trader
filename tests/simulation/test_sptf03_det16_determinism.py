import hashlib
import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


def _mk_samples(n=100, seed=42):
    snaps = []
    for i in range(n):
        h_eq = hashlib.sha256(f"{seed}-{i}-eq".encode()).hexdigest()[:8]
        eq = Decimal(str(int(h_eq, 16) % 50000 + 1000))
        h_r = hashlib.sha256(f"{seed}-{i}-r".encode()).hexdigest()[:8]
        r = Decimal(str(int(h_r, 16) % 10000))
        h_f = hashlib.sha256(f"{seed}-{i}-f".encode()).hexdigest()[:8]
        f = Decimal(str(int(h_f, 16) % 1000))
        h_e = hashlib.sha256(f"{seed}-{i}-e".encode()).hexdigest()[:8]
        ex = Decimal(str(int(h_e, 16) % 20000))
        snaps.append(make_snapshot(
            minutes_delta=-(n - i - 1) * 5,
            equity=eq,
            realized=r,
            fees_total=f,
            exposure=ex,
            corr=f"CORR_{seed}_{i}",
            caus=f"CAUS_{seed}_{i}",
        ))
    return snaps


class TestSPTF03DET16Determinism:
    @pytest.mark.parametrize("seed", [1, 3, 7, 11, 17, 23, 42, 73, 100, 333, 777, 1024])
    def test_10x_same_ordered_input(self, seed):
        snaps = _mk_samples(n=100, seed=seed)
        end_ts = make_ts(0)
        baseline = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
        d1 = baseline.to_sorted_dict()
        h1 = baseline.schema_sha256()
        for i in range(10):
            r = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
            assert r.rolling_realized_pnl_quote_24h == baseline.rolling_realized_pnl_quote_24h
            assert r.rolling_fees_quote_24h == baseline.rolling_fees_quote_24h
            assert r.rolling_return_pct == baseline.rolling_return_pct
            assert r.rolling_peak_equity_quote == baseline.rolling_peak_equity_quote
            assert r.rolling_drawdown_pct == baseline.rolling_drawdown_pct
            assert r.exposure_max_24h == baseline.exposure_max_24h
            assert r.exposure_avg_24h == baseline.exposure_avg_24h
            assert r.exposure_end_24h == baseline.exposure_end_24h
            assert r.correlation_id == baseline.correlation_id
            assert r.causation_id == baseline.causation_id
            assert r.to_sorted_dict() == d1
            assert r.schema_sha256() == h1

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7, 8, 13, 21, 34, 55])
    def test_unordered_input_10x_same(self, seed):
        import random
        snaps_orig = _mk_samples(n=50, seed=seed)
        end_ts = make_ts(0)
        baseline = build_rolling_24h(snapshot_samples=list(snaps_orig), end_ts=end_ts)
        for i in range(10):
            random.seed(seed * 100 + i)
            shuffled = list(snaps_orig)
            random.shuffle(shuffled)
            r = build_rolling_24h(snapshot_samples=shuffled, end_ts=end_ts)
            assert r.rolling_realized_pnl_quote_24h == baseline.rolling_realized_pnl_quote_24h
            assert r.rolling_fees_quote_24h == baseline.rolling_fees_quote_24h
            assert r.rolling_return_pct == baseline.rolling_return_pct
            assert r.rolling_peak_equity_quote == baseline.rolling_peak_equity_quote
            assert r.rolling_drawdown_pct == baseline.rolling_drawdown_pct
            assert r.exposure_max_24h == baseline.exposure_max_24h
            assert r.exposure_avg_24h == baseline.exposure_avg_24h
            assert r.exposure_end_24h == baseline.exposure_end_24h
            assert r.to_sorted_dict() == baseline.to_sorted_dict()
            assert r.schema_sha256() == baseline.schema_sha256()
            assert r.info_codes == baseline.info_codes

    def test_sorted_output_tuple_same_every_time(self):
        snaps = _mk_samples(n=20, seed=99)
        r1 = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        for _ in range(10):
            r2 = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
            assert tuple(sorted(r1.to_sorted_dict().items())) == tuple(sorted(r2.to_sorted_dict().items()))

    @pytest.mark.parametrize("n_samples", [1, 2, 3, 5, 10, 25, 50, 75, 150, 200])
    def test_different_sample_sizes_10x_deterministic(self, n_samples):
        snaps = _mk_samples(n=n_samples, seed=2024)
        end_ts = make_ts(0)
        r1 = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
        d1 = r1.to_sorted_dict()
        for _ in range(10):
            r2 = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
            assert r2.to_sorted_dict() == d1
            assert r2.schema_sha256() == r1.schema_sha256()

    def test_empty_input_10x_deterministic(self):
        end_ts = make_ts(0)
        r1 = build_rolling_24h(snapshot_samples=[], end_ts=end_ts)
        for _ in range(10):
            r2 = build_rolling_24h(snapshot_samples=[], end_ts=end_ts)
            assert r1.to_sorted_dict() == r2.to_sorted_dict()
            assert r1.correlation_id == r2.correlation_id
            assert r1.causation_id == r2.causation_id
            assert r1.info_codes == r2.info_codes

    def test_single_sample_10x_deterministic(self):
        s = make_snapshot(minutes_delta=-5, equity=Decimal("5000"), realized=Decimal("200"),
                          fees_total=Decimal("10"), exposure=Decimal("2500"),
                          corr="CORR_DET_SINGLE", caus="CAUS_DET_SINGLE")
        r1 = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        for _ in range(10):
            r2 = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
            assert r1.rolling_realized_pnl_quote_24h == r2.rolling_realized_pnl_quote_24h
            assert r1.rolling_fees_quote_24h == r2.rolling_fees_quote_24h
            assert r1.rolling_peak_equity_quote == r2.rolling_peak_equity_quote
            assert r1.correlation_id == r2.correlation_id
            assert r1.causation_id == r2.causation_id
            assert r1.to_sorted_dict() == r2.to_sorted_dict()

    @pytest.mark.parametrize("seed", [500, 600, 700, 800, 900])
    def test_shuffle_5x_50x_permutations_same_result(self, seed):
        import random
        snaps_orig = _mk_samples(n=30, seed=seed)
        end_ts = make_ts(0)
        baseline = build_rolling_24h(snapshot_samples=list(snaps_orig), end_ts=end_ts)
        for trial in range(50):
            random.seed(seed * 1000 + trial)
            shuffled = list(snaps_orig)
            random.shuffle(shuffled)
            r = build_rolling_24h(snapshot_samples=shuffled, end_ts=end_ts)
            assert r.to_sorted_dict() == baseline.to_sorted_dict()
            assert r.schema_sha256() == baseline.schema_sha256()

