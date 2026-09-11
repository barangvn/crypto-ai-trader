from __future__ import annotations

from app.contracts import ModelLifecycleStatus, ModelVersion
from tests.registry.conftest import sample_mv


def test_smdl01_24_crud_end2end_10_assertions(fresh_registry):
    reg, bus, storage = fresh_registry
    mv_input = sample_mv()

    # --- 1. CREATE ---
    created, sha_create = reg.create(mv_input)
    assert isinstance(created, ModelVersion), "A1: create returns ModelVersion"
    assert isinstance(sha_create, str) and len(sha_create) == 64, "A2: create sha 64-char hex"

    # --- 2. GET ---
    got_mv, sha_get = reg.get(created.model_id, created.version)
    assert got_mv.model_id == created.model_id, "A3: get model_id matches"
    assert got_mv.version == created.version, "A4: get version matches"
    assert sha_get == sha_create, "A5: get sha equals create sha"

    # --- 3. UPDATE ---
    new_flags = {"cap1_passed": True, "cap2_passed": True, "cap3_passed": True}
    updated, sha_update = reg.update(
        model_id=created.model_id,
        version=created.version,
        patch={"metadata": {"smoke_flag": "updated_ok"}},
    )
    assert isinstance(updated, ModelVersion), "A6: update returns ModelVersion"
    assert sha_update != sha_create, "A7: update sha differs from create sha"
    assert updated.metadata.get("smoke_flag") == "updated_ok", "A8: update patch value persisted"

    # --- 4. LIST ---
    listed = reg.list()
    assert len(listed) >= 1, "A9: list returns at least 1 model"

    # --- 5. TRANSITION candidate -> tested ---
    tx_result = reg.request_transition(
        model_id=created.model_id,
        version=created.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )
    tx_mv, tx_sha, tx_obj, tx_env = tx_result
    assert tx_mv.status == ModelLifecycleStatus.TESTED, "A10: transition status=TESTED"

    # --- 6. HISTORY ---
    history = reg.transition_history(created.model_id, created.version)
    assert len(history) == 1, "A11: transition history has 1 entry (bonus)"
    assert history[0].from_status == ModelLifecycleStatus.CANDIDATE, "A12: history from=CANDIDATE (bonus)"
    assert history[0].to_status == ModelLifecycleStatus.TESTED, "A13: history to=TESTED (bonus)"
