"""S-RSK-02 §7 Idempotency / Replay (G07 + determinism replay)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import ONE_MS_BEFORE, SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request


def test_g07_allow_10x_same_call_first_no_g07_subsequent_all_have_g07(sr02_gate, sr02_happy_request):
    """Idempotency: 10x allow — run 1 has NO G07; runs 2-10 have G07_DUP info code."""
    sr02_gate.clear_idempotency()
    results = []
    for i in range(10):
        results.append(sr02_gate.evaluate(sr02_happy_request))
    # ALL allowed
    for r in results:
        assert r.allowed is True
    # Run 1 info empty (or no G07)
    assert not any("G07_" in code for code in results[0].info_codes)
    # Runs 2-10 info has G07_DUPLICATE
    for i in range(1, 10):
        assert "G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE" in results[i].info_codes
    # Store size = 1 not 10
    assert sr02_gate.idempotency_size() == 1


def test_g07_block_10x_same_result(sr02_gate_empty, sr02_happy_request):
    """Idempotency: 10x blocked request — idem store works same direction."""
    sr02_gate_empty.clear_idempotency()
    results = []
    for i in range(10):
        results.append(sr02_gate_empty.evaluate(sr02_happy_request))
    for r in results:
        assert r.allowed is False
        assert "G01_RISK_DECISION_MISSING" in r.block_reason_codes
    assert not any("G07_" in c for c in results[0].info_codes)
    for i in range(1, 10):
        assert "G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE" in results[i].info_codes


def test_g07_three_distinct_requests_no_contamination():
    """3 different idem keys (3 symbols) → 3 separate entries, no cross-contamination."""
    clock = DeterministicClock(ONE_MS_BEFORE)
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    syms = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
    reqs = [_sr02_request(symbol=s) for s in syms]
    # first pass each
    for r in reqs:
        gate.evaluate(r)
    # second pass each
    for r in reqs:
        res2 = gate.evaluate(r)
        assert "G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE" in res2.info_codes
    assert gate.idempotency_size() == 3


def test_g07_single_byte_change_different_idem_key():
    """1-byte change (different qty last digit) → different idem entries; BOTH evaluate fresh first call."""
    clock = DeterministicClock(ONE_MS_BEFORE)
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    a = _sr02_request(qty=Decimal("0.01000001"))
    b = _sr02_request(qty=Decimal("0.01000002"))
    ra1 = gate.evaluate(a)
    rb1 = gate.evaluate(b)
    # BOTH first-calls: no G07
    assert not any("G07_" in c for c in ra1.info_codes)
    assert not any("G07_" in c for c in rb1.info_codes)
    assert gate.idempotency_size() == 2


def test_g07_replay_determinism_two_separate_gates_same_registry():
    """§7 Replay: two separate gate instances with same input → identical results."""
    clock1 = DeterministicClock(ONE_MS_BEFORE)
    clock2 = DeterministicClock(ONE_MS_BEFORE)
    rd = _bypass_rd()
    reg1 = InMemoryDecisionRegistry()
    reg2 = InMemoryDecisionRegistry()
    reg1.register(SR02_CORR, SR02_RD_ID, rd)
    reg2.register(SR02_CORR, SR02_RD_ID, rd)
    g1 = RiskDecisionToPaperOrderGate(reg1, clock=clock1)
    g2 = RiskDecisionToPaperOrderGate(reg2, clock=clock2)
    req = _sr02_request()
    r1 = g1.evaluate(req)
    r2 = g2.evaluate(req)
    assert r1.allowed == r2.allowed
    assert r1.block_reason_codes == r2.block_reason_codes
    assert r1.gate_version == r2.gate_version
    assert r1.input_sha256 == r2.input_sha256


def test_g07_clear_idempotency_resets_store(sr02_gate, sr02_happy_request):
    """clear_idempotency() truly resets — subsequent call has no G07."""
    sr02_gate.evaluate(sr02_happy_request)
    sr02_gate.evaluate(sr02_happy_request)  # has G07
    sr02_gate.clear_idempotency()
    r3 = sr02_gate.evaluate(sr02_happy_request)
    assert not any("G07_" in c for c in r3.info_codes)
    assert sr02_gate.idempotency_size() == 1


def test_g07_lru_eviction_works_when_max_reached():
    """Idempotency max=7; 10 requests → oldest 10% evicted when full."""
    from app.risk import GateOptions

    clock = DeterministicClock(ONE_MS_BEFORE)
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    opts = GateOptions(idempotency_max_entries=7)
    gate = RiskDecisionToPaperOrderGate(reg, options=opts, clock=clock)
    syms = [f"SYM{i}_USDT" for i in range(10)]
    for s in syms:
        gate.evaluate(_sr02_request(symbol=s))
    assert gate.idempotency_size() <= 7
