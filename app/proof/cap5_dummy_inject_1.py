from __future__ import annotations

from pathlib import Path
from typing import Any

from app.contracts.model import ModelVersion


def _dummy_p1_direct_assign(mv: ModelVersion) -> None:
    mv.status = "champion"
    mv.metadata["status"] = "challenger"


def _dummy_p2_non_registry_transition(mv: ModelVersion) -> None:
    non_registry = Any
    non_registry.request_transition(mv, "candidate", "champion")


def _dummy_p3_write_primitives() -> None:
    target = Path(".registry-artifacts") / "models" / "dummy.json"
    with open(target, "wb") as f:
        f.write(b"{}")
    target.write_text("{}")


def _dummy_p4_constructor_bypass() -> None:
    from app.contracts.model import (
        ModelCompatibilityRef,
        ModelLifecycleStatus,
        ModelPurposeEnum,
        TrainingDataRange,
    )
    _ = ModelVersion(
        model_id="bad_model",
        version="0.0.1",
        purpose=ModelPurposeEnum.DIRECTIONAL,
        training_data_range=TrainingDataRange(start="2024-01-01T00:00:00Z", end="2024-02-01T00:00:00Z"),
        feature_version="fv1",
        compatibility_ref=ModelCompatibilityRef(feature_version="fv1", strategy_version="sv1", regime_version="rv1"),
        hyperparams={},
        artifact_uri="file:///tmp/bad.pkl",
        status=ModelLifecycleStatus.CHAMPION,
        created_ts="2024-01-01T00:00:00Z",
        correlation_id="01HCORRELATIONID123456789",
        causation_id="01HCCAUSATIONID1234567890",
    )


def run_all_dummies() -> dict[str, int]:
    return {"p1_injects": 2, "p2_injects": 1, "p3_injects": 2, "p4_injects": 1}
