from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry.exceptions import (
    ERR_APPEND_ONLY,
    ERR_FIELD_IMMUTABLE,
    ERR_FIELD_MISSING,
    ERR_FIELD_VALIDATION,
    RegistryError,
)
from tests.registry.conftest import sample_mv


def test_update_allowed_artifact_uri(created_registry):
    reg, bus, storage, created, sha_old = created_registry
    new_uri = "file:///new/location/model.pkl"
    patched, sha_new = reg.update(
        created.model_id, created.version, {"artifact_uri": new_uri}
    )
    assert patched.artifact_uri == new_uri
    assert sha_new != sha_old


def test_update_allowed_promoted_at(created_registry):
    reg, bus, storage, created, sha_old = created_registry
    new_ts = "2026-09-10T12:00:00.000Z"
    patched, sha_new = reg.update(
        created.model_id, created.version, {"promoted_at": new_ts}
    )
    assert patched.promoted_at == new_ts


def test_update_allowed_retired_at(created_registry):
    reg, bus, storage, created, sha_old = created_registry
    new_ts = "2026-09-11T00:00:00.000Z"
    patched, sha_new = reg.update(
        created.model_id, created.version, {"retired_at": new_ts}
    )
    assert patched.retired_at == new_ts


def test_update_allowed_metadata_values(created_registry):
    reg, bus, storage, created, sha_old = created_registry
    new_meta = {"custom_key": "custom_value", "another": 42}
    patched, sha_new = reg.update(
        created.model_id, created.version, {"metadata": new_meta}
    )
    assert patched.metadata.get("custom_key") == "custom_value"
    assert patched.metadata.get("another") == 42


def test_update_walk_forward_append_ok(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(metadata={"walk_forward_run_ids": ["a"]})
    created, sha = reg.create(mv)
    patched, new_sha = reg.update(
        created.model_id,
        created.version,
        {"walk_forward_run_ids": ["a", "b"]},
    )
    assert patched.metadata["walk_forward_run_ids"] == ["a", "b"]


def test_update_walk_forward_remove_rejects_append_only(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(metadata={"walk_forward_run_ids": ["a", "b"]})
    created, sha = reg.create(mv)
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"walk_forward_run_ids": ["a"]},
        )
    assert excinfo.value.reason_code == ERR_APPEND_ONLY


def test_update_approval_refs_remove_rejects_append_only(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(metadata={"approval_refs": ["appr_1", "appr_2"]})
    created, sha = reg.create(mv)
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"approval_refs": ["appr_1"]},
        )
    assert excinfo.value.reason_code == ERR_APPEND_ONLY


def test_update_patch_status_immutable_rejects(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"status": ModelLifecycleStatus.TESTED},
        )
    assert excinfo.value.reason_code in ("FIELD_IMMUTABLE", "CAP5_DIRECT_MUTATION")


def test_update_patch_model_id_immutable_rejects(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"model_id": "different_model_id"},
        )
    assert excinfo.value.reason_code == ERR_FIELD_IMMUTABLE


def test_update_patch_version_immutable_rejects(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"version": "2.0.0"},
        )
    assert excinfo.value.reason_code == ERR_FIELD_IMMUTABLE


def test_update_patch_hyperparams_immutable_rejects(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(
            created.model_id,
            created.version,
            {"hyperparams": {"learning_rate": 0.001}},
        )
    assert excinfo.value.reason_code == ERR_FIELD_IMMUTABLE


def test_update_patch_empty_raises_field_missing(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(RegistryError) as excinfo:
        reg.update(created.model_id, created.version, {})
    assert excinfo.value.reason_code == ERR_FIELD_MISSING
