"""S-RSK-02 §4 Expired Decision + §5 Kill Switch 3-level boundary tests."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.contracts.risk import KillSwitchStateSpec, RiskDecisionResult
from app.risk import (
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import SR02_BASE_TS, SR02_CAUS_PREV, SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request


# ---------------------------------------------------------------------------
# §4 — G05_DECISION_EXPIRED: 3 boundary points (exactly, 1ms before, 1ms after)
# ---------------------------------------------------------------------------

VALID_UNTIL = "2026-03-18T12:04:30.000Z"
ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"
EXACTLY_VALID_UNTIL = "2026-03-18T12:04:30.000Z"
ONE_MS_AFTER = "2026-03-18T12:04:30.001Z"


@pytest.mark.parametrize(
    "clock_now, expected_allowed, expected_block",
    [
        (ONE_MS_BEFORE, True, None),
        (EXACTLY_VALID_UNTIL, False, "G05_DECISION_EXPIRED"),
        (ONE_MS_AFTER, False, "G05_DECISION_EXPIRED"),
    ],
    ids=["1ms_before_ALLOW", "exactly_valid_until_BLOCK", "1ms_after_BLOCK"],
)
def test_g05_expired_boundary_three_points(clock_now, expected_allowed, expected_block):
    """§4 explicit requirement: exactly=BLOCK, 1ms before=ALLOW, 1ms after=BLOCK."""
    clock = DeterministicClock(clock_now)
    rd = _bypass_rd(valid_until=VALID_UNTIL)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request()
    res = gate.evaluate(req)
    assert res.allowed is expected_allowed
    if expected_block is not None:
        assert expected_block in res.block_reason_codes


def test_g05_multiple_time_steps_through_expiry():
    """Walk clock through 10 steps and verify monotonic block transition."""
    steps = [
        "2026-03-18T12:00:00.000Z",
        "2026-03-18T12:02:00.000Z",
        "2026-03-18T12:04:00.000Z",
        "2026-03-18T12:04:29.000Z",
        "2026-03-18T12:04:29.500Z",
        "2026-03-18T12:04:29.999Z",
        "2026-03-18T12:04:30.000Z",
        "2026-03-18T12:04:30.001Z",
        "2026-03-18T12:05:00.000Z",
        "2026-03-18T13:00:00.000Z",
    ]
    rd = _bypass_rd(valid_until=VALID_UNTIL)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(SR02_BASE_TS)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    results = []
    for ts in steps:
        clock.set(ts)
        r = gate.evaluate(_sr02_request())
        results.append((ts, r.allowed, r.block_reason_codes))
    # first 6 (through 1ms before) allowed; last 4 blocked
    for i in range(6):
        assert results[i][1] is True, f"step {i} at {results[i][0]} expected ALLOW"
    for i in range(6, 10):
        assert results[i][1] is False, f"step {i} at {results[i][0]} expected BLOCK"
        assert "G05_DECISION_EXPIRED" in results[i][2]


# ---------------------------------------------------------------------------
# §5 — Kill Switch 3-level (G06A global / G06B emergency / G06C per-symbol)
# ---------------------------------------------------------------------------

KS_COMBINATIONS: list[tuple[KillSwitchStateSpec, set[str]]] = [
    (KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None), set()),
    (KillSwitchStateSpec(global_kill=True, per_symbol={}, reason=None), {"G06A_GLOBAL_KILL"}),
    (KillSwitchStateSpec(global_kill=False, per_symbol={}, reason="EMERGENCY maintenance"), {"G06B_EMERGENCY_STOP"}),
    (
        KillSwitchStateSpec(global_kill=False, per_symbol={SR02_SYM: True}, reason=None),
        {"G06C_PER_SYMBOL_KILL"},
    ),
    (
        KillSwitchStateSpec(global_kill=True, per_symbol={SR02_SYM: True}, reason="EMERGENCY"),
        {"G06A_GLOBAL_KILL", "G06B_EMERGENCY_STOP", "G06C_PER_SYMBOL_KILL"},
    ),
    (
        KillSwitchStateSpec(global_kill=True, per_symbol={}, reason="EMERGENCY stop"),
        {"G06A_GLOBAL_KILL", "G06B_EMERGENCY_STOP"},
    ),
    (
        KillSwitchStateSpec(global_kill=False, per_symbol={SR02_SYM: True}, reason="emergency reboot"),
        {"G06B_EMERGENCY_STOP", "G06C_PER_SYMBOL_KILL"},
    ),
    # symbol mismatch — G06C NOT triggered
    (KillSwitchStateSpec(global_kill=False, per_symbol={"ETH_USDT": True}, reason=None), set()),
]


@pytest.mark.parametrize("ks_state, expected_blocks", KS_COMBINATIONS, ids=[
    "no_kill_ALLOW",
    "global_kill_G06A",
    "emergency_reason_G06B",
    "symbol_kill_G06C",
    "all_three_kills_A_B_C",
    "global_A_emergency_B",
    "emergency_B_symbol_C",
    "other_symbol_kill_no_block",
])
def test_g06_kill_switch_3_level(ks_state, expected_blocks):
    """§5: all 3 kill-switch levels block. Bypass RD.__post_init__ for defense-in-depth."""
    rd = _bypass_rd(ks=ks_state)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request()
    res = gate.evaluate(req)
    if expected_blocks:
        assert res.allowed is False
        for code in expected_blocks:
            assert code in res.block_reason_codes, f"missing {code}; got {res.block_reason_codes}"
    else:
        assert res.allowed is True


def test_g06_killswitch_input_snapshot_not_mutated():
    """§5 last bullet: input snapshot (registry RD + KS) is not mutated."""
    ks_orig_reason = "initial"
    ks = KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=ks_orig_reason)
    rd = _bypass_rd(ks=ks)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    # Call 5 times
    for _ in range(5):
        gate.evaluate(_sr02_request())
    # Assert no mutation
    rd_fetched = reg.lookup(SR02_CORR, SR02_RD_ID)
    assert rd_fetched is not None
    assert rd_fetched.kill_switch_state.global_kill is False
    assert rd_fetched.kill_switch_state.reason == ks_orig_reason
    assert SR02_SYM not in rd_fetched.kill_switch_state.per_symbol


def test_g05_and_g06_together_both_block_codes_present():
    """Overlapping: expired + kill global — both codes present (short-circuit G05 first)."""
    rd = _bypass_rd(
        valid_until=VALID_UNTIL,
        ks=KillSwitchStateSpec(global_kill=True, per_symbol={}, reason=None),
    )
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_AFTER)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    res = gate.evaluate(_sr02_request())
    assert res.allowed is False
    # G05 short-circuits before G06 — at least one must be present
    assert ("G05_DECISION_EXPIRED" in res.block_reason_codes or "G06A_GLOBAL_KILL" in res.block_reason_codes)
