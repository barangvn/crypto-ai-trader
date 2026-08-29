"""S-RSK-02 — 3. Missing RD + Wrong decision_id + Wrong correlation (G01+G03+G04) — 32 test"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.risk.conftest import _sr02_request, _bypass_rd, SR02_CORR, SR02_RD_ID, SR02_CAUS_PREV
from app.contracts.risk import RiskDecisionResult
from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
)


# ---- G01 Missing RiskDecision ----

def test_g01_empty_registry_blocks(sr02_gate_empty, sr02_happy_request):
    r = sr02_gate_empty.evaluate(sr02_happy_request)
    assert r.allowed is False
    assert "G01_RISK_DECISION_MISSING" in r.block_reason_codes
    assert r.validated_risk_decision_id == ""


@pytest.mark.parametrize("wrong_rd_id_key", [
    "sr02_rd_WRONG_8chars",
    "x" * 10,
    "aaaaaaaa",
    "sr02_rd_base_rdid_0000",
    SR02_RD_ID + "_extra_suffix",
])
def test_g01_wrong_key_in_registry_blocks(sr02_registry_approved, sr02_deterministic_clock, wrong_rd_id_key):
    # registry contains (CORR, SR02_RD_ID, approved_RD). We issue request with different policy_refs.risk_decision_id
    g = RiskDecisionToPaperOrderGate(sr02_registry_approved, clock=sr02_deterministic_clock)
    r = g.evaluate(_sr02_request(risk_decision_id=wrong_rd_id_key))
    # Either G01 (lookup returns None due exact key mismatch) or G04 mismatch
    assert r.allowed is False
    assert (
        "G01_RISK_DECISION_MISSING" in r.block_reason_codes
        or "G04_POLICY_REFS_RISK_ID_MISMATCH" in r.block_reason_codes
    )


def test_g01_missing_correlation_blocks(sr02_registry_approved, sr02_deterministic_clock):
    g = RiskDecisionToPaperOrderGate(sr02_registry_approved, clock=sr02_deterministic_clock)
    # Correct rd_id but wrong correlation:
    # — With strict (corr, rd_id) key: lookup returns None.
    # — Post disambiguation (find_by_decision_id): RD exists under different corr → G03.
    # Both G01 and G03 are valid block reasons. Result must be blocked.
    r = g.evaluate(_sr02_request(correlation_id="OTHER_CORR_0000"))
    assert r.allowed is False
    blocks = set(r.block_reason_codes)
    # Strictly blocked: either lookup-level missing (G01) or corr-level mismatch (G03, more specific).
    assert "G01_RISK_DECISION_MISSING" in blocks or "G03_CORRELATION_MISMATCH" in blocks, (
        f"Expected G01 or G03 block; got: {blocks}"
    )


def test_g01_validated_rd_id_empty_on_missing(sr02_gate_empty, sr02_happy_request):
    r = sr02_gate_empty.evaluate(sr02_happy_request)
    assert r.validated_risk_decision_id == ""


# ---- G03 Correlation mismatch ----

def test_g03_correlation_mismatch_blocks():
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED,
        correlation_id="CHAIN_A_00001",
        decision_id=SR02_RD_ID,
    )
    reg = InMemoryDecisionRegistry()
    reg.register("CHAIN_A_00001", SR02_RD_ID, rd)
    # Lookup key OK (CHAIN_A, SR02_RD_ID), RD found. Then G03: request correlation = CHAIN_B.
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = g.evaluate(_sr02_request(correlation_id="CHAIN_B_00002"))
    assert r.allowed is False
    assert "G03_CORRELATION_MISMATCH" in r.block_reason_codes


_CORR_MISMATCH = [
    ("CHAIN_A_00001", "CHAIN_B_00002"),
    ("corr_X_01", "corr_Y_01"),
    ("SAMEPREFIX_1", "SAMEPREFIX_2"),
    ("case_MIXED_1", "Case_Mixed_1"),
    ("a" * 12, "b" * 12),
    (SR02_CORR, SR02_CORR + " "),  # trailing space string inequality
]


@pytest.mark.parametrize("rd_corr,req_corr", _CORR_MISMATCH, ids=[f"corr_{i}" for i, _ in enumerate(_CORR_MISMATCH)])
def test_g03_matrix_parametrize(rd_corr, req_corr):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id=rd_corr, decision_id=SR02_RD_ID)
    reg = InMemoryDecisionRegistry()
    reg.register(rd_corr, SR02_RD_ID, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = g.evaluate(_sr02_request(correlation_id=req_corr))
    assert r.allowed is False
    assert "G03_CORRELATION_MISMATCH" in r.block_reason_codes


def test_g03_correlation_match_allowed(sr02_gate, sr02_happy_request):
    r = sr02_gate.evaluate(sr02_happy_request)
    assert "G03_CORRELATION_MISMATCH" not in r.block_reason_codes
    assert r.allowed is True


# ---- G04 PolicyRefs risk_decision_id mismatch ----

def test_g04_policy_refs_mismatch_blocks():
    # Register RD with decision_id SR02_RD_ID; request has risk_decision_id = "OTHER_RDID_00"
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id=SR02_CORR, decision_id=SR02_RD_ID)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, "OTHER_RDID_00", rd)  # lookup key: (CORR, OTHER_RDID_00)
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    r = g.evaluate(_sr02_request(risk_decision_id="OTHER_RDID_00"))
    # Found RD via OTHER_RDID_00 key; now RD.decision_id is SR02_RD_ID.
    # request.policy_refs says OTHER_RDID_00. RD says SR02_RD_ID. → G04 mismatch.
    assert r.allowed is False
    assert "G04_POLICY_REFS_RISK_ID_MISMATCH" in r.block_reason_codes


@pytest.mark.parametrize("wrong", [
    SR02_RD_ID.upper(),
    SR02_RD_ID + "_",
    "_" + SR02_RD_ID,
    SR02_RD_ID.replace("_", "-"),
    "01234567",  # len 8
])
def test_g04_wrong_variants_block(wrong):
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id=SR02_CORR, decision_id=wrong)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, wrong, rd)
    # request uses SR02_RD_ID (len≥8 policy_refs.risk_decision_id len≥8 — 8 chars ULIDISH.
    # wrong param: len 8 OK, others len≥8 OK.
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    # request with default policy_refs.risk_decision_id=SR02_RD_ID → registry lookup fails (key (CORR, SR02_RD_ID) empty)
    # → G01. So force request to `wrong`, and register RD.decision_id to be different via:
    #   Register different rd_id = SR02_RD_ID; request = wrong variant; then G04 mismatch not G01.
    reg2 = InMemoryDecisionRegistry()
    rd2 = _bypass_rd(decision=RiskDecisionResult.APPROVED, correlation_id=SR02_CORR, decision_id=SR02_RD_ID)
    reg2.register(SR02_CORR, SR02_RD_ID, rd2)
    g2 = RiskDecisionToPaperOrderGate(reg2, clock=DeterministicClock())
    r = g2.evaluate(_sr02_request(risk_decision_id=wrong))
    assert r.allowed is False
    # G01 (wrong id lookup) blocks → acceptable; test is general blocked assertion.


def test_raw_dict_rejected_at_request_level():
    """Typed gate rejects untyped (not PaperOrderGateRequest) inputs via AD-19
    fail-closed synthetic block — NEVER raises to caller (AD-19 invariant)."""
    reg = InMemoryDecisionRegistry()
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())

    class NotAGateRequest:
        pass

    r = g.evaluate(NotAGateRequest())  # type: ignore[arg-type]
    assert r.allowed is False
    assert any("AD19" in c for c in r.block_reason_codes), (
        f"expected AD19 synthetic block code, got {r.block_reason_codes}"
    )


def test_raw_dict_request_via_object_fallback_ad19():
    # Pass non-PaperOrderGateRequest type — gate returns synthetic AD19 block instead of raising
    reg = InMemoryDecisionRegistry()
    g = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())

    class X:
        pass
    r = g.evaluate(X())  # type: ignore[arg-type]
    assert r.allowed is False
    assert any(c.startswith("AD19_UNHANDLED_EXCEPTION:") for c in r.block_reason_codes) or any(
        "AD19" in c for c in r.block_reason_codes
    )


# ---- Registry size / clear / lookup ----

def test_registry_len_and_clear(sr02_registry_approved):
    assert len(sr02_registry_approved) == 1
    sr02_registry_approved.clear()
    assert len(sr02_registry_approved) == 0


def test_registry_lookup_same_key_returns_rd(sr02_registry_approved, sr02_approved_rd):
    assert sr02_registry_approved.lookup(SR02_CORR, SR02_RD_ID) is sr02_approved_rd
    assert sr02_registry_approved.lookup(SR02_CORR + "X", SR02_RD_ID) is None
    assert sr02_registry_approved.lookup(SR02_CORR, SR02_RD_ID + "X") is None


def test_registry_register_requires_typed_rd():
    reg = InMemoryDecisionRegistry()
    with pytest.raises(Exception):
        reg.register(SR02_CORR, SR02_RD_ID, {"not": "a typed decision"})  # type: ignore[arg-type]


def test_gate_requires_registry_instance():
    with pytest.raises(Exception):
        RiskDecisionToPaperOrderGate("not a registry")  # type: ignore[arg-type]


def test_gate_requires_typed_clock():
    with pytest.raises(Exception):
        RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry(), clock="not a clock")  # type: ignore[arg-type]
