from __future__ import annotations

from app.contracts import ModelLifecycleStatus, ModelLifecycleTransition, ULID
from app.registry import build_status_transition_event
from tests.registry.conftest import sample_mv


def _make_tx(mv, from_status, to_status, command="test_command"):
    return ModelLifecycleTransition(
        transition_id="LT_TEST_001",
        model_id=mv.model_id,
        model_version=mv.version,
        from_status=from_status,
        to_status=to_status,
        reason=command,
        evidence_refs=["e1"],
        requested_by="tester",
        approved_by="gov",
        requested_ts="2026-09-09T12:00:00.000Z",
        correlation_id=ULID(mv.correlation_id),
        causation_id=ULID("01920000-0000-7000-8000-000000000099"),
        metadata={},
    )


def test_smdl01_08_build_event_event_type():
    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    tx = _make_tx(mv, ModelLifecycleStatus.CANDIDATE, ModelLifecycleStatus.TESTED)
    envelope = build_status_transition_event(
        envelope_event_id="01920000-0000-7000-8000-000000000100",
        mv=mv,
        tx=tx,
        previous_mv_sha="a" * 64,
        new_mv_sha="b" * 64,
    )
    assert envelope.event_type == "model_version_status_transitioned.v1"


def test_smdl01_08_payload_keys_sorted_alphabetical():
    mv = sample_mv(status=ModelLifecycleStatus.TESTED)
    tx = _make_tx(mv, ModelLifecycleStatus.TESTED, ModelLifecycleStatus.PAPER)
    envelope = build_status_transition_event(
        envelope_event_id="01920000-0000-7000-8000-000000000101",
        mv=mv,
        tx=tx,
        previous_mv_sha="a" * 64,
        new_mv_sha="b" * 64,
    )
    payload = envelope.payload
    assert payload == dict(sorted(payload.items()))


def test_smdl01_08_correlation_matches_mv_correlation_id():
    mv = sample_mv(status=ModelLifecycleStatus.PAPER)
    tx = _make_tx(mv, ModelLifecycleStatus.PAPER, ModelLifecycleStatus.CHALLENGER)
    envelope = build_status_transition_event(
        envelope_event_id="01920000-0000-7000-8000-000000000102",
        mv=mv,
        tx=tx,
        previous_mv_sha="a" * 64,
        new_mv_sha="b" * 64,
    )
    assert str(envelope.correlation_id) == str(mv.correlation_id)


def test_smdl01_08_causation_matches_tx_transition_id():
    mv = sample_mv(status=ModelLifecycleStatus.CHALLENGER, metadata={"approval_refs": ["ap-1"]})
    tx = _make_tx(mv, ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.CHAMPION)
    envelope = build_status_transition_event(
        envelope_event_id="01920000-0000-7000-8000-000000000103",
        mv=mv,
        tx=tx,
        previous_mv_sha="a" * 64,
        new_mv_sha="b" * 64,
    )
    assert str(envelope.causation_id) == str(tx.transition_id)


def test_smdl01_08_bus_publish_event_type_matches(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    _new_mv, _new_sha, _tx, envelope = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )

    assert envelope is not None
    assert len(bus.published) >= 1
    assert bus.published[-1].event_type == "model_version_status_transitioned.v1"
    assert str(envelope.event_id) == str(bus.published[-1].event_id)
