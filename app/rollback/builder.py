from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, NamedTuple

from app.contracts import deep_copy, to_sorted_dict, schema_sha256
from app.contracts.model import ModelLifecycleStatus


def _recursive_sorted_any(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return bool(obj)
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj)
    if isinstance(obj, str):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _recursive_sorted_any(obj[k]) for k in sorted(obj.keys(), key=str)}
    if isinstance(obj, (list, tuple)):
        return [_recursive_sorted_any(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        items = sorted(
            (_recursive_sorted_any(x) for x in obj),
            key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"), default=str),
        )
        return items
    if is_dataclass(obj):
        d = asdict(obj)
        return {str(k): _recursive_sorted_any(d[k]) for k in sorted(d.keys(), key=str)}
    return repr(obj)

from app.rollback.exceptions import (
    ERR_ROLLBACK_CURRENT_NOT_CHAMPION,
    ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS,
    ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL,
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING,
    ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT,
    ROLLBACK_REASON_CODES,
)
from app.rollback.thresholds import ThresholdsConfig, check_thresholds_version


ROLLBACK_COMMAND_NAME_LITERAL = "rollback_champion"

DECISION_SCHEMA_VERSION = "1.0.0"


class RollbackEligibilityDecision(NamedTuple):
    decision_id: str
    eligible: bool
    target_model_id: str | None
    target_version: str | None
    reasons: list[str]
    thresholds_version: str
    decision_sha256: str
    approval_count: int


def _dedup_sort_reasons(reason_lists: list[list[str]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    valid = set(ROLLBACK_REASON_CODES)
    for bucket in reason_lists:
        if not bucket:
            continue
        for item in bucket:
            if not isinstance(item, str) or not item:
                continue
            if item not in valid:
                continue
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    out.sort()
    return out


def _approval_count_total(
    approval_refs_len: int,
    explicit_approval_count_extra: Any,
) -> int:
    base = int(approval_refs_len) if isinstance(approval_refs_len, int) and approval_refs_len >= 0 else 0
    extra = 0
    if isinstance(explicit_approval_count_extra, int) and not isinstance(explicit_approval_count_extra, bool):
        if explicit_approval_count_extra > 0:
            extra = explicit_approval_count_extra
    return base + extra


def check_approval_minimum(
    total_approval_count: int,
    cfg: ThresholdsConfig,
) -> list[str]:
    reasons: list[str] = []
    if total_approval_count < cfg.min_rollback_approval_count:
        reasons.append(ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL)
    return reasons


def check_e1_current_champion(
    current_champion_status_value: Any,
) -> list[str]:
    reasons: list[str] = []
    champion_val = ModelLifecycleStatus.CHAMPION.value
    if isinstance(current_champion_status_value, ModelLifecycleStatus):
        status_str = current_champion_status_value.value
    elif isinstance(current_champion_status_value, str):
        status_str = current_champion_status_value
    else:
        status_str = ""
    if status_str != champion_val:
        reasons.append(ERR_ROLLBACK_CURRENT_NOT_CHAMPION)
    return reasons


def check_e2_predecessor_pointer_exists(
    predecessor_dict_or_none: Any,
) -> list[str]:
    reasons: list[str] = []
    if predecessor_dict_or_none is None:
        reasons.append(ERR_ROLLBACK_MISSING_ROLLBACK_TARGET)
        return reasons
    if not isinstance(predecessor_dict_or_none, dict):
        reasons.append(ERR_ROLLBACK_MISSING_ROLLBACK_TARGET)
        return reasons
    mid = predecessor_dict_or_none.get("model_id")
    ver = predecessor_dict_or_none.get("version")
    if not (isinstance(mid, str) and mid and isinstance(ver, str) and ver):
        reasons.append(ERR_ROLLBACK_MISSING_ROLLBACK_TARGET)
    return reasons


def check_e3_predecessor_eligible_status(
    predecessor_status_value: Any,
    cfg: ThresholdsConfig,
) -> list[str]:
    reasons: list[str] = []
    if isinstance(predecessor_status_value, ModelLifecycleStatus):
        status_str = predecessor_status_value.value
    elif isinstance(predecessor_status_value, str):
        status_str = predecessor_status_value
    elif predecessor_status_value is None:
        reasons.append(ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS)
        return reasons
    else:
        reasons.append(ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS)
        return reasons
    eligible_set = cfg.eligible_status_set()
    if status_str not in eligible_set:
        reasons.append(ERR_ROLLBACK_INELIGIBLE_ROLLBACK_TARGET_STATUS)
    return reasons


def check_e4_rollback_strategy_ref_exists(
    rollback_strategy_ref: Any,
) -> list[str]:
    reasons: list[str] = []
    if rollback_strategy_ref is None:
        reasons.append(ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING)
        return reasons
    if not isinstance(rollback_strategy_ref, str) or not rollback_strategy_ref.strip():
        reasons.append(ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING)
    return reasons


def check_e5_predecessor_artifact_integrity(
    predecessor_artifact_storage_ok_flag: Any,
) -> list[str]:
    reasons: list[str] = []
    if predecessor_artifact_storage_ok_flag is False:
        reasons.append(ERR_ROLLBACK_ROLLBACK_TARGET_ARTIFACT_CORRUPT)
    return reasons


def _decision_deterministic_id_seeded(
    canonical_inputs: dict[str, Any],
    seed: int | None,
) -> tuple[str, str]:
    base = {
        "seed": 0 if seed is None else int(seed),
        "schema": DECISION_SCHEMA_VERSION,
        "inputs": canonical_inputs,
    }
    payload = json.dumps(_recursive_sorted_any(base), sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    short = digest[:16]
    decision_id = f"rb-{short}"
    return decision_id, digest


@dataclass
class RollbackAuditPayload:
    decision_id: str
    correlation_id: str
    causation_id: str
    occurred_ts: str
    trigger_type: str
    current_champion_model_id: str
    current_champion_version: str
    target_model_id: str | None
    target_version: str | None
    target_mode: str
    eligible_flag: bool
    reasons: list[str]
    approval_count: int
    thresholds_version: str
    decision_sha256: str
    rollback_command_name: str = field(default=ROLLBACK_COMMAND_NAME_LITERAL)

    def to_sorted_dict(self) -> dict[str, Any]:
        return _recursive_sorted_any(self)  # type: ignore[return-value]

    def schema_sha256(self) -> str:
        sorted_dict = self.to_sorted_dict()
        payload = json.dumps(sorted_dict, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_rollback_decision(
    *,
    current_champion_model_id: str,
    current_champion_version: str,
    current_champion_status_value: Any,
    predecessor_dict_or_none: Any,
    predecessor_status_value: Any,
    predecessor_artifact_storage_ok_flag: Any,
    rollback_strategy_ref: Any,
    evidence_validated_reasons: list[str],
    thresholds_cfg: ThresholdsConfig,
    expected_thresholds_version: str | None,
    approval_refs_len: int,
    explicit_approval_count_extra: Any,
    trigger_type: str,
    target_mode: str,
    correlation_id: str,
    causation_id: str,
    evidence_ts: str,
    explicit_seed: int | None,
    promotion_gate_passed_bool_from_cce: bool,
    storage_schema_version: str = DECISION_SCHEMA_VERSION,
) -> tuple[RollbackEligibilityDecision, RollbackAuditPayload]:
    version_reasons = check_thresholds_version(thresholds_cfg, expected_thresholds_version)
    e1_reasons = check_e1_current_champion(current_champion_status_value)
    e2_reasons = check_e2_predecessor_pointer_exists(predecessor_dict_or_none)
    e3_reasons: list[str] = []
    if not e2_reasons:
        e3_reasons = check_e3_predecessor_eligible_status(
            predecessor_status_value, thresholds_cfg
        )
    e4_reasons = check_e4_rollback_strategy_ref_exists(rollback_strategy_ref)
    e5_reasons = check_e5_predecessor_artifact_integrity(predecessor_artifact_storage_ok_flag)
    total_approvals = _approval_count_total(approval_refs_len, explicit_approval_count_extra)
    approval_reasons = check_approval_minimum(total_approvals, thresholds_cfg)

    all_buckets = [
        list(evidence_validated_reasons) if evidence_validated_reasons else [],
        version_reasons,
        e1_reasons,
        e2_reasons,
        e3_reasons,
        e4_reasons,
        e5_reasons,
        approval_reasons,
    ]
    final_reasons = _dedup_sort_reasons(all_buckets)

    eligible = (
        len(final_reasons) == 0
        and bool(promotion_gate_passed_bool_from_cce) is True
    )

    if eligible and not e2_reasons and isinstance(predecessor_dict_or_none, dict):
        tmid = str(predecessor_dict_or_none.get("model_id"))
        tver = str(predecessor_dict_or_none.get("version"))
    else:
        tmid = None
        tver = None

    canonical_inputs: dict[str, Any] = {
        "champion": {
            "model_id": current_champion_model_id,
            "version": current_champion_version,
            "status": str(current_champion_status_value.value) if hasattr(current_champion_status_value, "value") else str(current_champion_status_value),
        },
        "predecessor": _recursive_sorted_any(predecessor_dict_or_none) if predecessor_dict_or_none is not None else None,
        "predecessor_status": str(predecessor_status_value.value) if hasattr(predecessor_status_value, "value") else str(predecessor_status_value),
        "predecessor_artifact_ok": bool(predecessor_artifact_storage_ok_flag),
        "rollback_strategy_ref": str(rollback_strategy_ref) if rollback_strategy_ref is not None else None,
        "trigger_type": str(trigger_type),
        "target_mode": str(target_mode),
        "evidence_reasons": sorted(set(str(r) for r in (evidence_validated_reasons or []) if r)),
        "thresholds_version": thresholds_cfg.thresholds_config_version,
        "expected_thresholds_version": str(expected_thresholds_version) if expected_thresholds_version is not None else None,
        "approval_count": total_approvals,
        "promotion_gate_passed": bool(promotion_gate_passed_bool_from_cce),
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id),
        "evidence_ts": str(evidence_ts),
        "schema_version": storage_schema_version,
    }
    decision_id, decision_sha = _decision_deterministic_id_seeded(canonical_inputs, explicit_seed)

    decision = RollbackEligibilityDecision(
        decision_id=decision_id,
        eligible=bool(eligible),
        target_model_id=tmid,
        target_version=tver,
        reasons=list(final_reasons),
        thresholds_version=str(thresholds_cfg.thresholds_config_version),
        decision_sha256=decision_sha,
        approval_count=int(total_approvals),
    )

    audit = RollbackAuditPayload(
        decision_id=decision_id,
        correlation_id=deep_copy(correlation_id),
        causation_id=deep_copy(causation_id),
        occurred_ts=str(evidence_ts),
        trigger_type=str(trigger_type),
        current_champion_model_id=str(current_champion_model_id),
        current_champion_version=str(current_champion_version),
        target_model_id=tmid,
        target_version=tver,
        target_mode=str(target_mode),
        eligible_flag=bool(eligible),
        reasons=list(final_reasons),
        approval_count=int(total_approvals),
        thresholds_version=str(thresholds_cfg.thresholds_config_version),
        decision_sha256=decision_sha,
        rollback_command_name=ROLLBACK_COMMAND_NAME_LITERAL,
    )

    return decision, audit
