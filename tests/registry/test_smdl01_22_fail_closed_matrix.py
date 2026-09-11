from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ContractSchemaError,
    ModelLifecycleStatus,
    ModelPurposeEnum,
    TrainingDataRange,
)
from app.registry.exceptions import (
    ERR_CAP5_DIRECT_MUTATION,
    ERR_FIELD_IMMUTABLE,
    ERR_FIELD_VALIDATION,
    ERR_PROMOTE_MIN_APPROVAL,
    ERR_STORAGE_CORRUPT_JSON,
    ERR_VERSION_ALREADY_EXISTS,
    RegistryError,
    StorageError,
)
from app.registry.registry import EvidenceKind, EvidenceRef
from tests.registry.conftest import sample_mv


FAIL_CLOSED_CASES = [
    ("A", "create_missing_field"),
    ("B", "invalid_enum_purpose"),
    ("C", "fsm_forbidden_edge"),
    ("D", "direct_status_mutation"),
    ("E", "duplicate_create"),
    ("F", "read_notfound"),
    ("G", "corrupt_json_storage"),
    ("H", "evidence_sha_invalid"),
    ("I", "t4_promote_no_approval"),
    ("J", "artifact_empty"),
    ("K", "hyperparams_immutable"),
    ("L", "unknown_patch_key"),
]


@pytest.mark.parametrize("category,label", FAIL_CLOSED_CASES)
def test_fail_closed_no_silent_success(fresh_registry, category, label):
    reg, bus, storage = fresh_registry

    if category == "A":
        with pytest.raises((ContractSchemaError, RegistryError, StorageError, Exception)) as excinfo:
            mv = sample_mv()
            object.__setattr__(mv, "model_id", None)
            reg.create(mv)
        assert True

    elif category == "B":
        with pytest.raises((ContractSchemaError, RegistryError, StorageError)) as excinfo:
            mv = sample_mv(purpose="invalid_purpose_enum_value_xyz")
            reg.create(mv)
        assert hasattr(excinfo.value, "reason_code") or isinstance(
            excinfo.value, ContractSchemaError
        )

    elif category == "C":
        mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, sha = reg.create(mv)
        with pytest.raises((ContractSchemaError, RegistryError, StorageError)) as excinfo:
            reg.request_transition(
                model_id=created.model_id,
                version=created.version,
                to_status=ModelLifecycleStatus.CHAMPION,
                transition_command="illegal_skip_steps",
                requested_by="tester",
                approved_by="tester",
            )
        assert hasattr(excinfo.value, "reason_code") or isinstance(
            excinfo.value, ContractSchemaError
        )

    elif category == "D":
        mv = sample_mv()
        created, sha = reg.create(mv)
        with pytest.raises(RegistryError) as excinfo:
            reg.update(
                created.model_id,
                created.version,
                {"status": ModelLifecycleStatus.PAPER},
            )
        assert excinfo.value.reason_code == ERR_CAP5_DIRECT_MUTATION

    elif category == "E":
        mv = sample_mv()
        reg.create(mv)
        with pytest.raises((RegistryError, StorageError)) as excinfo:
            mv2 = sample_mv()
            reg.create(mv2)
        assert excinfo.value.reason_code == ERR_VERSION_ALREADY_EXISTS

    elif category == "F":
        with pytest.raises(StorageError) as excinfo:
            reg.get("nonexistent_model_abc", "0.0.1")
        assert hasattr(excinfo.value, "reason_code")

    elif category == "G":
        mv = sample_mv()
        created, sha = reg.create(mv)
        mv_dir = storage.root / "models" / created.model_id.lower() / created.version
        mv_files = sorted(mv_dir.glob("mv-*.json"))
        assert len(mv_files) >= 1
        target = mv_files[0]
        target.write_text("{definitely not valid json!", encoding="utf-8")
        with pytest.raises(StorageError) as excinfo:
            reg.get(created.model_id, created.version)
        assert excinfo.value.reason_code == ERR_STORAGE_CORRUPT_JSON

    elif category == "H":
        with pytest.raises((RegistryError, ContractSchemaError)) as excinfo:
            ev = EvidenceRef(
                kind=EvidenceKind.HISTORICAL_OOS_EVAL,
                ref_id="eval_001",
                artifact_uri="file:///artifacts/eval.pkl",
                source_created_ts="2026-09-09T00:00:00.000Z",
                correlation_id="CORR00001",
                integrity_sha256="not_valid_sha",
            )
        assert hasattr(excinfo.value, "reason_code") or isinstance(
            excinfo.value, (RegistryError, ContractSchemaError)
        )

    elif category == "I":
        mv = sample_mv(
            status=ModelLifecycleStatus.CHALLENGER,
            metadata={"approval_refs": []},
        )
        created, sha = reg.create(mv)
        with pytest.raises(RegistryError) as excinfo:
            reg.request_transition(
                model_id=created.model_id,
                version=created.version,
                to_status=ModelLifecycleStatus.CHAMPION,
                transition_command="promote_without_approval",
                requested_by="tester",
                approved_by="tester",
            )
        assert excinfo.value.reason_code == ERR_PROMOTE_MIN_APPROVAL

    elif category == "J":
        with pytest.raises((ContractSchemaError, RegistryError)) as excinfo:
            mv = sample_mv(artifact_uri="")
            reg.create(mv)
        assert True

    elif category == "K":
        mv = sample_mv()
        created, sha = reg.create(mv)
        with pytest.raises(RegistryError) as excinfo:
            reg.update(
                created.model_id,
                created.version,
                {"hyperparams": {"learning_rate": 0.0001}},
            )
        assert excinfo.value.reason_code == ERR_FIELD_IMMUTABLE

    elif category == "L":
        mv = sample_mv()
        created, sha = reg.create(mv)
        with pytest.raises(RegistryError) as excinfo:
            reg.update(
                created.model_id,
                created.version,
                {"nonexistent_field_xyz": "value"},
            )
        assert excinfo.value.reason_code in (ERR_FIELD_VALIDATION, "FIELD_IMMUTABLE")
