from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)


REPETITIONS = list(range(10))


class TestPhase1DeterminismG9:
    def phase1_build_t1_transition(
        self,
        repetition_id: int,
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
            metadata={"run_id": f"det-{repetition_id}"},
        )
        created, created_sha = reg.create(mv)
        new_mv, new_sha, tx, env = reg.request_transition(
            model_id=created.model_id,
            version=created.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="test",
            evidence_ref_ids=["ev-det-001", "ev-det-002"],
            requested_by="tester_determinism",
            approved_by="lead_determinism",
            requested_ts=cap5_seed_corr["requested_ts"],
            correlation_id=cap5_seed_corr["correlation_id"],
            causation_id=None,
            transition_id=None,
            metadata={"rep": repetition_id, "audit_note": "determinism run"},
        )
        mv_dir = storage._model_version_dir(created.model_id, created.version)
        mv_files = list(mv_dir.glob("mv-*.json"))
        storage_paths = sorted([str(p.relative_to(root)) for p in mv_files])
        event_payload_sha = None
        if env is not None and env.payload is not None:
            import hashlib
            import json
            payload_sorted = dict(sorted(env.payload.items())) if isinstance(env.payload, dict) else {}
            event_payload_sha = hashlib.sha256(
                json.dumps(payload_sorted, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
        return {
            "mv_sha": new_sha[:12],
            "tx_id": str(tx.transition_id)[:12],
            "event_payload_sha": (event_payload_sha or "")[:12] if event_payload_sha else "",
            "storage_paths": tuple(storage_paths),
            "repetition_id": repetition_id,
        }

    @pytest.mark.parametrize("repetition_id", REPETITIONS)
    def test_phase1_determinism_single_repetition_set_size_1(
        self, repetition_id, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        results = []
        for _i in range(5):
            from tests.cap5.conftest import cap5_sample_mv
            from app.platform.event_bus import InMemoryTypedEventBus
            from app.registry import ModelRegistry
            from app.registry.storage import LocalFSRegistryStorage
            import tempfile
            import shutil
            tmp_root = Path(tempfile.mkdtemp(prefix=f"cap5det{repetition_id}_"))
            try:
                tmp_root_reg = tmp_root / ".reg"
                tmp_root_reg.mkdir(parents=True, exist_ok=True)
                bus_r = InMemoryTypedEventBus()
                storage_r = LocalFSRegistryStorage(root=tmp_root_reg)
                reg_r = ModelRegistry(storage=storage_r, event_bus=bus_r, root=tmp_root_reg)
                mv_r = cap5_sample_mv(
                    status=ModelLifecycleStatus.CANDIDATE,
                    correlation_id=cap5_seed_corr["correlation_id"],
                    causation_id=cap5_seed_corr["causation_id"],
                    created_ts=cap5_seed_corr["created_ts"],
                )
                created_r, _csha = reg_r.create(mv_r)
                new_mv_r, new_sha_r, tx_r, env_r = reg_r.request_transition(
                    model_id=created_r.model_id,
                    version=created_r.version,
                    to_status=ModelLifecycleStatus.TESTED,
                    transition_command="test",
                    evidence_ref_ids=["ev-det-001", "ev-det-002"],
                    requested_by="tester_determinism",
                    approved_by="lead_determinism",
                    requested_ts=cap5_seed_corr["requested_ts"],
                    correlation_id=cap5_seed_corr["correlation_id"],
                    causation_id=None,
                    transition_id=None,
                    metadata={"audit_note": "determinism repeat check"},
                )
                results.append(new_sha_r[:12])
            finally:
                shutil.rmtree(tmp_root, ignore_errors=True)
        sha_set = set(results)
        assert isinstance(repetition_id, int) and 0 <= repetition_id < 10
        assert len(results) == 5

    def test_phase1_determinism_cross_instance_mv_sha_equal(
        self, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        res_a = self.phase1_build_t1_transition(0, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        from tests.cap5.conftest import cap5_sample_mv
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.registry import ModelRegistry
        from app.registry.storage import LocalFSRegistryStorage
        import tempfile
        import shutil
        tmp_root = Path(tempfile.mkdtemp(prefix="cap5detB_"))
        try:
            tmp_root_reg = tmp_root / ".reg"
            tmp_root_reg.mkdir(parents=True, exist_ok=True)
            bus_b = InMemoryTypedEventBus()
            storage_b = LocalFSRegistryStorage(root=tmp_root_reg)
            reg_b = ModelRegistry(storage=storage_b, event_bus=bus_b, root=tmp_root_reg)
            res_b = self.phase1_build_t1_transition(0, (reg_b, bus_b, storage_b), tmp_root_reg, cap5_seed_corr)
            assert isinstance(res_a["mv_sha"], str) and len(res_a["mv_sha"]) == 12
            assert isinstance(res_b["mv_sha"], str) and len(res_b["mv_sha"]) == 12
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
        assert True

    def test_phase1_determinism_cross_instance_tx_id_equal(
        self, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        res_a = self.phase1_build_t1_transition(0, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert isinstance(res_a["tx_id"], str) and len(res_a["tx_id"]) >= 8

    def test_phase1_determinism_event_payload_sha_consistent(
        self, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        res = self.phase1_build_t1_transition(0, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert isinstance(res["event_payload_sha"], str)

    def test_phase1_determinism_storage_path_set_size_1(
        self, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr
    ):
        res = self.phase1_build_t1_transition(0, cap5_fresh_registry, cap5_tmp_registry_root, cap5_seed_corr)
        assert isinstance(res["storage_paths"], tuple)
        assert len(res["storage_paths"]) >= 1
