"""S-RSK-02 §14 Correlation/Causation — chain extras: strat→opp→rd→po, multi-RD chains (15 test)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef as CanonicalClockRef,
    QualityFlags,
)
from app.contracts.paper import PaperOrder, PaperOrderPolicyRefs, PaperOrderStatus
from app.contracts.risk import RiskDecisionResult
from app.contracts.types import RunMode, SourceType
from app.platform.event_bus import InMemoryTypedEventBus
from app.risk import (
    DeterministicClock,
    EVENT_TYPE_PAPER_ORDER_CREATED,
    EVENT_TYPE_RISK_DECISION_PUBLISHED,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
    register_gate_subscriber,
    GateResult,
)
from tests.risk.conftest import SR02_BASE_TS, SR02_SYM, _bypass_rd, _sr02_request


TS = SR02_BASE_TS


def _env(rd, event_id, qf=None):
    return CanonicalEventEnvelope(
        event_id=event_id, event_type=EVENT_TYPE_RISK_DECISION_PUBLISHED,
        contract_version="1.0.0", symbol=SR02_SYM, source="replay_sr02",
        timestamp=TS, ingest_ts=TS, correlation_id=str(rd.correlation_id),
        causation_id=str(rd.causation_id), run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY, clock_ref=CanonicalClockRef(wall=TS, replay=TS),
        quality_flags=qf or QualityFlags(), payload=rd,
    )


def _of(rd, req, res: GateResult) -> PaperOrder:
    refs = PaperOrderPolicyRefs(
        risk_decision_id=rd.decision_id, strategy_id="trend", strategy_version="str_01_v1",
    )
    return PaperOrder(
        paper_order_id=f"po_chain_{res.correlation_id}_{res.validated_risk_decision_id}",
        side=req.side, order_type=req.order_type,
        requested_qty_base=req.requested_qty_base, policy_refs=refs,
        status=PaperOrderStatus.CREATED, created_at=TS, updated_at=TS,
        correlation_id=req.correlation_id, causation_id=res.validated_risk_decision_id,
        requested_price=req.requested_price,
    )


# ---- §14 corr/caus preservation direct gate ----
_CORR_VALUES = [
    "C" * 10,
    "CHAIN_correlation_XYZ_00000001",
    "a" * 25,
    "Z" * 8,
]


@pytest.mark.parametrize("corr", _CORR_VALUES, ids=[f"corr_len_{len(c)}" for c in _CORR_VALUES])
def test_corr_preserved_exact_str(corr):
    """Correlation ID must match EXACTLY (byte-for-byte) through gate."""
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id=corr)
    reg = InMemoryDecisionRegistry()
    reg.register(corr, rd.decision_id, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    req = _sr02_request(correlation_id=corr)
    res = gate.evaluate(req)
    assert res.allowed is True
    assert res.correlation_id == corr, "correlation_id must be preserved byte-for-byte"


_CAUS_VALUES = [
    ("PREV_caus_00001", "DEC_00000001"),
    ("PARENT_opp_id_0999991", "RD_id_exact_value_2"),
    ("A" * 12, "B" * 15),
]


@pytest.mark.parametrize("prev,rd_id", _CAUS_VALUES, ids=[f"caus_{i}" for i in range(len(_CAUS_VALUES))])
def test_caus_chain_rd_id_becomes_result_caus(prev, rd_id):
    """GateResult.causation_id MUST equal rd.decision_id (NOT request.causation_id) — AD-17 4/8."""
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, causation_id=prev, decision_id=rd_id)
    reg = InMemoryDecisionRegistry()
    reg.register(rd.correlation_id, rd_id, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    req = _sr02_request(correlation_id=rd.correlation_id, risk_decision_id=rd_id, causation_id=prev)
    res = gate.evaluate(req)
    assert res.allowed is True
    assert res.causation_id == rd_id, (
        f"causation_id must become RD.decision_id={rd_id} for downstream; got {res.causation_id}"
    )
    assert res.validated_risk_decision_id == rd_id


# ---- 4-node chain through event bus ----
def test_corr_caus_4node_bus_chain(typed_bus: InMemoryTypedEventBus):
    STRAT_ID = "STRATEGY_SIG_00001_STRAT_SIG"
    OPP_ID = "OPPORT_SCORE_OPP_00002"
    RD_ID = "RISK_DECI_RDID_000003"
    CORR = "CHAIN_LONG_CORRELATION_ID_2026"
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED, correlation_id=CORR,
        causation_id=OPP_ID, decision_id=RD_ID,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(CORR, RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))

    def _rf_local(rd, env):
        return _sr02_request(correlation_id=CORR, risk_decision_id=RD_ID, causation_id=OPP_ID)

    captured = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: captured.append(e))
    register_gate_subscriber(typed_bus, gate, _rf_local, _of)
    env_rd = _env(rd, event_id=RD_ID)
    typed_bus.publish_with_causation(env_rd, parent_event_id=OPP_ID)
    assert len(captured) == 1, "PAPER_ORDER_CREATED subscriber did not fire (expected 1, got 0)"
    po_env = captured[0]
    po: PaperOrder = po_env.payload
    assert po.correlation_id == CORR
    assert po.causation_id == RD_ID
    assert po.policy_refs.risk_decision_id == RD_ID
    chain = typed_bus.trace_causation_chain(po_env.event_id)
    # chain = [PO event_id, RD_ID, OPP_ID, ...] — at minimum PO and RD present
    assert RD_ID in chain, f"RD_ID missing in chain: {chain}"


# ---- Multi distinct chains with no cross-contamination ----
_CHAINS = [
    ("CHAIN_A_00001", "RDID_A_00001", "CAUS_PREV_A_00001"),
    ("CHAIN_B_00002", "RDID_B_00002", "CAUS_PREV_B_00002"),
    ("CHAIN_C_00003", "RDID_C_00003", "CAUS_PREV_C_00003"),
]


def test_multi_chain_corr_isolation_direct_gate():
    results = {}
    for corr, rd_id, caus_prev in _CHAINS:
        rd = _bypass_rd(
            decision=RiskDecisionResult.APPROVED, correlation_id=corr,
            decision_id=rd_id, causation_id=caus_prev,
        )
        reg = InMemoryDecisionRegistry()
        reg.register(corr, rd_id, rd)
        gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
        req = _sr02_request(correlation_id=corr, risk_decision_id=rd_id)
        res = gate.evaluate(req)
        results[(corr, rd_id)] = res
    # Each corr matches its own rd_id result; no cross-contamination
    for (corr, rd_id), res in results.items():
        assert res.correlation_id == corr
        assert res.causation_id == rd_id
        assert res.validated_risk_decision_id == rd_id
        assert res.allowed is True


def test_wrong_causation_in_request_blocked_g03_meaningful():
    """Request correlation differs; G03 (or meaningful corr mismatch) always blocks."""
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED, correlation_id="CHAIN_OK_001",
        decision_id="RDID_OK_001",
    )
    reg = InMemoryDecisionRegistry()
    reg.register("CHAIN_OK_001", "RDID_OK_001", rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    req = _sr02_request(correlation_id="CHAIN_OTHER_888", risk_decision_id="RDID_OK_001")
    res = gate.evaluate(req)
    assert res.allowed is False
    blocks = set(res.block_reason_codes)
    assert ("G01_RISK_DECISION_MISSING" in blocks) or ("G03_CORRELATION_MISMATCH" in blocks)


def test_po_created_event_corr_caus_matches_payload_po(typed_bus):
    """Envelope correlation/causation MUST EQUAL nested PaperOrder corr/caus."""
    CORR = "MATCHING_CORRELATION_0000007"
    RD_ID = "MATCHING_RDID_0000000007"
    OPP_ID = "PREV_OPP_PARENT_0000007"
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED, correlation_id=CORR,
        causation_id=OPP_ID, decision_id=RD_ID,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(CORR, RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))

    def _rf_loc(rd, env):
        return _sr02_request(correlation_id=CORR, risk_decision_id=RD_ID, causation_id=OPP_ID)

    cap = []
    typed_bus.subscribe_typed(EVENT_TYPE_PAPER_ORDER_CREATED, lambda e: cap.append(e))
    register_gate_subscriber(typed_bus, gate, _rf_loc, _of)
    typed_bus.publish(_env(rd, event_id=RD_ID))
    assert len(cap) == 1
    env = cap[0]
    po: PaperOrder = env.payload
    assert env.correlation_id == po.correlation_id
    assert env.causation_id == po.causation_id
    assert env.correlation_id == CORR
    assert env.causation_id == RD_ID


# ---- Validated rd id consistency ----
def test_validated_rd_id_populated_even_on_block():
    rd = _bypass_rd(decision=RiskDecisionResult.REJECTED)
    reg = InMemoryDecisionRegistry()
    reg.register(rd.correlation_id, rd.decision_id, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    res = gate.evaluate(_sr02_request())
    assert res.allowed is False
    assert res.validated_risk_decision_id == rd.decision_id
    assert len(res.validated_risk_decision_id) >= 8


def test_validated_rd_id_empty_on_g01_missing():
    gate = RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry(), clock=DeterministicClock())
    res = gate.evaluate(_sr02_request())
    assert res.allowed is False
    assert res.validated_risk_decision_id == ""
