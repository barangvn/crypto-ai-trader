from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import ERR_PROMOTE_MIN_APPROVAL, RegistryError
from tests.registry.conftest import sample_mv


def test_smdl01_15_T4_promote_challenger_without_approval_refs_raises(created_registry):
    reg, _bus, _storage, created_mv, _sha = created_registry

    _mv1, _sha1, _tx1, _env1 = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )
    _mv2, _sha2, _tx2, _env2 = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.PAPER,
        transition_command="deploy_to_paper_track",
    )
    _mv3, _sha3, _tx3, _env3 = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.CHALLENGER,
        transition_command="promote_challenger_candidate",
    )

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=ModelLifecycleStatus.CHAMPION,
            transition_command="promote_champion",
        )
    assert exc_info.value.reason_code == ERR_PROMOTE_MIN_APPROVAL


def test_smdl01_15_T4_promote_challenger_with_approval_refs_ok(fresh_registry):
    reg, _bus, _storage = fresh_registry

    mv = sample_mv(
        status=ModelLifecycleStatus.CHALLENGER,
        metadata={"approval_refs": ["ap-1"]},
    )
    created_mv, _created_sha = reg.create(mv)

    new_mv, new_sha, tx, _env = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.CHAMPION,
        transition_command="promote_champion",
    )
    assert new_mv.status == ModelLifecycleStatus.CHAMPION
    assert tx.to_status == ModelLifecycleStatus.CHAMPION
    assert isinstance(new_sha, str) and len(new_sha) == 64


def test_smdl01_15_set_predecessor_then_get_returns_modelid_version(fresh_registry):
    reg, _bus, _storage = fresh_registry

    challenger = sample_mv(
        model_id="challenger_model",
        version="2.1.0",
        status=ModelLifecycleStatus.CHALLENGER,
        metadata={"approval_refs": ["ap-2"]},
    )
    champion_prev = sample_mv(
        model_id="champion_prev_model",
        version="1.9.0",
        status=ModelLifecycleStatus.CHAMPION,
    )
    reg.create(challenger)
    reg.create(champion_prev)

    reg.set_predecessor(
        model_id="challenger_model",
        version="2.1.0",
        prev_model_id="champion_prev_model",
        prev_version="1.9.0",
    )

    predecessor = reg.get_predecessor("challenger_model", "2.1.0")
    assert predecessor is not None
    assert "model_id" in predecessor
    assert "version" in predecessor
    assert predecessor["model_id"] == "champion_prev_model"
    assert predecessor["version"] == "1.9.0"


def test_smdl01_15_predecessor_default_none_for_candidate(created_registry):
    reg, _bus, _storage, created_mv, _sha = created_registry

    result = reg.get_predecessor(created_mv.model_id, created_mv.version)
    assert result is None


def test_smdl01_15_get_predecessor_nonexistent_returns_none(fresh_registry):
    reg, _bus, _storage = fresh_registry
    assert reg.get_predecessor("no_such_model", "0.0.0") is None


def test_smdl01_15_set_predecessor_used_registry_created_registry_fixtures(
    fresh_registry, created_registry
):
    f_reg, _f_bus, _f_storage = fresh_registry
    c_reg, _c_bus, _c_storage, c_mv, _c_sha = created_registry

    f_mv = sample_mv(
        model_id="fresh_reg_model",
        version="0.0.1",
        status=ModelLifecycleStatus.CHALLENGER,
        metadata={"approval_refs": ["ap-fresh"]},
    )
    f_reg.create(f_mv)

    f_reg.set_predecessor(
        "fresh_reg_model", "0.0.1",
        "created_reg_model", "9.9.9",
    )
    p1 = f_reg.get_predecessor("fresh_reg_model", "0.0.1")
    assert p1 is not None
    assert p1["model_id"] == "created_reg_model"
    assert p1["version"] == "9.9.9"

    c_reg.set_predecessor(
        c_mv.model_id, c_mv.version,
        "older_champion", "0.5.0",
    )
    p2 = c_reg.get_predecessor(c_mv.model_id, c_mv.version)
    assert p2 is not None
    assert p2["model_id"] == "older_champion"
    assert p2["version"] == "0.5.0"


def test_smdl01_15_T4_approval_refs_list_contains_string_entries(fresh_registry):
    reg, _bus, _storage = fresh_registry

    mv = sample_mv(
        status=ModelLifecycleStatus.CHALLENGER,
        metadata={"approval_refs": ["ap-a", "ap-b", "ap-c"]},
    )
    created_mv, _sha = reg.create(mv)

    new_mv, _new_sha, tx, _env = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.CHAMPION,
        transition_command="promote_champion",
    )
    assert new_mv.status == ModelLifecycleStatus.CHAMPION
    assert tx.reason == "promote_champion"
