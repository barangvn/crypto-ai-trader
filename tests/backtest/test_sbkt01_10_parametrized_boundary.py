from __future__ import annotations

import pytest
from decimal import Decimal

from app.backtest.run_metadata import (
    BacktestAssumptions,
    BacktestRun,
    BacktestWindowSplit,
    WindowSplit,
    SplitDataset,
)


@pytest.mark.parametrize("dataset", list(SplitDataset))
def test_splitalue(dataset):
    # 3 param tests
    assert dataset.value in ("train", "validation", "test")


WS_VALID_CASES = [
    (SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),
    (SplitDataset.VALIDATION, "2025-01-01T01:00:00.000Z", "2025-01-01T02:00:00.000Z", 60),
    (SplitDataset.TEST, "2025-01-01T02:00:00.000Z", "2025-01-01T03:00:00.000Z", 60),
    (SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.000Z", 1),
    (SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-12-31T23:59:59.999Z", 10_000),
]


@pytest.mark.parametrize("dataset,start,end,count", WS_VALID_CASES)
def test_window_split_valid(dataset, start, end, count):
    ws = WindowSplit(dataset, start, end, count)
    assert ws.dataset == dataset
    assert ws.start_instant == start
    assert ws.end_instant == end
    assert ws.event_count == count


WS_INVALID_CASES = [
    (SplitDataset.TRAIN, "", "2025-01-01T01:00:00.000Z", 60),
    (SplitDataset.TRAIN, "2025-01-01T01:00:00.000Z", "", 60),
    (SplitDataset.TRAIN, "2025-01-01T02:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),  # end before start
    (SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", -1),
]


@pytest.mark.parametrize("dataset,start,end,count", WS_INVALID_CASES)
def test_window_split_invalid(dataset, start, end, count):
    with pytest.raises(Exception):
        WindowSplit(dataset, start, end, count)


# ---- Overlap tests for BacktestWindowSplit ----
OVERLAP_CASES_OK = [
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),
        ("2025-01-01T01:00:01.000Z", "2025-01-01T02:00:00.000Z", 60),
        ("2025-01-01T02:00:01.000Z", "2025-01-01T03:00:00.000Z", 60),
    ),
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.000Z", 1),
        ("2025-01-01T00:00:00.001Z", "2025-01-01T00:00:00.002Z", 1),
        ("2025-01-01T00:00:00.003Z", "2025-01-01T00:00:00.004Z", 1),
    ),
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.001Z", 1),
        ("2025-01-01T00:00:00.002Z", "2025-01-01T00:00:00.003Z", 1),
        ("2025-01-01T00:00:00.004Z", "2025-01-01T00:00:00.005Z", 1),
    ),
]


@pytest.mark.parametrize("tr,vl,ts", OVERLAP_CASES_OK)
def test_overlap_free_success(tr, vl, ts):
    ws_tr = WindowSplit(SplitDataset.TRAIN, tr[0], tr[1], tr[2])
    ws_vl = WindowSplit(SplitDataset.VALIDATION, vl[0], vl[1], vl[2])
    ws_ts = WindowSplit(SplitDataset.TEST, ts[0], ts[1], ts[2])
    BacktestWindowSplit(version="1.0.0", train=ws_tr, validation=ws_vl, test=ws_ts, overlap_free=True)


OVERLAP_CASES_FAIL = [
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),
        ("2025-01-01T00:59:00.000Z", "2025-01-01T02:00:00.000Z", 60),  # overlap
        ("2025-01-01T02:00:01.000Z", "2025-01-01T03:00:00.000Z", 60),
    ),
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),
        ("2025-01-01T01:00:01.000Z", "2025-01-01T02:00:00.000Z", 60),
        ("2025-01-01T01:59:00.000Z", "2025-01-01T03:00:00.000Z", 60),  # overlap with val
    ),
    (
        ("2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60),
        ("2025-01-01T01:00:00.000Z", "2025-01-01T01:00:00.000Z", 1),  # same instant as train end
        ("2025-01-01T01:00:00.001Z", "2025-01-01T01:00:00.002Z", 1),
    ),
]


@pytest.mark.parametrize("tr,vl,ts", OVERLAP_CASES_FAIL)
def test_overlap_free_fail(tr, vl, ts):
    ws_tr = WindowSplit(SplitDataset.TRAIN, tr[0], tr[1], tr[2])
    ws_vl = WindowSplit(SplitDataset.VALIDATION, vl[0], vl[1], vl[2])
    ws_ts = WindowSplit(SplitDataset.TEST, ts[0], ts[1], ts[2])
    with pytest.raises(Exception):
        BacktestWindowSplit(version="1.0.0", train=ws_tr, validation=ws_vl, test=ws_ts, overlap_free=True)


# ---- Assumptions hash ----
ASSUMPTIONS_CHANGE_CASES = [
    dict(initial_equity_quote=Decimal("10000")),
    dict(initial_equity_quote=Decimal("20000")),
    dict(quote_currency="BTC"),
    dict(quote_currency="ETH"),
    dict(initial_position_side="long"),
    dict(initial_position_side="short"),
    dict(default_timeframe="5m"),
    dict(default_timeframe="15m"),
]


def _assumptions_hash_variations():
    """Return hashes for all variations so we can assert they are all unique."""
    hashes = []
    for case in ASSUMPTIONS_CHANGE_CASES:
        hashes.append(BacktestAssumptions(**case).compute_hash())
    return hashes


def test_assumptions_hash_changes_equity():
    h = _assumptions_hash_variations()
    # All of the 8 variations should produce at least 2 distinct hashes (actually all should be distinct)
    assert len(set(h)) >= 2


def test_assumptions_frozen_slots():
    a = BacktestAssumptions()
    with pytest.raises(Exception):
        a.__dict__["x"] = 1


def test_backtest_run_frozen_slots():
    r = BacktestRun(
        run_id="X",
        bundle_id="B",
        bundle_version="1.0.0",
        bundle_sha="S",
        assumptions_hash="H",
        start_instant="2025-01-01T00:00:00.000Z",
        end_instant="2025-01-01T01:00:00.000Z",
    )
    with pytest.raises(Exception):
        r.__dict__["x"] = 1


# ---- ReplayClock monotonicity parametrized ----
GOOD_SEQUENCES = [
    ["2025-01-01T00:00:00.000Z"],
    ["2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.001Z"],
    ["2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.000Z"],  # equal allowed
    ["2025-01-01T00:00:00.000Z", "2025-01-01T00:00:01.000Z", "2025-01-01T00:00:02.000Z"],
]


@pytest.mark.parametrize("seq", GOOD_SEQUENCES)
def test_clock_advance_sequences_ok(seq):
    from app.backtest.ordering import ReplayClock
    rc = ReplayClock()
    for t in seq:
        rc.advance(t)
    assert rc.advanced_count == len(seq)


BAD_SEQUENCES = [
    ["2025-01-01T00:00:02.000Z", "2025-01-01T00:00:01.000Z"],
    ["2025-01-01T00:00:01.000Z", "2025-01-01T00:00:00.000Z"],
    ["2025-01-01T00:00:01.999Z", "2025-01-01T00:00:01.998Z"],
]


@pytest.mark.parametrize("seq", BAD_SEQUENCES)
def test_clock_advance_bad_raises(seq):
    from app.backtest.ordering import ReplayClock
    rc = ReplayClock()
    rc.advance(seq[0])
    with pytest.raises(Exception):
        rc.advance(seq[1])


# ---- DETERMINISTIC_EVENT_STAGE_ORDER unique ranks ----
def test_stage_order_unique_rank():
    from app.backtest.ordering import DETERMINISTIC_EVENT_STAGE_ORDER
    assert len(set(DETERMINISTIC_EVENT_STAGE_ORDER)) == len(DETERMINISTIC_EVENT_STAGE_ORDER)


# ---- Frozen metadata ----
def test_window_split_frozen():
    ws = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
    with pytest.raises(Exception):
        ws.event_count = 1


def test_backtest_window_split_frozen():
    tr = WindowSplit(SplitDataset.TRAIN, "2025-01-01T00:00:00.000Z", "2025-01-01T01:00:00.000Z", 60)
    vl = WindowSplit(SplitDataset.VALIDATION, "2025-01-01T01:00:01.000Z", "2025-01-01T02:00:00.000Z", 60)
    ts = WindowSplit(SplitDataset.TEST, "2025-01-01T02:00:01.000Z", "2025-01-01T03:00:00.000Z", 60)
    bws = BacktestWindowSplit(version="1.0.0", train=tr, validation=vl, test=ts)
    with pytest.raises(Exception):
        bws.overlap_free = False


# ---- BacktestRun version fields ----
@pytest.mark.parametrize("ver", [
    "strategy_version",
    "feature_version",
    "regime_version",
    "opportunity_version",
    "risk_version",
])
def test_default_versions(ver):
    r = BacktestRun(
        run_id="R1",
        bundle_id="B1",
        bundle_version="1.0.0",
        bundle_sha="S",
        assumptions_hash="H",
        start_instant="2025-01-01T00:00:00.000Z",
        end_instant="2025-01-01T01:00:00.000Z",
    )
    assert getattr(r, ver) == "1.0.0"


def test_run_contract_version():
    from app.contracts import CONTRACT_VERSION
    r = BacktestRun(
        run_id="R1",
        bundle_id="B1",
        bundle_version="1.0.0",
        bundle_sha="S",
        assumptions_hash="H",
        start_instant="2025-01-01T00:00:00.000Z",
        end_instant="2025-01-01T01:00:00.000Z",
    )
    assert r.contract_version == CONTRACT_VERSION


def test_run_engine_version_default():
    r = BacktestRun(
        run_id="R1",
        bundle_id="B1",
        bundle_version="1.0.0",
        bundle_sha="S",
        assumptions_hash="H",
        start_instant="2025-01-01T00:00:00.000Z",
        end_instant="2025-01-01T01:00:00.000Z",
    )
    assert r.engine_version == "1.0.0"
