"""S-RSK-02 §8 EventBus — S-PLN-01 typed bus + gate subscriber + DLQ isolation."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef as CanonicalClockRef,
    QualityFlags,
)
from app.contracts.paper import PaperOrder, PaperOrderPolicyRefs, PaperOrderSide, PaperOrderStatus, PaperOrderType
from app.contracts.risk import RiskDecisionResult
from app.contracts.types import RunMode, SourceType
from app.platform.event_bus import InMemoryTypedEventBus
from app.risk import (
    DeterministicClock,
    EVENT_TYPE_PAPER_ORDER_BLOCKED,
    EVENT_TYPE_PAPER_ORDER_CREATED,
    EVENT_TYPE_RISK_DECISION_PUBLISHED,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    GateResult,
    RiskDecisionToPaperOrderGate,
    register_gate_subscriber,
)
from tests.risk.conftest import SR02_BASE_TS, SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request

ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"


def _make_env(rd, event_id="env_001", symbol=SR02_SYM, ts=SR02_BASE_TS):
    return CanonicalEventEnvelope(
        event_id=event_id,
        event_type=EVENT_TYPE_RISK_DECISION_PUBLISHED,
        contract_version="1.0.0",
        symbol=symbol,
        source="replay_sr02",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=str(rd.correlation_id),
        causation_id=str(rd.causation_id),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=CanonicalClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        payload=rd,
    )


def _rf(rd, env) -> PaperOrderGateRequest:
    return _sr02_request(
        risk_decision_id=rd.decision_id,
        correlation_id=rd.correlation_id,
        causation_id=rd.causation_id,
    )


def _of(rd, req, res: GateResult) -> PaperOrder:
    refs = PaperOrderPolicyRefs(
        risk_decision_id=rd.decision_id,
        strategy_id="trend",
        strategy_version="str_01_v1",
    )
    ts_now = "2026-03-18T12:04:29.999Z"
    return PaperOrder(
        paper_order_id=f"po_{res.correlation_id}_{res.validated_risk_decision_id}",
        side=req.side,
        order_type=req.order_type,
        requested_qty_base=req.requested_qty_base,
        policy_refs=refs,
        status=PaperOrderStatus.CREATED,
        created_at=ts_now,
        updated_at=ts_now,
        correlation_id=req.correlation_id,
        causation_id=res.validated_risk_decision_id,
        requested_price=req.requested_price,
    )


def test_evb_approved_publish_creates_po_created_event(typed_bus):
    """Approved RD publish → PAPER_ORDER_CREATED event with correct corr/caus."""
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    register_gate_subscriber(typed_bus, gate, _rf, _of)

    received_created = []
    received_blocked = []

    def _on_created(env):
        received_created.append(env)

    def _on_blocked(env):
        received_blocked.append(env)

    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, _on_created)
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_BLOCKED, _on_blocked)

    typed_bus.publish(_make_env(rd))

    assert len(received_created) == 1
    assert len(received_blocked) == 0
    po_env = received_created[0]
    po: PaperOrder = po_env.payload
    assert isinstance(po, PaperOrder)
    assert po.correlation_id == rd.correlation_id
    assert po.causation_id == rd.decision_id
    assert po.policy_refs.risk_decision_id == rd.decision_id


def test_evb_rejected_publish_no_events_emitted(typed_bus):
    """REJECTED RD publish → subscriber short circuits; 0 downstream events."""
    rd = _bypass_rd(decision=RiskDecisionResult.REJECTED, decision_id=SR02_RD_ID + "_rej")
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID + "_rej", rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    register_gate_subscriber(typed_bus, gate, _rf, _of)

    received_created = []
    received_blocked = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: received_created.append(e))
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_BLOCKED, lambda e: received_blocked.append(e))

    typed_bus.publish(_make_env(rd, event_id="env_rej_001"))
    assert len(received_created) == 0
    assert len(received_blocked) == 0


def test_evb_gate_block_result_emits_blocked_event(typed_bus):
    """Approved RD registered but gate blocks (e.g. symbol kill) → PAPER_ORDER_BLOCKED."""
    from app.contracts.risk import KillSwitchStateSpec
    ks = KillSwitchStateSpec(global_kill=False, per_symbol={SR02_SYM: True}, reason=None)
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, ks=ks)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    register_gate_subscriber(typed_bus, gate, _rf, _of)

    blocked = []
    created = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_BLOCKED, lambda e: blocked.append(e))
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: created.append(e))

    typed_bus.publish(_make_env(rd, "env_blocked_001"))
    assert len(created) == 0
    assert len(blocked) == 1
    bpayload = blocked[0].payload
    assert isinstance(bpayload, dict)
    assert "G06C_PER_SYMBOL_KILL" in bpayload["block_reason_codes"]


def test_evb_one_subscriber_raises_goes_to_dlq_other_succeeds(typed_bus):
    """§8 — 2 subscribers: 1 raises → DLQ + 1 normal callback still works (AD19 isolation)."""
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    register_gate_subscriber(typed_bus, gate, _rf, _of)

    ok_calls = []

    def raising_subscriber(env):
        raise RuntimeError("boom")

    def ok_subscriber(env):
        ok_calls.append(env)

    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, raising_subscriber)
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, ok_subscriber)

    typed_bus.publish(_make_env(rd, "env_dlq_001"))
    assert len(ok_calls) == 1
    assert len(typed_bus.dead_letters) >= 1
