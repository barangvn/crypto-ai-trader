from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import ERR_CAP5_FSM_FORBIDDEN, ERR_PROMOTE_MIN_APPROVAL, RegistryError
from tests.registry.conftest import sample_mv


VALID_TRANSITIONS = [
    (
        ModelLifecycleStatus.CANDIDATE,
        ModelLifecycleStatus.TESTED,
        "run_backtest_and_evaluate",
        {},
    ),
    (
        ModelLifecycleStatus.TESTED,
        ModelLifecycleStatus.PAPER,
        "deploy_to_paper_track",
        {},
    ),
    (
        ModelLifecycleStatus.PAPER,
        ModelLifecycleStatus.CHALLENGER,
        "promote_challenger_candidate",
        {},
    ),
    (
        ModelLifecycleStatus.CHALLENGER,
        ModelLifecycleStatus.CHAMPION,
        "promote_champion",
        {"approval_refs": ["ap-1"]},
    ),
    (
        ModelLifecycleStatus.CHAMPION,
        ModelLifecycleStatus.RETIRED,
        "retire_champion",
        {},
    ),
    (
        ModelLifecycleStatus.CANDIDATE,
        ModelLifecycleStatus.RETIRED,
        "admin_retire",
        {},
    ),
    (
        ModelLifecycleStatus.TESTED,
        ModelLifecycleStatus.RETIRED,
        "admin_retire",
        {},
    ),
    (
        ModelLifecycleStatus.PAPER,
        ModelLifecycleStatus.RETIRED,
        "admin_retire",
        {},
    ),
    (
        ModelLifecycleStatus.CHALLENGER,
        ModelLifecycleStatus.RETIRED,
        "admin_retire",
        {},
    ),
]


@pytest.mark.parametrize(
    "from_enum,to_enum,command,extra_metadata",
    VALID_TRANSITIONS,
    ids=[
        "T1_candidate_to_tested",
        "T2_tested_to_paper",
        "T3_paper_to_challenger",
        "T4_challenger_to_champion",
        "T5_champion_to_retired",
        "T6_admin_retire_candidate",
        "T7_admin_retire_tested",
        "T8_admin_retire_paper",
        "T9_admin_retire_challenger",
    ],
)
def test_smdl01_06_valid_transition(
    fresh_registry, from_enum, to_enum, command, extra_metadata
):
    reg, bus, storage = fresh_registry

    base_meta = {}
    base_meta.update(extra_metadata)
    mv = sample_mv(
        status=from_enum,
        metadata=base_meta if base_meta else None,
    )
    created_mv, created_sha = reg.create(mv)

    new_mv, new_sha, tx, envelope = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=to_enum,
        transition_command=command,
    )

    assert tx.from_status == from_enum
    assert tx.to_status == to_enum
    assert new_mv.status == to_enum
    assert isinstance(new_sha, str) and len(new_sha) == 64


def test_smdl01_06_T4_challenger_to_champion_fails_without_approval(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(status=ModelLifecycleStatus.CHALLENGER)
    created_mv, _ = reg.create(mv)

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=ModelLifecycleStatus.CHAMPION,
            transition_command="promote_champion",
        )
    assert exc_info.value.reason_code == ERR_PROMOTE_MIN_APPROVAL
