from __future__ import annotations

import pytest

from app.rollback import (
    VALID_TRIGGER_TYPES,
    validate_trigger_type,
    RollbackEngine,
    ERR_ROLLBACK_INVALID_TRIGGER_TYPE,
)


@pytest.mark.parametrize("t", list(VALID_TRIGGER_TYPES))
def test_valid_trigger_types_pass_individually(t):
    assert validate_trigger_type(t) == []


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "",
        "   ",
        "degradation",
        "manual",
        "kill_switch",
        "DEGRADATION_BREACH",
        "auto_rollback_forbidden",
        1,
        0,
        False,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_trigger_types_fail_validation(invalid):
    reasons = validate_trigger_type(invalid)
    assert ERR_ROLLBACK_INVALID_TRIGGER_TYPE in reasons


@pytest.mark.parametrize("t", list(VALID_TRIGGER_TYPES))
def test_valid_trigger_through_engine_no_invalid_reason(
    t, dummy_storage_happy, common_evaluate_kwargs
):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=10)
    kw = dict(common_evaluate_kwargs)
    kw["trigger_type"] = t
    d, _ = engine.evaluate(**kw)
    assert ERR_ROLLBACK_INVALID_TRIGGER_TYPE not in d.reasons


@pytest.mark.parametrize("invalid", [None, "", "bad_one", object()])
def test_invalid_trigger_through_engine(invalid, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy)
    kw = dict(common_evaluate_kwargs)
    kw["trigger_type"] = invalid
    d, _ = engine.evaluate(**kw)
    assert d.eligible is False
    assert ERR_ROLLBACK_INVALID_TRIGGER_TYPE in d.reasons
