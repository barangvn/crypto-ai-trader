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


CAP5_TEST_TS = "2026-09-15T00:00:00.000Z"
CAP5_FIXED_CORR = ULID("01920000-0000-7000-8000-0000000000AA")
CAP5_FIXED_CAUS = ULID("01920000-0000-7000-8000-0000000000BB")

CAP5_PURPOSES = list(ModelPurposeEnum.__members__.values())
CAP5_STATUSES = list(ModelLifecycleStatus.__members__.values())


def cap5_sample_training_range(
    start: str = "2024-01-01T00:00:00.000Z",
    end: str = "2025-12-31T00:00:00.000Z",
) -> TrainingDataRange:
    return TrainingDataRange(start=start, end=end)


def cap5_sample_compat(
    f: str = "v1.2.3",
    s: str = "v0.9.1",
    r: str = "v2.0.0",
) -> ModelCompatibilityRef:
    return ModelCompatibilityRef(feature_version=f, strategy_version=s, regime_version=r)


def cap5_sample_hyperparams() -> dict[str, Any]:
    return {
        "learning_rate": 0.01,
        "epochs": 100,
        "hidden_size": 64,
        "dropout": 0.2,
        "model_family": "xgboost",
    }


def cap5_sample_mv(
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
    correlation_id: str | ULID = CAP5_FIXED_CORR,
    causation_id: str | ULID = CAP5_FIXED_CAUS,
    metadata: dict[str, Any] | None = None,
    quality_flags: QualityFlags | None = None,
    promoted_at: str | None = None,
    retired_at: str | None = None,
) -> ModelVersion:
    meta = dict(metadata or {})
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
        training_data_range=training_range or cap5_sample_training_range(),
        feature_version=feature_version,
        compatibility_ref=compat or cap5_sample_compat(feature_version),
        hyperparams=hyperparams or cap5_sample_hyperparams(),
        artifact_uri=artifact_uri,
        status=status,
        created_ts=created_ts or CAP5_TEST_TS,
        correlation_id=ULID(correlation_id) if isinstance(correlation_id, str) else correlation_id,
        causation_id=ULID(causation_id) if isinstance(causation_id, str) else causation_id,
        quality_flags=quality_flags,
        metadata=meta,
        promoted_at=promoted_at,
        retired_at=retired_at,
    )


@pytest.fixture()
def cap5_tmp_registry_root(tmp_path: Path) -> Path:
    root = tmp_path / ".registry-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    yield root
    try:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture()
def cap5_fresh_storage(cap5_tmp_registry_root: Path):
    from app.registry.storage import LocalFSRegistryStorage

    return LocalFSRegistryStorage(root=cap5_tmp_registry_root)


@pytest.fixture()
def cap5_fresh_registry(cap5_tmp_registry_root: Path):
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry import ModelRegistry
    from app.registry.storage import LocalFSRegistryStorage

    bus = InMemoryTypedEventBus()
    storage = LocalFSRegistryStorage(root=cap5_tmp_registry_root)
    return ModelRegistry(storage=storage, event_bus=bus, root=cap5_tmp_registry_root), bus, storage


@pytest.fixture()
def cap5_seed_corr() -> dict[str, str]:
    return {
        "correlation_id": str(CAP5_FIXED_CORR),
        "causation_id": str(CAP5_FIXED_CAUS),
        "created_ts": CAP5_TEST_TS,
        "requested_ts": CAP5_TEST_TS,
    }


@pytest.fixture()
def cap5_created_candidate(cap5_fresh_registry):
    reg, bus, storage = cap5_fresh_registry
    mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created, sha = reg.create(mv)
    return reg, bus, storage, created, sha


@pytest.fixture()
def cap5_created_tested(cap5_created_candidate):
    reg, bus, storage, mv, sha = cap5_created_candidate
    new_mv, new_sha, tx, env = reg.request_transition(
        model_id=mv.model_id,
        version=mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="test",
        evidence_ref_ids=["ev-001"],
        requested_by="tester",
        approved_by="lead",
    )
    return reg, bus, storage, new_mv, new_sha, tx


@pytest.fixture()
def cap5_created_paper(cap5_created_tested):
    reg, bus, storage, mv, sha, _tx = cap5_created_tested
    new_mv, new_sha, tx, env = reg.request_transition(
        model_id=mv.model_id,
        version=mv.version,
        to_status=ModelLifecycleStatus.PAPER,
        transition_command="paper",
        evidence_ref_ids=["ev-002"],
        requested_by="tester",
        approved_by="lead",
    )
    return reg, bus, storage, new_mv, new_sha, tx


@pytest.fixture()
def cap5_created_challenger(cap5_created_paper):
    reg, bus, storage, mv, sha, _tx = cap5_created_paper
    new_mv, new_sha, tx, env = reg.request_transition(
        model_id=mv.model_id,
        version=mv.version,
        to_status=ModelLifecycleStatus.CHALLENGER,
        transition_command="challenger",
        evidence_ref_ids=["ev-003"],
        requested_by="tester",
        approved_by="lead",
    )
    return reg, bus, storage, new_mv, new_sha, tx


@pytest.fixture()
def cap5_champion_with_approval(cap5_created_challenger):
    reg, bus, storage, mv, sha, _tx = cap5_created_challenger
    reg.update(
        model_id=mv.model_id,
        version=mv.version,
        patch={"approval_refs": ["appr-001", "appr-002"]},
    )
    reg.set_predecessor(
        model_id=mv.model_id,
        version=mv.version,
        prev_model_id="old_champion",
        prev_version="0.9.0",
    )
    reloaded_mv, reloaded_sha = reg.get(mv.model_id, mv.version)
    new_mv, new_sha, tx, env = reg.request_transition(
        model_id=reloaded_mv.model_id,
        version=reloaded_mv.version,
        to_status=ModelLifecycleStatus.CHAMPION,
        transition_command="promote_champion",
        evidence_ref_ids=["ev-004", "ev-005"],
        requested_by="promotion_panel",
        approved_by="chief_ml",
        metadata={
            "gate_decision_id": "gate-dec-001",
            "approval_refs": ["appr-001", "appr-002"],
            "audit_note": "Gate passed, challenger outperforms champion on all 11 metrics",
        },
    )
    return reg, bus, storage, new_mv, new_sha, tx
