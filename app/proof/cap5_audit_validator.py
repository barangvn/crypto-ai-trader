from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts import ModelLifecycleStatus
from app.registry import RegistryError


FAMILY_CAP5A = "CAP5A_DIRECT_MUTATION"
FAMILY_CAP5E = "CAP5E_GATE_PREREQ_MISSING"
FAMILY_CAP5F = "CAP5F_ROLLBACK_PREREQ_MISSING"
FAMILY_CAP5G = "CAP5G_ADMIN_AUDIT_NOTE_MISSING"

REASON_CODE_EVIDENCE_EMPTY = "CAP5G_EVIDENCE_INCOMPLETE"
REASON_CODE_APPROVAL_EMPTY = "CAP5E_APPROVAL_MIN_UNMET"
REASON_CODE_AUDIT_NOTE_EMPTY = "CAP5G_ADMIN_AUDIT_NOTE_EMPTY"
REASON_CODE_GATE_MISSING = "CAP5E_GATE_DECISION_MISSING"
REASON_CODE_ROLLBACK_PRED_NULL = "CAP5F_PREDECESSOR_POINTER_NULL"
REASON_CODE_ROLLBACK_DEC_NULL = "CAP5F_ROLLBACK_DECISION_MISSING"
REASON_CODE_ROLLBACK_NOT_ELIGIBLE = "CAP5F_ROLLBACK_ELIGIBLE_FLAG_FALSE"
REASON_CODE_ROLLBACK_COMBO_INVALID = "CAP5F_ROLLBACK_COMBINED_PREREQ_INVALID"


ADMIN_RETIRE_COMMANDS = frozenset((
    "admin_retire_candidate",
    "admin_retire_tested",
    "admin_retire_paper",
    "admin_retire_challenger",
    "admin_retire_champion",
    "retire_champion",
))


PROMOTE_COMMANDS = frozenset(("promote_champion",))

ROLLBACK_COMMANDS = frozenset(("rollback_champion",))


@dataclass
class Cap5AuditResult:
    passed: bool
    reason_code: str | None = None
    reason_prefix_family: str | None = None
    message: str = ""


def _metadata_flag(metadata: dict | None, key: str, default: Any = None) -> Any:
    if not isinstance(metadata, dict):
        return default
    return metadata.get(key, default)


def _is_whitespace_or_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def validate_cap5_gate_prereq(
    to_status: ModelLifecycleStatus,
    transition_command: str,
    metadata: dict | None,
) -> Cap5AuditResult:
    if transition_command not in PROMOTE_COMMANDS:
        return Cap5AuditResult(passed=True)
    if to_status != ModelLifecycleStatus.CHAMPION:
        return Cap5AuditResult(passed=True)

    gate_decision_id = _metadata_flag(metadata, "gate_decision_id")
    approval_refs = _metadata_flag(metadata, "approval_refs")

    if _is_whitespace_or_empty(gate_decision_id):
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_GATE_MISSING,
            reason_prefix_family=FAMILY_CAP5E,
            message="CAP5E gate_decision_id required on promote_champion",
        )

    approvals_list: list[Any] = []
    if isinstance(approval_refs, list):
        approvals_list = [x for x in approval_refs if not _is_whitespace_or_empty(x)]
    elif isinstance(approval_refs, str) and approval_refs.strip():
        approvals_list = [approval_refs]
    if len(approvals_list) < 1:
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_APPROVAL_EMPTY,
            reason_prefix_family=FAMILY_CAP5E,
            message="CAP5E approval_refs len>=1 required on promote_champion",
        )

    return Cap5AuditResult(passed=True)


def validate_cap5_rollback_prereq(
    from_status: ModelLifecycleStatus,
    to_status: ModelLifecycleStatus,
    transition_command: str,
    metadata: dict | None,
) -> Cap5AuditResult:
    if transition_command not in ROLLBACK_COMMANDS:
        return Cap5AuditResult(passed=True)
    if from_status != ModelLifecycleStatus.CHAMPION:
        return Cap5AuditResult(passed=True)
    if to_status != ModelLifecycleStatus.RETIRED:
        return Cap5AuditResult(passed=True)

    predecessor = _metadata_flag(metadata, "predecessor_model_ref")
    rb_dec_id = _metadata_flag(metadata, "rollback_decision_id")
    eligible_flag = _metadata_flag(metadata, "rollback_eligible", default=None)

    has_pred = predecessor is not None
    if isinstance(predecessor, dict):
        pid = predecessor.get("model_id")
        pv = predecessor.get("version")
        has_pred = bool(pid) and bool(pv) and not (_is_whitespace_or_empty(pid) or _is_whitespace_or_empty(pv))

    has_rb_dec = not _is_whitespace_or_empty(rb_dec_id)
    is_eligible = eligible_flag is True

    if (not has_pred) and (not has_rb_dec) and (not is_eligible):
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_ROLLBACK_COMBO_INVALID,
            reason_prefix_family=FAMILY_CAP5F,
            message="CAP5F combined rollback prereq empty (no pred, no dec, not eligible)",
        )

    if not has_pred:
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_ROLLBACK_PRED_NULL,
            reason_prefix_family=FAMILY_CAP5F,
            message="CAP5F predecessor_model_ref required on rollback_champion",
        )
    if not has_rb_dec:
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_ROLLBACK_DEC_NULL,
            reason_prefix_family=FAMILY_CAP5F,
            message="CAP5F rollback_decision_id required on rollback_champion",
        )
    if not is_eligible:
        return Cap5AuditResult(
            passed=False,
            reason_code=REASON_CODE_ROLLBACK_NOT_ELIGIBLE,
            reason_prefix_family=FAMILY_CAP5F,
            message="CAP5F rollback_eligible=True required on rollback_champion",
        )

    return Cap5AuditResult(passed=True)


def validate_cap5_evidence_and_audit(
    transition_command: str,
    to_status: ModelLifecycleStatus,
    evidence_ref_ids: list[str] | None,
    metadata: dict | None,
    from_status: ModelLifecycleStatus | None = None,
) -> Cap5AuditResult:
    evidence_list: list[str] = []
    if isinstance(evidence_ref_ids, list):
        evidence_list = [str(x) for x in evidence_ref_ids if not _is_whitespace_or_empty(x)]
    audit_note = _metadata_flag(metadata, "audit_note")

    is_admin_retire = transition_command in ADMIN_RETIRE_COMMANDS
    is_promote = transition_command in PROMOTE_COMMANDS
    is_rollback = transition_command in ROLLBACK_COMMANDS

    # OD-04 admin_retire_candidate: evidence len=0 default PASS (audit note still required)
    if is_admin_retire:
        if transition_command == "admin_retire_candidate":
            pass
        else:
            if len(evidence_list) < 1:
                return Cap5AuditResult(
                    passed=False,
                    reason_code=REASON_CODE_EVIDENCE_EMPTY,
                    reason_prefix_family=FAMILY_CAP5G,
                    message=f"CAP5G evidence_ref_ids len>=1 required on {transition_command}",
                )
        if _is_whitespace_or_empty(audit_note):
            return Cap5AuditResult(
                passed=False,
                reason_code=REASON_CODE_AUDIT_NOTE_EMPTY,
                reason_prefix_family=FAMILY_CAP5G,
                message=f"CAP5G admin audit_note non-empty required on {transition_command}",
            )
        return Cap5AuditResult(passed=True)

    if is_promote:
        if len(evidence_list) < 1:
            return Cap5AuditResult(
                passed=False,
                reason_code=REASON_CODE_EVIDENCE_EMPTY,
                reason_prefix_family=FAMILY_CAP5G,
                message="CAP5G evidence_ref_ids len>=1 required on promote_champion",
            )
        return Cap5AuditResult(passed=True)

    if is_rollback:
        if len(evidence_list) < 1:
            return Cap5AuditResult(
                passed=False,
                reason_code=REASON_CODE_EVIDENCE_EMPTY,
                reason_prefix_family=FAMILY_CAP5G,
                message="CAP5G evidence_ref_ids len>=1 required on rollback_champion",
            )
        if _is_whitespace_or_empty(audit_note):
            return Cap5AuditResult(
                passed=False,
                reason_code=REASON_CODE_AUDIT_NOTE_EMPTY,
                reason_prefix_family=FAMILY_CAP5G,
                message="CAP5G rollback audit_note non-empty required",
            )
        return Cap5AuditResult(passed=True)

    return Cap5AuditResult(passed=True)


def run_cap5_audit_precheck(
    from_status: ModelLifecycleStatus | None,
    to_status: ModelLifecycleStatus,
    transition_command: str,
    evidence_ref_ids: list[str] | None,
    metadata: dict | None,
) -> Cap5AuditResult:
    r1 = validate_cap5_evidence_and_audit(
        transition_command=transition_command,
        to_status=to_status,
        evidence_ref_ids=evidence_ref_ids,
        metadata=metadata,
        from_status=from_status,
    )
    if not r1.passed:
        return r1
    r2 = validate_cap5_gate_prereq(
        to_status=to_status,
        transition_command=transition_command,
        metadata=metadata,
    )
    if not r2.passed:
        return r2
    if from_status is not None:
        r3 = validate_cap5_rollback_prereq(
            from_status=from_status,
            to_status=to_status,
            transition_command=transition_command,
            metadata=metadata,
        )
        if not r3.passed:
            return r3
    return Cap5AuditResult(passed=True)


def run_cap5_proof_then_registry(registry, request_transition_kwargs: dict[str, Any]):
    model_id = request_transition_kwargs["model_id"]
    version = request_transition_kwargs["version"]
    to_status = request_transition_kwargs["to_status"]
    transition_command = request_transition_kwargs.get("transition_command", "")
    evidence_ref_ids = request_transition_kwargs.get("evidence_ref_ids", [])
    metadata = request_transition_kwargs.get("metadata") or {}

    from_status = None
    try:
        pre_mv, _ = registry.get(model_id, version)
        from_status = pre_mv.status
    except Exception:
        from_status = None

    audit = run_cap5_audit_precheck(
        from_status=from_status,
        to_status=to_status,
        transition_command=transition_command,
        evidence_ref_ids=evidence_ref_ids,
        metadata=metadata,
    )
    if not audit.passed:
        raise RegistryError(
            reason_code=audit.reason_code or "CAP5_AUDIT_FAILED",
            message=audit.message,
            details={"family": audit.reason_prefix_family, "audit_step": "cap5_precheck"},
        )
    if transition_command == "admin_retire_candidate":
        ev_list = list(request_transition_kwargs.get("evidence_ref_ids") or [])
        if not ev_list:
            ev_list = ["OD04_ADMIN_RETIRE_CANDIDATE_DEFAULT_EVIDENCE"]
            request_transition_kwargs = dict(request_transition_kwargs)
            request_transition_kwargs["evidence_ref_ids"] = ev_list
    return registry.request_transition(**request_transition_kwargs)
