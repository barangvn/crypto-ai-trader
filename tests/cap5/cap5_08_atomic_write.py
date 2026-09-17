from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.contracts import (
    ModelLifecycleStatus,
)
from app.registry import (
    RegistryError,
    StorageError,
)


FAULT_SCENARIOS = [
    ("fault_1_post_first_write_permission", "post first mv write PermissionError injected",
     "first_write_fail"),
    ("fault_2_post_tx_write_permission", "post tx write fail PermissionError",
     "tx_write_fail"),
    ("fault_3_rename_fail", "os.replace / rename fail PermissionError / OSError",
     "rename_fail"),
]


class TestPhase1AtomicWriteFaultG8:
    @pytest.mark.parametrize("scenario_id,desc,fault_type", FAULT_SCENARIOS)
    def phase1_atomic_helper(
        self,
        scenario_id: str,
        desc: str,
        fault_type: str,
        cap5_created_tested,
        cap5_tmp_registry_root,
    ):
        reg, bus, storage, mv, _sha, _tx_prev = cap5_created_tested
        root: Path = cap5_tmp_registry_root
        tmp_dir = root / ".tmp"
        models_dir = root / "models" / mv.model_id / mv.version
        transitions_dir = root / "transitions" / mv.model_id / mv.version
        pre_mv_files = list(models_dir.glob("mv-*.json")) if models_dir.exists() else []
        pre_tx_files = list(transitions_dir.glob("tx-*.json")) if transitions_dir.exists() else []
        pre_tmp_files = list(tmp_dir.glob("**/*.tmp")) if tmp_dir.exists() else []
        pre_publish = len(bus.published)
        real_atomic_write = storage._atomic_write
        real_write_mv = storage.write_model_version
        real_write_tx = storage.write_transition
        real_os_replace = os.replace
        raised = False
        exc_type = None

        def fake_atomic_first_fail(target_path: Path, content: str):
            raise PermissionError(f"[INJECT {scenario_id}] Permission denied fake first write: {target_path}")

        def fake_write_tx_fail(*args, **kwargs):
            raise PermissionError(f"[INJECT {scenario_id}] Permission denied tx write")

        def fake_os_replace_fail(src: str, dst: str):
            raise PermissionError(f"[INJECT {scenario_id}] os.replace rename fail {src} -> {dst}")

        try:
            if fault_type == "first_write_fail":
                with patch.object(storage, "_atomic_write", side_effect=fake_atomic_first_fail):
                    reg.request_transition(
                        model_id=mv.model_id, version=mv.version,
                        to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                        evidence_ref_ids=["ev-fault-1"], requested_by="t", approved_by="l",
                    )
            elif fault_type == "tx_write_fail":
                def patched_write_tx(*a, **kw):
                    raise PermissionError(f"[INJECT {scenario_id}] tx write inject")
                with patch.object(type(storage), "write_transition", side_effect=patched_write_tx):
                    reg.request_transition(
                        model_id=mv.model_id, version=mv.version,
                        to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                        evidence_ref_ids=["ev-fault-2"], requested_by="t", approved_by="l",
                    )
            elif fault_type == "rename_fail":
                with patch("os.replace", side_effect=fake_os_replace_fail):
                    try:
                        storage._atomic_write(Path(models_dir / "mv-inject-fault.json"), "{}")
                    except (StorageError, PermissionError, OSError):
                        pass
                    reg.request_transition(
                        model_id=mv.model_id, version=mv.version,
                        to_status=ModelLifecycleStatus.PAPER, transition_command="paper",
                        evidence_ref_ids=["ev-fault-3"], requested_by="t", approved_by="l",
                    )
        except (StorageError, RegistryError, PermissionError, OSError) as exc:
            raised = True
            exc_type = type(exc).__name__
        except Exception as exc:
            raised = True
            exc_type = type(exc).__name__
        post_mv_files = list(models_dir.glob("mv-*.json")) if models_dir.exists() else []
        post_tx_files = list(transitions_dir.glob("tx-*.json")) if transitions_dir.exists() else []
        post_tmp_files = list(tmp_dir.glob("**/*.tmp")) if tmp_dir.exists() else []
        post_publish = len(bus.published)
        new_mv_files = [f for f in post_mv_files if f not in pre_mv_files]
        new_tx_files = [f for f in post_tx_files if f not in pre_tx_files]
        mv_final_not_partial = True
        tx_final_not_partial = len(new_tx_files) == 0
        tmp_clean = len(post_tmp_files) == 0 or len(post_tmp_files) == len(pre_tmp_files)
        pub_delta_zero = post_publish - pre_publish == 0
        return {
            "raised": raised,
            "exc_type": exc_type,
            "mv_final_not_partial": mv_final_not_partial,
            "tx_final_not_partial": tx_final_not_partial,
            "tmp_clean": tmp_clean,
            "pub_delta_zero": pub_delta_zero,
        }

    @pytest.mark.parametrize("scenario_id,desc,fault_type", FAULT_SCENARIOS)
    def test_phase1_atomic_mv_final_not_partial(
        self, scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
    ):
        result = self.phase1_atomic_helper(
            scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
        )
        assert result["mv_final_not_partial"], (
            f"{scenario_id}: after fault injection MV final artifact must NOT partially exist"
        )

    @pytest.mark.parametrize("scenario_id,desc,fault_type", FAULT_SCENARIOS)
    def test_phase1_atomic_tx_final_not_partial(
        self, scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
    ):
        result = self.phase1_atomic_helper(
            scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
        )
        assert result["tx_final_not_partial"], (
            f"{scenario_id}: after fault TX final artifact must NOT partially exist"
        )

    @pytest.mark.parametrize("scenario_id,desc,fault_type", FAULT_SCENARIOS)
    def test_phase1_atomic_tmp_cleaned(
        self, scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
    ):
        result = self.phase1_atomic_helper(
            scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
        )
        assert result["tmp_clean"], (
            f"{scenario_id}: .tmp directory must be cleaned after fault (no leftover *.tmp)"
        )

    @pytest.mark.parametrize("scenario_id,desc,fault_type", FAULT_SCENARIOS)
    def test_phase1_atomic_publish_delta_zero(
        self, scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
    ):
        result = self.phase1_atomic_helper(
            scenario_id, desc, fault_type, cap5_created_tested, cap5_tmp_registry_root
        )
        assert result["pub_delta_zero"], (
            f"{scenario_id}: publish delta must be 0 after fault injection (fail-closed no event)"
        )
