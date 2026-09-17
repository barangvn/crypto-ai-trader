from __future__ import annotations

import pytest

from app.contracts import (
    ModelLifecycleStatus,
    ModelPurposeEnum,
)
from app.registry import (
    EvidenceKind,
    EvidenceRef,
)
from tests.cap5.conftest import (
    CAP5_TEST_TS,
    cap5_sample_mv,
)


class TestPhase1FullIntegrationCompanions:
    def test_phase1_integ_01_full_cycle_candidate_to_retired(
        self, cap5_fresh_registry, cap5_seed_corr
    ):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(
            model_id="full_cycle_model",
            version="3.0.0",
            purpose=ModelPurposeEnum.EXECUTION_POLICY,
            status=ModelLifecycleStatus.CANDIDATE,
            correlation_id=cap5_seed_corr["correlation_id"],
            causation_id=cap5_seed_corr["causation_id"],
            created_ts=cap5_seed_corr["created_ts"],
        )
        created, sha1 = reg.create(mv)
        assert created.status == ModelLifecycleStatus.CANDIDATE

        ev1 = EvidenceRef(
            kind=EvidenceKind.HISTORICAL_OOS_EVAL,
            ref_id="full-cyc-oos-1",
            artifact_uri="file:///fc/oos-1.pkl",
            source_created_ts=CAP5_TEST_TS,
            correlation_id=cap5_seed_corr["correlation_id"].replace("AA", "CC"),
        )
        ev2 = EvidenceRef(
            kind=EvidenceKind.WALK_FORWARD_RUN,
            ref_id="full-cyc-wf-1",
            artifact_uri="file:///fc/wf-1.pkl",
            source_created_ts=CAP5_TEST_TS,
            correlation_id=cap5_seed_corr["correlation_id"].replace("AA", "DD"),
        )
        reg.append_evidence(created.model_id, created.version, ev1)
        reg.append_evidence(created.model_id, created.version, ev2)
        listed_ev = reg.list_evidence(created.model_id, created.version)
        assert len(listed_ev) == 2

        t1, sha2, tx1, env1 = reg.request_transition(
            model_id=created.model_id, version=created.version,
            to_status=ModelLifecycleStatus.TESTED, transition_command="test",
            evidence_ref_ids=["full-cyc-oos-1", "full-cyc-wf-1"],
            requested_by="sre_tester", approved_by="lead_sre",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            metadata={"audit_note": "historical OOS + walk-forward passed"},
        )
        assert t1.status == ModelLifecycleStatus.TESTED
        assert sha1 != sha2

        t2, sha3, tx2, env2 = reg.request_transition(
            model_id=t1.model_id, version=t1.version,
            to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
            evidence_ref_ids=["full-cyc-wf-1"],
            requested_by="sre_tester", approved_by="lead_sre",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            metadata={"audit_note": "paper trading 14-day window approved"},
        )
        assert t2.status == ModelLifecycleStatus.PAPER

        t3, sha4, tx3, env3 = reg.request_transition(
            model_id=t2.model_id, version=t2.version,
            to_status=ModelLifecycleStatus.CHALLENGER, transition_command="challenger",
            evidence_ref_ids=["full-cyc-oos-1"],
            requested_by="sre_tester", approved_by="lead_sre",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            metadata={"audit_note": "challenger vs current champion"},
        )
        assert t3.status == ModelLifecycleStatus.CHALLENGER

        reg.update(
            model_id=t3.model_id, version=t3.version,
            patch={"approval_refs": ["appr-panel-001", "appr-panel-002"]},
        )
        reg.set_predecessor(
            model_id=t3.model_id, version=t3.version,
            prev_model_id="prev_champion_v2", prev_version="2.9.9",
        )

        t4, sha5, tx4, env4 = reg.request_transition(
            model_id=t3.model_id, version=t3.version,
            to_status=ModelLifecycleStatus.CHAMPION, transition_command="promote_champion",
            evidence_ref_ids=["full-cyc-oos-1", "full-cyc-wf-1"],
            requested_by="promotion_panel", approved_by="chief_ml_officer",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            metadata={
                "gate_decision_id": "gate-dec-fullcyc-001",
                "approval_refs": ["appr-panel-001", "appr-panel-002"],
                "audit_note": "11/11 metrics passed, challenger promoted to champion",
            },
        )
        assert t4.status == ModelLifecycleStatus.CHAMPION
        assert t4.promoted_at is not None

        pred = reg.get_predecessor(t4.model_id, t4.version)
        assert pred is not None
        assert pred["model_id"] == "prev_champion_v2"

        t5, sha6, tx5, env5 = reg.request_transition(
            model_id=t4.model_id, version=t4.version,
            to_status=ModelLifecycleStatus.RETIRED, transition_command="retire_champion",
            evidence_ref_ids=["full-cyc-oos-1"],
            requested_by="sre_team", approved_by="production_manager",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            metadata={"audit_note": "newer champion v4.0.0 promoted, retiring v3"},
        )
        assert t5.status == ModelLifecycleStatus.RETIRED
        assert t5.retired_at is not None

        hist = reg.transition_history(t5.model_id, t5.version)
        assert len(hist) == 5
        published_count = len(bus.published)
        assert published_count >= 5, "5 valid transitions must each emit >=1 event"

    def test_phase1_integ_02_two_models_list_sorted_canonical(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        reg.create(cap5_sample_mv(model_id="zebra_model", version="1.0.0", purpose=ModelPurposeEnum.COST_MODEL))
        reg.create(cap5_sample_mv(model_id="alpha_model", version="2.0.0", purpose=ModelPurposeEnum.DIRECTIONAL))
        reg.create(cap5_sample_mv(model_id="alpha_model", version="1.0.0", purpose=ModelPurposeEnum.DIRECTIONAL))
        items = reg.list()
        model_ids = [m.model_id for m, _s in items]
        assert model_ids == sorted(model_ids)

    def test_phase1_integ_03_fail_closed_complete_attempt_leaves_clean_state(
        self, cap5_fresh_registry, cap5_tmp_registry_root
    ):
        from pathlib import Path as P
        reg, bus, storage = cap5_fresh_registry
        root: P = cap5_tmp_registry_root
        mv = cap5_sample_mv(model_id="clean_state", version="1.0.0")
        created, sha_before = reg.create(mv)
        pre_mv_files = list((root / "models" / "clean_state" / "1.0.0").glob("mv-*.json")) if (root / "models" / "clean_state").exists() else []
        pre_publish = len(bus.published)
        raised_count = 0
        total_attempts = 6
        for _ in range(total_attempts):
            try:
                reg.request_transition(
                    model_id=created.model_id, version=created.version,
                    to_status=ModelLifecycleStatus.CHAMPION,
                    transition_command="invalid_direct_promote_F1",
                    evidence_ref_ids=["bad-ev"],
                    requested_by="bad_actor", approved_by="nobody",
                )
            except Exception:
                raised_count += 1
        assert raised_count == total_attempts, f"All {total_attempts} invalid attempts must raise"
        post_publish = len(bus.published)
        assert post_publish - pre_publish == 0, "Invalid FSM attempts must produce zero events"
        post_mv_files = list((root / "models" / "clean_state" / "1.0.0").glob("mv-*.json")) if (root / "models" / "clean_state").exists() else []
        assert len(post_mv_files) == len(pre_mv_files), "Invalid transitions must not write new mv artifact files"
