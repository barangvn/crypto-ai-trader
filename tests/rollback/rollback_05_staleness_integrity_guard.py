from __future__ import annotations

import pytest

from app.rollback import (
    validate_staleness_window,
    validate_evidence_integrity,
    ThresholdsConfig,
    ERR_ROLLBACK_STALE_DEGRADATION_WINDOW,
    ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH,
    RollbackEngine,
)


@pytest.mark.parametrize("ev_ts,win_ts,days_max,stale", [
    ("2026-09-01T00:00:00Z", "2026-09-15T00:00:00Z", 30, False),
    ("2026-09-01T00:00:00Z", "2026-09-16T00:00:00Z", 14, True),
    ("2026-09-15T00:00:00Z", "2026-09-01T00:00:00Z", 30, True),
    (None, "2026-09-15T00:00:00Z", 30, True),
    ("2026-09-15T00:00:00Z", None, 30, True),
    ("not-a-date", "2026-09-15T00:00:00Z", 30, True),
])
def test_staleness_window_cases(ev_ts, win_ts, days_max, stale):
    cfg = ThresholdsConfig.from_dict({"max_degradation_window_days": days_max})
    r = validate_staleness_window(ev_ts, win_ts, cfg)
    if stale:
        assert ERR_ROLLBACK_STALE_DEGRADATION_WINDOW in r
    else:
        assert ERR_ROLLBACK_STALE_DEGRADATION_WINDOW not in r


@pytest.mark.parametrize("ok_flag,sha,expect_fail", [
    (False, "", True),
    (True, "", False),
    (None, "zzzz", True),
    (True, "not-hex-64", True),
    (True, "0" * 64, False),
    (True, "a" * 64, False),
    (True, ("deadbeef" * 8), False),
    (False, "0" * 64, True),
    (None, None, False),
    (None, "", False),
])
def test_evidence_integrity_cases(ok_flag, sha, expect_fail):
    r = validate_evidence_integrity(ok_flag, sha)
    if expect_fail:
        assert ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH in r
    else:
        assert ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH not in r


def test_stale_evidence_engine(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=5)
    kw = dict(common_evaluate_kwargs)
    kw["evidence_ts"] = "2026-01-01T00:00:00Z"
    kw["comparison_window_end_ts"] = "2026-09-15T00:00:00Z"
    d, _ = engine.evaluate(**kw)
    assert d.eligible is False
    assert ERR_ROLLBACK_STALE_DEGRADATION_WINDOW in d.reasons


def test_integrity_false_flag_engine(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=6)
    kw = dict(common_evaluate_kwargs)
    kw["evidence_integrity_ok_flag"] = False
    d, _ = engine.evaluate(**kw)
    assert d.eligible is False
    assert ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH in d.reasons
