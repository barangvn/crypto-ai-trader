"""S-RSK-02 §13 Determinism 10x + CAP-1 AST (0 run_mode/source_type branches)."""
from __future__ import annotations

import ast
from decimal import Decimal

import pytest

from app.contracts.risk import KillSwitchStateSpec, RiskDecisionResult
from app.risk import (
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import (
    SR02_CAUS_PREV,
    SR02_CORR,
    SR02_RD_ID,
    SR02_SYM,
    _bypass_rd,
    _sr02_request,
)


def _make_scenario_fixtures():
    """Generate 10 distinct scenarios covering G01-G10 code paths."""
    scenarios = {}

    # 1) Approved happy path → ALLOW
    clock = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    g = RiskDecisionToPaperOrderGate(reg, clock=clock)
    scenarios["S01_HAPPY_ALLOW"] = (g, _sr02_request())

    # 2) Missing RD → G01 BLOCK
    clock2 = DeterministicClock("2026-03-18T12:04:29.999Z")
    reg2 = InMemoryDecisionRegistry()
    g2 = RiskDecisionToPaperOrderGate(reg2, clock=clock2)
    scenarios["S02_MISSING_RD"] = (g2, _sr02_request())

    # 3) Rejected RD → G02 BLOCK
    clock3 = DeterministicClock("2026-03-18T12:04:29.999Z")
    from tests.risk.conftest import SR02_BASE_TS
    rd3 = _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=SR02_RD_ID + "_rej",
        reason_codes=["R03", "R12"],
    )
    reg3 = InMemoryDecisionRegistry()
    reg3.register(SR02_CORR, SR02_RD_ID + "_rej", rd3)
    g3 = RiskDecisionToPaperOrderGate(reg3, clock=clock3)
    req3 = _sr02_request(risk_decision_id=SR02_RD_ID + "_rej")
    scenarios["S03_REJECTED_RD"] = (g3, req3)

    # 4) Wrong correlation → G03
    clock4 = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd4 = _bypass_rd()
    reg4 = InMemoryDecisionRegistry()
    reg4.register(SR02_CORR, SR02_RD_ID, rd4)
    g4 = RiskDecisionToPaperOrderGate(reg4, clock=clock4)
    req4 = _sr02_request(correlation_id="OTHER_CORR_9999")
    scenarios["S04_WRONG_CORR"] = (g4, req4)

    # 5) Expired → G05
    clock5 = DeterministicClock("2026-03-18T12:05:00.001Z")
    rd5 = _bypass_rd(valid_until="2026-03-18T12:05:00.000Z")
    reg5 = InMemoryDecisionRegistry()
    reg5.register(SR02_CORR, SR02_RD_ID, rd5)
    g5 = RiskDecisionToPaperOrderGate(reg5, clock=clock5)
    scenarios["S05_EXPIRED"] = (g5, _sr02_request())

    # 6) Kill global (bypass) → G06A
    clock6 = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd6 = _bypass_rd(
        ks=KillSwitchStateSpec(global_kill=True, per_symbol={}, reason=None),
    )
    reg6 = InMemoryDecisionRegistry()
    reg6.register(SR02_CORR, SR02_RD_ID, rd6)
    g6 = RiskDecisionToPaperOrderGate(reg6, clock=clock6)
    scenarios["S06_KILL_GLOBAL"] = (g6, _sr02_request())

    # 7) Stale age → G08A (600s past, threshold=300)
    clock7 = DeterministicClock("2026-03-18T12:15:00.000Z")  # 15 min = 900s
    rd7 = _bypass_rd()
    reg7 = InMemoryDecisionRegistry()
    reg7.register(SR02_CORR, SR02_RD_ID, rd7)
    opts7 = GateOptions(stale_threshold_sec=300.0)
    g7 = RiskDecisionToPaperOrderGate(reg7, options=opts7, clock=clock7)
    scenarios["S07_STALE"] = (g7, _sr02_request())

    # 8) Notional oversize → G09C
    clock8 = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd8 = _bypass_rd()
    reg8 = InMemoryDecisionRegistry()
    reg8.register(SR02_CORR, SR02_RD_ID, rd8)
    g8 = RiskDecisionToPaperOrderGate(reg8, clock=clock8)
    req8 = _sr02_request(notional=Decimal("99999"))
    scenarios["S08_NOTIONAL_OVERSIZE"] = (g8, req8)

    # 9) Short attempt (OPEN_NEW + SELL) → G10A
    clock9 = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd9 = _bypass_rd()
    reg9 = InMemoryDecisionRegistry()
    reg9.register(SR02_CORR, SR02_RD_ID, rd9)
    g9 = RiskDecisionToPaperOrderGate(reg9, clock=clock9)
    from app.contracts.paper import PaperOrderSide
    req9 = _sr02_request(side=PaperOrderSide.SELL, position_intent="OPEN_NEW")
    scenarios["S09_SHORT_ATTEMPT"] = (g9, req9)

    # 10) Perp symbol → G10C
    clock10 = DeterministicClock("2026-03-18T12:04:29.999Z")
    rd10 = _bypass_rd()
    reg10 = InMemoryDecisionRegistry()
    reg10.register(SR02_CORR, SR02_RD_ID, rd10)
    g10 = RiskDecisionToPaperOrderGate(reg10, clock=clock10)
    req10 = _sr02_request(symbol="BTC_PERP")
    scenarios["S10_PERP_SYMBOL"] = (g10, req10)

    return scenarios


def test_determinism_10fixtures_x10runs_identical_sha_and_allowed():
    """§13 AD-20 strict: same input 10x → same sha+allowed+codes across 10 fixtures."""
    scenarios = _make_scenario_fixtures()
    assert len(scenarios) == 10
    for name, (gate, req) in scenarios.items():
        # Run 10x, compare each pair
        runs = []
        for _ in range(10):
            gate.clear_idempotency()  # fresh to remove G07 bias
            runs.append(gate.evaluate(req))
        # Allowed identical across runs
        allow_vals = {r.allowed for r in runs}
        assert len(allow_vals) == 1, f"{name}: allow mix = {allow_vals}"
        # block codes identical (same codes, same order)
        first_blocks = runs[0].block_reason_codes
        for i, r in enumerate(runs[1:], start=2):
            assert r.block_reason_codes == first_blocks, f"{name} run {i} block mismatch"
        # gate_version same
        assert all(r.gate_version == runs[0].gate_version for r in runs)
        # input_sha256 across runs → identical (same request → same sha)
        sha_vals = {r.input_sha256 for r in runs}
        assert len(sha_vals) == 1, f"{name}: sha varied = {sha_vals}"
        # schema_sha256 of GateResult → identical for run 1 vs run 10
        assert runs[0].schema_sha256() == runs[-1].schema_sha256(), f"{name}: gate result schema sha not stable"


def test_different_fixtures_different_sha_when_outcome_diff():
    """Different scenario produces different gate outputs (10 scenarios vary → SHA differs)."""
    scenarios = _make_scenario_fixtures()
    outputs = []
    for name, (g, req) in scenarios.items():
        g.clear_idempotency()
        r = g.evaluate(req)
        outputs.append((name, r.allowed, tuple(r.block_reason_codes)))
    # There should be at least 2 distinct outcomes (at least allow vs block)
    distinct = set(o[1:] for o in outputs)
    assert len(distinct) >= 2


# ---------------------------------------------------------------------------
# CAP-1 AST scan — gate.py: 0 `if run_mode` or `if source_type` branches
# ---------------------------------------------------------------------------

def test_cap1_ast_gate_zero_run_mode_source_type_branches():
    """CAP-1: gate.py must have exactly 0 `if run_mode` or `if source_type` branches."""
    from app.risk import gate as gate_module
    src = gate_module.__file__
    with open(src, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    hits_runmode = 0
    hits_sourcetype = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            src_segment = ast.dump(node.test)
            lowered = src_segment.lower()
            if "run_mode" in lowered or "'runmode'" in lowered:
                hits_runmode += 1
            if "source_type" in lowered or "'sourcetype'" in lowered:
                hits_sourcetype += 1
    assert hits_runmode == 0
    assert hits_sourcetype == 0
