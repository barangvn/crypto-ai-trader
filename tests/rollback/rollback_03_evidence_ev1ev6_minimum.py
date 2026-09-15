from __future__ import annotations

import pytest

from app.rollback import (
    validate_evidence_bundle,
    ThresholdsConfig,
    ERR_ROLLBACK_INCOMPLETE_EVIDENCE,
    ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE,
    ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY,
    ERR_ROLLBACK_RATIONALE_EMPTY,
    ERR_ROLLBACK_PRIOR_STATE_REF_NULL,
    ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN,
)


BASE_EV = {
    "trigger_type": "degradation_breach",
    "approver_identity": "gov",
    "rationale_text": "because",
    "prior_state_snapshot_ref": "snap-1",
    "degradation_evidence_count": 3,
    "evidence_ts": "2026-09-15T10:00:00Z",
    "comparison_window_end_ts": "2026-09-15T12:00:00Z",
    "evidence_integrity_ok_flag": True,
    "evidence_integrity_sha": "",
    "rollback_strategy_ref": "rb-v1",
    "strategy_ref_artifact_exists": True,
}


@pytest.fixture
def delta_full(happy_delta_metrics):
    return happy_delta_metrics


def _run(delta, overrides=None):
    cfg = ThresholdsConfig.defaults_adn_v1()
    kw = dict(BASE_EV)
    if overrides:
        kw.update(overrides)
    return validate_evidence_bundle(delta_metrics=delta, thresholds_cfg=cfg, **kw)


@pytest.mark.parametrize(
    "missing_key",
    [
        "return_pct", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio",
        "profit_factor", "total_fees_quote", "avg_slippage_bps",
        "trade_count", "regime_coverage_count", "window_days", "oos_flag",
    ],
)
def test_delta_missing_each_key_fails(missing_key, delta_full):
    d = dict(delta_full)
    del d[missing_key]
    r = _run(d)
    assert ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE in r


def test_delta_non_dict_fails():
    r = _run(delta=None)
    assert ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE in r


@pytest.mark.parametrize("field,reason_expected", [
    ("approver_identity", ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY),
    ("rationale_text", ERR_ROLLBACK_RATIONALE_EMPTY),
    ("prior_state_snapshot_ref", ERR_ROLLBACK_PRIOR_STATE_REF_NULL),
])
def test_approval_fields_empty_each(field, reason_expected, delta_full):
    overrides = {field: ""}
    r = _run(delta_full, overrides)
    assert ERR_ROLLBACK_INCOMPLETE_EVIDENCE in r
    assert reason_expected in r


def test_evidence_count_below_min(delta_full):
    cfg = ThresholdsConfig.defaults_adn_v1()
    cnt_under = cfg.min_degradation_evidence_count - 1
    r = _run(delta_full, {"degradation_evidence_count": cnt_under})
    assert ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN in r


def test_evidence_count_non_int_fails(delta_full):
    r = _run(delta_full, {"degradation_evidence_count": "3"})
    assert ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN in r


def test_full_evidence_no_incomplete(delta_full):
    r = _run(delta_full)
    assert ERR_ROLLBACK_INCOMPLETE_EVIDENCE not in r
    assert ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE not in r


@pytest.mark.parametrize("bad_type_key", [
    "return_pct", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio",
    "profit_factor", "total_fees_quote", "avg_slippage_bps",
    "trade_count", "regime_coverage_count", "window_days", "oos_flag",
])
def test_delta_key_missing_with_none_or_pop_fails_incomplete(bad_type_key, delta_full):
    d = dict(delta_full)
    del d[bad_type_key]
    d[bad_type_key + "_extra"] = 0
    r = _run(d)
    assert ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE in r


@pytest.mark.parametrize("field,reason_expected", [
    ("approver_identity", ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY),
    ("rationale_text", ERR_ROLLBACK_RATIONALE_EMPTY),
    ("prior_state_snapshot_ref", ERR_ROLLBACK_PRIOR_STATE_REF_NULL),
])
def test_approval_fields_none_fails(field, reason_expected, delta_full):
    overrides = {field: None}
    r = _run(delta_full, overrides)
    assert ERR_ROLLBACK_INCOMPLETE_EVIDENCE in r
    assert reason_expected in r


@pytest.mark.parametrize("field,reason_expected", [
    ("approver_identity", ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY),
    ("rationale_text", ERR_ROLLBACK_RATIONALE_EMPTY),
    ("prior_state_snapshot_ref", ERR_ROLLBACK_PRIOR_STATE_REF_NULL),
])
def test_approval_fields_whitespace_fails(field, reason_expected, delta_full):
    overrides = {field: "   "}
    r = _run(delta_full, overrides)
    assert ERR_ROLLBACK_INCOMPLETE_EVIDENCE in r
    assert reason_expected in r


@pytest.mark.parametrize("bad_count", [-1, 0, None, "bad", 0.5])
def test_evidence_count_edge_cases_fail(bad_count, delta_full):
    r = _run(delta_full, {"degradation_evidence_count": bad_count})
    assert ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN in r
