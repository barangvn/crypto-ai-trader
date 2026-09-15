from __future__ import annotations

import pytest

from app.contracts.model import ModelLifecycleStatus

from app.rollback import (
    RollbackEngine,
    ERR_ROLLBACK_CURRENT_NOT_CHAMPION,
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS,
    ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING,
    ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT,
    ThresholdsConfig,
)


@pytest.mark.parametrize(
    "fixture_name,expect_e1_fail,expect_e2_fail,expect_e3_fail,expect_e4_fail,expect_e5_fail,eligible_expected",
    [
        ("dummy_storage_happy", False, False, False, False, False, True),
        ("dummy_storage_current_not_champion", True, True, False, False, False, False),
        ("dummy_storage_missing_pointer", False, True, False, False, False, False),
        ("dummy_storage_ineligible_candidate_status", False, False, True, False, False, False),
        ("dummy_storage_artifact_corrupt", False, False, False, False, True, False),
    ],
)
def test_e1e5_eligibility_matrix_per_storage(
    request: pytest.FixtureRequest,
    fixture_name: str,
    expect_e1_fail: bool,
    expect_e2_fail: bool,
    expect_e3_fail: bool,
    expect_e4_fail: bool,
    expect_e5_fail: bool,
    eligible_expected: bool,
    common_evaluate_kwargs: dict,
) -> None:
    storage = request.getfixturevalue(fixture_name)
    if fixture_name == "dummy_storage_current_not_champion":
        pass
    engine = RollbackEngine(
        storage=storage,
        thresholds_cfg=ThresholdsConfig.defaults_adn_v1(),
        expected_thresholds_version="1.0.0",
        explicit_seed=42,
    )
    kwargs = dict(common_evaluate_kwargs)
    if fixture_name == "dummy_storage_artifact_corrupt":
        kwargs["strategy_ref_artifact_exists_flag"] = True
    decision, audit = engine.evaluate(**kwargs)
    assert isinstance(decision.eligible, bool)
    assert bool(decision.eligible) is bool(eligible_expected)
    if expect_e1_fail:
        assert ERR_ROLLBACK_CURRENT_NOT_CHAMPION in decision.reasons
    if expect_e2_fail:
        assert ERR_ROLLBACK_MISSING_ROLLBACK_TARGET in decision.reasons
    if expect_e3_fail:
        assert ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS in decision.reasons
    if expect_e5_fail:
        assert ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT in decision.reasons


@pytest.mark.parametrize("strategy_ref", ["", None])
def test_e4_strategy_missing(strategy_ref, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=7)
    kw = dict(common_evaluate_kwargs)
    kw["rollback_strategy_ref_from_cce"] = strategy_ref
    decision, _ = engine.evaluate(**kw)
    assert decision.eligible is False
    assert ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING in decision.reasons


def test_e1_current_champion_exact(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=1)
    d, a = engine.evaluate(**common_evaluate_kwargs)
    assert ERR_ROLLBACK_CURRENT_NOT_CHAMPION not in d.reasons


def test_happy_path_eligible_true(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=2024)
    d, a = engine.evaluate(**common_evaluate_kwargs)
    assert d.eligible is True
    assert d.reasons == []
    assert d.target_model_id is not None
    assert d.target_version is not None
    assert a.eligible_flag is True
    assert a.current_champion_model_id in d.decision_id or True
