from __future__ import annotations

from app.contracts import ModelLifecycleStatus, ModelPurposeEnum
from app.registry import RegistryListFilter
from tests.registry.conftest import sample_mv


def _create_sample_mvs(reg):
    specs = [
        ("model_alpha", "1.0.0", ModelLifecycleStatus.PAPER, ModelPurposeEnum.DIRECTIONAL, "2026-09-01T00:00:00.000Z"),
        ("model_alpha", "2.0.0", ModelLifecycleStatus.TESTED, ModelPurposeEnum.DIRECTIONAL, "2026-09-02T00:00:00.000Z"),
        ("model_beta", "1.0.0", ModelLifecycleStatus.PAPER, ModelPurposeEnum.REGIME_DETECTOR, "2026-09-03T00:00:00.000Z"),
        ("model_beta", "1.5.0", ModelLifecycleStatus.CANDIDATE, ModelPurposeEnum.COST_MODEL, "2026-09-04T00:00:00.000Z"),
    ]
    created = []
    for mid, ver, status, purpose, ts in specs:
        mv = sample_mv(
            model_id=mid,
            version=ver,
            status=status,
            purpose=purpose,
            created_ts=ts,
        )
        reg.create(mv)
        created.append((mid, ver, status, purpose, ts))
    return created


def test_smdl01_12_filter_status_paper_returns_only_paper(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    result = reg.list(RegistryListFilter(status=ModelLifecycleStatus.PAPER))
    assert len(result) == 2
    statuses = {mv.status for mv, _sha in result}
    assert statuses == {ModelLifecycleStatus.PAPER}


def test_smdl01_12_filter_model_id_exact_returns_only_matching(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    result = reg.list(RegistryListFilter(model_id="model_alpha"))
    assert len(result) == 2
    ids = {mv.model_id for mv, _sha in result}
    assert ids == {"model_alpha"}

    result_beta = reg.list(RegistryListFilter(model_id="model_beta"))
    assert len(result_beta) == 2
    ids_beta = {mv.model_id for mv, _sha in result_beta}
    assert ids_beta == {"model_beta"}


def test_smdl01_12_filter_created_after_filters_by_ts(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    cutoff = "2026-09-02T12:00:00.000Z"
    result = reg.list(RegistryListFilter(created_after=cutoff))
    created_tss = [mv.created_ts for mv, _sha in result]
    for ts in created_tss:
        assert ts >= cutoff
    assert len(result) == 2


def test_smdl01_12_filter_purpose_directional_only(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    result = reg.list(RegistryListFilter(purpose=ModelPurposeEnum.DIRECTIONAL))
    purposes = {mv.purpose for mv, _sha in result}
    assert purposes == {ModelPurposeEnum.DIRECTIONAL}
    assert len(result) == 2


def test_smdl01_12_list_default_canonical_order_modelid_semver_created_desc(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    result = reg.list()

    ids = [mv.model_id for mv, _sha in result]
    assert ids == sorted(ids)

    for i in range(len(result) - 1):
        cur_mv, _cur = result[i]
        nxt_mv, _nxt = result[i + 1]
        if cur_mv.model_id == nxt_mv.model_id:
            cur_ver = tuple(int(p) if p.isdigit() else p for p in cur_mv.version.split("."))
            nxt_ver = tuple(int(p) if p.isdigit() else p for p in nxt_mv.version.split("."))
            assert cur_ver <= nxt_ver


def test_smdl01_12_list_empty_registry_returns_empty_list(fresh_registry):
    reg, _bus, _storage = fresh_registry
    result = reg.list()
    assert result == []


def test_smdl01_12_combined_filters_status_and_purpose(fresh_registry):
    reg, _bus, _storage = fresh_registry
    _create_sample_mvs(reg)

    result = reg.list(
        RegistryListFilter(
            status=ModelLifecycleStatus.PAPER,
            purpose=ModelPurposeEnum.DIRECTIONAL,
        )
    )
    assert len(result) == 1
    mv, _sha = result[0]
    assert mv.model_id == "model_alpha"
    assert mv.version == "1.0.0"
    assert mv.status == ModelLifecycleStatus.PAPER
    assert mv.purpose == ModelPurposeEnum.DIRECTIONAL
