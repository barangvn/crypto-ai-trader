from __future__ import annotations

import pytest

from app.rollback import (
    RollbackEngine,
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS,
    ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT,
    ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING,
)


@pytest.mark.parametrize(
    "fixture_name,expected_reason",
    [
        ("dummy_storage_missing_pointer", ERR_ROLLBACK_MISSING_ROLLBACK_TARGET),
        ("dummy_storage_ineligible_candidate_status", ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS),
        ("dummy_storage_artifact_corrupt", ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT),
    ],
)
def test_5_missing_target_reasons_per_fixture(
    request, fixture_name, expected_reason, common_evaluate_kwargs
):
    storage = request.getfixturevalue(fixture_name)
    engine = RollbackEngine(storage=storage, explicit_seed=11)
    d, _ = engine.evaluate(**common_evaluate_kwargs)
    assert d.eligible is False
    assert expected_reason in d.reasons


def test_strategy_ref_null_produces_reason(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=12)
    kw = dict(common_evaluate_kwargs)
    kw["rollback_strategy_ref_from_cce"] = None
    d, _ = engine.evaluate(**kw)
    assert ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING in d.reasons


def test_combined_5_blockers_sorted_asc(dummy_storage_missing_pointer, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_missing_pointer, explicit_seed=13)
    kw = dict(common_evaluate_kwargs)
    kw["rollback_strategy_ref_from_cce"] = None
    kw["evidence_integrity_ok_flag"] = False
    kw["delta_metrics"] = {}
    kw["trigger_type"] = "BAD"
    d, _ = engine.evaluate(**kw)
    assert d.eligible is False
    # dedup ascending sort invariant
    assert d.reasons == sorted(set(d.reasons))
    # contains multiple distinct reasons
    assert len(d.reasons) >= 4
    assert ERR_ROLLBACK_MISSING_ROLLBACK_TARGET in d.reasons
    assert ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING in d.reasons
