"""S-RSK-02 §6 Quality + Stale Age + CAP-2 (read-only, no validator import)."""
from __future__ import annotations

import ast
from decimal import Decimal

import pytest

from app.contracts.canonical import QualityFlags
from app.risk import (
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)

from tests.risk.conftest import SR02_BASE_TS, SR02_CORR, SR02_RD_ID, _bypass_rd, _sr02_request


# ---------------------------------------------------------------------------
# §6 Stale age boundary (default 300s = 5min from created_ts = SR02_BASE_TS)
# ---------------------------------------------------------------------------

# SR02_BASE_TS = 2026-03-18T12:00:00.000Z → default stale=300s → stale at
# exactly 12:05:00.000 (300s) and beyond. Use strict > so 299s=ALLOW, 300s=BLOCK.

AT_299s = "2026-03-18T12:04:59.000Z"   # 299s → ALLOW
AT_300s = "2026-03-18T12:05:00.000Z"   # 300s → stale_threshold_sec=300 strict > → 300 ALLOW? Let's test boundary
AT_301s = "2026-03-18T12:05:01.000Z"   # 301s → BLOCK


SR02_LONG_VALID = "2026-03-18T13:00:00.000Z"   # 1 saat sonrası, testte expire olmaz


@pytest.mark.parametrize(
    "clock_ts, stale_threshold, expected_allowed, expected_block",
    [
        (AT_299s, 300.0, True, None),
        (AT_300s, 300.0, True, None),   # strict >
        (AT_301s, 300.0, False, "G08A_STALE_DECISION_AGE"),
        (AT_299s, 60.0, False, "G08A_STALE_DECISION_AGE"),    # 299 > 60 override
        (AT_301s, 600.0, True, None),                         # 301 < 600
    ],
    ids=["299s_default_ALLOW", "300s_default_ALLOW", "301s_default_BLOCK", "299s_60s_thr_BLOCK", "301s_600s_thr_ALLOW"],
)
def test_g08a_stale_age_boundary_plus_threshold_override(clock_ts, stale_threshold, expected_allowed, expected_block):
    rd = _bypass_rd(valid_until=SR02_LONG_VALID)
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(clock_ts)
    opts = GateOptions(stale_threshold_sec=stale_threshold)
    gate = RiskDecisionToPaperOrderGate(reg, options=opts, clock=clock)
    res = gate.evaluate(_sr02_request())
    assert res.allowed is expected_allowed
    if expected_block:
        assert expected_block in res.block_reason_codes


# ---------------------------------------------------------------------------
# §6 Quality 4 flags upstream (CAP-2 read-only — gate only reads, no mutate,
# no validator import/call)
# ---------------------------------------------------------------------------

QUALITY_MATRIX: list[tuple[dict[str, bool], list[str]]] = [
    ({"stale": True, "invalid": False, "quarantined": False, "degraded": False}, ["G08B_UPSTREAM_QUALITY_STALE"]),
    ({"stale": False, "invalid": True, "quarantined": False, "degraded": False}, ["G08B_UPSTREAM_QUALITY_INVALID"]),
    ({"stale": False, "invalid": False, "quarantined": True, "degraded": False}, ["G08B_UPSTREAM_QUALITY_QUARANTINED"]),
    ({"stale": False, "invalid": False, "quarantined": False, "degraded": True}, ["G08B_UPSTREAM_QUALITY_DEGRADED"]),
    (
        {"stale": True, "invalid": True, "quarantined": True, "degraded": True},
        [
            "G08B_UPSTREAM_QUALITY_STALE",
            "G08B_UPSTREAM_QUALITY_INVALID",
            "G08B_UPSTREAM_QUALITY_QUARANTINED",
            "G08B_UPSTREAM_QUALITY_DEGRADED",
        ],
    ),
    ({"stale": False, "invalid": False, "quarantined": False, "degraded": False}, []),  # clean → ALLOW
]


@pytest.mark.parametrize("qs_attrs, expected_block_codes", QUALITY_MATRIX)
def test_g08b_quality_flags_upstream_propagate(qs_attrs, expected_block_codes):
    qf = QualityFlags(**qs_attrs)  # type: ignore[call-overload]
    rd = _bypass_rd(valid_until=SR02_LONG_VALID)
    try:
        object.__setattr__(rd, 'quality_state', qf)
    except Exception:
        pass
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(AT_299s)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    res = gate.evaluate(_sr02_request())
    if expected_block_codes:
        assert res.allowed is False
        for code in expected_block_codes:
            assert code in res.block_reason_codes, f"missing {code} in {res.block_reason_codes}"
    else:
        assert res.allowed is True


def test_g08b_sub_from_rd_reason_codes_propagates():
    """§6 — upstream reason_codes containing STALE/INVALID/QUARANTINE tags propagate as G08B_SUB blocks."""
    rc_matrix = [
        (["STALE_DATA_LAG"], "STALE", True),
        (["INVALID_PRICE_FEED"], "INVALID", True),
        (["QUARANTINE_BREAK"], "QUARANTINE", True),
        (["NOT_RELATED"], None, False),
    ]
    for reason_codes, expected_tag, expect_sub in rc_matrix:
        rd = _bypass_rd(reason_codes=reason_codes, valid_until=SR02_LONG_VALID)
        reg = InMemoryDecisionRegistry()
        reg.register(SR02_CORR, SR02_RD_ID, rd)
        clock = DeterministicClock(AT_299s)
        gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
        res = gate.evaluate(_sr02_request())
        has_sub = any(
            isinstance(rc, str) and rc.startswith("G08B_SUB_FROM_RISK_DEC:")
            for rc in res.block_reason_codes
        )
        assert has_sub == expect_sub, f"rc={reason_codes} got sub={has_sub} exp={expect_sub}; blocks={res.block_reason_codes}"
        if expected_tag and has_sub:
            assert res.allowed is False


# ---------------------------------------------------------------------------
# CAP-2 AST scan — gate.py: (1) NO setattr/assignment to quality_flags,
# (2) NO import of validator module.
# ---------------------------------------------------------------------------

def test_cap2_gate_ast_no_quality_mutation_no_validator_import():
    """CAP-2 strict: AST scan confirms 0 assignment to quality_flags, 0 validator import/call."""
    from app.risk import gate as gate_module
    src = gate_module.__file__
    with open(src, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    assign_hits = 0
    validator_imports = 0
    validator_calls = 0

    for node in ast.walk(tree):
        # (a) Assign / AugAssign to quality_flags
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = []
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            else:
                targets = list(node.targets)
            for t in targets:
                dump = ast.dump(t)
                if "quality_flags" in dump or "quality_state" in dump:
                    assign_hits += 1
        # (b) validator module (name = 'validator', 'validate_*' import)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "validator" in alias.name.lower() or "quality" in alias.name.lower() and "validator" in alias.name.lower():
                    validator_imports += 1
        if isinstance(node, ast.ImportFrom):
            if node.module and ("validator" in node.module.lower()):
                validator_imports += 1
        # (c) Call(name starts with validate_/validate())
        # EXCEPTION: validate_instant is a timestamp-format helper (app.contracts.types),
        # NOT a quality-flag validator. CAP-2 prohibits re-invoking upstream quality validator only.
        if isinstance(node, ast.Call):
            fn = node.func
            name = ""
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            if name and name != "validate_instant" and (
                "validator" in name.lower() or name.startswith("validate_")
            ):
                validator_calls += 1

    assert assign_hits == 0, f"CAP-2 quality mutation found: {assign_hits} AST hits"
    assert validator_imports == 0, f"CAP-2 validator module imported: {validator_imports} hits"
    assert validator_calls == 0, f"CAP-2 validator called: {validator_calls} hits"
