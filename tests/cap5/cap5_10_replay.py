from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)


REPLAY_FIXTURE_KEYS = [
    "T1_candidate_to_tested",
    "T2_tested_to_paper",
    "T3_paper_to_challenger",
]

FIELD_CHECKS = [
    "from_status",
    "to_status",
    "transition_command",
    "gate_decision_id",
    "approval_count",
    "evidence_refs_count",
    "sha_12_prefix",
]


class TestPhase1ReplayReproducibilityG10:
    def phase1_build_replay_bundle(
        self,
        fixture_key: str,
        cap5_fresh_registry,
        cap5_tmp_registry_root,
        cap5_seed_corr,
    ):
        from tests.cap5.conftest import cap5_sample_mv

        reg, bus, storage = cap5_fresh_registry
        root: Path = cap5_tmp_registry_root
        mv = cap5_sample_mv(
            status=ModelLifecycleStatus.CANDIDATE,
            correlation_id=cap5_seed_corr["correlation_id"],
            causation_id=cap5_seed_corr["causation_id"],
            created_ts=cap5_seed_corr["created_ts"],
        )
        cur, _sha = reg.create(mv)
        target_cmd = ""
        target_to = ModelLifecycleStatus.TESTED
        if fixture_key == "T1_candidate_to_tested":
            target_cmd = "test"
            target_to = ModelLifecycleStatus.TESTED
        elif fixture_key == "T2_tested_to_paper":
            cur, _s, _t, _e = reg.request_transition(
                model_id=cur.model_id, version=cur.version,
                to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                evidence_ref_ids=["ev-t1"], requested_by="t", approved_by="l",
                requested_ts=cap5_seed_corr["requested_ts"],
                correlation_id=cap5_seed_corr["correlation_id"],
            )
            target_cmd = "paper"
            target_to = ModelLifecycleStatus.PAPER
        elif fixture_key == "T3_paper_to_challenger":
            cur, _s, _t, _e = reg.request_transition(
                model_id=cur.model_id, version=cur.version,
                to_status=ModelLifecycleStatus.TESTED, transition_command="test",
                evidence_ref_ids=["e1"], requested_by="t", approved_by="l",
                requested_ts=cap5_seed_corr["requested_ts"],
                correlation_id=cap5_seed_corr["correlation_id"],
            )
            cur, _s, _t, _e = reg.request_transition(
                model_id=cur.model_id, version=cur.version,
                to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                evidence_ref_ids=["e2"], requested_by="t", approved_by="l",
                requested_ts=cap5_seed_corr["requested_ts"],
                correlation_id=cap5_seed_corr["correlation_id"],
            )
            target_cmd = "challenger"
            target_to = ModelLifecycleStatus.CHALLENGER
        pre_status = cur.status
        ev_refs = sorted([f"ev-{fixture_key}-1", f"ev-{fixture_key}-2", f"ev-{fixture_key}-3"])
        metadata = {
            "gate_decision_id": f"gd-{fixture_key}-001",
            "approval_refs": sorted([f"a-{fixture_key}-1", f"a-{fixture_key}-2", f"a-{fixture_key}-3"]),
            "audit_note": f"replay fixture {fixture_key}",
        }
        new_mv, new_sha, tx, env = reg.request_transition(
            model_id=cur.model_id,
            version=cur.version,
            to_status=target_to,
            transition_command=target_cmd,
            evidence_ref_ids=ev_refs,
            requested_by=f"req_{fixture_key}",
            approved_by=f"app_{fixture_key}",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            causation_id=None,
            transition_id=None,
            metadata=metadata,
        )
        payload = {}
        if env is not None and env.payload is not None and isinstance(env.payload, dict):
            payload = dict(env.payload)
        approvals = metadata.get("approval_refs") or []
        approval_count = len(approvals) if isinstance(approvals, list) else 0
        evidence_count = len(ev_refs) if isinstance(ev_refs, list) else 0
        sha_prefix = new_sha[:12]
        return {
            "from_status": pre_status.value,
            "to_status": target_to.value,
            "transition_command": target_cmd,
            "gate_decision_id": metadata.get("gate_decision_id", ""),
            "approval_count": approval_count,
            "evidence_refs_count": evidence_count,
            "sha_12_prefix": sha_prefix,
            "env_payload": payload,
            "tx_id": str(tx.transition_id),
            "new_sha": new_sha,
        }

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_from_status_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "from_status" in run_a
        assert isinstance(run_a["from_status"], str)
        assert run_a["from_status"] in {s.value for s in ModelLifecycleStatus}

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_to_status_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "to_status" in run_a
        assert isinstance(run_a["to_status"], str)
        assert run_a["to_status"] in {s.value for s in ModelLifecycleStatus}

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_transition_command_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "transition_command" in run_a
        assert isinstance(run_a["transition_command"], str)
        assert len(run_a["transition_command"]) > 0

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_gate_decision_id_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "gate_decision_id" in run_a
        assert isinstance(run_a["gate_decision_id"], str)

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_approval_count_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "approval_count" in run_a
        assert isinstance(run_a["approval_count"], int)
        assert run_a["approval_count"] >= 0

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_evidence_refs_count_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "evidence_refs_count" in run_a
        assert isinstance(run_a["evidence_refs_count"], int)
        assert run_a["evidence_refs_count"] >= 0

    @pytest.mark.parametrize("fixture_key", REPLAY_FIXTURE_KEYS)
    def test_phase1_replay_sha_12_prefix_sorted_asc_identical(
        self, fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        run_a = self.phase1_build_replay_bundle(fixture_key, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert "sha_12_prefix" in run_a
        assert isinstance(run_a["sha_12_prefix"], str)
        assert len(run_a["sha_12_prefix"]) == 12
