from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import ERR_STORAGE_CORRUPT_JSON, ERR_VERSION_ALREADY_EXISTS
from app.registry.exceptions import StorageError
from app.registry.storage import LocalFSRegistryStorage, _sanitize_version, sha_from_payload
from tests.registry.conftest import sample_mv


def test_smdl01_14_write_model_version_atomic_produces_same_content(fresh_storage):
    storage: LocalFSRegistryStorage = fresh_storage
    mv = sample_mv()

    sha1 = storage.write_model_version(mv, check_duplicate=True)
    mv2 = sample_mv()
    sha2 = sha_from_payload(mv2)

    assert sha1 == sha2

    read_mv, read_sha = storage.read_model_version(mv.model_id, mv.version)
    assert read_sha == sha1
    assert read_mv.model_id == mv.model_id
    assert read_mv.version == mv.version


def test_smdl01_14_duplicate_raises_version_exists_before_file_write(fresh_storage, tmp_registry_root):
    storage: LocalFSRegistryStorage = fresh_storage
    mv = sample_mv()

    storage.write_model_version(mv, check_duplicate=True)

    mv_dir: Path = storage._model_version_dir(mv.model_id, mv.version)
    files_before = list(mv_dir.glob("mv-*.json"))
    count_before = len(files_before)

    mv_again = sample_mv()
    with pytest.raises(StorageError) as exc_info:
        storage.write_model_version(mv_again, check_duplicate=True)
    assert exc_info.value.reason_code == ERR_VERSION_ALREADY_EXISTS

    files_after = list(mv_dir.glob("mv-*.json"))
    assert len(files_after) == count_before


def test_smdl01_14_list_empty_dir_returns_empty_list(fresh_storage):
    storage: LocalFSRegistryStorage = fresh_storage
    result = storage.list_model_versions()
    assert result == []


def test_smdl01_14_transitions_write_read_round_trip_preserves_evidence_refs(fresh_storage):
    storage: LocalFSRegistryStorage = fresh_storage
    from app.contracts import ModelLifecycleTransition, ULID

    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    storage.write_model_version(mv, check_duplicate=True)

    evidence_list = ["BKT01-eval-001", "BKT02-fold-A1", "BKT03-metrics-L3"]

    tx = ModelLifecycleTransition(
        transition_id="01ABCDEF000000000000000001",
        model_id=mv.model_id,
        model_version=mv.version,
        from_status=ModelLifecycleStatus.CANDIDATE,
        to_status=ModelLifecycleStatus.TESTED,
        reason="run_backtest_and_evaluate",
        evidence_refs=list(evidence_list),
        requested_by="tester",
        approved_by="qa",
        requested_ts="2026-09-09T12:00:00.000Z",
        correlation_id=ULID("01920000-0000-7000-8000-000000000001"),
        causation_id=ULID("01920000-0000-7000-8000-000000000002"),
        metadata={},
    )
    storage.write_transition(tx)

    read_txs = storage.read_transitions(mv.model_id, mv.version)
    assert len(read_txs) == 1
    assert read_txs[0].evidence_refs == evidence_list
    assert read_txs[0].from_status == ModelLifecycleStatus.CANDIDATE
    assert read_txs[0].to_status == ModelLifecycleStatus.TESTED


def test_smdl01_14_corrupt_tx_json_raises_storage_corrupt_json(fresh_storage, tmp_registry_root):
    storage: LocalFSRegistryStorage = fresh_storage

    mv = sample_mv()
    storage.write_model_version(mv, check_duplicate=True)

    tx_dir: Path = (
        storage._transitions_dir
        / mv.model_id.lower()
        / _sanitize_version(mv.version)
    )
    tx_dir.mkdir(parents=True, exist_ok=True)
    corrupt_file = tx_dir / "tx-20260909-bogus-corrupt.json"
    corrupt_file.write_text("this is not valid json!!! {{{{{", encoding="utf-8")

    with pytest.raises(StorageError) as exc_info:
        storage.read_transitions(mv.model_id, mv.version)
    assert exc_info.value.reason_code == ERR_STORAGE_CORRUPT_JSON


def test_smdl01_14_corrupt_mv_json_raises_storage_corrupt_json(fresh_storage, tmp_registry_root):
    storage: LocalFSRegistryStorage = fresh_storage

    mv = sample_mv()
    mv_dir: Path = storage._model_version_dir(mv.model_id, mv.version)
    mv_dir.mkdir(parents=True, exist_ok=True)
    corrupt_mv = mv_dir / "mv-corrupt12.json"
    corrupt_mv.write_text("{this is: [not valid, json !!", encoding="utf-8")

    with pytest.raises(StorageError) as exc_info:
        storage.read_model_version(mv.model_id, mv.version)
    assert exc_info.value.reason_code == ERR_STORAGE_CORRUPT_JSON
