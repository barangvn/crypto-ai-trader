from __future__ import annotations

import pytest
from decimal import Decimal
from app.contracts.exceptions import ContractSchemaError
from app.contracts import (
    ModelLifecycleStatus,
    ModelPurposeEnum,
    DatasetKindEnum,
    CCWinnerEnum,
    ModelVersion,
    TrainingDataRange,
    ModelCompatibilityRef,
    QualityFlags,
    schema_sha256,
)


# ---------------------------------------------------------------------------
# C-14: ModelLifecycleStatus tam 6 değer exact — 7. değer (HOLD) FAIL
# ---------------------------------------------------------------------------


def test_C14_enum_6_values_exact():
    actual = sorted(e.value for e in ModelLifecycleStatus)
    expected = sorted(
        ["candidate", "tested", "paper", "challenger", "champion", "retired"]
    )
    assert actual == expected
    assert len(ModelLifecycleStatus) == 6


def test_C14_hold_7th_value_not_exists():
    # 7. değer HOLD yok
    with pytest.raises(ValueError):
        ModelLifecycleStatus("hold")


def test_C14_other_exact_enums_size():
    # ModelPurposeEnum 5
    assert len(ModelPurposeEnum) == 5
    # DatasetKindEnum 4
    assert len(DatasetKindEnum) == 4
    # CCWinnerEnum 3
    assert len(CCWinnerEnum) == 3


# ---------------------------------------------------------------------------
# Base fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_mv_args() -> dict:
    return dict(
        model_id="trend_dual_momentum",
        version="1.2.0",
        purpose=ModelPurposeEnum.DIRECTIONAL,
        training_data_range=TrainingDataRange(
            start="2024-01-01T00:00:00.000Z",
            end="2026-01-01T00:00:00.000Z",
        ),
        feature_version="fv_2026_01",
        compatibility_ref=ModelCompatibilityRef(
            feature_version="fv_2026_01",
            strategy_version="strat_v2.3.0",
            regime_version="regime_v1.0.0",
        ),
        hyperparams={
            "lookback_bars": 60,
            "threshold_z": 1.96,
            "use_volume": False,
        },
        artifact_uri="s3://crypto-models/trend_dual/v1.2.0/model.onnx",
        status=ModelLifecycleStatus.CANDIDATE,
        created_ts="2026-01-15T08:00:00.000Z",
        correlation_id="COR_MODEL_VER_001",
        causation_id="TRAIN_RUN_778899",
        quality_flags=None,
        metadata={"dataset_hash": "abc123"},
        promoted_at=None,
        retired_at=None,
    )


# ---------------------------------------------------------------------------
# C-15: model_id / version empty RAISE
# ---------------------------------------------------------------------------


def test_C15_model_id_empty_raises(base_mv_args):
    base_mv_args["model_id"] = ""
    with pytest.raises(ContractSchemaError):
        ModelVersion(**base_mv_args)


def test_C15_version_empty_raises(base_mv_args):
    base_mv_args["version"] = ""
    with pytest.raises(ContractSchemaError):
        ModelVersion(**base_mv_args)


# ---------------------------------------------------------------------------
# C-16: purpose invalid (non-5-enum) RAISE
# ---------------------------------------------------------------------------


def test_C16_purpose_invalid_string_raises(base_mv_args):
    base_mv_args["purpose"] = "invalid_purpose_foo"  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        ModelVersion(**base_mv_args)


def test_C16_all_5_purpose_values_pass(base_mv_args):
    for p in ModelPurposeEnum:
        base_mv_args["purpose"] = p
        mv = ModelVersion(**base_mv_args)
        assert mv.purpose == p


# ---------------------------------------------------------------------------
# C-17: training_data_range.start > end RAISE
# ---------------------------------------------------------------------------


def test_C17_training_range_start_after_end_raises(base_mv_args):
    with pytest.raises(ContractSchemaError):
        base_mv_args["training_data_range"] = TrainingDataRange(
            start="2026-06-01T00:00:00.000Z",
            end="2024-01-01T00:00:00.000Z",
        )
        ModelVersion(**base_mv_args)


# ---------------------------------------------------------------------------
# C-18: hyperparams nested dict RAISE (FLAT DICT rule AD-22)
# ---------------------------------------------------------------------------


def test_C18_hyperparams_nested_dict_raises(base_mv_args):
    base_mv_args["hyperparams"] = {
        "tree": 3,
        "nested": {"key": "value"},  # nested — FLAT YASAK
    }
    with pytest.raises(ContractSchemaError):
        ModelVersion(**base_mv_args)


def test_C18_hyperparams_flat_pass(base_mv_args):
    # int, float, str, bool, Decimal, None — FLAT — geçer
    base_mv_args["hyperparams"] = {
        "a": 1,
        "b": 2.5,
        "c": "foo",
        "d": True,
        "e": Decimal("3.14"),
        "f": None,
    }
    mv = ModelVersion(**base_mv_args)
    assert mv.hyperparams["a"] == 1


# ---------------------------------------------------------------------------
# C-19: compatibility_ref.feature_version EMPTY RAISE
# ---------------------------------------------------------------------------


def test_C19_compatibility_feature_version_empty_raises():
    with pytest.raises(ContractSchemaError):
        ModelCompatibilityRef(
            feature_version="",  # empty
            strategy_version="s1",
            regime_version="r1",
        )


# ---------------------------------------------------------------------------
# C-20: artifact_uri empty RAISE
# ---------------------------------------------------------------------------


def test_C20_artifact_uri_empty_raises(base_mv_args):
    base_mv_args["artifact_uri"] = ""
    with pytest.raises(ContractSchemaError):
        ModelVersion(**base_mv_args)


# ---------------------------------------------------------------------------
# C-21: status=retired + promoted_at var + retired_at None → PASS
# (proposal-only fields — schema no-raise)
# ---------------------------------------------------------------------------


def test_C21_retired_status_metadata_pass(base_mv_args):
    base_mv_args["status"] = ModelLifecycleStatus.RETIRED
    base_mv_args["promoted_at"] = "2026-04-01T00:00:00.000Z"
    base_mv_args["retired_at"] = None
    mv = ModelVersion(**base_mv_args)
    assert mv.status == ModelLifecycleStatus.RETIRED
    assert mv.promoted_at is not None


# ---------------------------------------------------------------------------
# Ek: Determinism ModelVersion 10x
# ---------------------------------------------------------------------------


def test_modelversion_10x_determinism(base_mv_args):
    mv = ModelVersion(**base_mv_args)
    digests = [schema_sha256(mv) for _ in range(10)]
    assert len(set(digests)) == 1
