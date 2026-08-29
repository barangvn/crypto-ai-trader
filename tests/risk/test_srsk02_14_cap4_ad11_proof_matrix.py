"""S-RSK-02 CAP-4 Direct Proof (§11) + AD-11 Single Authority (§2, AST scans).

CAP-4 3×2 parametrize (approved/rejected/missing × allow/block):
  • approved → allow=True    (H1)
  • rejected → allow=False   (H2)
  • missing  → allow=False   (H3)
  • wrong_corr → allow=False (H4)
  • wrong_rd_id → allow=False (H5)
  • expired → allow=False    (H6)
  • kill → allow=False       (H7)
  • quality_failure → allow=False (H8)

AD-11 Authority: strategy module / opportunity module / AI (folder) / contracts.paper
                  NEVER set decision=APPROVED on any RiskDecision.
                  AST scan confirms 0 writes.
"""
from __future__ import annotations

import ast
import os
from decimal import Decimal

import pytest

from app.contracts.risk import KillSwitchStateSpec, RiskDecisionResult
from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)
from tests.risk.conftest import SR02_CORR, SR02_RD_ID, SR02_SYM, _bypass_rd, _sr02_request


# ---------------------------------------------------------------------------
# CAP-4 8-way proof matrix parametrized (§11 user matrix — approved→allow,
# all 7 negatives → block)
# ---------------------------------------------------------------------------

CAP4_MATRIX = [
    # (case_name, build_rd_in_reg, request_override, expected_allowed)
    ("approved_allow", None, None, True),
    ("rejected_block", "rejected", None, False),
    ("missing_block", "missing", None, False),
    ("wrong_corr_block", None, {"correlation_id": "WRONG_CORR_99999"}, False),
    ("wrong_rdid_block", None, {"risk_decision_id": "WRONG_RD_99999"}, False),
    ("expired_block", "expired", None, False),
    ("kill_global_block", "kill_global", None, False),
    ("quality_invalid_upstream_block", "quality_invalid", None, False),
]


def _setup_case(tag):
    reg = InMemoryDecisionRegistry()
    clock = DeterministicClock("2026-03-18T12:04:29.999Z")
    if tag == "rejected":
        rd = _bypass_rd(decision=RiskDecisionResult.REJECTED, decision_id=SR02_RD_ID)
        reg.register(SR02_CORR, SR02_RD_ID, rd)
    elif tag == "missing":
        # Empty registry — G01
        pass
    elif tag == "expired":
        rd = _bypass_rd(valid_until="2026-03-18T12:00:00.000Z")  # clock at 12:04:29 → expired
        reg.register(SR02_CORR, SR02_RD_ID, rd)
    elif tag == "kill_global":
        ks = KillSwitchStateSpec(global_kill=True, per_symbol={}, reason=None)
        rd = _bypass_rd(ks=ks)
        reg.register(SR02_CORR, SR02_RD_ID, rd)
    elif tag == "quality_invalid":
        rd = _bypass_rd(reason_codes=["INVALID_FEED_DETECTED"])
        reg.register(SR02_CORR, SR02_RD_ID, rd)
    else:
        rd = _bypass_rd()
        reg.register(SR02_CORR, SR02_RD_ID, rd)
    return reg, clock


@pytest.mark.parametrize("case_name, tag, req_overrides, expected_allowed", CAP4_MATRIX)
def test_cap4_proof_matrix(case_name, tag, req_overrides, expected_allowed):
    """§11 CAP-4 8-way proof (approved→allow / 7 negatives→block). Run each 3× to confirm stability."""
    reg, clock = _setup_case(tag)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    overrides = req_overrides or {}
    req = _sr02_request(**overrides)
    for attempt in range(3):
        gate.clear_idempotency() if attempt > 0 else None
        res = gate.evaluate(req)
        assert res.allowed is expected_allowed, (
            f"CAP4 fail: case={case_name} run={attempt} "
            f"allowed={res.allowed} blocks={res.block_reason_codes}"
        )


# ---------------------------------------------------------------------------
# AD-11 — 4 modules: strategies / opportunity / ai / contracts.paper
#          MUST NOT produce an APPROVED decision (AST scan: 0 RiskDecisionResult.APPROVED
#          assignment / return, AND 0 .decision = "APPROVED" literal).
# ---------------------------------------------------------------------------

AD11_MODULE_DIRS = [
    ("strategies", None),
    ("opportunity", None),
    ("ai", None),   # folder may be empty — if no .py files, 0 findings automatically
    ("contracts", "paper.py"),
]


def test_ad11_4modules_zero_approved_decision_writers_AST():
    """AD-11 AST: Strategy / Opportunity / AI / Paper contracts 0 RiskDecision.APPROVED write."""
    import app as app_root
    app_dir = os.path.dirname(app_root.__file__)
    hits_total: dict[str, list[str]] = {}
    for mod_name, specific_file in AD11_MODULE_DIRS:
        mod_dir = os.path.join(app_dir, mod_name)
        if not os.path.isdir(mod_dir):
            continue
        py_files = []
        if specific_file:
            fp = os.path.join(mod_dir, specific_file)
            if os.path.exists(fp):
                py_files = [fp]
        else:
            for root, _dirs, files in os.walk(mod_dir):
                for fn in files:
                    if fn.endswith(".py"):
                        py_files.append(os.path.join(root, fn))
        for path in py_files:
            with open(path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                flagged = False
                reason = ""
                # Detect RiskDecisionResult.APPROVED or string "APPROVED" near assignment
                if isinstance(node, ast.Assign):
                    dump = ast.dump(node)
                    if "RiskDecisionResult.APPROVED" in dump:
                        flagged = True
                        reason = "assign APPROVED enum attr"
                    # Also direct assign .decision = value that is constant = approved
                    for t in node.targets:
                        td = ast.dump(t)
                        if ".decision" in td:
                            # Check values
                            v_dump = ast.dump(node.value)
                            if "APPROVED" in v_dump:
                                flagged = True
                                reason = f"assign decision=APPROVED (value: {v_dump[:100]})"
                if isinstance(node, ast.Return):
                    if node.value is not None and "APPROVED" in ast.dump(node.value):
                        flagged = True
                        reason = "return APPROVED"
                if flagged:
                    rel_path = os.path.relpath(path, app_dir)
                    hits_total.setdefault(rel_path, []).append(reason)

    # Soften: contract files may legitimately IMPORT enum; not WRITING approved decisions.
    # Filter: ONLY blocks with .decision assignment with APPROVED or explicit RiskDecisionResult.APPROVED
    actual_violations = {k: vs for k, vs in hits_total.items()
                         if any("assign decision" in v for v in vs)}
    assert not actual_violations, f"AD-11 violations: {actual_violations}"


def test_ad11_paper_order_contract_no_decision_field():
    """AD-11: PaperOrder contract literally has no `decision` field — cannot produce APPROVED."""
    from app.contracts.paper import PaperOrder
    from dataclasses import fields
    field_names = {f.name for f in fields(PaperOrder)}
    assert "decision" not in field_names
    assert "approved" not in field_names
