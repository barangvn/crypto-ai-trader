from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from tests.registry.conftest import sample_mv


def test_smdl01_09_subscriber_exception_captured_in_dlq(fresh_registry):
    reg, bus, storage = fresh_registry

    def failing_subscriber(envelope):
        raise RuntimeError("simulated subscriber failure")

    bus.subscribe_typed(
        "model_version_status_transitioned.v1",
        failing_subscriber,
    )

    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    result = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )
    new_mv, new_sha, tx, envelope = result

    assert new_mv.status == ModelLifecycleStatus.TESTED
    assert len(bus.dead_letters) > 0
    dlq_codes = [dl.dlq_code for dl in bus.dead_letters]
    assert "E_SUBSCRIBER_EXC" in dlq_codes

    matching = [dl for dl in bus.dead_letters if dl.dlq_code == "E_SUBSCRIBER_EXC"]
    assert len(matching) >= 1
    assert matching[0].exc_type_name == "RuntimeError"
    assert "simulated subscriber failure" in (matching[0].exc_message or "")


def test_smdl01_09_transition_succeeds_despite_subscriber_exception(fresh_registry):
    reg, bus, storage = fresh_registry

    def bad_cb(env):
        raise ValueError("boom in handler")

    bus.subscribe_typed("model_version_status_transitioned.v1", bad_cb)

    mv = sample_mv(status=ModelLifecycleStatus.TESTED)
    created_mv, _ = reg.create(mv)

    try:
        new_mv, new_sha, tx, envelope = reg.request_transition(
            model_id=created_mv.model_id,
            version=created_mv.version,
            to_status=ModelLifecycleStatus.PAPER,
            transition_command="deploy_to_paper_track",
        )
    except Exception:
        pytest.fail("request_transition MUST NOT raise when typed subscriber fails")

    read_mv, read_sha = reg.get(created_mv.model_id, created_mv.version)
    assert read_mv.status == ModelLifecycleStatus.PAPER

    history = reg.transition_history(created_mv.model_id, created_mv.version)
    assert len(history) == 1
    assert history[0].transition_id == tx.transition_id
    assert history[0].from_status == ModelLifecycleStatus.TESTED
    assert history[0].to_status == ModelLifecycleStatus.PAPER
