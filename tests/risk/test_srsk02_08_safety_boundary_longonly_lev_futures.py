"""S-RSK-02 §9/10 Safety — long-only / leverage==1 / no futures-perps (G10A/B/C)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.paper import PaperOrderSide
from app.contracts.risk import LimitsSnapshot, RiskDecisionResult
from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request

ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"


# ---------------------------------------------------------------------------
# G10A — Long-only (OPEN_NEW + SELL = short attempt → BLOCKED)
# ---------------------------------------------------------------------------

def test_g10a_open_new_sell_is_short_attempt_blocked():
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(side=PaperOrderSide.SELL, position_intent="OPEN_NEW")
    res = gate.evaluate(req)
    assert res.allowed is False
    assert "G10A_SHORT_ATTEMPT_BLOCKED" in res.block_reason_codes


def test_g10a_close_existing_sell_ALLOWED():
    """§11.11 long-only boundary: Close existing → Sell is ALLOWED (no short open)."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(side=PaperOrderSide.SELL, position_intent="CLOSE_EXISTING")
    res = gate.evaluate(req)
    assert res.allowed is True


def test_g10a_open_new_buy_ALLOWED():
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(side=PaperOrderSide.BUY, position_intent="OPEN_NEW")
    res = gate.evaluate(req)
    assert res.allowed is True


def test_g10a_close_existing_buy_ALLOWED():
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(side=PaperOrderSide.BUY, position_intent="CLOSE_EXISTING")
    res = gate.evaluate(req)
    assert res.allowed is True


# ---------------------------------------------------------------------------
# G10B — leverage != 1 → BLOCK (defense-in-depth; LimitsSnapshot invariant
# raises ContractSchemaError for lev!=1; gate re-checks post-construction)
# ---------------------------------------------------------------------------

def _bypass_limits_lev(lev: int | float) -> LimitsSnapshot:
    obj = object.__new__(LimitsSnapshot)
    obj.max_position_notional_per_symbol = Decimal("10000")
    obj.max_exposure_notional_total = Decimal("50000")
    obj.max_daily_loss_notional = Decimal("-1000")
    obj.max_drawdown_pct = 0.20
    obj.max_consecutive_losses = 5
    obj.max_leverage_allowed = lev  # type: ignore[assignment]
    obj.current_exposure_notional = Decimal("8000")
    obj.current_daily_pnl = Decimal("-200")
    obj.current_drawdown_pct = 0.05
    obj.current_consecutive_losses = 1
    return obj


LEV_CASES: list[tuple[object, bool, str]] = [
    (0, False, "G10B_LEVERAGE_OVER_1X_BLOCKED"),
    (1, True, ""),
    (1.5, False, "G10B_LEVERAGE_OVER_1X_BLOCKED"),
    (2, False, "G10B_LEVERAGE_OVER_1X_BLOCKED"),
    (10, False, "G10B_LEVERAGE_OVER_1X_BLOCKED"),
]


@pytest.mark.parametrize("lev, allow, blk", LEV_CASES)
def test_g10b_leverage_boundary_all(lev, allow, blk):
    limits = _bypass_limits_lev(lev)
    rd = _bypass_rd(limits=limits)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request()
    res = gate.evaluate(req)
    assert res.allowed is allow
    if not allow:
        assert blk in res.block_reason_codes


# ---------------------------------------------------------------------------
# G10C — Futures / Perpetual tokens (SYM or ORDER_TYPE)
# ---------------------------------------------------------------------------

FUTURES_SYM_BLOCKED: list[tuple[str, str]] = [
    ("BTC_PERP", "G10C_FUTURES_OR_PERPETUAL_BLOCKED"),
    ("BTC_USDT_FUTURES", "G10C_FUTURES_OR_PERPETUAL_BLOCKED"),
    ("BTC-USD-SWAP", "G10C_FUTURES_OR_PERPETUAL_BLOCKED"),
    ("BTC_SHORT", "G10C_FUTURES_OR_PERPETUAL_BLOCKED"),
]


@pytest.mark.parametrize("sym, blk", FUTURES_SYM_BLOCKED)
def test_g10c_futures_perp_symbols_blocked(sym, blk):
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request(symbol=sym)
    res = gate.evaluate(req)
    assert res.allowed is False
    assert blk in res.block_reason_codes


def test_g10c_spot_symbols_ALLOWED():
    for sym in ["BTC_USDT", "ETH_BTC", "SOL_USDC", "XRP_USD"]:
        rd = _bypass_rd()
        reg = InMemoryDecisionRegistry()
        reg.register(SR02_CORR, SR02_RD_ID, rd)
        clock = DeterministicClock(ONE_MS_BEFORE)
        gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
        req = _sr02_request(symbol=sym)
        res = gate.evaluate(req)
        assert res.allowed is True, f"spot {sym} should be ALLOWED"
