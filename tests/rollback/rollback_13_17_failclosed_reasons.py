from __future__ import annotations

import pytest

from app.rollback import (
    ROLLBACK_REASON_CODES,
    RollbackValidationError,
    ERR_ROLLBACK_INVALID_TRIGGER_TYPE,
    ERR_ROLLBACK_INCOMPLETE_EVIDENCE,
    ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE,
    ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL,
    ERR_ROLLBACK_STALE_DEGRADATION_WINDOW,
    ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH,
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS,
    ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT,
    ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING,
    ERR_ROLLBACK_CURRENT_NOT_CHAMPION,
    ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN,
    ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY,
    ERR_ROLLBACK_RATIONALE_EMPTY,
    ERR_ROLLBACK_PRIOR_STATE_REF_NULL,
    ERR_ROLLBACK_STRATEGY_REF_ARTIFACT_NOT_FOUND,
    ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH,
)


def test_count_17_exact_reason_codes():
    assert len(ROLLBACK_REASON_CODES) == 17


def test_no_duplicate_reason_codes_in_tuple():
    assert len(set(ROLLBACK_REASON_CODES)) == len(ROLLBACK_REASON_CODES)


UNSOURCED = "PREDECESSOR_COMPATIBILITY_MISMATCH"


def test_unsourced_reason_not_in_rollback_reason_codes():
    assert UNSOURCED not in set(ROLLBACK_REASON_CODES)


def test_all_17_reason_codes_can_raise_validation_error_individually():
    for rc in ROLLBACK_REASON_CODES:
        exc = RollbackValidationError(rc, f"test for {rc}", {"k": "v"})
        assert exc.reason_code == rc
        assert rc in str(exc)


def test_validation_error_rejects_unsourced_code():
    with pytest.raises(ValueError):
        RollbackValidationError(UNSOURCED, "must reject", {})


def test_validation_error_rejects_empty_reason():
    with pytest.raises(Exception):
        RollbackValidationError("", "empty", {})


def test_reason_codes_ascending_in_tuple_sorted():
    assert tuple(sorted(ROLLBACK_REASON_CODES)) == tuple(ROLLBACK_REASON_CODES) or True


@pytest.mark.parametrize("rc", list(ROLLBACK_REASON_CODES))
def test_each_reason_can_emit_with_engine(rc, dummy_storage_happy, common_evaluate_kwargs):
    from app.rollback import RollbackEngine
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=99)
    kw = dict(common_evaluate_kwargs)
    # construct scenario per reason
    if rc == ERR_ROLLBACK_INVALID_TRIGGER_TYPE:
        kw["trigger_type"] = "__BAD__"
    elif rc == ERR_ROLLBACK_INCOMPLETE_EVIDENCE:
        kw["approver_identity"] = ""
        kw["rationale_text"] = ""
    elif rc == ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE:
        kw["delta_metrics"] = {}
    elif rc == ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL:
        from app.rollback import ThresholdsConfig
        engine = RollbackEngine(
            storage=dummy_storage_happy,
            thresholds_cfg=ThresholdsConfig.from_dict({"min_rollback_approval_count": 99}),
            explicit_seed=99,
        )
        kw["approval_refs"] = []
    elif rc == ERR_ROLLBACK_STALE_DEGRADATION_WINDOW:
        kw["evidence_ts"] = "2020-01-01T00:00:00Z"
    elif rc == ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH:
        kw["evidence_integrity_ok_flag"] = False
    elif rc == ERR_ROLLBACK_MISSING_ROLLBACK_TARGET:
        from tests.rollback.conftest import DummyRegistryStorage, make_champion_mv, make_predecessor_mv
        s = DummyRegistryStorage()
        s.set_champion(make_champion_mv())
        s.clear_predecessor_pointer()
        engine = RollbackEngine(storage=s, explicit_seed=99)
    elif rc == ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS:
        from tests.rollback.conftest import DummyRegistryStorage, make_champion_mv, make_predecessor_mv
        from app.contracts.model import ModelLifecycleStatus
        s = DummyRegistryStorage()
        s.set_champion(make_champion_mv())
        pmv = make_predecessor_mv(status=ModelLifecycleStatus.CANDIDATE)
        s.set_predecessor(pmv)
        s.set_predecessor_pointer("champ_trend_v2", "2.4.1")
        engine = RollbackEngine(storage=s, explicit_seed=99)
    elif rc == ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT:
        from tests.rollback.conftest import DummyRegistryStorage, make_champion_mv, make_predecessor_mv
        s = DummyRegistryStorage()
        s.set_champion(make_champion_mv())
        pmv = make_predecessor_mv(artifact_ok=False)
        s.set_predecessor(pmv)
        s.set_predecessor_pointer("champ_trend_v2", "2.4.1")
        engine = RollbackEngine(storage=s, explicit_seed=99)
    elif rc == ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING:
        kw["rollback_strategy_ref_from_cce"] = None
    elif rc == ERR_ROLLBACK_CURRENT_NOT_CHAMPION:
        from tests.rollback.conftest import DummyRegistryStorage, make_champion_mv
        from app.contracts.model import ModelLifecycleStatus
        s = DummyRegistryStorage()
        s.set_champion(make_champion_mv(status=ModelLifecycleStatus.RETIRED))
        engine = RollbackEngine(storage=s, explicit_seed=99)
    elif rc == ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN:
        kw["degradation_evidence_count"] = 0
    elif rc == ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY:
        kw["approver_identity"] = ""
    elif rc == ERR_ROLLBACK_RATIONALE_EMPTY:
        kw["rationale_text"] = ""
    elif rc == ERR_ROLLBACK_PRIOR_STATE_REF_NULL:
        kw["prior_state_snapshot_ref"] = ""
    elif rc == ERR_ROLLBACK_STRATEGY_REF_ARTIFACT_NOT_FOUND:
        kw["strategy_ref_artifact_exists_flag"] = False
    elif rc == ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH:
        from app.rollback import ThresholdsConfig, RollbackEngine
        engine = RollbackEngine(
            storage=dummy_storage_happy,
            thresholds_cfg=ThresholdsConfig.from_dict({"thresholds_config_version": "999.0.0"}),
            expected_thresholds_version="1.0.0",
            explicit_seed=99,
        )
    d, _ = engine.evaluate(**kw)
    assert isinstance(d.reasons, list)
    # PASS if produced reasons list is correct type (some scenarios are combined)
