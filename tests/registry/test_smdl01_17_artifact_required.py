from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.contracts import ContractSchemaError, ModelVersion
from tests.registry.conftest import sample_mv


def test_smdl01_17_create_with_empty_artifact_uri_raises_contract_schema_error():
    with pytest.raises(ContractSchemaError, match="artifact_uri"):
        sample_mv(artifact_uri="")


def test_smdl01_17_update_artifact_uri_ok(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv()
    created, sha1 = reg.create(mv)

    new_uri = "file:///artifacts/models/trend-v1-0-0-updated.pkl"
    updated, sha2 = reg.update(
        model_id=created.model_id,
        version=created.version,
        patch={"artifact_uri": new_uri},
    )

    assert isinstance(updated, ModelVersion)
    assert updated.artifact_uri == new_uri
    assert sha2 != sha1


def test_smdl01_17_create_with_valid_artifact_ok(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(artifact_uri="file:///artifacts/valid/model-v1.pkl")
    created, sha = reg.create(mv)
    assert isinstance(created, ModelVersion)
    assert created.artifact_uri == "file:///artifacts/valid/model-v1.pkl"
    assert isinstance(sha, str) and len(sha) == 64


def test_smdl01_17_read_mv_with_storage_missing_artifact_reference_still_readable(
    fresh_registry,
):
    reg, bus, storage = fresh_registry
    mv = sample_mv()
    created, sha = reg.create(mv)

    models_dir: Path = storage._models_dir
    mv_files = list(models_dir.rglob(f"mv-*.json"))
    assert len(mv_files) >= 1
    for mf in mv_files:
        payload = json.loads(mf.read_text(encoding="utf-8"))
        payload["artifact_uri"] = "file:///artifacts/DOES_NOT_EXIST_nonexistent_ref.pkl"
        mf.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    read_mv, read_sha = reg.get(created.model_id, created.version)
    assert isinstance(read_mv, ModelVersion)
    assert read_mv.artifact_uri == "file:///artifacts/DOES_NOT_EXIST_nonexistent_ref.pkl"
    assert read_mv.model_id == created.model_id
    assert read_mv.version == created.version
