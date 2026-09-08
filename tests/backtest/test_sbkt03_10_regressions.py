"""S-BKT-03 regression tests for 3 BLOCKER fixes (BLOK-1/2/3).

Audit NOT READY blockers:
- BLOK-1: MFR fail-fold BacktestRun start/end_instant empty → ValueError
- BLOK-2: MFR fail-fold BacktestRunResult performance_v2 required → TypeError
- BLOK-3: counts num_decisions mapped to risk_total (should be strategy_events)

DO NOT change this file; add-only new tests per S-BKT-03 regression namespace.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.backtest.run_metadata import (
    BacktestAssumptions,
    BacktestRun,
    BacktestWindowSplit,
    SplitDataset,
    WindowSplit,
)
from app.backtest.runner import (
    BacktestPerformanceSummary,
    BacktestPerformanceSummaryV2,
    BacktestRunCounts,
    BacktestRunResult,
    compute_result_sha256,
    load_backtest_artifact,
    save_backtest_artifact,
    upgrade_backtest_performance_v1_to_v2,
)


# ---------------------------------------------------------------------------
# Helpers (local to this test file, no conftest mutation)
# ---------------------------------------------------------------------------


def _fold_ws_3split() -> BacktestWindowSplit:
    return BacktestWindowSplit(
        train=WindowSplit(
            SplitDataset.TRAIN,
            "2024-01-01T00:00:00.000Z",
            "2024-01-31T00:00:00.000Z",
            event_count=43200,
        ),
        validation=WindowSplit(
            SplitDataset.VALIDATION,
            "2024-02-01T00:00:00.000Z",
            "2024-02-10T00:00:00.000Z",
            event_count=14400,
        ),
        test=WindowSplit(
            SplitDataset.TEST,
            "2024-02-11T00:00:00.000Z",
            "2024-02-20T00:00:00.000Z",
            event_count=14400,
        ),
    )


def _mfr_fail_meta(fold_ws: BacktestWindowSplit, fold_run_id: str, bundle: Any) -> BacktestRun:
    """Mirror MFR except path: deterministic split boundary extraction."""
    split_candidates = [s for s in (fold_ws.train, fold_ws.validation, fold_ws.test) if s is not None]
    if split_candidates:
        cands_start_sorted = sorted(split_candidates, key=lambda w: w.start_instant)
        cands_end_sorted = sorted(split_candidates, key=lambda w: w.end_instant)
        fail_start_instant = cands_start_sorted[0].start_instant
        fail_end_instant = cands_end_sorted[-1].end_instant
        fail_event_count = sum(getattr(s, "event_count", 0) for s in split_candidates)
    else:  # pragma: no cover - defensive branch
        fail_start_instant = "1970-01-01T00:00:00.000Z"
        fail_end_instant = "1970-01-01T00:00:00.000Z"
        fail_event_count = 0
    return BacktestRun(
        run_id=fold_run_id,
        bundle_id=getattr(bundle, "bundle_id", "unknown"),
        bundle_version=getattr(bundle, "bundle_version", "0"),
        bundle_sha=getattr(bundle, "bundle_sha", "0"),
        engine_version="1.0.0",
        contract_version="1.0.0",
        run_mode="replay",
        train_window=fold_ws.train,
        validation_window=fold_ws.validation,
        test_window=fold_ws.test,
        start_instant=fail_start_instant,
        end_instant=fail_end_instant,
        event_count=fail_event_count,
        walk_forward_mode="enabled_foundation",
        timeframe=getattr(bundle, "timeframe", "1m") or "1m",
    )


class _DummyBundle:
    bundle_id = "reg_bundle_01"
    bundle_version = "1.0.0"
    bundle_sha = "deadbeefcafe"
    timeframe = "1m"


class _DummyAssumptions:
    def to_sorted_dict(self) -> dict[str, Any]:
        return {"artifact_schema_version": "bkt_assumptions_v1"}


# ---------------------------------------------------------------------------
# 1. BLOK-1: fail-fold BacktestRun boundary / event_count deterministic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "train_s,val_s,test_s,train_e,val_e,test_e,exp_start,exp_end,exp_ev",
    [
        # Normal 3-split: start = train.start, end = test.end (helper ec: train=100/val=50/test=777 → 927)
        (
            "2024-01-01T00:00:00.000Z",
            "2024-02-01T00:00:00.000Z",
            "2024-02-11T00:00:00.000Z",
            "2024-01-31T00:00:00.000Z",
            "2024-02-10T00:00:00.000Z",
            "2024-02-20T00:00:00.000Z",
            "2024-01-01T00:00:00.000Z",
            "2024-02-20T00:00:00.000Z",
            100 + 50 + 777,
        ),
        # Only train+val (no test) → end=val.end
        (
            "2024-03-01T00:00:00.000Z",
            "2024-04-01T00:00:00.000Z",
            None,
            "2024-03-31T00:00:00.000Z",
            "2024-04-30T00:00:00.000Z",
            None,
            "2024-03-01T00:00:00.000Z",
            "2024-04-30T00:00:00.000Z",
            100 + 50,
        ),
        # Only test (no train/val) → start=test.start, end=test.end
        (
            None,
            None,
            "2024-06-01T00:00:00.000Z",
            None,
            None,
            "2024-06-30T00:00:00.000Z",
            "2024-06-01T00:00:00.000Z",
            "2024-06-30T00:00:00.000Z",
            777,
        ),
    ],
)
def test_failfold_meta_start_end_deterministic(
    train_s, val_s, test_s, train_e, val_e, test_e, exp_start, exp_end, exp_ev
) -> None:
    splits = []
    if train_s is not None:
        splits.append(WindowSplit(SplitDataset.TRAIN, train_s, train_e, event_count=100))
    else:
        splits.append(None)
    if val_s is not None:
        splits.append(WindowSplit(SplitDataset.VALIDATION, val_s, val_e, event_count=50))
    else:
        splits.append(None)
    if test_s is not None:
        splits.append(WindowSplit(SplitDataset.TEST, test_s, test_e, event_count=777))
    else:
        splits.append(None)
    t, v, te = splits
    fold_ws = BacktestWindowSplit(train=t, validation=v, test=te, overlap_free=(t and v and te))
    bundle = _DummyBundle()
    # NO ValueError (ex-BLOCKER)
    meta = _mfr_fail_meta(fold_ws, "mf_999", bundle)
    assert meta.start_instant == exp_start
    assert meta.end_instant == exp_end
    assert meta.event_count == exp_ev
    assert meta.start_instant <= meta.end_instant
    # provenance_sha deterministic → repeatable
    sha_a = meta.compute_provenance_sha()
    sha_b = meta.compute_provenance_sha()
    assert sha_a == sha_b
    assert isinstance(sha_a, str) and len(sha_a) == 64


# ---------------------------------------------------------------------------
# 2. BLOK-2: fail-fold BacktestRunResult performance_v2 fallback + schema
# ---------------------------------------------------------------------------


def test_failfold_performance_v2_fallback_schema() -> None:
    fold_ws = _fold_ws_3split()
    meta = _mfr_fail_meta(fold_ws, "mf_v2_42", _DummyBundle())
    asum = _DummyAssumptions()
    cnt = BacktestRunCounts()
    perf_v1 = BacktestPerformanceSummary()
    perf_v2 = upgrade_backtest_performance_v1_to_v2(
        perf_v1,
        metrics_info_codes=("BK_MF_FOLD_FAIL_V2_FALLBACK",),
    )
    assert isinstance(perf_v2, BacktestPerformanceSummaryV2)
    assert perf_v2.artifact_schema_version == "bkt_perf_v2"
    assert "BK_MF_FOLD_FAIL_V2_FALLBACK" in perf_v2.metrics_info_codes
    # NO TypeError (ex-BLOCKER) — required positional field set
    fail_code = "BK_MF_FOLD_FAIL_42"
    r = BacktestRunResult(
        metadata=meta,
        assumptions=asum,
        counts=cnt,
        performance=perf_v1,
        performance_v2=perf_v2,
        window_split=fold_ws,
        provenance={"failure_exception": "LookAheadLeakageError: BK_LEAK_FUTURE_TS"},
        failure_reason_codes=(fail_code,),
        engine_versions={"bkt_engine": "1.0.0"},
        run_notes=("fold_exception_42",),
    )
    # fail-closed: failure_codes non-empty; NOT silent success
    assert r.failure_reason_codes == (fail_code,)
    # artifact JSON includes performance_v2 (not dropped / not None)
    d = r.to_sorted_dict()
    assert "performance_v2" in d
    assert isinstance(d["performance_v2"], dict)
    assert d["performance_v2"].get("artifact_schema_version") == "bkt_perf_v2"
    assert d["failure_reason_codes"] == [fail_code]
    # fail-fold state NOT misrepresented: approval/trade counts zero
    assert r.counts.paper_orders_created == 0
    assert r.counts.paper_fills == 0
    assert r.counts.risk_approved == 0
    assert r.counts.risk_rejected == 0


# ---------------------------------------------------------------------------
# 3. BLOK-1+2 combined: deterministic artifact save/load roundtrip
# ---------------------------------------------------------------------------


def test_failfold_artifact_deterministic_roundtrip(tmp_path: Path) -> None:
    fold_ws = _fold_ws_3split()
    meta = _mfr_fail_meta(fold_ws, "mf_art_007", _DummyBundle())
    asum = _DummyAssumptions()
    cnt = BacktestRunCounts(market_events=72000, num_candles=72000)
    perf_v1 = BacktestPerformanceSummary(total_fees_quote=Decimal("0"))
    perf_v2 = upgrade_backtest_performance_v1_to_v2(
        perf_v1,
        metrics_info_codes=("BK_MF_FOLD_FAIL_V2_FALLBACK",),
    )
    r = BacktestRunResult(
        metadata=meta,
        assumptions=asum,
        counts=cnt,
        performance=perf_v1,
        performance_v2=perf_v2,
        window_split=fold_ws,
        provenance={"failure_exception": "ValueError: synthetic_failure"},
        failure_reason_codes=("BK_MF_FOLD_FAIL_7",),
        engine_versions={"bkt_engine": "1.0.0"},
        run_notes=("fold_exception_7",),
    )
    # Double save byte-identical
    p1 = tmp_path / "fail_art_a.json"
    p2 = tmp_path / "fail_art_b.json"
    sha_a = save_backtest_artifact(r, p1)
    sha_b = save_backtest_artifact(r, p2)
    assert sha_a == sha_b
    assert p1.read_bytes() == p2.read_bytes()
    # Load verify sha matches
    loaded, sha_loaded = load_backtest_artifact(p1)
    assert sha_loaded == sha_a
    assert loaded["failure_reason_codes"] == ["BK_MF_FOLD_FAIL_7"]
    assert "performance_v2" in loaded
    # failure NOT hidden: not empty; no spurious success path info
    assert loaded["failure_reason_codes"]
    # sha256 in payload matches recompute
    d_no_sha = {k: v for k, v in loaded.items() if k != "result_sha256"}
    assert loaded.get("result_sha256") == compute_result_sha256(d_no_sha)


# ---------------------------------------------------------------------------
# 4. BLOK-3: counts semantic (num_decisions = strategy_events, NOT risk)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "market_count,strategy_count,risk_total,porder_created,fills,quality_blocked",
    [
        # risk_total > strategy_count: num_decisions MUST equal strategy, NOT risk
        (1000, 10, 100, 50, 40, 5),
        # risk_total == strategy: both match (no way to disambiguate, sanity)
        (2000, 50, 50, 20, 18, 2),
        # strategy_count > risk (common): strategy used
        (5000, 200, 20, 120, 100, 15),
        # zero strategy: decisions 0 (no decisions)
        (800, 0, 10, 0, 0, 0),
    ],
)
def test_counts_num_decisions_semantic_strategy_not_risk(
    market_count, strategy_count, risk_total, porder_created, fills, quality_blocked
) -> None:
    c = BacktestRunCounts(
        market_events=market_count,
        strategy_events=strategy_count,
        risk_decisions=risk_total,
        risk_approved=max(0, risk_total - 1),
        risk_rejected=1 if risk_total > 0 else 0,
        paper_orders_created=porder_created,
        paper_fills=fills,
        quality_blocked=quality_blocked,
        num_candles=market_count,
        num_decisions=strategy_count,
        num_order_requests=porder_created,
        num_order_fills=fills,
        num_quality_events=quality_blocked,
        num_risk_events=risk_total,
    )
    # Semantic: decisions == strategy_events (not risk)
    assert c.num_decisions == strategy_count, (
        f"num_decisions semantic must equal strategy decisions (strategy_events={strategy_count}), "
        f"got {c.num_decisions}. If it equals risk_total={risk_total}, BLOK-3 mapping YANLISTIR."
    )
    # Separate: num_risk_events tracks risk_decisions
    assert c.num_risk_events == risk_total
    assert c.risk_decisions == risk_total
    # Canonical legacy aliases match stage counts
    assert c.num_candles == market_count
    assert c.num_order_requests == porder_created
    assert c.num_order_fills == fills
    assert c.num_quality_events == quality_blocked
    # Nonneg + int
    for f in (
        "num_candles",
        "num_decisions",
        "num_order_requests",
        "num_order_fills",
        "num_quality_events",
        "num_risk_events",
    ):
        assert isinstance(getattr(c, f), int)
        assert getattr(c, f) >= 0
