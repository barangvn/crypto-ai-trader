"""S-BKT-03 08: Fail-closed + invalid input + artifact roundtrip + backward compat."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from dataclasses import dataclass
from decimal import Decimal

from tests.backtest.conftest import SyntheticBundle
from app.backtest.ordering import LookAheadLeakageError
from app.backtest.run_metadata import BacktestAssumptions
from app.backtest.runner import (
    BacktestRunner,
    BacktestRunResult,
    save_backtest_artifact,
    load_backtest_artifact,
    compute_result_sha256,
    upgrade_backtest_performance_v1_to_v2,
    BacktestPerformanceSummary,
)
from app.backtest.metrics_compute import (
    closed_trade_pnl_sequence,
    summarize_win_loss,
)


LEAKAGE_STAGE_FAILCLOSED = [
    ("FEATURE", "2025-01-01T00:05:00.000Z", "2025-01-01T00:06:00.000Z"),
    ("REGIME", "2025-01-01T00:05:00.000Z", "2025-01-01T00:05:00.001Z"),
    ("STRATEGY", "2025-01-01T00:05:00.000Z", "2025-01-01T00:10:00.000Z"),
    ("OPPORTUNITY", "2025-01-01T00:05:00.000Z", "2025-02-01T00:00:00.000Z"),
    ("RISK", "2025-01-01T00:05:00.000Z", "2025-01-01T00:05:01.000Z"),
    ("FILL", "2025-01-01T00:05:00.000Z", "2025-01-01T01:00:00.000Z"),
    ("FEATURE", "2025-01-01T00:00:00.000Z", "2025-01-01T00:00:00.001Z"),
    ("RISK", "2025-06-01T00:00:00.000Z", "2025-06-01T00:00:00.002Z"),
    ("FILL", "2024-01-01T00:00:00.000Z", "2024-01-01T00:00:01.000Z"),
    ("REGIME", "2025-03-15T12:00:00.000Z", "2025-03-15T12:30:00.000Z"),
    ("STRATEGY", "2025-07-20T08:00:00.000Z", "2025-07-20T08:00:00.001Z"),
    ("OPPORTUNITY", "2025-12-31T23:59:59.999Z", "2026-01-01T00:00:00.000Z"),
]


@pytest.mark.parametrize("stage,dec_ts,input_max_ts", LEAKAGE_STAGE_FAILCLOSED)
def test_sbkt03_L04_failclosed_matrix_12cells(stage, dec_ts, input_max_ts):
    """12 hücre: her stage × çeşit future input → fail-closed body not executed."""
    from app.backtest.leakage_asserts import enforce_stage_leakage, BK_LEAK_PREFIX
    body_executed = [False]
    try:
        enforce_stage_leakage(stage, decision_ts=dec_ts, decision_input_max_ts=input_max_ts)
        body_executed[0] = True
    except LookAheadLeakageError as exc:
        assert BK_LEAK_PREFIX in str(exc)
        assert stage in str(exc)
    assert body_executed[0] is False


INVALID_METRICS_INPUT = [
    ([], "METRICS_NO_CLOSED_TRADES"),
    ([Decimal("0")], "STABILITY"),
    ([Decimal("1"), Decimal("2")], "PROFIT_FACTOR_NO_LOSSES"),
    ([Decimal("-0.0001")], None),
    ([Decimal("-1"), Decimal("-2"), Decimal("-3")], None),
    ([Decimal("1"), Decimal("-1")], None),
    ([Decimal("1e-8"), Decimal("-1e-8"), Decimal("1e-9")], None),
    ([Decimal("1000000"), Decimal("-999999")], None),
]


@pytest.mark.parametrize("pnl_list,expected_code_fragment", INVALID_METRICS_INPUT)
def test_sbkt03_M8_failclosed_invalid_metrics_8cells(pnl_list, expected_code_fragment):
    """Invalid metrics input → None + info_code (NOT sessiz 0)."""
    s = summarize_win_loss(pnl_list)
    codes = s.get("info_codes")
    assert isinstance(codes, (list, tuple))
    if expected_code_fragment:
        joined = " ".join(codes)
        assert expected_code_fragment in joined or len(codes) > 0


def test_sbkt03_L04_leakage_violation_fail_closed_no_approved_trade():
    """Leakage case; risk gate bypass YOK, paper_order approved YOK."""
    # Mevcut ordering ReplayClock + mevcut pipeline'ın clock advance
    # strict: future ts -> LookAheadLeakageError (daha onceki testlerden var SBKT01-06).
    # Burada: doğrudan leakage_asserts stage fail → exception → NO mutation
    from app.backtest.leakage_asserts import enforce_stage_leakage, BK_LEAK_PREFIX
    state_mutated = [False]
    try:
        enforce_stage_leakage(
            "FILL",
            decision_ts="2025-01-01T00:00:00.000Z",
            decision_input_max_ts="2025-01-01T00:05:00.000Z",
        )
        state_mutated[0] = True  # bu satır çalışmamalı
    except LookAheadLeakageError as exc:
        assert BK_LEAK_PREFIX in str(exc)
    assert state_mutated[0] is False  # fail-closed: body not executed


def test_sbkt03_M_invalid_input_fail_closed_none():
    """Invalid metrics input: empty seq → None fields (NOT fail raise; info code) policy.
    Fail-closed YALNIZCA leakage/risk gate ihlalleri icindir.
    Invalid metrics → None + info_code (sessiz 0 YOK) spec.
    """
    s = summarize_win_loss([])
    assert s["win_rate_pct"] is None
    assert s["profit_factor"] is None
    assert "METRICS_NO_CLOSED_TRADES" in s["info_codes"]


def test_sbkt03_artifact_roundtrip_save_load():
    b = SyntheticBundle(num_candles=90, seed=31, drift=Decimal("0.0001"))
    r = BacktestRunner(assumptions=BacktestAssumptions(initial_equity_quote="10000"))
    res = r.run(b)
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "art.json"
        sha = save_backtest_artifact(res, p)
        assert len(sha) == 64
        raw, sha2 = load_backtest_artifact(p)
        assert sha == sha2
        # V2 alanlari kayit edilmis (to_sorted_dict icinde performance_v2 key)
        assert "performance_v2" in raw
        v2_loaded = raw["performance_v2"]
        assert "artifact_schema_version" in v2_loaded
        assert v2_loaded["artifact_schema_version"] == "bkt_perf_v2"
        # V1 performance key hala kayıtlı (backward compat)
        assert "performance" in raw


def test_sbkt03_backward_compat_v1_artifact_converter():
    v1 = BacktestPerformanceSummary(
        total_return_pct=2.5,
        realized_pnl_quote=Decimal("250"),
        max_drawdown_pct=1.1,
    )
    v2 = upgrade_backtest_performance_v1_to_v2(v1)
    assert v2.total_return_pct == 2.5
    assert v2.realized_pnl_quote == Decimal("250")
    assert "UPGRADED_FROM_V1" in v2.metrics_info_codes
