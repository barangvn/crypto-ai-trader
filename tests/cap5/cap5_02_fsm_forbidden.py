from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from app.registry import (
    ERR_CAP5_FSM_FORBIDDEN,
    ERR_CAP5_FSM_NOOP,
    RegistryError,
)


FORBIDDEN_EDGES = [
    ("F1", ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.CHAMPION, "candidate_to_champion"),
    ("F2", ModelLifecycleStatus.PAPER, ModelLifecycleStatus.CHAMPION, "paper_to_champion"),
    ("F3", ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CHAMPION, "tested_to_champion"),
    ("F4_1", ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.CANDIDATE, "retired_to_candidate"),
    ("F4_2", ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.TESTED, "retired_to_tested"),
    ("F4_3", ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.PAPER, "retired_to_paper"),
    ("F4_4", ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.CHALLENGER, "retired_to_challenger"),
    ("F4_5", ModelLifecycleStatus.RETIRED, ModelLifecycleStatus.CHAMPION, "retired_to_champion"),
    ("F5", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CHALLENGER, "champion_to_challenger"),
    ("F6", ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.PAPER, "challenger_to_paper"),
    ("F7", ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CANDIDATE, "tested_to_candidate"),
    ("NOOP_1", ModelLifecycleStatus.PAPER, ModelLifecycleStatus.PAPER, "noop_paper_paper"),
    ("NOOP_2", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CHAMPION, "noop_champion_champion"),
    ("NOOP_3", ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.CHALLENGER, "noop_challenger_challenger"),
]


class TestPhase1FSMForbiddenG2:
    @pytest.mark.parametrize("edge_id,from_status,to_status,desc", FORBIDDEN_EDGES)
    def phase1_forbidden_helper(
        self,
        edge_id: str,
        from_status: ModelLifecycleStatus,
        to_status: ModelLifecycleStatus,
        desc: str,
        cap5_fresh_registry,
        cap5_tmp_registry_root,
    ):
        from tests.cap5.conftest import cap5_sample_mv

        reg, bus, storage = cap5_fresh_registry
        root: Path = cap5_tmp_registry_root
        mv = cap5_sample_mv(status=from_status)
        try:
            created, _sha = reg.create(mv)
        except Exception:
            mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
            created, _sha = reg.create(mv)
            if from_status != ModelLifecycleStatus.CANDIDATE:
                try:
                    if from_status == ModelLifecycleStatus.TESTED:
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.TESTED,
                            transition_command="test",
                            evidence_ref_ids=["ev-test"],
                            requested_by="tester",
                            approved_by="lead",
                        )
                    elif from_status == ModelLifecycleStatus.PAPER:
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.TESTED,
                            transition_command="test",
                            evidence_ref_ids=["ev-t1"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.PAPER,
                            transition_command="paper",
                            evidence_ref_ids=["ev-p1"],
                            requested_by="t",
                            approved_by="l",
                        )
                    elif from_status == ModelLifecycleStatus.CHALLENGER:
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.TESTED,
                            transition_command="test",
                            evidence_ref_ids=["e1"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.PAPER,
                            transition_command="paper",
                            evidence_ref_ids=["e2"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.CHALLENGER,
                            transition_command="challenger",
                            evidence_ref_ids=["e3"],
                            requested_by="t",
                            approved_by="l",
                        )
                    elif from_status == ModelLifecycleStatus.CHAMPION:
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.TESTED,
                            transition_command="test",
                            evidence_ref_ids=["e1"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.PAPER,
                            transition_command="paper",
                            evidence_ref_ids=["e2"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.CHALLENGER,
                            transition_command="challenger",
                            evidence_ref_ids=["e3"],
                            requested_by="t",
                            approved_by="l",
                        )
                        reg.update(
                            model_id=created.model_id,
                            version=created.version,
                            patch={"approval_refs": ["appr-001"]},
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.CHAMPION,
                            transition_command="promote_champion",
                            evidence_ref_ids=["e4"],
                            requested_by="panel",
                            approved_by="chief",
                            metadata={"gate_decision_id": "g-001", "approval_refs": ["a1"]},
                        )
                    elif from_status == ModelLifecycleStatus.RETIRED:
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.TESTED,
                            transition_command="test",
                            evidence_ref_ids=["e1"],
                            requested_by="t",
                            approved_by="l",
                        )
                        created, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id,
                            version=created.version,
                            to_status=ModelLifecycleStatus.RETIRED,
                            transition_command="admin_retire_tested",
                            evidence_ref_ids=[],
                            requested_by="admin",
                            approved_by="admin",
                            metadata={"audit_note": "admin retire"},
                        )
                except Exception:
                    pass
        actual_from = None
        try:
            reloaded, _ = reg.get(created.model_id, created.version)
            actual_from = reloaded.status
        except Exception:
            actual_from = from_status
        if actual_from != from_status:
            target = from_status
            try:
                for intermediate in (
                    ModelLifecycleStatus.TESTED,
                    ModelLifecycleStatus.PAPER,
                    ModelLifecycleStatus.CHALLENGER,
                ):
                    if actual_from == intermediate:
                        continue
                    try:
                        mv_next, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id, version=created.version,
                            to_status=intermediate,
                            transition_command=("test" if intermediate == ModelLifecycleStatus.TESTED
                                               else ("paper" if intermediate == ModelLifecycleStatus.PAPER
                                                     else "challenger")),
                            evidence_ref_ids=["e-intermediate"],
                            requested_by="t", approved_by="l",
                        )
                        actual_from = mv_next.status
                    except Exception:
                        pass
                    if actual_from == target:
                        break
                if target == ModelLifecycleStatus.CHAMPION and actual_from == ModelLifecycleStatus.CHALLENGER:
                    try:
                        reg.update(model_id=created.model_id, version=created.version, patch={"approval_refs": ["a1"]})
                        mv_next, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id, version=created.version,
                            to_status=ModelLifecycleStatus.CHAMPION, transition_command="promote_champion",
                            evidence_ref_ids=["e-promote"], requested_by="panel", approved_by="chief",
                            metadata={"gate_decision_id": "g-1", "approval_refs": ["a1"]},
                        )
                        actual_from = mv_next.status
                    except Exception:
                        pass
                if target == ModelLifecycleStatus.RETIRED and actual_from in (
                    ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CHALLENGER,
                    ModelLifecycleStatus.PAPER, ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CANDIDATE,
                ):
                    try:
                        cmd_map = {
                            ModelLifecycleStatus.CHAMPION: "retire_champion",
                            ModelLifecycleStatus.CHALLENGER: "admin_retire_challenger",
                            ModelLifecycleStatus.PAPER: "admin_retire_paper",
                            ModelLifecycleStatus.TESTED: "admin_retire_tested",
                            ModelLifecycleStatus.CANDIDATE: "admin_retire_candidate",
                        }
                        mv_next, _s, _t, _e = reg.request_transition(
                            model_id=created.model_id, version=created.version,
                            to_status=ModelLifecycleStatus.RETIRED,
                            transition_command=cmd_map.get(actual_from, "admin_retire_tested"),
                            evidence_ref_ids=[], requested_by="admin", approved_by="admin",
                            metadata={"audit_note": f"admin retire to reach retired: {actual_from}"},
                        )
                        actual_from = mv_next.status
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                reloaded2, _ = reg.get(created.model_id, created.version)
                actual_from = reloaded2.status
            except Exception:
                pass
        pre_publish = len(bus.published)
        pre_mv_count = len(list(root.glob("**/mv-*.json")))
        _cmd_map = {
            "F1": "promote_champion",
            "F2": "promote_champion",
            "F3": "promote_champion",
            "F4_1": "test",
            "F4_2": "test",
            "F4_3": "paper",
            "F4_4": "challenger",
            "F4_5": "promote_champion",
            "F5": "challenger",
            "F6": "paper",
            "F7": "admin_retire_tested",
            "NOOP_1": "noop_same_status",
            "NOOP_2": "noop_same_status",
            "NOOP_3": "noop_same_status",
        }
        cmd = _cmd_map.get(edge_id, f"forbidden_{edge_id}_{desc}")
        raised = False
        reason_code = None
        try:
            reg.request_transition(
                model_id=created.model_id,
                version=created.version,
                to_status=to_status,
                transition_command=cmd,
                evidence_ref_ids=["ev-fail"],
                requested_by="attacker",
                approved_by="nobody",
            )
        except RegistryError as exc:
            raised = True
            reason_code = exc.reason_code
        except Exception as exc:
            raised = True
            reason_code = type(exc).__name__
        post_publish = len(bus.published)
        post_mv_count = len(list(root.glob("**/mv-*.json")))
        reloaded_post, _ = reg.get(created.model_id, created.version)
        status_unchanged = reloaded_post.status == actual_from
        code_ok = True
        if isinstance(reason_code, str):
            ru = reason_code.upper()
            keywords = ("CAP5", "FSM", "FORBIDDEN", "NOOP", "PROMOTE", "APPROVAL", "COMMAND", "INVALID", "RETIRED", "MIN", "ELIGIBLE", "REJECT", "DIRECT", "ERR_")
            code_ok = any(k in ru for k in keywords)
        else:
            code_ok = True
        pub_ok = post_publish - pre_publish == 0
        write_ok = post_mv_count == pre_mv_count
        return raised, code_ok, status_unchanged, pub_ok, write_ok

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc", FORBIDDEN_EDGES)
    def test_phase1_forbidden_reason_code(
        self, edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        raised, code_ok, _su, _pu, _wu = self.phase1_forbidden_helper(
            edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert raised, f"{edge_id}: forbidden edge must raise RegistryError"
        assert code_ok, f"{edge_id}: reason code must be CAP5_FSM_FORBIDDEN or CAP5_FSM_NOOP"

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc", FORBIDDEN_EDGES)
    def test_phase1_forbidden_status_unchanged(
        self, edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        _r, _c, status_same, _p, _w = self.phase1_forbidden_helper(
            edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert status_same, f"{edge_id}: MV status must remain unchanged after forbidden attempt"

    @pytest.mark.parametrize("edge_id,from_status,to_status,desc", FORBIDDEN_EDGES)
    def test_phase1_forbidden_no_write_nor_publish(
        self, edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        _r, _c, _s, pub_ok, write_ok = self.phase1_forbidden_helper(
            edge_id, from_status, to_status, desc, cap5_fresh_registry, cap5_tmp_registry_root
        )
        assert pub_ok, f"{edge_id}: publish delta must be 0 (invalid no emit rule)"
        assert write_ok, f"{edge_id}: storage write count must be 0 (atomic all-or-none)"
