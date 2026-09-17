from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from app.proof import run_cap5_proof_then_registry
from app.registry import (
    RegistryError,
)


ROLLBACK_SCENARIOS = [
    ("a_predecessor_null", False, None, False, "predecessor pointer null/None"),
    ("b_rollback_decision_missing", True, None, True, "rollback_decision_id missing from metadata"),
    ("c_eligible_false", True, "rb-dec-001", False, "eligible=False flag set in metadata"),
    ("d_combined_empty", False, None, False, "combined empty - no predecessor + no decision + not eligible"),
]


class TestPhase1RollbackPrereqMissingG6:
    @pytest.mark.parametrize("scenario_id,has_pred,rb_dec_id,eligible_flag,desc", ROLLBACK_SCENARIOS)
    def phase1_rollback_helper(
        self,
        scenario_id: str,
        has_pred: bool,
        rb_dec_id,
        eligible_flag: bool,
        desc: str,
        cap5_champion_with_approval,
        cap5_tmp_registry_root,
    ):
        reg, bus, storage, mv, _sha, _tx = cap5_champion_with_approval
        root: Path = cap5_tmp_registry_root
        pre_reloaded, pre_sha = reg.get(mv.model_id, mv.version)
        if not has_pred:
            pass
        test_meta: dict = {}
        if rb_dec_id is not None:
            test_meta["rollback_decision_id"] = rb_dec_id
        test_meta["rollback_eligible"] = eligible_flag
        test_meta["audit_note"] = "rollback attempt prereq check"
        test_meta["predecessor_model_ref"] = {"model_id": "old_champion", "version": "0.9.0"} if has_pred else None
        pre_publish = len(bus.published)
        pre_mv_count = len(list(root.glob("**/mv-*.json")))
        raised = False
        reason_code = None
        transition_kwargs = dict(
            model_id=pre_reloaded.model_id,
            version=pre_reloaded.version,
            to_status=ModelLifecycleStatus.RETIRED,
            transition_command="rollback_champion",
            evidence_ref_ids=["ev-rb-1"],
            requested_by="rollback_team",
            approved_by="sre_manager",
            metadata=test_meta,
        )
        try:
            run_cap5_proof_then_registry(reg, transition_kwargs)
        except RegistryError as exc:
            raised = True
            reason_code = exc.reason_code
        except Exception as exc:
            raised = True
            reason_code = type(exc).__name__
        post_publish = len(bus.published)
        post_mv_count = len(list(root.glob("**/mv-*.json")))
        post_reloaded, _ = reg.get(mv.model_id, mv.version)
        status_unchanged = post_reloaded.status == ModelLifecycleStatus.CHAMPION
        code_ok = isinstance(reason_code, str) and (
            "ROLLBACK" in reason_code.upper()
            or "PREREQ" in reason_code.upper()
            or "ELIGIBLE" in reason_code.upper()
            or "PREDECESSOR" in reason_code.upper()
            or "DECISION" in reason_code.upper()
            or "COMBO" in reason_code.upper()
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

    @pytest.mark.parametrize("scenario_id,has_pred,rb_dec_id,eligible_flag,desc", ROLLBACK_SCENARIOS)
    def test_phase1_rollback_reason_code_match(
        self, scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
    ):
        result = self.phase1_rollback_helper(
            scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
        )
        assert result["raised"], f"{scenario_id}: rollback with missing prereq must raise RegistryError"
        assert result["code_ok"], (
            f"{scenario_id}: reason code must be ROLLBACK/PREREQ/PREDECESSOR prefix; got={result['reason_code']}"
        )

    @pytest.mark.parametrize("scenario_id,has_pred,rb_dec_id,eligible_flag,desc", ROLLBACK_SCENARIOS)
    def test_phase1_rollback_status_pre_eq_post(
        self, scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
    ):
        result = self.phase1_rollback_helper(
            scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
        )
        assert result["status_unchanged"], (
            f"{scenario_id}: status must remain CHAMPION (PRE=POST); got "
            f"{result['pre_status']} -> {result['post_status']}"
        )

    @pytest.mark.parametrize("scenario_id,has_pred,rb_dec_id,eligible_flag,desc", ROLLBACK_SCENARIOS)
    def test_phase1_rollback_no_write(
        self, scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
    ):
        result = self.phase1_rollback_helper(
            scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
        )
        assert result["write_delta_zero"], (
            f"{scenario_id}: storage write count must be 0 (atomic no partial)"
        )

    @pytest.mark.parametrize("scenario_id,has_pred,rb_dec_id,eligible_flag,desc", ROLLBACK_SCENARIOS)
    def test_phase1_rollback_publish_delta_zero(
        self, scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
    ):
        result = self.phase1_rollback_helper(
            scenario_id, has_pred, rb_dec_id, eligible_flag, desc, cap5_champion_with_approval, cap5_tmp_registry_root
        )
        assert result["pub_delta_zero"], (
            f"{scenario_id}: event publish delta must be 0 (invalid no emit rule)"
        )
