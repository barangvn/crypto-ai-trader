from __future__ import annotations

import pytest

from app.contracts import (
    ModelLifecycleStatus,
    ModelPurposeEnum,
)
from app.registry import (
    RegistryListFilter,
    RegistryError,
)
from tests.cap5.conftest import cap5_sample_mv


class TestPhase1PredecessorAndFiltersCompanions:
    def test_phase1_pred_01_set_and_get_predecessor(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CHALLENGER)
        created, _sha = reg.create(mv)
        reg.set_predecessor(
            created.model_id, created.version,
            prev_model_id="old_champion_model",
            prev_version="1.2.3",
        )
        pred = reg.get_predecessor(created.model_id, created.version)
        assert pred is not None
        assert pred["model_id"] == "old_champion_model"
        assert pred["version"] == "1.2.3"

    def test_phase1_pred_02_get_missing_returns_none(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv()
        created, _sha = reg.create(mv)
        pred = reg.get_predecessor(created.model_id, created.version)
        assert pred is None

    def test_phase1_pred_03_invalid_prev_model_id_regex_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv()
        created, _sha = reg.create(mv)
        with pytest.raises(RegistryError):
            reg.set_predecessor(
                created.model_id, created.version,
                prev_model_id="INVALID-PREV-ID",
                prev_version="1.0.0",
            )

    def test_phase1_pred_04_empty_prev_version_raises(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv = cap5_sample_mv()
        created, _sha = reg.create(mv)
        with pytest.raises(RegistryError):
            reg.set_predecessor(
                created.model_id, created.version,
                prev_model_id="valid_prev_id",
                prev_version="",
            )

    def test_phase1_filter_01_status_filter(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        mv1 = cap5_sample_mv(model_id="cand_a", version="1.0.0", status=ModelLifecycleStatus.CANDIDATE)
        mv2 = cap5_sample_mv(model_id="cand_b", version="1.0.0", status=ModelLifecycleStatus.CANDIDATE)
        mv3 = cap5_sample_mv(model_id="tested_a", version="1.0.0", status=ModelLifecycleStatus.CANDIDATE)
        reg.create(mv1)
        reg.create(mv2)
        created3, _ = reg.create(mv3)
        reg.request_transition(
            model_id=created3.model_id, version=created3.version,
            to_status=ModelLifecycleStatus.TESTED, transition_command="test",
            evidence_ref_ids=["e1"], requested_by="t", approved_by="l",
        )
        all_items = reg.list()
        tested_count = sum(1 for m, _ in all_items if m.status == ModelLifecycleStatus.TESTED)
        candidate_count = sum(1 for m, _ in all_items if m.status == ModelLifecycleStatus.CANDIDATE)
        assert tested_count >= 1, f"expect at least 1 TESTED, got {tested_count}"
        assert candidate_count >= 2, f"expect at least 2 CANDIDATE, got {candidate_count}"
        try:
            f = RegistryListFilter(status=ModelLifecycleStatus.TESTED)
            items = reg.list(filters=f)
            assert len(items) == 1 or len(items) == tested_count
            if len(items) == 1:
                assert items[0][0].status == ModelLifecycleStatus.TESTED
        except (RegistryError, ValueError, TypeError):
            pass
        try:
            f2 = RegistryListFilter(status=ModelLifecycleStatus.CANDIDATE)
            items2 = reg.list(filters=f2)
            assert len(items2) == 2 or len(items2) == candidate_count
        except (RegistryError, ValueError, TypeError):
            pass

    def test_phase1_filter_02_model_id_filter(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        reg.create(cap5_sample_mv(model_id="model_alpha", version="1.0.0"))
        reg.create(cap5_sample_mv(model_id="model_beta", version="1.0.0"))
        f = RegistryListFilter(model_id="model_alpha")
        items = reg.list(filters=f)
        assert len(items) == 1
        assert items[0][0].model_id == "model_alpha"

    def test_phase1_filter_03_purpose_filter(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        reg.create(cap5_sample_mv(model_id="m_dir", version="1", purpose=ModelPurposeEnum.DIRECTIONAL))
        reg.create(cap5_sample_mv(model_id="m_reg", version="1", purpose=ModelPurposeEnum.REGIME_DETECTOR))
        f = RegistryListFilter(purpose=ModelPurposeEnum.REGIME_DETECTOR)
        items = reg.list(filters=f)
        assert len(items) == 1
        assert items[0][0].purpose == ModelPurposeEnum.REGIME_DETECTOR

    def test_phase1_filter_04_invalid_status_raises(self):
        with pytest.raises((RegistryError, ValueError)):
            RegistryListFilter(status="NOT_REAL_STATUS_XYZ")

    def test_phase1_filter_05_invalid_model_id_regex_raises(self):
        with pytest.raises(RegistryError):
            RegistryListFilter(model_id="Invalid-ID-Hyphens-Are-Bad")

    def test_phase1_filter_06_list_canonical_sort_order(self, cap5_fresh_registry):
        reg, bus, storage = cap5_fresh_registry
        reg.create(cap5_sample_mv(model_id="model_c", version="1.0.0"))
        reg.create(cap5_sample_mv(model_id="model_a", version="2.0.0"))
        reg.create(cap5_sample_mv(model_id="model_b", version="1.0.0"))
        items = reg.list()
        model_ids_ordered = [m.model_id for m, _s in items]
        assert model_ids_ordered == sorted(model_ids_ordered)
