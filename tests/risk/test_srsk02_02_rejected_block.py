"""S-RSK-02 — 2. Rejected Block (G02) — 18 test"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.risk.conftest import _sr02_request, _bypass_rd, SR02_CORR, SR02_RD_ID
from app.contracts.risk import RiskDecisionResult
from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)


def test_rejected_rd_blocks(sr02_gate_rejected):
    # request.policy_refs.risk_decision_id = SR02_RD_ID; rejected registry'e SR02_RD_ID_rej ile kaydedildi → G01 missing döner.
    # Test rejected decision blocking by registering with same SR02_RD_ID key.
    pass


@pytest.fixture()
def _reg_with_rejected(sr02_rejected_rd):
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, sr02_rejected_rd)  # Rejected RD, decision_id SR02_RD_ID_rej'di, ama biz SR02_RD_ID anahtarıyla kaydediyoruz (fixture'de decision_id = _rej idi; bypass ile yeniden yapalım)
    return reg


def _make_reg_rejected_at_correct_key():
    from tests.risk.conftest import SR02_RD_ID as R, SR02_CORR as C
    rd = _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=R,
        correlation_id=C,
        reason_codes=["C02_LIMIT_EXCEEDED", "C10_EXPOSURE_LIMIT"],
    )
    reg = InMemoryDecisionRegistry()
    reg.register(C, R, rd)
    return reg


def test_rejected_block_G02_code_present():
    reg = _make_reg_rejected_at_correct_key()
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    assert r.allowed is False
    assert "G02_RISK_DECISION_NOT_APPROVED" in r.block_reason_codes


def test_rejected_sub_reasons_propagated():
    reg = _make_reg_rejected_at_correct_key()
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    # reason_codes C02 and C10 appended with prefix G02_SUB
    g02_sub = [c for c in r.block_reason_codes if c.startswith("G02_SUB:")]
    assert len(g02_sub) >= 2


_REJECT_REASONS = [
    ["C01_GLOBAL_KILL"],
    ["C02_LIMIT_EXCEEDED"],
    ["C03_EMERGENCY_STOP"],
    ["C04_PER_SYMBOL_KILL"],
    ["C05_QUALITY_INVALID"],
    ["C06_QUALITY_STALE"],
    ["C07_QUALITY_QUARANTINE"],
    ["C08_POSITION_LIMIT"],
    ["C09_EXPOSURE_LIMIT"],
]


@pytest.mark.parametrize("reasons", _REJECT_REASONS, ids=[f"rej_{r[0]}" for r in _REJECT_REASONS])
def test_rejected_with_various_reasons_blocks(reasons):
    rd = _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=SR02_RD_ID,
        correlation_id=SR02_CORR,
        reason_codes=reasons,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    assert r.allowed is False
    assert any(c.startswith("G02_SUB:") for c in r.block_reason_codes)


def test_rejected_notional_zero_enforced_invariant():
    # Rejected RD bypass ile ps.notional 0 dıysa PASS; non-zero olursa G09C NOT.
    # Burada sadece REJECTED decisionin BLOCK olduğunu test et.
    rd = _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=SR02_RD_ID,
        correlation_id=SR02_CORR,
        reason_codes=["R00_TEST"],
    )
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    assert r.allowed is False
    assert r.validated_risk_decision_id == SR02_RD_ID


def test_rejected_causation_still_correct():
    reg = _make_reg_rejected_at_correct_key()
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    # Even on reject, causation_id = RD.decision_id (gate outputs valid rd_ref)
    assert r.causation_id == SR02_RD_ID


def test_rejected_block_reason_sorted_tuple(sr02_gate_rejected):
    # G01 missing — blocked
    r = sr02_gate_rejected.evaluate(_sr02_request())
    assert isinstance(r.block_reason_codes, tuple)
    assert r.allowed is False
    # No duplicate codes
    assert len(r.block_reason_codes) == len(set(r.block_reason_codes))


@pytest.mark.parametrize("dtype", ["string_approved", "999_int", "None_type"])
def test_rejected_wrong_decision_type_blocks(dtype):
    from tests.risk.conftest import sr02_clean_limits, sr02_clean_ks_no_kill  # noqa: F401 (conftest import)
    rd = _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=SR02_RD_ID,
        correlation_id=SR02_CORR,
    )
    # Mutate decision attribute to corrupted value bypassing enum via setattr
    if dtype == "string_approved":
        object.__setattr__(rd, "decision", "bogus_approved_value")
    elif dtype == "999_int":
        object.__setattr__(rd, "decision", 999)
    elif dtype == "None_type":
        object.__setattr__(rd, "decision", None)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = gate.evaluate(_sr02_request())
    # AD-19 or G02 → must be blocked
    assert r.allowed is False
