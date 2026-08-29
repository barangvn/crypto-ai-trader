"""S-RSK-02 §14 Correlation / Causation full chain (StrategySignal → OppScore → RD → PO)."""
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
    PaperOrderType,
)
from app.contracts.risk import RiskDecisionResult
from app.contracts.types import RunMode, SourceType
from app.platform.event_bus import InMemoryTypedEventBus
from app.risk import (
    DeterministicClock,
    EVENT_TYPE_PAPER_ORDER_CREATED,
    EVENT_TYPE_RISK_DECISION_PUBLISHED,
    GateResult,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
    register_gate_subscriber,
)
from tests.risk.conftest import SR02_BASE_TS, _bypass_rd, _sr02_request

ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"


def test_corr_48_chain_same_correlation_id_through_all():
    """Chain: (OppScore id) → RD.causation_id → PO.causation_id = RD.event_id. Single corr_id."""
    OPP_SCORE_ID = "oppscore_z_chain_000123"
    CHAIN_CORR = "full_chain_corr_abc_7788"
    RD_ID = "rd_chain_0099_rdid_0001"

    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED,
        decision_id=RD_ID,
        correlation_id=CHAIN_CORR,
        causation_id=OPP_SCORE_ID,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(CHAIN_CORR, RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)

    req = _sr02_request(
        correlation_id=CHAIN_CORR,
        risk_decision_id=RD_ID,
        causation_id=OPP_SCORE_ID,
    )
    res: GateResult = gate.evaluate(req)
    assert res.allowed is True
    assert res.causation_id == RD_ID
    assert res.correlation_id == CHAIN_CORR


def test_corr_cross_chain_correlation_mismatch_blocks():
    """3 chains A/B/C — cross lookup G03 correlation mismatch → BLOCK."""
    chain_ids = [
        ("CORR_A_chain_long_0001", "RD_A_rdid_chain_0001", "OPP_A_prev_chain_0001"),
        ("CORR_B_chain_long_0002", "RD_B_rdid_chain_0002", "OPP_B_prev_chain_0002"),
        ("CORR_C_chain_long_0003", "RD_C_rdid_chain_0003", "OPP_C_prev_chain_0003"),
    ]
    reg = InMemoryDecisionRegistry()
    for corr, rd_id, opp_id in chain_ids:
        rd = _bypass_rd(decision=RiskDecisionResult.APPROVED,
                         decision_id=rd_id, correlation_id=corr, causation_id=opp_id)
        reg.register(corr, rd_id, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)

    corr_a, rdid_a, _opp_a = chain_ids[0]
    corr_b, _rdid_b, _opp_b = chain_ids[1]

    req_ok = _sr02_request(correlation_id=corr_a, risk_decision_id=rdid_a)
    assert gate.evaluate(req_ok).allowed is True

    gate.clear_idempotency()
    req_bad = _sr02_request(correlation_id=corr_b, risk_decision_id=rdid_a)
    res = gate.evaluate(req_bad)
    assert res.allowed is False


def test_caus_chain_trace_through_eventbus_publish_with_causation(typed_bus):
    """Publish with publish_with_causation → bus.trace_causation_chain includes RD & OPP ids."""
    OPP_SCORE_ID = "opp_id_999999999999_long"
    CHAIN_CORR = "chain_corr_xyz_31415926"
    RD_ID = "rd_id_causchain_27182818"
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED,
        decision_id=RD_ID,
        correlation_id=CHAIN_CORR,
        causation_id=OPP_SCORE_ID,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(CHAIN_CORR, RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)

    def _rf_local(rd, env):
        return _sr02_request(correlation_id=rd.correlation_id,
                             risk_decision_id=rd.decision_id,
                             causation_id=rd.causation_id)

    def _of_local(rd, req, res):
        ts_now = "2026-03-18T12:04:29.999Z"
        return PaperOrder(
            paper_order_id=f"po_id_chain_{res.validated_risk_decision_id}_88",
            side=req.side,
            order_type=req.order_type,
            requested_qty_base=req.requested_qty_base,
            policy_refs=PaperOrderPolicyRefs(
                risk_decision_id=rd.decision_id,
                strategy_id="trend",
                strategy_version="str_01_v1",
            ),
            status=PaperOrderStatus.CREATED,
            created_at=ts_now,
            updated_at=ts_now,
            correlation_id=req.correlation_id,
            causation_id=res.validated_risk_decision_id,
            requested_price=req.requested_price,
        )

    register_gate_subscriber(typed_bus, gate, _rf_local, _of_local)

    captured = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: captured.append(e))

    ts = SR02_BASE_TS
    env_rd = CanonicalEventEnvelope(
        event_id=RD_ID,
        event_type=EVENT_TYPE_RISK_DECISION_PUBLISHED,
        contract_version="1.0.0",
        symbol="BTC_USDT",
        source="replay_sr02",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=CHAIN_CORR,
        causation_id=OPP_SCORE_ID,
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=CanonicalClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        payload=rd,
    )
    typed_bus.publish_with_causation(env_rd, parent_event_id=OPP_SCORE_ID)

    assert len(captured) >= 1, "PAPER_ORDER_CREATED subscriber fired zero times"
    po_env = captured[0]
    chain = typed_bus.trace_causation_chain(po_env.event_id)
    chain_ids: list[str] = list(chain)
    assert RD_ID in chain_ids, f"RD_ID {RD_ID} not in chain ids: {chain_ids}"
