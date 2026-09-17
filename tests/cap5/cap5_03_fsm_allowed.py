from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from app.registry import (
    RegistryError,
)


ALLOWED_EDGES = [
    ("T1", ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.TESTED, "candidate_to_tested", "test"),
    ("T2", ModelLifecycleStatus.TESTED, ModelLifecycleStatus.PAPER, "tested_to_paper", "paper"),
    ("T3", ModelLifecycleStatus.PAPER, ModelLifecycleStatus.CHALLENGER, "paper_to_challenger", "challenger"),
    ("T4", ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.CHAMPION, "challenger_to_champion", "promote_champion"),
    ("T5", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.RETIRED, "champion_to_retired", "retire_champion"),
    ("T6", ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.RETIRED, "admin_retire_candidate", "admin_retire_candidate"),
    ("T7", ModelLifecycleStatus.TESTED, ModelLifecycleStatus.RETIRED, "admin_retire_tested", "admin_retire_tested"),
    ("T8", ModelLifecycleStatus.PAPER, ModelLifecycleStatus.RETIRED, "admin_retire_paper", "admin_retire_paper"),
    ("T9", ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.RETIRED, "admin_retire_challenger", "admin_retire_challenger"),
    ("T10", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.RETIRED, "rollback_champion_retired", "rollback_champion"),
]


class TestPhase1FSMAllowedG3:
    @pytest.mark.parametrize("edge_id,from_status,to_status,desc,cmd", ALLOWED_EDGES)
    def phase1_allowed_helper(
        self,
        edge_id: str,
        from_status: ModelLifecycleStatus,
        to_status: ModelLifecycleStatus,
        desc: str,
        cmd: str,
        cap5_fresh_registry,
        cap5_tmp_registry_root,
    ):
        from tests.cap5.conftest import cap5_sample_mv

        reg, bus, storage = cap5_fresh_registry
        root: Path = cap5_tmp_registry_root
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        pre_publish = len(bus.published)
        pre_mv_count = len(list(root.glob("**/mv-*.json")))
        cur = created
        try:
            if from_status == ModelLifecycleStatus.TESTED:
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                    evidence_ref_ids=["e-t1"], requested_by="t", approved_by="l",
                )
            elif from_status == ModelLifecycleStatus.PAPER:
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                    evidence_ref_ids=["e1"], requested_by="t", approved_by="l",
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                    evidence_ref_ids=["e2"], requested_by="t", approved_by="l",
                )
            elif from_status == ModelLifecycleStatus.CHALLENGER:
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                    evidence_ref_ids=["e1"], requested_by="t", approved_by="l",
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                    evidence_ref_ids=["e2"], requested_by="t", approved_by="l",
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.CHALLENGER, transition_command="challenger",
                    evidence_ref_ids=["e3"], requested_by="t", approved_by="l",
                )
            elif from_status == ModelLifecycleStatus.CHAMPION:
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                    evidence_ref_ids=["e1"], requested_by="t", approved_by="l",
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                    evidence_ref_ids=["e2"], requested_by="t", approved_by="l",
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.CHALLENGER, transition_command="challenger",
                    evidence_ref_ids=["e3"], requested_by="t", approved_by="l",
                )
                reg.update(
                    model_id=cur.model_id, version=cur.version,
                    patch={"approval_refs": ["appr-001"]},
                )
                cur, _s, _t, _e = reg.request_transition(
                    model_id=cur.model_id, version=cur.version,
                    to_status=ModelLifecycleStatus.CHAMPION, transition_command="promote_champion",
                    evidence_ref_ids=["e4", "e5"], requested_by="panel", approved_by="chief",
                    metadata={"gate_decision_id": "gd-001", "approval_refs": ["a1"], "audit_note": "ok"},
                )
        except Exception:
            pass
        pre_reloaded, pre_sha = reg.get(cur.model_id, cur.version)
        metadata = {}
        ev_refs = ["ev-ok-1", "ev-ok-2"]
        if edge_id == "T4":
            metadata = {"gate_decision_id": "gd-ok", "approval_refs": ["appr-ok"], "audit_note": "all good"}
            try:
                has_appr = pre_reloaded.metadata.get("approval_refs")
                if not has_appr or len(has_appr) < 1:
                    reg.update(
                        model_id=pre_reloaded.model_id, version=pre_reloaded.version,
                        patch={"approval_refs": ["pre-appr-001"]},
                    )
            except Exception:
                pass
        if edge_id in ("T6", "T7", "T8", "T9", "T10"):
            metadata = {"audit_note": f"admin command {cmd} executed by SRE team"}
            ev_refs = []
        try:
            new_mv, new_sha, tx, env = reg.request_transition(
                model_id=pre_reloaded.model_id,
                version=pre_reloaded.version,
                to_status=to_status,
                transition_command=cmd,
                evidence_ref_ids=ev_refs,
                requested_by="valid_user",
                approved_by="valid_approver",
                metadata=metadata,
            )
            ok = True
        except Exception as exc:
            ok = False
            new_mv = None
            new_sha = None
            tx = None
            env = None
            exc_obj = exc
        post_publish = len(bus.published)
        post_mv_count = len(list(root.glob("**/mv-*.json")))
        return {
            "ok": ok,
            "new_mv": new_mv,
            "new_sha": new_sha,
            "tx": tx,
            "env": env,
            "pre_sha": pre_sha,
            "pre_status": pre_reloaded.status,
            "to_status": to_status,
            "pre_publish": pre_publish,
            "post_publish": post_publish,
            "pre_mv_count": pre_mv_count,
            "post_mv_count": post_mv_count,
        }

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc,cmd", ALLOWED_EDGES)
    def test_phase1_allowed_to_status_ok(
        self, edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        result = self.phase1_allowed_helper(
            edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert result["ok"], f"{edge_id}: allowed edge must succeed (got no exception)"
        assert result["new_mv"] is not None
        assert result["new_mv"].status == to_status, (
            f"{edge_id}: expected status={to_status.value}, got={result['new_mv'].status.value}"
        )

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc,cmd", ALLOWED_EDGES)
    def test_phase1_allowed_tx_persisted_ok(
        self, edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        result = self.phase1_allowed_helper(
            edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert result["ok"], f"{edge_id}: must succeed first"
        assert result["tx"] is not None, f"{edge_id}: transition object must be returned"
        assert result["new_sha"] is not None, f"{edge_id}: new_sha must be returned"
        assert result["post_mv_count"] >= result["pre_mv_count"] + 1, (
            f"{edge_id}: storage mv file count must increase with transition"
        )

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc,cmd", ALLOWED_EDGES)
    def test_phase1_allowed_sha_differs(
        self, edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        result = self.phase1_allowed_helper(
            edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert result["ok"]
        assert result["pre_sha"] != result["new_sha"], (
            f"{edge_id}: mv sha must differ after allowed transition"
        )

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc,cmd", ALLOWED_EDGES)
    def test_phase1_allowed_event_publish_plus_1(
        self, edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        result = self.phase1_allowed_helper(
            edge_id, from_status, to_status, desc, cmd, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert result["ok"]
        assert result["post_publish"] - result["pre_publish"] >= 1, (
            f"{edge_id}: publish delta must be +1 for valid transition"
        )
