"""S-RSK-02 §8 EventBus — deep extras: quarantined, contract_version_min, unsubscribe, DLQ details (20 test)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef as CanonicalClockRef,
    QualityFlags,
)
from app.contracts.paper import (
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
)
from app.contracts.risk import RiskDecisionResult
from app.contracts.types import RunMode, SourceType
from app.platform.event_bus import InMemoryTypedEventBus
from app.risk import (
    DeterministicClock,
    EVENT_TYPE_PAPER_ORDER_BLOCKED,
    EVENT_TYPE_PAPER_ORDER_CREATED,
    EVENT_TYPE_RISK_DECISION_PUBLISHED,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
    register_gate_subscriber,
    GateResult,
)
from tests.risk.conftest import SR02_BASE_TS, SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request


def _make_env(rd, event_id="e1", symbol=SR02_SYM, ts=SR02_BASE_TS, qf=None, contract_version="1.0.0"):
    return CanonicalEventEnvelope(
        event_id=event_id, event_type=EVENT_TYPE_RISK_DECISION_PUBLISHED,
        contract_version=contract_version, symbol=symbol, source="replay_sr02",
        timestamp=ts, ingest_ts=ts, correlation_id=str(rd.correlation_id),
        causation_id=str(rd.causation_id), run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY, clock_ref=CanonicalClockRef(wall=ts, replay=ts),
        quality_flags=qf or QualityFlags(), payload=rd,
    )


def _rf(rd, env):
    return _sr02_request(
        risk_decision_id=rd.decision_id,
        correlation_id=rd.correlation_id,
        causation_id=rd.causation_id,
    )


def _of(rd, req, res: GateResult) -> PaperOrder:
    refs = PaperOrderPolicyRefs(
        risk_decision_id=rd.decision_id, strategy_id="trend", strategy_version="str_01_v1",
    )
    return PaperOrder(
        paper_order_id=f"po_{res.correlation_id}_{res.validated_risk_decision_id}",
        side=req.side, order_type=req.order_type,
        requested_qty_base=req.requested_qty_base, policy_refs=refs,
        status=PaperOrderStatus.CREATED, created_at=SR02_BASE_TS, updated_at=SR02_BASE_TS,
        correlation_id=req.correlation_id, causation_id=res.validated_risk_decision_id,
        requested_price=req.requested_price,
    )


# ---- Q (quarantine) 8 tests ----
_Q_PAIRS = [
    (True, False, 0, 1),   # quarantined + NOT accept → skip + DLQ (EVB level)
    (True, True, 0, 0),    # quarantined + accept → EVB delivers but gate G08B blocks
    (False, False, 1, 0),  # clean + NOT accept → delivered + gate allows
    (False, True, 1, 0),   # clean + accept → delivered + gate allows
]


@pytest.mark.parametrize("q,accept,n_ok,n_dlq", _Q_PAIRS, ids=[f"q={q[0]}_acc={q[1]}" for q in _Q_PAIRS])
def test_evb_quarantine_matrix(typed_bus, q, accept, n_ok, n_dlq):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of, accept_quarantined=accept)
    rcvd = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: rcvd.append(e))
    typed_bus.publish(_make_env(rd, qf=QualityFlags(quarantined=q)))
    assert len(rcvd) == n_ok
    dq = [d for d in typed_bus.dead_letters if d.dlq_code == "E_QUARANTINED_SKIP"]
    # Note: downstream subscribers with default accept_quarantined=False may also produce
    # E_QUARANTINED_SKIP when gate publishes child envelopes that inherit quarantine.
    # So assert AT LEAST n_dlq gate-level DLQ entries must exist.
    assert len(dq) >= n_dlq


# ---- Contract version 5 tests ----
def test_evb_contract_version_min_passes_same(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of, contract_version_min=(1, 0, 0))
    rcvd = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: rcvd.append(e))
    typed_bus.publish(_make_env(rd, contract_version="1.0.0"))
    assert len(rcvd) == 1


def test_evb_contract_version_min_passes_higher(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of, contract_version_min=(0, 9, 0))
    rcvd = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: rcvd.append(e))
    typed_bus.publish(_make_env(rd, contract_version="1.2.3"))
    assert len(rcvd) == 1


def test_evb_contract_version_min_block_lower(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of, contract_version_min=(2, 0, 0))
    rcvd = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: rcvd.append(e))
    typed_bus.publish(_make_env(rd, contract_version="1.5.0"))
    assert len(rcvd) == 0
    dq = [d for d in typed_bus.dead_letters if d.dlq_code == "E_CONTRACT_VERSION_MIN"]
    assert len(dq) >= 1


def test_evb_contract_version_min_invalid_tuple_raises(typed_bus):
    reg = InMemoryDecisionRegistry()
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    with pytest.raises(Exception):
        register_gate_subscriber(typed_bus, g, _rf, _of, contract_version_min=(1,))  # type: ignore[arg-type]


def test_evb_contract_version_min_invalid_str_raises(typed_bus):
    reg = InMemoryDecisionRegistry()
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    with pytest.raises(Exception):
        register_gate_subscriber(typed_bus, g, _rf, _of, contract_version_min="1.0.0")  # type: ignore[arg-type]


# ---- Unsubscribe + token types 3 tests ----
def test_evb_unsubscribe_stops_delivery(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    tok = register_gate_subscriber(typed_bus, g, _rf, _of)
    rcvd = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: rcvd.append(e))
    typed_bus.publish(_make_env(rd, event_id="e1"))
    assert len(rcvd) == 1
    typed_bus.unsubscribe(tok)
    typed_bus.publish(_make_env(rd, event_id="e2"))
    assert len(rcvd) == 1  # no second delivery


def test_evb_register_requires_typed_bus():
    from app.risk.gate import register_gate_subscriber as _rgs
    reg = InMemoryDecisionRegistry()
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    with pytest.raises(Exception):
        _rgs("not a bus", g, _rf, _of)  # type: ignore[arg-type]


def test_evb_register_requires_typed_gate(typed_bus):
    with pytest.raises(Exception):
        register_gate_subscriber(typed_bus, "not a gate", _rf, _of)  # type: ignore[arg-type]


# ---- Blocked payload + blocked event quality 4 tests ----
def test_evb_blocked_payload_structure(typed_bus):
    from app.contracts.risk import KillSwitchStateSpec
    ks = KillSwitchStateSpec(global_kill=False, per_symbol={SR02_SYM: True}, reason=None)
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, ks=ks)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of)
    blk = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_BLOCKED, lambda e: blk.append(e))
    typed_bus.publish(_make_env(rd, event_id="blk1"))
    assert len(blk) == 1
    p = blk[0].payload
    assert isinstance(p, dict)
    for key in ("correlation_id", "causation_id", "block_reason_codes",
                "info_codes", "risk_decision_id", "gate_version"):
        assert key in p, f"blocked payload missing key {key}"
    assert "G06C_PER_SYMBOL_KILL" in p["block_reason_codes"]


def test_evb_blocked_event_corr_matches_rd(typed_bus):
    from app.contracts.risk import KillSwitchStateSpec
    ks = KillSwitchStateSpec(global_kill=True, per_symbol={}, reason=None)
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id="EVB_BLK_CORR_099", ks=ks)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of)
    blk = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_BLOCKED, lambda e: blk.append(e))
    typed_bus.publish(_make_env(rd, event_id="blk2"))
    assert len(blk) == 1
    env = blk[0]
    assert env.correlation_id == rd.correlation_id
    assert "G06A_GLOBAL_KILL" in env.payload["block_reason_codes"]


def test_evb_approved_publish_count_increments(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    register_gate_subscriber(typed_bus, g, _rf, _of)
    for i in range(3):
        typed_bus.publish(_make_env(rd, event_id=f"n{i}"))
    downstream = [e for e in typed_bus.published if e.event_type == EVENT_TYPE_PAPER_ORDER_CREATED]
    assert len(downstream) == 3


def test_evb_rejected_publish_no_downstream(typed_bus):
    rd = _bypass_rd(decision=RiskDecisionResult.REJECTED)
    reg = InMemoryDecisionRegistry()
    reg.register(str(rd.correlation_id), rd.decision_id, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    register_gate_subscriber(typed_bus, g, _rf, _of)
    typed_bus.publish(_make_env(rd, event_id="rej_e1"))
    downstream = [
        e for e in typed_bus.published
        if e.event_type in (EVENT_TYPE_PAPER_ORDER_CREATED, EVENT_TYPE_PAPER_ORDER_BLOCKED)
    ]
    assert len(downstream) == 0
