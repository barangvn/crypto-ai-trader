from __future__ import annotations

import os
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.contracts import (
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelPurposeEnum,
    ModelVersion,
    QualityFlags,
    TrainingDataRange,
    ULID,
    now_instant,
)


TEST_TS = "2026-09-09T00:00:00.000Z"
FIXED_CORR = ULID("01920000-0000-7000-8000-000000000001")
FIXED_CAUS = ULID("01920000-0000-7000-8000-000000000002")

# Real 5-purpose enum values
PURPOSES = list(ModelPurposeEnum.__members__.values())
STATUSES = list(ModelLifecycleStatus.__members__.values())


def _sample_training_range(
    start: str = "2024-01-01T00:00:00.000Z",
    end: str = "2025-12-31T00:00:00.000Z",
) -> TrainingDataRange:
    return TrainingDataRange(start=start, end=end)


def _sample_compat(
    f: str = "v1.2.3",
    s: str = "v0.9.1",
    r: str = "v2.0.0",
) -> ModelCompatibilityRef:
    return ModelCompatibilityRef(feature_version=f, strategy_version=s, regime_version=r)


def sample_hyperparams() -> dict[str, Any]:
    return {
        "learning_rate": 0.01,
        "epochs": 100,
        "hidden_size": 64,
        "dropout": 0.2,
        "model_family": "xgboost",
    }


def sample_mv(
    model_id: str = "trend_momentum_v1",
    version: str = "1.0.0",
    purpose: ModelPurposeEnum = ModelPurposeEnum.DIRECTIONAL,
    status: ModelLifecycleStatus = ModelLifecycleStatus.CANDIDATE,
    training_range: TrainingDataRange | None = None,
    feature_version: str = "v1.2.3",
    compat: ModelCompatibilityRef | None = None,
    hyperparams: dict[str, Any] | None = None,
    artifact_uri: str = "file:///artifacts/models/trend-v1-0-0.pkl",
    created_ts: str | None = None,
    correlation_id: str | ULID = FIXED_CORR,
    causation_id: str | ULID = FIXED_CAUS,
    metadata: dict[str, Any] | None = None,
    quality_flags: QualityFlags | None = None,
    promoted_at: str | None = None,
    retired_at: str | None = None,
) -> ModelVersion:
    meta = dict(metadata or {})
    # registry expects walk_forward_run_ids / approval_refs to be IN metadata (OD)
    meta.setdefault("walk_forward_run_ids", [])
    meta.setdefault("metrics_on_promotion", {
        "return_pct": Decimal("0.185"),
        "max_drawdown_pct": 0.055,
        "sharpe_ratio": 1.95,
    })
    return ModelVersion(
        model_id=model_id,
        version=version,
        purpose=purpose,
        training_data_range=training_range or _sample_training_range(),
        feature_version=feature_version,
        compatibility_ref=compat or _sample_compat(feature_version),
        hyperparams=hyperparams or sample_hyperparams(),
        artifact_uri=artifact_uri,
        status=status,
        created_ts=created_ts or TEST_TS,
        correlation_id=ULID(correlation_id) if isinstance(correlation_id, str) else correlation_id,
        causation_id=ULID(causation_id) if isinstance(causation_id, str) else causation_id,
        quality_flags=quality_flags,
        metadata=meta,
        promoted_at=promoted_at,
        retired_at=retired_at,
    )


@pytest.fixture()
def tmp_registry_root(tmp_path: Path) -> Path:
    root = tmp_path / "registry-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    yield root
    # Cleanup optional (tmp_path does it)
    try:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture()
def fresh_storage(tmp_registry_root: Path):
    from app.registry.storage import LocalFSRegistryStorage

    return LocalFSRegistryStorage(root=tmp_registry_root)


@pytest.fixture()
def fresh_registry(tmp_registry_root: Path):
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry import ModelRegistry
    from app.registry.storage import LocalFSRegistryStorage

    bus = InMemoryTypedEventBus()
    storage = LocalFSRegistryStorage(root=tmp_registry_root)
    return ModelRegistry(storage=storage, event_bus=bus, root=tmp_registry_root), bus, storage


@pytest.fixture()
def created_registry(fresh_registry):
    """Registry with sample mv already created."""
    reg, bus, storage = fresh_registry
    mv = sample_mv()
    created, sha = reg.create(mv)
    return reg, bus, storage, created, sha
