"""S-RSK-02 §1 G09 — Quantity / Notional boundary (3-point boundaries)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.risk import (
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import (
    ONE_MS_BEFORE,
    SR02_CORR,
    SR02_RD_ID,
    SR02_SYM,
    _bypass_rd,
    _sr02_request,
)

# Risk decision notional = 1000 (from sr02_clean_position_sizing)
RISK_NOTIONAL = Decimal("1000")
REF_PRICE = Decimal("100000")  # $100k / BTC


# G09A QTY non-positive -------------------------------------------------
@pytest.mark.parametrize(
    "qty, expected_block",
    [
        (Decimal("0"), "G09A_QTY_NON_POSITIVE"),
        (Decimal("-0.0001"), "G09A_QTY_NON_POSITIVE"),
        (Decimal("-100"), "G09A_QTY_NON_POSITIVE"),
        (Decimal("0.00000001"), None),   # tiny positive OK
        (Decimal("1.0"), None),
    ],
)
def test_g09a_quantity_non_positive(qty, expected_block):
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(qty=qty, notional=RISK_NOTIONAL)
    res = gate.evaluate(req)
    if expected_block:
        assert res.allowed is False
        assert expected_block in res.block_reason_codes
    else:
        assert res.allowed is True


# G09B NOTIONAL non-positive -------------------------------------------
@pytest.mark.parametrize(
    "notional, expected_block",
    [
        (Decimal("0"), "G09B_NOTIONAL_NON_POSITIVE"),
        (Decimal("-1"), "G09B_NOTIONAL_NON_POSITIVE"),
        (Decimal("-0.01"), "G09B_NOTIONAL_NON_POSITIVE"),
        (Decimal("0.01"), None),
        (Decimal("999"), None),
    ],
)
def test_g09b_notional_non_positive(notional, expected_block):
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    qty_small = Decimal("0.001")
    req = _sr02_request(qty=qty_small, notional=notional)
    res = gate.evaluate(req)
    if expected_block:
        assert res.allowed is False
        assert expected_block in res.block_reason_codes
    else:
        assert res.allowed is True


# G09C Notional vs Risk (3-pt: risk_notional = 1000) -------------------
@pytest.mark.parametrize(
    "notional, expected",
    [
        (Decimal("999"), True),
        (RISK_NOTIONAL, True),      # equality allowed
        (Decimal("1001"), False),   # 1 bps over → blocked (boundary)
    ],
)
def test_g09c_notional_oversize_3pt_boundary(notional, expected):
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(qty=Decimal("0.009"), notional=notional)
    res = gate.evaluate(req)
    assert res.allowed is expected
    if not expected:
        assert "G09C_NOTIONAL_OVERSIZED_VS_RISK" in res.block_reason_codes


# G09D qty * price vs notional tolerance -------------------------------
def test_g09d_fallback_none_skip_check():
    """Fallback ref price None → G09D skipped (even if mismatch huge)."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    opts = GateOptions(fallback_reference_price=None)
    gate = RiskDecisionToPaperOrderGate(reg, options=opts, clock=clock)
    # qty=1.0 * implicit price (would be huge) vs notional=1 — mismatch but SKIP
    req = _sr02_request(qty=Decimal("1.0"), notional=Decimal("1"))
    res = gate.evaluate(req)
    # NOT blocked by G09D; might be blocked by G09C (notional oversize no: 1 < 1000)
    # qty=1.0 > base_qty 0.01 OK → not blocked by G09 (qty>0 OK, notional>0 OK)
    # So ALLOWED (skipping G09D)
    assert res.allowed is True  # no G09D


def test_g09d_0_bps_tolerance_strict_3pt():
    """Fallback REF_PRICE, 0 bps tol. qty*price == notional → ALLOW. > → BLOCK."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    opts = GateOptions(
        fallback_reference_price=REF_PRICE,
        oversize_tolerance_bps=0,
    )
    gate = RiskDecisionToPaperOrderGate(reg, options=opts, clock=clock)
    # qty * price = 0.01 * 100,000 = 1,000 exactly → match notional = 1000
    cases = [
        (Decimal("0.00999"), Decimal("999"), True),     # implied=999 vs notional=999 → OK
        (Decimal("0.01"), Decimal("1000"), True),        # exact equality OK
        (Decimal("0.01000001"), Decimal("1000"), False), # implied > notional + 0 tol → BLOCK
    ]
    for q, n, exp in cases:
        gate.clear_idempotency()
        req = _sr02_request(qty=q, notional=n)
        res = gate.evaluate(req)
        assert res.allowed is exp, f"qty={q} notional={n}"
        if not exp:
            assert "G09D_QTY_PRICE_MISMATCH_VS_NOTIONAL" in res.block_reason_codes


def test_g09d_50bps_tolerance_allows_within():
    """50bps = 0.5% tolerance — qty*price 0.002 > notional → still ALLOW."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    opts = GateOptions(
        fallback_reference_price=REF_PRICE,
        oversize_tolerance_bps=50,
    )
    gate = RiskDecisionToPaperOrderGate(reg, options=opts, clock=clock)
    # notional = 1000; tol = 1000 * 50/10000 = 5
    # qty * price = 1004 → within 1000+5 → ALLOW
    qty = Decimal("1004") / REF_PRICE  # exactly 1004
    req = _sr02_request(qty=qty, notional=Decimal("1000"))
    res = gate.evaluate(req)
    assert res.allowed is True
