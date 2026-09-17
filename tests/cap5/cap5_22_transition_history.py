from __future__ import annotations

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from tests.cap5.conftest import (
    CAP5_FIXED_CORR,
    CAP5_TEST_TS,
    cap5_sample_mv,
)


class TestPhase1TransitionHistoryCompanions:
    def test_phase1_txhist_01_empty_history_on_create(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        hist = reg.transition_history(created.model_id, created.version)
        assert isinstance(hist, list)
        assert len(hist) == 0

    def test_phase1_txhist_02_history_after_t1_contains_one(self, cap5_created_tested):
        reg, bus, storage, mv, _sha, tx = cap5_created_tested
        hist = reg.transition_history(mv.model_id, mv.version)
        assert len(hist) >= 1
        last_tx = hist[-1]
        assert last_tx.to_status == ModelLifecycleStatus.TESTED

    def test_phase1_txhist_03_history_after_multi_steps(self, cap5_created_challenger):
        reg, bus, storage, mv, _sha, _tx = cap5_created_challenger
        hist = reg.transition_history(mv.model_id, mv.version)
        assert len(hist) >= 3
        statuses = [tx.to_status.value for tx in hist]
        assert ModelLifecycleStatus.TESTED.value in statuses
        assert ModelLifecycleStatus.PAPER.value in statuses
        assert ModelLifecycleStatus.CHALLENGER.value in statuses

    def test_phase1_txhist_04_history_deterministic_order(self, cap5_fresh_registry, cap5_seed_corr):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(
            status=ModelLifecycleStatus.CANDIDATE,
            correlation_id=cap5_seed_corr["correlation_id"],
            causation_id=cap5_seed_corr["causation_id"],
            created_ts=cap5_seed_corr["created_ts"],
        )
        created, _sha = reg.create(mv)
        for cmd, to_s in [
            ("test", ModelLifecycleStatus.TESTED),
            ("paper", ModelLifecycleStatus.PAPER),
            ("challenger", ModelLifecycleStatus.CHALLENGER),
        ]:
            reg.request_transition(
                model_id=created.model_id, version=created.version,
                to_status=to_s, transition_command=cmd,
                evidence_ref_ids=[f"ev-{cmd}-1"],
                requested_by="tester", approved_by="lead",
                requested_ts=CAP5_TEST_TS,
                correlation_id=cap5_seed_corr["correlation_id"],
            )
        hist = reg.transition_history(created.model_id, created.version)
        expected_order = [
            ModelLifecycleStatus.TESTED,
            ModelLifecycleStatus.PAPER,
            ModelLifecycleStatus.CHALLENGER,
        ]
        assert [tx.to_status for tx in hist] == expected_order

    def test_phase1_txhist_05_tx_from_to_fields_match_fsm(self, cap5_champion_with_approval):
        reg, bus, storage, mv, _sha, _tx = cap5_champion_with_approval
        hist = reg.transition_history(mv.model_id, mv.version)
        assert len(hist) >= 4
        champion_tx = [tx for tx in hist if tx.to_status == ModelLifecycleStatus.CHAMPION]
        assert len(champion_tx) >= 1
        tx4 = champion_tx[-1]
        assert tx4.from_status == ModelLifecycleStatus.CHALLENGER
        assert tx4.to_status == ModelLifecycleStatus.CHAMPION

    def test_phase1_txhist_06_reason_command_literal_preserved(self, cap5_created_tested):
        reg, bus, storage, mv, _sha, tx = cap5_created_tested
        hist = reg.transition_history(mv.model_id, mv.version)
        t1 = [t for t in hist if t.to_status == ModelLifecycleStatus.TESTED][-1]
        assert t1.reason == "test", "transition_command literal must be preserved as tx.reason (AD-23)"
