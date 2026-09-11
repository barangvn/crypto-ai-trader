from __future__ import annotations

from dataclasses import replace

import pytest

from app.contracts import (
    ContractSchemaError,
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelPurposeEnum,
    ModelVersion,
    QualityFlags,
    TrainingDataRange,
    ULID,
)
from app.registry.exceptions import RegistryError, StorageError
from tests.registry.conftest import (
    FIXED_CAUS,
    FIXED_CORR,
    TEST_TS,
    _sample_compat,
    _sample_training_range,
    sample_hyperparams,
    sample_mv,
)


def _build_overrides(raw_overrides):
    built = {}
    for k, v in raw_overrides.items():
        if callable(v):
            built[k] = v()
        else:
            built[k] = v
    return built


def _raw_mv(**overrides):
    base = {
        "model_id": "trend_momentum_v1",
        "version": "1.0.0",
        "purpose": ModelPurposeEnum.DIRECTIONAL,
        "training_data_range": _sample_training_range(),
        "feature_version": "v1.2.3",
        "compatibility_ref": _sample_compat(),
        "hyperparams": sample_hyperparams(),
        "artifact_uri": "file:///artifacts/models/trend-v1-0-0.pkl",
        "status": ModelLifecycleStatus.CANDIDATE,
        "created_ts": TEST_TS,
        "correlation_id": FIXED_CORR,
        "causation_id": FIXED_CAUS,
        "quality_flags": None,
        "metadata": {
            "walk_forward_run_ids": [],
            "metrics_on_promotion": {},
        },
        "promoted_at": None,
        "retired_at": None,
    }
    for k, v in overrides.items():
        base[k] = v
    return ModelVersion(**base)


INVALID_PAYLOAD_CASES = [
    (
        "model_id_none",
        lambda: {"model_id": None},
        (ContractSchemaError, RegistryError, StorageError, Exception),
    ),
    (
        "model_id_invalid",
        lambda: {"model_id": "UPPERCASE-NOT-ALLOWED"},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "version_empty",
        lambda: {"version": ""},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "purpose_wrong_enum",
        lambda: {"purpose": "not_a_real_purpose"},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "training_range_start_after_end",
        lambda: {
            "training_data_range": TrainingDataRange(
                start="2025-12-31T00:00:00.000Z",
                end="2024-01-01T00:00:00.000Z",
            )
        },
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "feature_version_empty",
        lambda: {"feature_version": ""},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "compat_missing",
        lambda: {"compatibility_ref": None},
        (ContractSchemaError, RegistryError, StorageError, TypeError),
    ),
    (
        "hyperparams_nested_dict",
        lambda: {"hyperparams": {"nested": {"key": "value"}}},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "hyperparams_nested_list",
        lambda: {"hyperparams": {"list_val": [1, 2, 3]}},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "artifact_uri_empty",
        lambda: {"artifact_uri": ""},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "status_invalid_enum",
        lambda: {"status": "not_a_real_status"},
        (ContractSchemaError, RegistryError, StorageError),
    ),
    (
        "created_ts_invalid",
        lambda: {"created_ts": "not-a-real-timestamp"},
        (ContractSchemaError, RegistryError, StorageError),
    ),
]


@pytest.mark.parametrize("case_name,overrides_fn,exceptions", INVALID_PAYLOAD_CASES)
def test_invalid_payload_raises(fresh_registry, case_name, overrides_fn, exceptions):
    reg, bus, storage = fresh_registry
    with pytest.raises(exceptions):
        overrides = overrides_fn()
        mv = _raw_mv(**overrides)
        reg.create(mv)


def test_correlation_id_too_short_raises(fresh_registry):
    reg, bus, storage = fresh_registry
    with pytest.raises((ContractSchemaError, RegistryError, StorageError)):
        mv = sample_mv(correlation_id="short")
        reg.create(mv)


def test_causation_id_too_short_raises(fresh_registry):
    reg, bus, storage = fresh_registry
    with pytest.raises((ContractSchemaError, RegistryError, StorageError)):
        mv = sample_mv(causation_id="tiny")
        reg.create(mv)
