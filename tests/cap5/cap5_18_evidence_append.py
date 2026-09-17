from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import (
    EvidenceKind,
    EvidenceRef,
    RegistryError,
)
from tests.cap5.conftest import CAP5_TEST_TS, cap5_sample_mv


EVIDENCE_KINDS = list(EvidenceKind.__members__.values())


class TestPhase1EvidenceAppendCompanions:
    def _ev(self, kind: EvidenceKind, ref_id: str) -> EvidenceRef:
        return EvidenceRef(
            kind=kind,
            ref_id=ref_id,
            artifact_uri=f"file:///artifacts/evidence/{ref_id}.bin",
            source_created_ts=CAP5_TEST_TS,
            correlation_id=f"0192000000007000800000000000EE{ref_id[-2:]}" if len(ref_id) >= 2 else "0192000000007000800000000000EEEE",
        )

    def test_phase1_evidence_01_append_one_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        ev = self._ev(EvidenceKind.HISTORICAL_OOS_EVAL, "oos-eval-001")
        result = reg.append_evidence(created.model_id, created.version, ev)
        assert isinstance(result, list)
        assert len(result) == 1
        listed = reg.list_evidence(created.model_id, created.version)
        assert len(listed) == 1
        assert listed[0].ref_id == "oos-eval-001"

    def test_phase1_evidence_02_append_multiple_kinds_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        for i, kind in enumerate(EVIDENCE_KINDS[:4], 1):
            ev = self._ev(kind, f"ev-kind-{kind.value}-{i:03d}")
            reg.append_evidence(created.model_id, created.version, ev)
        listed = reg.list_evidence(created.model_id, created.version)
        assert len(listed) == 4
        kinds_present = {e.kind for e in listed}
        expected = set(EVIDENCE_KINDS[:4])
        assert kinds_present == expected

    def test_phase1_evidence_03_duplicate_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        ev = self._ev(EvidenceKind.WALK_FORWARD_RUN, "wf-dup-ref")
        reg.append_evidence(created.model_id, created.version, ev)
        with pytest.raises(RegistryError):
            reg.append_evidence(created.model_id, created.version, ev)

    def test_phase1_evidence_04_list_empty_ok(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        listed = reg.list_evidence(created.model_id, created.version)
        assert isinstance(listed, list)
        assert len(listed) == 0

    def test_phase1_evidence_05_invalid_kind_raises(self, cap5_created_candidate):
        reg, bus, storage, mv, _sha = cap5_created_candidate
        with pytest.raises((RegistryError, ValueError, TypeError)):
            bad_ev = EvidenceRef(
                kind="not_a_valid_kind_xyz",
                ref_id="bad-kind-ref",
                artifact_uri="file:///bad.pkl",
                source_created_ts=CAP5_TEST_TS,
                correlation_id="0192000000007000800000000000FFFF",
            )
            reg.append_evidence(mv.model_id, mv.version, bad_ev)

    def test_phase1_evidence_06_empty_ref_id_raises(self, cap5_created_candidate):
        reg, bus, storage, mv, _sha = cap5_created_candidate
        with pytest.raises((RegistryError, Exception)):
            bad_ev = EvidenceRef(
                kind=EvidenceKind.ARTIFACT_PACKAGE,
                ref_id="",
                artifact_uri="file:///ok.pkl",
                source_created_ts=CAP5_TEST_TS,
                correlation_id="0192000000007000800000000000AAA0",
            )
            reg.append_evidence(mv.model_id, mv.version, bad_ev)

    def test_phase1_evidence_07_empty_artifact_uri_raises(self, cap5_created_candidate):
        reg, bus, storage, mv, _sha = cap5_created_candidate
        with pytest.raises((RegistryError, Exception)):
            bad_ev = EvidenceRef(
                kind=EvidenceKind.FEATURESET_REF,
                ref_id="fsr-001",
                artifact_uri="",
                source_created_ts=CAP5_TEST_TS,
                correlation_id="0192000000007000800000000000AAA1",
            )
            reg.append_evidence(mv.model_id, mv.version, bad_ev)

    def test_phase1_evidence_08_canonical_order_by_kind_then_ref(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, _sha = reg.create(mv)
        ev_b = self._ev(EvidenceKind.WALK_FORWARD_RUN, "bbb")
        ev_a = self._ev(EvidenceKind.WALK_FORWARD_RUN, "aaa")
        ev_z = self._ev(EvidenceKind.ARTIFACT_PACKAGE, "zzz")
        reg.append_evidence(created.model_id, created.version, ev_b)
        reg.append_evidence(created.model_id, created.version, ev_a)
        reg.append_evidence(created.model_id, created.version, ev_z)
        listed = reg.list_evidence(created.model_id, created.version)
        kinds = [e.kind.value for e in listed]
        assert kinds == sorted(kinds), "evidence must be in canonical order by kind ASC"
        wf_items = [e for e in listed if e.kind == EvidenceKind.WALK_FORWARD_RUN]
        ref_ids = [e.ref_id for e in wf_items]
        assert ref_ids == sorted(ref_ids), "same kind must be sorted by ref_id ASC"
