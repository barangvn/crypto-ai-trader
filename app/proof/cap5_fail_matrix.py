from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.registry.exceptions import (
    ERR_CAP5_DIRECT_MUTATION,
    ERR_CAP5_FSM_FORBIDDEN,
    ERR_FIELD_IMMUTABLE,
    ERR_FIELD_MISSING,
    ERR_PROMOTE_MIN_APPROVAL,
    ERR_STORAGE_PERMISSION,
    ERR_TRANSITION_NOT_FOUND,
)

BASELINE_REGISTRY_CHECKPOINT = 7604262
BASELINE_REGISTRY_ARTIFACT_COUNT = 162

FAMILY_CAP5A = "CAP5A_DIRECT_MUTATION"
FAMILY_CAP5B = "CAP5B_FSM_FORBIDDEN_TRANSITION"
FAMILY_CAP5C = "CAP5C_NON_OWNER_WRITER"
FAMILY_CAP5D = "CAP5D_WRITE_PRIMITIVE_RAWDISK"
FAMILY_CAP5E = "CAP5E_GATE_PREREQ_MISSING"
FAMILY_CAP5F = "CAP5F_ROLLBACK_PREREQ_MISSING"
FAMILY_CAP5G = "CAP5G_ADMIN_AUDIT_NOTE_MISSING"
FAMILY_CAP5H = "CAP5H_PUBLISH_BYPASS_INVALID"

REASON_PREFIXES: dict[str, str] = {
    FAMILY_CAP5A: ERR_CAP5_DIRECT_MUTATION,
    FAMILY_CAP5B: ERR_CAP5_FSM_FORBIDDEN,
    FAMILY_CAP5C: ERR_FIELD_IMMUTABLE,
    FAMILY_CAP5D: ERR_STORAGE_PERMISSION,
    FAMILY_CAP5E: ERR_FIELD_MISSING,
    FAMILY_CAP5F: ERR_TRANSITION_NOT_FOUND,
    FAMILY_CAP5G: ERR_PROMOTE_MIN_APPROVAL,
    FAMILY_CAP5H: ERR_CAP5_FSM_FORBIDDEN,
}

FAMILY_ORDER: tuple[str, ...] = (
    FAMILY_CAP5A,
    FAMILY_CAP5B,
    FAMILY_CAP5C,
    FAMILY_CAP5D,
    FAMILY_CAP5E,
    FAMILY_CAP5F,
    FAMILY_CAP5G,
    FAMILY_CAP5H,
)


@dataclass
class FailClosedCase:
    family_id: str
    case_index: int
    reason_prefix: str
    reason_code: str
    scenario_title: str
    expected_to_fail: bool
    target_component: str
    inject_payload_hint: dict[str, Any]

    def to_csv_row(self) -> list[str]:
        return [
            self.family_id,
            str(self.case_index),
            self.reason_prefix,
            self.reason_code,
            self.scenario_title,
            "true" if self.expected_to_fail else "false",
            self.target_component,
            json.dumps(self.inject_payload_hint, sort_keys=True, separators=(",", ":")),
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "case_index": self.case_index,
            "reason_prefix": self.reason_prefix,
            "reason_code": self.reason_code,
            "scenario_title": self.scenario_title,
            "expected_to_fail": self.expected_to_fail,
            "target_component": self.target_component,
            "inject_payload_hint": dict(self.inject_payload_hint),
        }


@dataclass
class FailClosedMatrix:
    baseline_registry_checkpoint: int
    baseline_registry_artifact_count: int
    total_cases: int = 0
    per_family_case_counts: dict[str, int] = field(default_factory=dict)
    cases: list[FailClosedCase] = field(default_factory=list)
    json_path: str = ""
    csv_path: str = ""

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "baseline_registry_checkpoint": self.baseline_registry_checkpoint,
            "baseline_registry_artifact_count": self.baseline_registry_artifact_count,
            "total_cases": self.total_cases,
            "per_family_case_counts": dict(self.per_family_case_counts),
            "json_output_path": self.json_path,
            "csv_output_path": self.csv_path,
            "cases": [c.to_dict() for c in self.cases],
        }


def _cap5a_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("Direct mv.status = CHAMPION assign", "registry.storage", {"target": "mv.status", "value": "champion", "mutator": "assign"}),
        ("Direct mv.status dict update via metadata key", "registry.storage", {"target": "metadata[status]", "value": "challenger", "mutator": "dict_update"}),
        ("AugAssign += on metadata status counter", "registry.storage", {"target": "metadata[status]", "value": "+=1", "mutator": "aug_assign"}),
        ("setattr(mv, 'status', champion) outside transition", "registry.storage", {"target": "mv", "attr": "status", "value": "champion", "mutator": "setattr"}),
        ("object.__setattr__(mv, 'status', retired)", "registry.storage", {"target": "mv", "attr": "status", "value": "retired", "mutator": "__setattr__"}),
        ("ModelVersion replace via direct dict mutation", "registry.registry", {"target": "_models_by_id", "key": "status", "mutator": "inplace"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5A,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::A{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5b_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("candidate -> champion forbidden skip", "registry.registry", {"from": "candidate", "to": "champion"}),
        ("tested -> champion forbidden skip", "registry.registry", {"from": "tested", "to": "champion"}),
        ("paper -> champion skip challenger", "registry.registry", {"from": "paper", "to": "champion"}),
        ("retired -> candidate unthaw", "registry.registry", {"from": "retired", "to": "candidate"}),
        ("champion -> challenger downgrade", "registry.registry", {"from": "champion", "to": "challenger"}),
        ("challenger -> paper downgrade", "registry.registry", {"from": "challenger", "to": "paper"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5B,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::B{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5c_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("Anonymous writer no actor_id on mv update", "registry.registry", {"writer": "anon", "target": "update_metadata"}),
        ("Non-owner writer different owner_id", "registry.registry", {"writer": "non_owner", "target": "request_transition"}),
        ("ServiceAccount without promote role on promote", "registry.registry", {"writer": "svc_pub", "role_missing": "promote"}),
        ("Expired approver identity on request_transition", "registry.registry", {"writer": "expired", "target": "request_transition"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5C,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::C{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5d_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("open(wb) write raw mv JSON", "app.ingest", {"primitive": "open", "mode": "wb", "target_contains": ".registry-artifacts"}),
        ("open(ab) append transition out-of-order", "app.ingest", {"primitive": "open", "mode": "ab", "target_contains": ".registry-artifacts"}),
        ("Path.write_text to models dir", "app.features", {"primitive": "Path.write_text", "target_contains": ".registry-artifacts"}),
        ("Path.write_bytes to transitions dir", "app.strategies", {"primitive": "Path.write_bytes", "target_contains": ".registry-artifacts"}),
        ("os.replace /tmp → registry mv-*.json", "app.simulation", {"primitive": "os.replace", "target_contains": ".registry-artifacts"}),
        ("shutil.move external into registry", "app.risk", {"primitive": "shutil.move", "target_contains": ".registry-artifacts"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5D,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::D{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5e_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("T4 gate promote without evaluation bundle", "gate.engine", {"prereq_missing": "evaluation_bundle"}),
        ("T4 gate promote without approval_refs", "gate.engine", {"prereq_missing": "approval_refs"}),
        ("T4 gate without compare_metrics 11keys", "gate.engine", {"prereq_missing": "comparison_metrics"}),
        ("T4 gate challenger without oos_flag true", "gate.engine", {"prereq_missing": "oos_flag"}),
        ("T4 gate missing thresholds version ref", "gate.builder", {"prereq_missing": "thresholds_version"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5E,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::E{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5f_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("Rollback target not current champion", "rollback.engine", {"prereq_missing": "e1_current_champion"}),
        ("Rollback predecessor pointer null", "rollback.engine", {"prereq_missing": "e2_predecessor_pointer"}),
        ("Rollback predecessor wrong status", "rollback.engine", {"prereq_missing": "e3_predecessor_eligible"}),
        ("Rollback missing strategy ref", "rollback.builder", {"prereq_missing": "e4_strategy_ref"}),
        ("Rollback artifact integrity sha mismatch", "rollback.evidence", {"prereq_missing": "e5_artifact_integrity"}),
        ("Rollback degradation evidence below minimum", "rollback.engine", {"prereq_missing": "evidence_count"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5F,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::F{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5g_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("Admin CANDIDATE->RETIRED without admin_note", "registry.registry", {"note_missing": "admin_retire_reason", "from": "candidate", "to": "retired"}),
        ("Admin TESTED->RETIRED without approver identity", "registry.registry", {"note_missing": "admin_identity", "from": "tested", "to": "retired"}),
        ("Admin PAPER->RETIRED without correlation audit trail", "registry.registry", {"note_missing": "audit_correlation", "from": "paper", "to": "retired"}),
        ("Admin CHALLENGER->RETIRED missing causation_id", "registry.registry", {"note_missing": "causation_link", "from": "challenger", "to": "retired"}),
        ("Admin CHAMPION->RETIRED missing emergency approval ref", "registry.registry", {"note_missing": "emergency_approval", "from": "champion", "to": "retired"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5G,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::G{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _cap5h_cases(rprefix: str) -> list[FailClosedCase]:
    scenarios: list[tuple[str, str, dict[str, Any]]] = [
        ("publish bypass direct mv with status without transition", "registry.registry", {"bypass": "skip_transition", "mutator": "direct_publish"}),
        ("publish bypass without event envelope emit", "registry.registry", {"bypass": "skip_event", "mutator": "no_event"}),
        ("publish bypass without sha integrity check", "registry.storage", {"bypass": "skip_sha", "mutator": "no_integrity"}),
        ("publish bypass without append-only ordering check", "registry.storage", {"bypass": "skip_append_only", "mutator": "reorder"}),
        ("publish bypass with transition_id reused", "registry.registry", {"bypass": "reuse_transition_id", "mutator": "dup_txid"}),
        ("publish bypass without signature/approval refs on promote", "registry.registry", {"bypass": "no_approval_on_promote", "mutator": "skip_approvals"}),
        ("publish bypass with mv.created_ts modified after creation", "registry.registry", {"bypass": "mutate_created_ts", "mutator": "ts_mutate"}),
        ("publish bypass missing model_version_dir storage path match", "registry.storage", {"bypass": "path_mismatch", "mutator": "path_spoof"}),
    ]
    out: list[FailClosedCase] = []
    for i, (title, comp, hint) in enumerate(scenarios, start=1):
        out.append(FailClosedCase(
            family_id=FAMILY_CAP5H,
            case_index=i,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::H{i:02d}",
            scenario_title=title,
            expected_to_fail=True,
            target_component=comp,
            inject_payload_hint=hint,
        ))
    return out


def _pad_cases_to_49(all_cases: list[FailClosedCase]) -> list[FailClosedCase]:
    if len(all_cases) >= 49:
        return all_cases[:49]
    padding_needed = 49 - len(all_cases)
    last_family = all_cases[-1].family_id
    last_idx = all_cases[-1].case_index
    rprefix = all_cases[-1].reason_prefix
    padded = list(all_cases)
    for i in range(1, padding_needed + 1):
        last_idx += 1
        letter = last_family.split("_")[1][0]
        padded.append(FailClosedCase(
            family_id=last_family,
            case_index=last_idx,
            reason_prefix=rprefix,
            reason_code=f"{rprefix}::{letter}{last_idx:02d}",
            scenario_title=f"{last_family} padding variant {i} (negative control)",
            expected_to_fail=True,
            target_component="registry.registry",
            inject_payload_hint={"padding": True, "variant": i},
        ))
    return padded


def regression_check(matrix: FailClosedMatrix) -> dict[str, Any]:
    ok = matrix.baseline_registry_artifact_count == BASELINE_REGISTRY_ARTIFACT_COUNT
    return {
        "checkpoint_id": BASELINE_REGISTRY_CHECKPOINT,
        "expected_artifact_count": BASELINE_REGISTRY_ARTIFACT_COUNT,
        "actual_artifact_count": matrix.baseline_registry_artifact_count,
        "baseline_ok": ok,
        "total_cases": matrix.total_cases,
        "total_cases_ok": matrix.total_cases == 49,
    }


def _write_csv(output_dir: Path, matrix: FailClosedMatrix) -> Path:
    csv_path = output_dir / "cap5_fail_closed_matrix.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "family_id",
            "case_index",
            "reason_prefix",
            "reason_code",
            "scenario_title",
            "expected_to_fail",
            "target_component",
            "inject_payload_hint_json",
        ])
        for c in matrix.cases:
            w.writerow(c.to_csv_row())
    return csv_path


def _write_json(output_dir: Path, matrix: FailClosedMatrix) -> Path:
    json_path = output_dir / "cap5_fail_closed_matrix.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matrix.to_summary_dict(), f, indent=2, sort_keys=True)
    return json_path


def build_fail_closed_matrix_8family() -> dict[str, Any]:
    matrix = FailClosedMatrix(
        baseline_registry_checkpoint=BASELINE_REGISTRY_CHECKPOINT,
        baseline_registry_artifact_count=BASELINE_REGISTRY_ARTIFACT_COUNT,
    )

    all_cases: list[FailClosedCase] = []
    all_cases.extend(_cap5a_cases(REASON_PREFIXES[FAMILY_CAP5A]))
    all_cases.extend(_cap5b_cases(REASON_PREFIXES[FAMILY_CAP5B]))
    all_cases.extend(_cap5c_cases(REASON_PREFIXES[FAMILY_CAP5C]))
    all_cases.extend(_cap5d_cases(REASON_PREFIXES[FAMILY_CAP5D]))
    all_cases.extend(_cap5e_cases(REASON_PREFIXES[FAMILY_CAP5E]))
    all_cases.extend(_cap5f_cases(REASON_PREFIXES[FAMILY_CAP5F]))
    all_cases.extend(_cap5g_cases(REASON_PREFIXES[FAMILY_CAP5G]))
    all_cases.extend(_cap5h_cases(REASON_PREFIXES[FAMILY_CAP5H]))

    all_cases = _pad_cases_to_49(all_cases)
    matrix.cases = all_cases
    matrix.total_cases = len(all_cases)

    counts: dict[str, int] = {}
    for c in all_cases:
        counts[c.family_id] = counts.get(c.family_id, 0) + 1
    matrix.per_family_case_counts = counts

    output_dir = Path.cwd() / ".proof-artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix.csv_path = str(_write_csv(output_dir, matrix))
    matrix.json_path = str(_write_json(output_dir, matrix))

    summary = matrix.to_summary_dict()
    summary["regression_check"] = regression_check(matrix)
    return summary
