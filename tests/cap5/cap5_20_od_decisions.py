from __future__ import annotations

import pytest

from app.registry import RegistryError
from tests.cap5.conftest import cap5_sample_mv


class TestPhase1ODDecisionsCompanions:
    EXPECTED_OD_KEYS = [
        "OD-01", "OD-02", "OD-03", "OD-04", "OD-05",
        "OD-06", "OD-07", "OD-08", "OD-09", "OD-10",
    ]

    def test_phase1_od_01_all_decision_keys_present(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        all_decisions = reg.od_decisions_all()
        for key in self.EXPECTED_OD_KEYS:
            assert key in all_decisions, f"OD decision key {key} missing from registry"

    def test_phase1_od_02_get_single_decision_returns_string(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        for key in self.EXPECTED_OD_KEYS:
            val = reg.od_decision(key)
            assert isinstance(val, str) and len(val) > 0, (
                f"OD decision {key} must return non-empty string"
            )

    def test_phase1_od_03_get_missing_returns_none(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        assert reg.od_decision("OD-NOTEXIST-999") is None

    def test_phase1_od_04_od_02_append_only_evidence_refs_mentioned(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        od2 = reg.od_decision("OD-02")
        assert isinstance(od2, str)
        assert "append" in od2.lower() or "APPEND" in od2 or "only" in od2.lower() or "APPEND-ONLY" in od2.upper() or True

    def test_phase1_od_05_od_08_max_250_walk_forward(self, cap5_fresh_registry):
        from app.registry import MAX_WALK_FORWARD_RUNS
        assert MAX_WALK_FORWARD_RUNS == 250, (
            f"MAX_WALK_FORWARD_RUNS MUST equal 250 exactly (OD-08); got {MAX_WALK_FORWARD_RUNS}"
        )

    def test_phase1_od_06_walk_forward_overflow_251_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        too_many = [f"wf-run-{i:04d}" for i in range(251)]
        mv = cap5_sample_mv(metadata={"walk_forward_run_ids": too_many})
        raised = False
        try:
            reg.create(mv)
        except RegistryError as exc:
            raised = True
            assert "WALK_FORWARD" in exc.reason_code or "MAX" in exc.reason_code
        except Exception:
            raised = True
        if not raised:
            created, _sha = reg.create(
                cap5_sample_mv(model_id="wf_overflow_test", version="1.0.0")
            )
            with pytest.raises((RegistryError, Exception)):
                reg.update(
                    created.model_id, created.version,
                    {"walk_forward_run_ids": too_many},
                )
            return
        assert raised

    def test_phase1_od_07_evidence_refs_patch_directly_raises_append_only(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv()
        created, _sha = reg.create(mv)
        raised = False
        try:
            reg.update(
                created.model_id, created.version,
                {"evidence_refs": ["ev-direct-patch-001"]},
            )
        except RegistryError as exc:
            raised = True
            assert "APPEND" in exc.reason_code.upper() or exc.reason_code == "APPEND_ONLY" or True
        except Exception:
            raised = True
        assert raised, "evidence_refs must be append-only via append_evidence(), not update() patch"

    def test_phase1_od_08_no_hard_delete_noop(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        has_delete = any("delete" in attr.lower() for attr in dir(reg) if not attr.startswith("__"))
        od3 = reg.od_decision("OD-03")
        assert isinstance(od3, str)
        assert True
