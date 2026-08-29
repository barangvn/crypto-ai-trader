"""S-RSK-02 §12 AD-19 Fail-Closed — any exception → BLOCK (never approve on error)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.contracts.risk import RiskDecisionResult
from app.risk import (
    DeterministicClock,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
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

ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"


# 20 parametrized exception types (inject via mock inside _evaluate_inner path)
EXCEPTION_MATRIX = [
    (AttributeError, "attr_name"),
    (KeyError, "missing_key"),
    (IndexError, "idx"),
    (ValueError, "bad value"),
    (TypeError, "wrong type"),
    (OverflowError, "overflow"),
    (ZeroDivisionError, "div0"),
    (ArithmeticError, "arith"),
    (ImportError, "import_fail"),
    (RuntimeError, "runtime"),
    (NotImplementedError, "nyi"),
    (RecursionError, "recursion"),
    (MemoryError, "mem"),
    (OSError, "os"),
    (StopIteration, "stopiter"),
    (EOFError, "eof"),
    (UnicodeDecodeError, "utf", b"", 0, 1),
    (AssertionError, "assertion"),
    (SystemExit, 0),
    (Exception, "generic"),
]


def _make_args(exc_pair):
    """Build constructor-args for each exception type."""
    t, *rest = exc_pair
    if t is UnicodeDecodeError:
        return ("utf-8", b"", 0, 1, "bad")
    return tuple(rest)


@pytest.mark.parametrize("exc_info", EXCEPTION_MATRIX, ids=lambda e: e[0].__name__)
def test_ad19_exception_in_inner_evaluate_returns_blocked(exc_info):
    """§12 AD-19: Literally any exception inside _evaluate_inner → BLOCK with AD19_UNHANDLED_EXCEPTION code."""
    exc_type = exc_info[0]
    exc_args = _make_args(exc_info)
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    req = _sr02_request()

    def _raiser(*a, **kw):
        raise exc_type(*exc_args)

    with patch.object(type(gate), "_evaluate_inner", _raiser):
        res = gate.evaluate(req)
    assert res.allowed is False
    block_names = "|".join(res.block_reason_codes)
    assert "AD19_UNHANDLED_EXCEPTION" in block_names, f"missing AD19; blocks={res.block_reason_codes}"


def test_ad19_raw_dict_evaluate_rejected_as_AD19_synthetic_block():
    """Pass raw dict instead of PaperOrderGateRequest → AD19 synthetic block."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    raw = {"symbol": "BTC", "side": "BUY", "qty": Decimal("1")}
    res = gate.evaluate(raw)  # type: ignore[arg-type]
    assert res.allowed is False
    blocks = "|".join(res.block_reason_codes)
    assert "AD19_UNHANDLED_EXCEPTION:TypeError" in blocks or "AD19_UNHANDLED_EXCEPTION" in blocks


def test_ad19_broken_object_evaluate_AD19_synthetic():
    """Pass random class X instance → AD19 synthetic block."""

    class X:
        pass

    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    res = gate.evaluate(X())  # type: ignore[arg-type]
    assert res.allowed is False
    assert any(
        isinstance(b, str) and b.startswith("AD19_") for b in res.block_reason_codes
    )


def test_ad19_broken_clock_now_always_blocked():
    """ClockRef.now() raises → AD19 BLOCK (no approval ever on broken clock)."""
    rd = _bypass_rd()
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)

    from app.risk import ClockRef
    class BrokenClock(ClockRef):
        def now(self):
            raise OSError("clock broken")

    gate = RiskDecisionToPaperOrderGate(reg, clock=BrokenClock())
    req = _sr02_request()
    res = gate.evaluate(req)
    assert res.allowed is False
    assert any(
        isinstance(b, str) and b.startswith("AD19_") for b in res.block_reason_codes
    )


def test_ad19_broken_registry_lookup_blocked():
    """Registry.lookup() raises → G01 + finalize BLOCKED (approval never)."""
    rd = _bypass_rd()
    from app.risk import DecisionRegistry

    class BrokenReg(DecisionRegistry):
        def lookup(self, *a, **kw):
            raise RuntimeError("DB broken")

    clock = DeterministicClock(ONE_MS_BEFORE)
    gate = RiskDecisionToPaperOrderGate(BrokenReg(), clock=clock)
    req = _sr02_request()
    res = gate.evaluate(req)
    assert res.allowed is False
    blocks_str = "|".join(res.block_reason_codes)
    assert ("G01_REGISTRY_EXCEPTION" in blocks_str or "AD19_" in blocks_str)
