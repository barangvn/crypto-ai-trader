from __future__ import annotations

from app.contracts import ModelLifecycleStatus
from tests.registry.conftest import sample_mv


def test_smdl01_16_two_transitions_history_length_and_order(fresh_registry):
    reg, bus, storage = fresh_registry

    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    _mv1, _sha1, tx1, _env1 = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )

    _mv2, _sha2, tx2, _env2 = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.PAPER,
        transition_command="deploy_to_paper_track",
    )

    history = reg.transition_history(created_mv.model_id, created_mv.version)
    assert len(history) == 2

    assert history[0].transition_id == tx1.transition_id
    assert history[0].from_status == ModelLifecycleStatus.CANDIDATE
    assert history[0].to_status == ModelLifecycleStatus.TESTED

    assert history[1].transition_id == tx2.transition_id
    assert history[1].from_status == ModelLifecycleStatus.TESTED
    assert history[1].to_status == ModelLifecycleStatus.PAPER


def test_smdl01_16_history_from_status_sequence_matches(fresh_registry):
    reg, bus, storage = fresh_registry

    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )
    reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.PAPER,
        transition_command="deploy_to_paper_track",
    )

    history = reg.transition_history(created_mv.model_id, created_mv.version)
    from_sequence = [h.from_status for h in history]
    assert from_sequence == [ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.TESTED]

    to_sequence = [h.to_status for h in history]
    assert to_sequence == [ModelLifecycleStatus.TESTED, ModelLifecycleStatus.PAPER]


def test_smdl01_16_history_empty_before_any_transition(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    history = reg.transition_history(created_mv.model_id, created_mv.version)
    assert len(history) == 0
