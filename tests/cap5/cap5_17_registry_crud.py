from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
    ModelPurposeEnum,
)
from app.registry import RegistryError
from tests.cap5.conftest import cap5_sample_mv


class TestPhase1RegistryCRUDCompanions:
    def test_phase1_crud_01_create_then_get_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(
            model_id="crud_test_model",
            version="2.3.4",
            purpose=ModelPurposeEnum.REGIME_DETECTOR,
            status=ModelLifecycleStatus.CANDIDATE,
        )
        created, created_sha = reg.create(mv)
        assert created.model_id == "crud_test_model"
        assert created.version == "2.3.4"
        assert created.status == ModelLifecycleStatus.CANDIDATE
        got, got_sha = reg.get("crud_test_model", "2.3.4")
        assert got.model_id == created.model_id
        assert got.version == created.version
        assert got_sha == created_sha
        assert got.purpose == ModelPurposeEnum.REGIME_DETECTOR

    def test_phase1_crud_02_update_mutable_artifact_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        new_uri = "file:///new/artifact/location/v2.pkl"
        updated, _new_sha = reg.update(
            created.model_id, created.version, {"artifact_uri": new_uri}
        )
        assert updated.artifact_uri == new_uri

    def test_phase1_crud_03_update_metadata_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        patch_meta = {"custom_key": "custom_value", "oos_range": "2025"}
        updated, _new_sha = reg.update(
            created.model_id, created.version, {"metadata": patch_meta}
        )
        assert updated.metadata.get("custom_key") == "custom_value"
        assert updated.metadata.get("oos_range") == "2025"

    def test_phase1_crud_04_update_walk_forward_append_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        new_wf = ["wf-run-001", "wf-run-002"]
        updated, _new_sha = reg.update(
            created.model_id, created.version, {"walk_forward_run_ids": new_wf}
        )
        assert set(updated.metadata.get("walk_forward_run_ids") or []) == set(new_wf)
        new_wf2 = new_wf + ["wf-run-003"]
        updated2, _new_sha2 = reg.update(
            created.model_id, created.version, {"walk_forward_run_ids": new_wf2}
        )
        assert set(updated2.metadata["walk_forward_run_ids"]) == set(new_wf2)

    def test_phase1_crud_05_update_status_direct_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        with pytest.raises(RegistryError):
            reg.update(
                created.model_id, created.version,
                {"status": ModelLifecycleStatus.CHALLENGER},
            )

    def test_phase1_crud_06_create_duplicate_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(model_id="dup_model", version="1.0.0")
        reg.create(mv)
        mv2 = cap5_sample_mv(model_id="dup_model", version="1.0.0")
        with pytest.raises((RegistryError, Exception)):
            reg.create(mv2)

    def test_phase1_crud_07_get_missing_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        with pytest.raises((RegistryError, Exception)):
            reg.get("no_such_model_ever", "0.0.0")

    def test_phase1_crud_08_list_empty_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        items = reg.list()
        assert isinstance(items, list)
        assert len(items) == 0

    def test_phase1_crud_09_list_after_create_returns_item(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(model_id="list_test", version="1.0.0")
        reg.create(mv)
        items = reg.list()
        assert len(items) == 1
        got_mv, got_sha = items[0]
        assert got_mv.model_id == "list_test"
        assert got_mv.version == "1.0.0"
