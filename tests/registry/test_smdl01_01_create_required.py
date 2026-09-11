from __future__ import annotations

import re

import pytest

from app.contracts import ModelVersion
from app.registry.exceptions import ERR_WALK_FORWARD_MAX, RegistryError
from tests.registry.conftest import sample_mv


def test_create_happy_path_returns_tuple(created_registry):
    reg, bus, storage, created, sha = created_registry
    assert isinstance(created, ModelVersion)
    assert isinstance(sha, str)


def test_create_returns_modelversion_instance(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv()
    created, sha = reg.create(mv)
    assert isinstance(created, ModelVersion)


def test_create_sha_is_64_char_hex_lowercase(created_registry):
    reg, bus, storage, created, sha = created_registry
    assert len(sha) == 64
    assert re.match(r"^[0-9a-f]{64}$", sha) is not None


def test_create_sample_mv_has_16_required_fields(created_registry):
    reg, bus, storage, created, sha = created_registry
    mv_dict = created.to_sorted_dict()
    required_16 = {
        "model_id",
        "version",
        "purpose",
        "training_data_range",
        "feature_version",
        "compatibility_ref",
        "hyperparams",
        "artifact_uri",
        "status",
        "created_ts",
        "correlation_id",
        "causation_id",
        "quality_flags",
        "metadata",
        "promoted_at",
        "retired_at",
    }
    assert required_16.issubset(set(mv_dict.keys()))


def test_create_walk_forward_run_ids_exceeds_max_250_raises(fresh_registry):
    reg, bus, storage = fresh_registry
    too_many = [f"wf_{i}" for i in range(251)]
    mv = sample_mv(metadata={"walk_forward_run_ids": too_many})
    with pytest.raises(RegistryError) as excinfo:
        reg.create(mv)
    assert excinfo.value.reason_code == ERR_WALK_FORWARD_MAX


def test_create_walk_forward_run_ids_max_250_ok(fresh_registry):
    reg, bus, storage = fresh_registry
    exactly_max = [f"wf_{i}" for i in range(250)]
    mv = sample_mv(metadata={"walk_forward_run_ids": exactly_max})
    created, sha = reg.create(mv)
    assert isinstance(created, ModelVersion)
    assert len(created.metadata.get("walk_forward_run_ids", [])) == 250
