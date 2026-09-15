from __future__ import annotations

import pytest

from app.rollback import (
    RollbackEngine,
    RollbackAuditPayload,
    ROLLBACK_COMMAND_NAME_LITERAL,
    ThresholdsConfig,
)


AUDIT_FIELD_NAMES = [
    "decision_id",
    "correlation_id",
    "causation_id",
    "occurred_ts",
    "trigger_type",
    "current_champion_model_id",
    "current_champion_version",
    "target_model_id",
    "target_version",
    "target_mode",
    "eligible_flag",
    "reasons",
    "approval_count",
    "thresholds_version",
    "decision_sha256",
    "rollback_command_name",
]


def test_audit_payload_has_all_expected_fields(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=30)
    _, audit = engine.evaluate(**common_evaluate_kwargs)
    for f in AUDIT_FIELD_NAMES:
        assert hasattr(audit, f), f"audit missing field {f}"


def test_occurred_ts_equals_evidence_ts_not_now(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=31)
    _, audit = engine.evaluate(**common_evaluate_kwargs)
    assert audit.occurred_ts == common_evaluate_kwargs["evidence_ts"]


def test_corr_caus_preserved_unchanged(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=32)
    _, audit = engine.evaluate(**common_evaluate_kwargs)
    assert audit.correlation_id == common_evaluate_kwargs["correlation_id"]
    assert audit.causation_id == common_evaluate_kwargs["causation_id"]


def test_command_name_only_literal_not_executed(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=33)
    _, audit = engine.evaluate(**common_evaluate_kwargs)
    assert audit.rollback_command_name == ROLLBACK_COMMAND_NAME_LITERAL
    assert audit.rollback_command_name == "rollback_champion"


def test_audit_payload_to_sorted_dict_schema_sha_ok(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=34)
    _, audit = engine.evaluate(**common_evaluate_kwargs)
    sd = audit.to_sorted_dict()
    assert isinstance(sd, dict)
    sha = audit.schema_sha256()
    assert isinstance(sha, str) and len(sha) == 64


@pytest.mark.parametrize("mode", ["restore_prior_champion", "observe_only_disabled"])
def test_target_mode_preserved_in_audit(mode, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=35)
    kw = dict(common_evaluate_kwargs)
    kw["target_mode"] = mode
    _, audit = engine.evaluate(**kw)
    assert audit.target_mode == mode
