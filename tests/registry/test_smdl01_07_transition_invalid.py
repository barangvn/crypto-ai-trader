from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import (
    ERR_CAP5_COMMAND_EMPTY,
    ERR_CAP5_FSM_FORBIDDEN,
    ERR_CAP5_FSM_NOOP,
    RegistryError,
)
from tests.registry.conftest import sample_mv


FORBIDDEN_TRANSITIONS = [
    (ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.CHAMPION, "F1_candidate_to_champion"),
    (ModelLifecycleStatus.PAPER, ModelLifecycleStatus.CHAMPION, "F2_paper_to_champion"),
    (ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CHAMPION, "F3_tested_to_champion"),
    (ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CHALLENGER, "F5_champion_to_challenger"),
    (ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.PAPER, "F6_challenger_to_paper"),
    (ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CANDIDATE, "F7_tested_to_candidate"),
]


@pytest.mark.parametrize(
    "from_enum,to_enum,case_id",
    FORBIDDEN_TRANSITIONS,
)
def test_smdl01_07_forbidden_fsm_transition(fresh_registry, from_enum, to_enum, case_id):
    reg, bus, storage = fresh_registry
    meta = {}
    if to_enum == ModelLifecycleStatus.CHAMPION:
        meta["approval_refs"] = ["ap-1"]
    mv = sample_mv(status=from_enum, metadata=meta if meta else None)
    created_mv, _ = reg.create(mv)

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=to_enum,
            transition_command="try_forbidden",
        )
    assert exc_info.value.reason_code == ERR_CAP5_FSM_FORBIDDEN


RETIRED_TO_ANY = [
    ModelLifecycleStatus.CANDIDATE,
    ModelLifecycleStatus.TESTED,
    ModelLifecycleStatus.PAPER,
    ModelLifecycleStatus.CHALLENGER,
    ModelLifecycleStatus.CHAMPION,
    ModelLifecycleStatus.RETIRED,
]


@pytest.mark.parametrize("to_enum", RETIRED_TO_ANY)
def test_smdl01_07_F4_retired_to_any_forbidden(fresh_registry, to_enum):
    reg, bus, storage = fresh_registry
    meta = {}
    if to_enum == ModelLifecycleStatus.CHAMPION:
        meta["approval_refs"] = ["ap-1"]
    mv = sample_mv(status=ModelLifecycleStatus.RETIRED, metadata=meta if meta else None)
    created_mv, _ = reg.create(mv)

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=to_enum,
            transition_command="try_retired_out",
        )
    assert exc_info.value.reason_code in (ERR_CAP5_FSM_FORBIDDEN, ERR_CAP5_FSM_NOOP)


SAME_STATUS_NOOP = [
    ModelLifecycleStatus.CANDIDATE,
    ModelLifecycleStatus.TESTED,
    ModelLifecycleStatus.PAPER,
    ModelLifecycleStatus.CHALLENGER,
    ModelLifecycleStatus.CHAMPION,
    ModelLifecycleStatus.RETIRED,
]


@pytest.mark.parametrize("same_status", SAME_STATUS_NOOP)
def test_smdl01_07_same_status_noop_forbidden(fresh_registry, same_status):
    reg, bus, storage = fresh_registry
    meta = {}
    if same_status == ModelLifecycleStatus.CHAMPION:
        meta["approval_refs"] = ["ap-1"]
    mv = sample_mv(status=same_status, metadata=meta if meta else None)
    created_mv, _ = reg.create(mv)

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=same_status,
            transition_command="noop_attempt",
        )
    assert exc_info.value.reason_code == ERR_CAP5_FSM_NOOP


def test_smdl01_07_empty_command_forbidden(created_registry):
    reg, bus, storage, created_mv, _sha = created_registry

    with pytest.raises(RegistryError) as exc_info:
        reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="",
        )
    assert exc_info.value.reason_code == ERR_CAP5_COMMAND_EMPTY
