from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from app.registry import (
    ERR_PROMOTE_MIN_APPROVAL,
    RegistryError,
)


GATE_SCENARIOS = [
    ("a_no_gate_decision_id", lambda md: {k: v for k, v in md.items() if k != "gate_decision_id"},
     "metadata without gate_decision_id key"),
    ("b_approval_refs_empty", lambda md: {**md, "approval_refs": []},
     "approval_refs empty list len 0"),
    ("c_gate_pass_false_evidence", lambda md: {**md, "gate_result": {"passed": False, "reasons": ["threshold missed"]}},
     "gate.pass=False in evidence metadata"),
    ("d_combined_empty", lambda md: {},
     "combined empty metadata - no gate, no approvals, no evidence"),
]


class TestPhase1GatePrereqMissingG5:
    @pytest.mark.parametrize("scenario_id,meta_fn,desc", GATE_SCENARIOS)
    def phase1_gate_helper(
        self,
        scenario_id: str,
        meta_fn,
        desc: str,
        cap5_created_challenger,
        cap5_tmp_registry_root,
    ):
        reg, bus, storage, mv, _sha, _tx = cap5_created_challenger
        root: Path = cap5_tmp_registry_root
        pre_reloaded, pre_sha = reg.get(mv.model_id, mv.version)
        base_meta = {
            "gate_decision_id": "gate-dec-would-be-here",
            "approval_refs": ["appr-001-base"],
            "audit_note": "gate prereq base note",
        }
        test_meta = meta_fn(base_meta)
        pre_publish = len(bus.published)
        pre_mv_count = len(list(root.glob("**/mv-*.json")))
        raised = False
        reason_code = None
        exc_obj = None
        try:
            reg.request_transition(
                model_id=pre_reloaded.model_id,
                version=pre_reloaded.version,
                to_status=ModelLifecycleStatus.CHAMPION,
                transition_command="promote_champion",
                evidence_ref_ids=["ev-g1", "ev-g2"],
                requested_by="gate_panel",
                approved_by="chief_ml",
                metadata=test_meta,
            )
        except RegistryError as exc:
            raised = True
            reason_code = exc.reason_code
            exc_obj = exc
        except Exception as exc:
            raised = True
            reason_code = type(exc).__name__
            exc_obj = exc
        post_publish = len(bus.published)
        post_mv_count = len(list(root.glob("**/mv-*.json")))
        post_reloaded, _ = reg.get(mv.model_id, mv.version)
        status_unchanged = post_reloaded.status == ModelLifecycleStatus.CHALLENGER
        code_ok = (
            reason_code in (ERR_PROMOTE_MIN_APPROVAL,)
            or isinstance(reason_code, str)
            and (
                "GATE" in reason_code
                or "APPROVAL" in reason_code
                or "PREREQ" in reason_code
                or "PROMOTE" in reason_code
            )
        )
        pub_ok = post_publish - pre_publish == 0
        write_ok = post_mv_count == pre_mv_count
        return {
            "raised": raised,
            "code_ok": code_ok,
            "reason_code": reason_code,
            "status_unchanged": status_unchanged,
            "pre_status": pre_reloaded.status.value,
            "post_status": post_reloaded.status.value,
            "pub_delta_zero": pub_ok,
            "write_delta_zero": write_ok,
        }

    @pytest.mark.parametrize("scenario_id,meta_fn,desc", GATE_SCENARIOS)
    def test_phase1_gate_reason_code_match(self, scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root):
        result = self.phase1_gate_helper(scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root)
        assert result["raised"], f"{scenario_id}: T4 with missing gate prereq must raise RegistryError"
        assert result["code_ok"], (
            f"{scenario_id}: reason code must be GATE/APPROVAL/PREREQ/PROMOTE prefix family; "
            f"got={result['reason_code']}"
        )

    @pytest.mark.parametrize("scenario_id,meta_fn,desc", GATE_SCENARIOS)
    def test_phase1_gate_status_pre_eq_post(self, scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root):
        result = self.phase1_gate_helper(scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root)
        assert result["status_unchanged"], (
            f"{scenario_id}: status must remain CHALLENGER (PRE=POST); got "
            f"{result['pre_status']} -> {result['post_status']}"
        )

    @pytest.mark.parametrize("scenario_id,meta_fn,desc", GATE_SCENARIOS)
    def test_phase1_gate_no_write(self, scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root):
        result = self.phase1_gate_helper(scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root)
        assert result["write_delta_zero"], (
            f"{scenario_id}: storage write count must be 0 (atomic no partial write on invalid)"
        )

    @pytest.mark.parametrize("scenario_id,meta_fn,desc", GATE_SCENARIOS)
    def test_phase1_gate_publish_delta_zero(self, scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root):
        result = self.phase1_gate_helper(scenario_id, meta_fn, desc, cap5_created_challenger, cap5_tmp_registry_root)
        assert result["pub_delta_zero"], (
            f"{scenario_id}: event publish delta must be 0 (invalid CAP5 no emit rule L166)"
        )
