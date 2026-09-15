from __future__ import annotations

import pytest

from app.rollback import RollbackEngine, VALID_TARGET_MODES


@pytest.mark.parametrize("mode", list(VALID_TARGET_MODES))
def test_target_modes_produce_same_eligibility_happy(mode, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=21)
    kw = dict(common_evaluate_kwargs)
    kw["target_mode"] = mode
    d, a = engine.evaluate(**kw)
    assert d.eligible is True
    assert a.target_mode == mode


def test_target_1to1_predecessor_pointer_consumed(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=22)
    d, _ = engine.evaluate(**common_evaluate_kwargs)
    assert d.target_model_id is not None
    assert d.target_version is not None


def test_observe_only_still_targets_pred_pointer(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=23)
    kw = dict(common_evaluate_kwargs)
    kw["target_mode"] = "observe_only_disabled"
    d, a = engine.evaluate(**kw)
    assert d.target_model_id is not None
    assert a.target_mode == "observe_only_disabled"
