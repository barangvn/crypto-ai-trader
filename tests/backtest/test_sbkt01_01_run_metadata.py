from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.run_metadata import (
    BACKTEST_ASSUMPTIONS_VERSION,
    BACKTEST_RUN_VERSION,
    BacktestAssumptions,
    BacktestRun,
    BacktestWindowSplit,
    SplitDataset,
    WindowSplit,
    WINDOW_SPLIT_VERSION,
)


class TestMetadataVersions:
    def test_run_version_literal(self):
        assert BACKTEST_RUN_VERSION == "1.0.0"

    def test_assumptions_version_literal(self):
        assert BACKTEST_ASSUMPTIONS_VERSION == "1.0.0"

    def test_window_split_version_literal(self):
        assert WINDOW_SPLIT_VERSION == "1.0.0"


class TestSplitDataset:
    @pytest.mark.parametrize("d,expected", [
        (SplitDataset.TRAIN, "train"),
        (SplitDataset.VALIDATION, "validation"),
        (SplitDataset.TEST, "test"),
    ])
    def test_values(self, d, expected):
        assert d.value == expected

    def test_three_splits(self):
        assert len(list(SplitDataset)) == 3


class TestWindowSplit:
    @pytest.mark.parametrize("start,end,count,dataset", [
        ("2025-01-01T00:00:00.000Z", "2025-01-01T00:10:00.000Z", 10, SplitDataset.TRAIN),
        ("2025-01-01T00:10:00.000Z", "2025-01-01T00:20:00.000Z", 10, SplitDataset.VALIDATION),
        ("2025-01-01T00:20:00.000Z", "2025-01-01T00:30:00.000Z", 10, SplitDataset.TEST),
    ])
    def test_valid_window_split(self, start, end, count, dataset):
        ws = WindowSplit(dataset, start, end, count)
        assert ws.start_instant == start
        assert ws.end_instant == end
        assert ws.event_count == count
        assert ws.dataset == dataset

    def test_frozen(self):
        ws = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
        with pytest.raises(Exception):
            ws.event_count = 61

    def test_count_zero(self):
        ws = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 0)
        assert ws.event_count == 0

    def test_nonempty_str_required_start(self):
        with pytest.raises(Exception):
            WindowSplit(SplitDataset.TRAIN, "", "2025-01-01T01:00:00.000Z", 1)

    def test_nonempty_str_required_end(self):
        with pytest.raises(Exception):
            WindowSplit(SplitDataset.TRAIN, "2025-01-01T01:00:00.000Z", "", 1)

    def test_positive_count_required(self):
        with pytest.raises(Exception):
            WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", -1)


class TestBacktestWindowSplit:
    def test_overlap_free_invariant(self):
        tr = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
        vl = WindowSplit(SplitDataset.VALIDATION, "2025-01-01T01:00:01.000Z", "2025-01-01T01:10:00.000Z", 10)
        ts = WindowSplit(SplitDataset.TEST, "2025-01-01T01:10:01.000Z", "2025-01-01T01:20:00.000Z", 10)
        bws = BacktestWindowSplit(version="1.0.0", train=tr, validation=vl, test=ts, overlap_free=True)
        assert bws.overlap_free is True

    def test_overlap_detected(self):
        tr = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
        vl = WindowSplit(SplitDataset.VALIDATION, "2025-01-01T00:59:00.000Z", "2025-01-01T01:10:00.000Z", 10)
        with pytest.raises(Exception):
            BacktestWindowSplit(version="1.0.0", train=tr, validation=vl, test=None, overlap_free=True)

    @pytest.mark.parametrize("ts,expected", [
        ("2025-01-01T00:30:00.000Z", SplitDataset.TRAIN),
        ("2025-01-01T01:05:00.000Z", SplitDataset.VALIDATION),
        ("2025-01-01T01:15:00.000Z", SplitDataset.TEST),
        ("2025-12-31T23:59:59.999Z", None),
    ])
    def test_split_for_ts(self, ts, expected):
        tr = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
        vl = WindowSplit(SplitDataset.VALIDATION, "2025-01-01T01:00:01.000Z", "2025-01-01T01:10:00.000Z", 10)
        ts_w = WindowSplit(SplitDataset.TEST, "2025-01-01T01:10:01.000Z", "2025-01-01T01:20:00.000Z", 10)
        bws = BacktestWindowSplit(version="1.0.0", train=tr, validation=vl, test=ts_w)
        got = bws.split_for_ts(ts)
        assert got == expected


class TestBacktestAssumptions:
    def test_defaults(self):
        a = BacktestAssumptions()
        assert a.version == BACKTEST_ASSUMPTIONS_VERSION
        assert a.initial_equity_quote == Decimal("10000")
        assert a.quote_currency == "USDT"
        assert a.initial_position_side == "flat"
        assert isinstance(a.universe, tuple)

    def test_frozen(self):
        a = BacktestAssumptions()
        with pytest.raises(Exception):
            a.initial_equity_quote = Decimal("20000")

    def test_compute_hash_deterministic(self):
        a1 = BacktestAssumptions()
        a2 = BacktestAssumptions()
        assert a1.compute_hash() == a2.compute_hash()

    def test_compute_hash_changes_with_equity(self):
        a1 = BacktestAssumptions(initial_equity_quote=Decimal("10000"))
        a2 = BacktestAssumptions(initial_equity_quote=Decimal("20000"))
        assert a1.compute_hash() != a2.compute_hash()

    def test_to_sorted_dict_keys_sorted(self):
        import json
        a = BacktestAssumptions()
        d = a.to_sorted_dict()
        serialized = json.dumps(d, sort_keys=True, separators=(",", ":"))
        rebuilt = json.loads(serialized)
        assert list(rebuilt.keys()) == sorted(rebuilt.keys())
        # and compute_hash with sorted keys gives deterministic result
        h1 = a.compute_hash()
        h2 = a.compute_hash()
        assert h1 == h2

    @pytest.mark.parametrize("val", [
        Decimal("1"),
        Decimal("100"),
        Decimal("1000000"),
    ])
    def test_various_equity(self, val):
        a = BacktestAssumptions(initial_equity_quote=val)
        assert a.initial_equity_quote == val


class TestBacktestRun:
    def _mk_minimal(self, **kw):
        base = dict(
            run_id="R-001",
            bundle_id="B-001",
            bundle_version="1.0.0",
            bundle_sha="sha-xxx",
            assumptions_hash="hash-xxx",
            start_instant="2025-01-01T00:00:00.000Z",
            end_instant="2025-01-01T01:00:00.000Z",
        )
        base.update(kw)
        return BacktestRun(**base)

    def test_minimal_construct(self):
        r = self._mk_minimal()
        assert r.run_id == "R-001"
        assert r.bundle_id == "B-001"
        assert r.contract_version == "1.0.0"
        assert r.run_mode == "backtest"
        assert r.source_type == "replay"

    def test_post_init_empty_runid_rejected(self):
        with pytest.raises(Exception):
            self._mk_minimal(run_id="")

    def test_post_init_empty_bundleid_rejected(self):
        with pytest.raises(Exception):
            self._mk_minimal(bundle_id="")

    def test_frozen(self):
        r = self._mk_minimal()
        with pytest.raises(Exception):
            r.run_id = "R-002"

    def test_provenance_sha(self):
        r = self._mk_minimal()
        sha = r.compute_provenance_sha()
        assert isinstance(sha, str)
        assert len(sha) == 64

    def test_provenance_sha_deterministic(self):
        r1 = self._mk_minimal()
        r2 = self._mk_minimal()
        assert r1.compute_provenance_sha() == r2.compute_provenance_sha()

    def test_provenance_sha_changes_bundle(self):
        r1 = self._mk_minimal(bundle_sha="aaa")
        r2 = self._mk_minimal(bundle_sha="bbb")
        assert r1.compute_provenance_sha() != r2.compute_provenance_sha()

    def test_to_sorted_dict(self):
        import json
        r = self._mk_minimal()
        d = r.to_sorted_dict()
        assert isinstance(d, dict)
        serialized = json.dumps(d, sort_keys=True, separators=(",", ":"))
        rebuilt = json.loads(serialized)
        assert list(rebuilt.keys()) == sorted(rebuilt.keys())
        assert "run_id" in d

    def test_defaults_strategy_version(self):
        r = self._mk_minimal()
        assert r.strategy_version == "1.0.0"
        assert r.feature_version == "1.0.0"
        assert r.regime_version == "1.0.0"
        assert r.opportunity_version == "1.0.0"
        assert r.risk_version == "1.0.0"
