from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry.exceptions import ERR_CAP5_DIRECT_MUTATION, RegistryError


def test_update_patch_status_raises_cap5_direct_mutation(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"status": ModelLifecycleStatus.PAPER},
        )
    assert excinfo.value.reason_code == ERR_CAP5_DIRECT_MUTATION


def test_setattr_on_read_copy_does_not_affect_registry(created_registry):
    reg, bus, storage, created, sha_created = created_registry
    mv_copy1, _ = reg.get(created.model_id, created.version)
    original_status = mv_copy1.status
    try:
        mv_copy1.status = ModelLifecycleStatus.PAPER
    except Exception:
        pass
    mv_copy2, sha = reg.get(created.model_id, created.version)
    assert mv_copy2.status == original_status
    assert mv_copy2.status != ModelLifecycleStatus.PAPER


def test_setattr_model_id_on_copy_does_not_affect_registry(created_registry):
    reg, bus, storage, created, sha_created = created_registry
    mv_copy1, _ = reg.get(created.model_id, created.version)
    original_id = mv_copy1.model_id
    try:
        mv_copy1.model_id = "hacked_model_id"
    except Exception:
        pass
    mv_copy2, sha = reg.get(created.model_id, created.version)
    assert mv_copy2.model_id == original_id
    assert mv_copy2.model_id != "hacked_model_id"


def test_setattr_hyperparams_on_copy_does_not_affect_registry(created_registry):
    reg, bus, storage, created, sha_created = created_registry
    mv_copy1, _ = reg.get(created.model_id, created.version)
    original_hp = dict(mv_copy1.hyperparams)
    try:
        mv_copy1.hyperparams["learning_rate"] = 999.999
    except Exception:
        pass
    mv_copy2, sha = reg.get(created.model_id, created.version)
    assert mv_copy2.hyperparams.get("learning_rate") == original_hp.get("learning_rate")
