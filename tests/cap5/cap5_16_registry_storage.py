from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import (
    ERR_STORAGE_CORRUPT_JSON,
    RegistryError,
    StorageError,
)
from tests.cap5.conftest import cap5_sample_mv


class TestPhase1RegistryStorageCompanions:
    def test_phase1_storage_01_write_then_read_roundtrip(self, cap5_fresh_storage, cap5_tmp_registry_root):
        storage = cap5_fresh_storage
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        sha = storage.write_model_version(mv, check_duplicate=True)
        assert isinstance(sha, str) and len(sha) == 64
        read_mv, read_sha = storage.read_model_version(mv.model_id, mv.version)
        assert read_mv.model_id == mv.model_id
        assert read_mv.version == mv.version
        assert read_mv.status == mv.status
        assert read_sha == sha

    def test_phase1_storage_02_duplicate_create_raises(self, cap5_fresh_storage):
        storage = cap5_fresh_storage
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        storage.write_model_version(mv, check_duplicate=True)
        with pytest.raises(StorageError):
            storage.write_model_version(mv, check_duplicate=True)

    def test_phase1_storage_03_read_missing_raises(self, cap5_fresh_storage):
        storage = cap5_fresh_storage
        with pytest.raises(StorageError):
            storage.read_model_version("does_not_exist_model_xyz", "99.99.99")

    def test_phase1_storage_04_corrupt_json_raises(self, cap5_fresh_storage, cap5_tmp_registry_root):
        storage = cap5_fresh_storage
        root: Path = cap5_tmp_registry_root
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        sha = storage.write_model_version(mv, check_duplicate=True)
        short_sha = sha[:12]
        mv_dir = storage._model_version_dir(mv.model_id, mv.version)
        target = mv_dir / f"mv-{short_sha}.json"
        target.write_text("NOT VALID JSON {{{", encoding="utf-8")
        with pytest.raises((StorageError, RegistryError)):
            storage.read_model_version(mv.model_id, mv.version)

    def test_phase1_storage_05_list_empty_returns_empty(self, cap5_fresh_storage):
        storage = cap5_fresh_storage
        items = storage.list_model_versions()
        assert isinstance(items, list)
        assert len(items) == 0

    def test_phase1_storage_06_list_after_create_has_item(self, cap5_fresh_storage):
        storage = cap5_fresh_storage
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        storage.write_model_version(mv, check_duplicate=True)
        items = storage.list_model_versions()
        assert len(items) == 1
        item_mv, _sha, _p = items[0]
        assert item_mv.model_id == mv.model_id

    def test_phase1_storage_07_write_then_read_transition(self, cap5_fresh_storage):
        from app.contracts import ModelLifecycleTransition
        storage = cap5_fresh_storage
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        storage.write_model_version(mv, check_duplicate=True)
        from tests.cap5.conftest import CAP5_FIXED_CORR, CAP5_FIXED_CAUS, CAP5_TEST_TS
        tx = ModelLifecycleTransition(
            transition_id="01920000000070008000000000009999",
            model_id=mv.model_id,
            model_version=mv.version,
            from_status=ModelLifecycleStatus.CANDIDATE,
            to_status=ModelLifecycleStatus.TESTED,
            reason="test command",
            evidence_refs=["ev-1"],
            requested_by="tester",
            approved_by="lead",
            requested_ts=CAP5_TEST_TS,
            correlation_id=CAP5_FIXED_CORR,
            causation_id=CAP5_FIXED_CAUS,
        )
        tx_sha = storage.write_transition(tx)
        assert isinstance(tx_sha, str) and len(tx_sha) == 64
        history = storage.read_transitions(mv.model_id, mv.version)
        assert len(history) == 1
        assert history[0].transition_id == tx.transition_id

    def test_phase1_storage_08_update_overwrites_appends_new_sha(self, cap5_fresh_storage):
        from dataclasses import replace
        storage = cap5_fresh_storage
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        sha1 = storage.write_model_version(mv, check_duplicate=True)
        mv2 = replace(mv, artifact_uri="file:///updated/artifact.pkl")
        sha2 = storage.write_model_version(mv2, check_duplicate=False)
        assert sha1 != sha2
        mv_dir = storage._model_version_dir(mv.model_id, mv.version)
        files = list(mv_dir.glob("mv-*.json"))
        assert len(files) >= 2
