from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts import to_sorted_dict, schema_sha256

from app.rollback.builder import (
    DECISION_SCHEMA_VERSION,
    RollbackAuditPayload,
    RollbackEligibilityDecision,
    build_rollback_decision,
)
from app.rollback.evidence import (
    validate_evidence_bundle,
    validate_target_mode,
    validate_trigger_type,
)
from app.rollback.exceptions import (
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT,
)
from app.rollback.thresholds import (
    THRESHOLDS_CONFIG_VERSION_V1,
    ThresholdsConfig,
)


@dataclass
class RollbackEngine:
    storage: Any = field(default=None)
    thresholds_cfg: ThresholdsConfig | None = None
    expected_thresholds_version: str | None = None
    explicit_seed: int | None = None
    schema_version: str = DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.thresholds_cfg is None:
            self.thresholds_cfg = ThresholdsConfig.defaults_adn_v1()
        if not isinstance(self.thresholds_cfg, ThresholdsConfig):
            raise ValueError("thresholds_cfg must be ThresholdsConfig instance")
        if self.explicit_seed is not None:
            if not isinstance(self.explicit_seed, int) or isinstance(self.explicit_seed, bool):
                raise ValueError("explicit_seed must be int or None")

    def _cfg(self) -> ThresholdsConfig:
        cfg = self.thresholds_cfg
        assert cfg is not None
        return cfg

    def _champion_get(self, model_id: str, version: str) -> tuple[Any, bool]:
        storage = self.storage
        if storage is None:
            return None, False
        try:
            getter = getattr(storage, "get", None)
            if callable(getter):
                result = getter(model_id, version)
            else:
                return None, False
        except Exception:
            return None, False
        if isinstance(result, tuple) and len(result) >= 1:
            mv = result[0]
            return mv, True
        return None, False

    def _predecessor_pointer_get(self, model_id: str, version: str) -> dict[str, str] | None:
        storage = self.storage
        if storage is None:
            return None
        try:
            meth = getattr(storage, "get_predecessor", None)
            if callable(meth):
                result = meth(model_id, version)
            else:
                return None
        except Exception:
            return None
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        return None

    def _predecessor_mv_get(self, model_id: str, version: str) -> tuple[Any, bool]:
        return self._champion_get(model_id, version)

    def _artifact_storage_ok_for_mv(self, mv: Any) -> bool:
        if mv is None:
            return False
        artifact_uri = None
        try:
            artifact_uri = getattr(mv, "artifact_uri", None)
        except Exception:
            return False
        if artifact_uri is None or (isinstance(artifact_uri, str) and not artifact_uri.strip()):
            return False
        return True

    def evaluate(
        self,
        *,
        champion_model_id: str,
        champion_version: str,
        trigger_type: Any,
        rollback_strategy_ref_from_cce: Any,
        promotion_gate_passed_bool_from_cce: Any,
        delta_metrics: Any,
        approver_identity: Any,
        rationale_text: Any,
        prior_state_snapshot_ref: Any,
        degradation_evidence_count: Any,
        evidence_ts: Any,
        comparison_window_end_ts: Any,
        evidence_integrity_ok_flag: Any,
        evidence_integrity_sha: Any,
        strategy_ref_artifact_exists_flag: Any,
        approval_refs: list[Any] | None,
        explicit_approval_count_extra: Any = 0,
        correlation_id: Any = "",
        causation_id: Any = "",
        target_mode: str = "restore_prior_champion",
        evidence_canonical_bundle: Any = None,
    ) -> tuple[RollbackEligibilityDecision, RollbackAuditPayload]:
        cfg = self._cfg()

        champion_mv, _ = self._champion_get(champion_model_id, champion_version)
        if champion_mv is not None:
            champion_status = getattr(champion_mv, "status", None)
            champion_mid_use = getattr(champion_mv, "model_id", None) or champion_model_id
            champion_ver_use = getattr(champion_mv, "version", None) or champion_version
            approval_refs_from_mv = getattr(champion_mv, "approval_refs", None)
            if isinstance(approval_refs_from_mv, list) and not approval_refs:
                approval_refs_use = approval_refs_from_mv
            elif isinstance(approval_refs, list):
                approval_refs_use = approval_refs
            else:
                approval_refs_use = []
        else:
            champion_status = None
            champion_mid_use = champion_model_id
            champion_ver_use = champion_version
            approval_refs_use = list(approval_refs) if isinstance(approval_refs, list) else []

        predecessor_dict = self._predecessor_pointer_get(champion_mid_use, champion_ver_use)

        predecessor_status: Any = None
        predecessor_artifact_ok: bool = True
        if predecessor_dict is not None and isinstance(predecessor_dict, dict):
            p_mid = predecessor_dict.get("model_id")
            p_ver = predecessor_dict.get("version")
            if isinstance(p_mid, str) and isinstance(p_ver, str) and p_mid and p_ver:
                p_mv, p_found = self._predecessor_mv_get(p_mid, p_ver)
                if not p_found:
                    predecessor_dict = None
                else:
                    predecessor_status = getattr(p_mv, "status", None)
                    predecessor_artifact_ok = self._artifact_storage_ok_for_mv(p_mv)
                    if not predecessor_artifact_ok:
                        predecessor_artifact_ok = False

        evidence_reasons = validate_evidence_bundle(
            trigger_type=trigger_type,
            delta_metrics=delta_metrics,
            approver_identity=approver_identity,
            rationale_text=rationale_text,
            prior_state_snapshot_ref=prior_state_snapshot_ref,
            degradation_evidence_count=degradation_evidence_count,
            evidence_ts=evidence_ts,
            comparison_window_end_ts=comparison_window_end_ts,
            evidence_integrity_ok_flag=evidence_integrity_ok_flag,
            evidence_integrity_sha=evidence_integrity_sha,
            rollback_strategy_ref=rollback_strategy_ref_from_cce,
            strategy_ref_artifact_exists=strategy_ref_artifact_exists_flag,
            thresholds_cfg=cfg,
            evidence_canonical_bundle=evidence_canonical_bundle,
        )

        gate_passed = bool(promotion_gate_passed_bool_from_cce) is True

        t_reasons = validate_trigger_type(trigger_type)
        if predecessor_dict is None:
            if ERR_ROLLBACK_MISSING_ROLLBACK_TARGET not in evidence_reasons:
                pass
        if predecessor_artifact_ok is False and predecessor_dict is not None:
            if ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT not in evidence_reasons:
                pass

        decision, audit = build_rollback_decision(
            current_champion_model_id=str(champion_mid_use),
            current_champion_version=str(champion_ver_use),
            current_champion_status_value=champion_status,
            predecessor_dict_or_none=predecessor_dict,
            predecessor_status_value=predecessor_status,
            predecessor_artifact_storage_ok_flag=predecessor_artifact_ok,
            rollback_strategy_ref=rollback_strategy_ref_from_cce,
            evidence_validated_reasons=evidence_reasons + t_reasons,
            thresholds_cfg=cfg,
            expected_thresholds_version=self.expected_thresholds_version,
            approval_refs_len=len(approval_refs_use),
            explicit_approval_count_extra=explicit_approval_count_extra,
            trigger_type=str(trigger_type) if trigger_type is not None else "",
            target_mode=str(target_mode) if target_mode else "restore_prior_champion",
            correlation_id=str(correlation_id) if correlation_id else "",
            causation_id=str(causation_id) if causation_id else "",
            evidence_ts=str(evidence_ts) if evidence_ts else "",
            explicit_seed=self.explicit_seed,
            promotion_gate_passed_bool_from_cce=gate_passed,
            storage_schema_version=self.schema_version,
        )

        return decision, audit

    def to_sorted_dict(self) -> dict[str, Any]:
        cfg = self._cfg()
        return {
            "thresholds_cfg": to_sorted_dict(cfg),
            "expected_thresholds_version": self.expected_thresholds_version,
            "schema_version": self.schema_version,
        }

    def schema_sha256(self) -> str:
        return schema_sha256(self.to_sorted_dict())


def evaluate_rollback_eligibility(
    *,
    engine: RollbackEngine | None = None,
    **kwargs: Any,
) -> tuple[RollbackEligibilityDecision, RollbackAuditPayload]:
    eng = engine if isinstance(engine, RollbackEngine) else RollbackEngine()
    return eng.evaluate(**kwargs)
