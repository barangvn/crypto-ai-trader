from __future__ import annotations

from dataclasses import asdict

import pytest

from app.contracts import ModelVersion
from app.registry.exceptions import ERR_STORAGE_CORRUPT_JSON, StorageError
from tests.registry.conftest import sample_mv


def test_happy_read_returns_same_mv(created_registry):
    reg, bus, storage, created, sha_created = created_registry
    read_mv, sha_read = reg.get(created.model_id, created.version)
    assert isinstance(read_mv, ModelVersion)
    assert sha_read == sha_created
    assert read_mv.model_id == created.model_id
    assert read_mv.version == created.version
    assert read_mv.purpose == created.purpose
    assert read_mv.status == created.status


def test_two_reads_same_sha(created_registry):
    reg, bus, storage, created, sha_created = created_registry
    mv1, sha1 = reg.get(created.model_id, created.version)
    mv2, sha2 = reg.get(created.model_id, created.version)
    assert sha1 == sha2
    assert sha1 == sha_created


def test_read_wrong_version_raises_not_found(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(StorageError) as excinfo:
        reg.get(created.model_id, "999.999.999")
    reason = excinfo.value.reason_code
    assert reason in ("MODEL_VERSION_NOT_FOUND", "MODEL_NOT_FOUND")


def test_read_wrong_model_id_raises_not_found(created_registry):
    reg, bus, storage, created, sha = created_registry
    with pytest.raises(StorageError) as excinfo:
        reg.get("nonexistent_model_xyz", created.version)
    reason = excinfo.value.reason_code
    assert reason in ("MODEL_VERSION_NOT_FOUND", "MODEL_NOT_FOUND")


def test_read_corrupt_json_raises_storage_corrupt(created_registry, tmp_registry_root):
    reg, bus, storage, created, sha = created_registry
    mv_dir = tmp_registry_root / "models" / created.model_id.lower() / created.version
    if not mv_dir.exists():
        mv_dir.mkdir(parents=True, exist_ok=True)
    mv_files = sorted(mv_dir.glob("mv-*.json"))
    assert len(mv_files) >= 1, "Expected at least one mv file to corrupt"
    target = mv_files[0]
    target.write_text("{bad json", encoding="utf-8")
    with pytest.raises(StorageError) as excinfo:
        reg.get(created.model_id, created.version)
    assert excinfo.value.reason_code == ERR_STORAGE_CORRUPT_JSON
