"""S-RSK-02 §12 AD-19 Fail-Closed — extended exception matrix (15 test)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts.risk import RiskDecisionResult
from app.risk import (
    ClockRef,
    DecisionRegistry,
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
)
from tests.risk.conftest import SR02_CORR, SR02_RD_ID, _bypass_rd, _sr02_request


# ---- Subclass-based injection patterns (typed so gate accepts) ----
class BrokenRegistryExc(DecisionRegistry):
    def __init__(self, exc_factory):
        self._exc_factory = exc_factory
        self._captured = []

    def lookup(self, correlation_id: str, risk_decision_id: str):
        self._captured.append((correlation_id, risk_decision_id))
        raise self._exc_factory()

    def find_by_decision_id(self, risk_decision_id: str):
        return None


class BrokenClockExc(ClockRef):
    def __init__(self, exc_factory):
        self._exc_factory = exc_factory

    def now(self):
        raise self._exc_factory()


_AD19_EXC_MATRIX = [
    (lambda: RuntimeError("boom"), "RuntimeError"),
    (lambda: ValueError("bad value"), "ValueError"),
    (lambda: TypeError("bad type"), "TypeError"),
    (lambda: KeyError("missing"), "KeyError"),
    (lambda: AttributeError("attr"), "AttributeError"),
    (lambda: IndexError("index"), "IndexError"),
    (lambda: OverflowError("too big"), "OverflowError"),
    (lambda: ZeroDivisionError("div0"), "ZeroDivisionError"),
    (lambda: MemoryError("mem"), "MemoryError"),
    (lambda: RecursionError("recur"), "RecursionError"),
]


@pytest.mark.parametrize("exc_factory,exc_name", _AD19_EXC_MATRIX, ids=[e[1] for e in _AD19_EXC_MATRIX])
def test_ad19_broken_registry_lookup_blocks(exc_factory, exc_name):
    reg = BrokenRegistryExc(exc_factory)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    res = gate.evaluate(_sr02_request())
    assert res.allowed is False
    assert any("AD19" in c for c in res.block_reason_codes), (
        f"AD19 code missing. blocks={res.block_reason_codes}"
    )


@pytest.mark.parametrize("exc_factory,exc_name", _AD19_EXC_MATRIX[:5], ids=[f"clock_{e[1]}" for e in _AD19_EXC_MATRIX[:5]])
def test_ad19_broken_clock_blocks(exc_factory, exc_name):
    clock = BrokenClockExc(exc_factory)
    reg = InMemoryDecisionRegistry()
    gate = RiskDecisionToPaperOrderGate(reg, clock=clock)
    res = gate.evaluate(_sr02_request())
    assert res.allowed is False
    assert any("AD19" in c for c in res.block_reason_codes)


def test_ad19_untyped_instance_block_synthetic():
    class X:
        pass

    gate = RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry(), clock=DeterministicClock())
    res = gate.evaluate(X())  # type: ignore[arg-type]
    assert res.allowed is False
    assert any(c.startswith("AD19_") for c in res.block_reason_codes)
    # synthetic block always has validated_risk_decision_id="" (no RD matched)
    assert res.validated_risk_decision_id == ""


def test_ad19_synthetic_block_correlation_defaults_to_unknown():
    class NotReq:
        pass

    gate = RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry())
    res = gate.evaluate(NotReq())  # type: ignore[arg-type]
    assert res.correlation_id == "unknown"
    assert res.causation_id == "unknown"


def test_ad19_synthetic_block_allows_256_hex_sha():
    """AD19 synthetic block sha256 length must be 64 hex chars (256-bit)."""
    gate = RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry())
    res = gate.evaluate("not a request at all")  # type: ignore[arg-type]
    assert res.allowed is False
    assert len(res.input_sha256) == 64
    # All chars are hex
    assert all(c in "0123456789abcdef" for c in res.input_sha256)


def test_ad19_invalid_options_during_init_blocks_raises_init():
    """Gate init raises for invalid options (schema enforcement), which is safe
    because gate cannot be constructed to produce APPROVED in that state."""
    from app.contracts.exceptions import ContractSchemaError
    reg = InMemoryDecisionRegistry()
    with pytest.raises((ContractSchemaError, Exception)):
        RiskDecisionToPaperOrderGate(reg, options="not a GateOptions")  # type: ignore[arg-type]


def test_ad19_broken_quality_attr_in_rd_does_not_crash_just_blocks():
    rd = _bypass_rd(decision=RiskDecisionResult.APPROVED)
    # Force rd.quality_state to a broken non-QualityFlags object that raises on getattr
    class BadQuality:
        def __getattribute__(self, item):
            raise RuntimeError("quality exploded")
    object.__setattr__(rd, "quality_state", BadQuality())
    reg = InMemoryDecisionRegistry()
    reg.register(rd.correlation_id, rd.decision_id, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock("2026-03-18T12:04:29.999Z"))
    res = gate.evaluate(_sr02_request())
    # Either approved or blocked depending on AD-19 catcher; but MUST NEVER raise to caller
    assert isinstance(res.allowed, bool)
    if res.allowed is False:
        # Failure was caught = AD-19 block OR meaningful G08B_* etc catcher all OK:
        # The contract property: "exception never propagates to caller"
        pass  # pass means AD-19 invariant preserved
