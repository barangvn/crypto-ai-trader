from __future__ import annotations

import pytest

from app.contracts import (
    ContractSchemaError,
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelLifecycleTransition,
    ModelPurposeEnum,
    ModelVersion,
    QualityFlags,
    TrainingDataRange,
    ULID,
)
from tests.cap5.conftest import (
    CAP5_FIXED_CORR,
    CAP5_FIXED_CAUS,
    CAP5_TEST_TS,
    cap5_sample_compat,
    cap5_sample_hyperparams,
    cap5_sample_training_range,
)


class TestPhase1ContractSchemaCompanions:
    def phase1_mv_construct(self, **overrides) -> ModelVersion:
        base = dict(
            model_id="test_model_v1",
            version="1.0.0",
            purpose=ModelPurposeEnum.DIRECTIONAL,
            training_data_range=cap5_sample_training_range(),
            feature_version="v1.0.0",
            compatibility_ref=cap5_sample_compat("v1.0.0", "v1.0.0", "v1.0.0"),
            hyperparams=cap5_sample_hyperparams(),
            artifact_uri="file:///artifacts/models/test-v1.pkl",
            status=ModelLifecycleStatus.CANDIDATE,
            created_ts=CAP5_TEST_TS,
            correlation_id=CAP5_FIXED_CORR,
            causation_id=CAP5_FIXED_CAUS,
        )
        base.update(overrides)
        return ModelVersion(**base)

    def test_phase1_contract_01_invalid_model_id_regex(self):
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(model_id="Invalid-Id-With-Dashes")

    def test_phase1_contract_02_invalid_version_regex(self):
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(version="version with spaces")

    def test_phase1_contract_03_invalid_purpose_enum(self):
        with pytest.raises((ContractSchemaError, ValueError)):
            self.phase1_mv_construct(purpose="not_a_real_purpose")

    @pytest.mark.xfail(strict=False, reason="ADN open decision: TrainingDataRange Instant compare edge case")
    def test_phase1_contract_04_training_end_before_start(self):
        bad_range = TrainingDataRange(
            start="2025-12-31T00:00:00.000Z",
            end="2024-01-01T00:00:00.000Z",
        )
        with pytest.raises((ContractSchemaError, TypeError, ValueError)):
            self.phase1_mv_construct(training_data_range=bad_range)

    @pytest.mark.xfail(strict=False, reason="ADN open decision: ModelCompatibilityRef empty feature edge case")
    def test_phase1_contract_05_compat_empty_feature_version(self):
        try:
            bad_compat = ModelCompatibilityRef(
                feature_version="",
                strategy_version="v1.0.0",
                regime_version="v1.0.0",
            )
        except (ContractSchemaError, ValueError, TypeError):
            return
        with pytest.raises((ContractSchemaError, ValueError, TypeError)):
            self.phase1_mv_construct(compatibility_ref=bad_compat)

    def test_phase1_contract_06_hyperparams_nested_dict_rejected(self):
        bad_hp = {"nested": {"key": "value"}}
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(hyperparams=bad_hp)

    def test_phase1_contract_07_artifact_uri_empty(self):
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(artifact_uri="")

    def test_phase1_contract_08_invalid_status_enum(self):
        with pytest.raises((ContractSchemaError, ValueError)):
            self.phase1_mv_construct(status="not_a_lifecycle_enum_value")

    def test_phase1_contract_09_created_ts_bad_instant(self):
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(created_ts="not-a-timestamp")

    def test_phase1_contract_10_tx_fsm_forbidden_raises(self):
        with pytest.raises(ContractSchemaError):
            ModelLifecycleTransition(
                transition_id="01920000000070008000000000001111",
                model_id="x",
                model_version="1.0.0",
                from_status=ModelLifecycleStatus.CANDIDATE,
                to_status=ModelLifecycleStatus.CHAMPION,
                reason="F1 forbidden edge",
                evidence_refs=["e1"],
                requested_by="x",
                approved_by="y",
                requested_ts=CAP5_TEST_TS,
                correlation_id=CAP5_FIXED_CORR,
                causation_id=CAP5_FIXED_CAUS,
            )

    def test_phase1_contract_11_tx_same_status_noop_raises(self):
        with pytest.raises(ContractSchemaError):
            ModelLifecycleTransition(
                transition_id="01920000000070008000000000002222",
                model_id="x",
                model_version="1.0.0",
                from_status=ModelLifecycleStatus.PAPER,
                to_status=ModelLifecycleStatus.PAPER,
                reason="noop same status YASAK C-29",
                evidence_refs=["e1"],
                requested_by="x",
                approved_by="y",
                requested_ts=CAP5_TEST_TS,
                correlation_id=CAP5_FIXED_CORR,
                causation_id=CAP5_FIXED_CAUS,
            )

    def test_phase1_contract_12_tx_empty_reason_raises(self):
        with pytest.raises(ContractSchemaError):
            ModelLifecycleTransition(
                transition_id="01920000000070008000000000003333",
                model_id="x",
                model_version="1.0.0",
                from_status=ModelLifecycleStatus.CANDIDATE,
                to_status=ModelLifecycleStatus.TESTED,
                reason="",
                evidence_refs=["e1"],
                requested_by="x",
                approved_by="y",
                requested_ts=CAP5_TEST_TS,
                correlation_id=CAP5_FIXED_CORR,
                causation_id=CAP5_FIXED_CAUS,
            )

    def test_phase1_contract_13_correlation_id_non_ulidish(self):
        with pytest.raises(ContractSchemaError):
            self.phase1_mv_construct(correlation_id="short")
