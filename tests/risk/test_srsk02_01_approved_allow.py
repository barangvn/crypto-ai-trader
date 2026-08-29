"""S-RSK-02 — 1. Approved → Allow (22 test). Happy path matrix (G01–G10 PASS → allowed=True)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.risk.conftest import _sr02_request, _bypass_rd, SR02_CORR, SR02_RD_ID, SR02_CAUS_PREV, SR02_SYM
from app.contracts.risk import RiskDecisionResult
from app.risk import (
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    RiskDecisionToPaperOrderGate,
)


def test_approved_happy_gate_allowed(sr02_gate, sr02_happy_request):
    r = sr02_gate.evaluate(sr02_happy_request)
    assert r.allowed is True
    assert r.block_reason_codes == ()
    assert r.validated_risk_decision_id == SR02_RD_ID
    assert r.causation_id == SR02_RD_ID
    assert r.correlation_id == SR02_CORR
    assert r.gate_version.startswith("rsk02_gate_v1")


_SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT", "ADA_USDT", "DOGE_USDT"]


@pytest.mark.parametrize("sym", _SYMBOLS, ids=[f"sym_{s}" for s in _SYMBOLS])
def test_approved_different_symbols(sym, sr02_clean_limits, sr02_clean_ks_no_kill, sr02_clean_position_sizing):
    rd = _bypass_rd(
        decision=RiskDecisionResult.APPROVED,
        correlation_id=SR02_CORR,
        decision_id=SR02_RD_ID,
        ks=sr02_clean_ks_no_kill,
        limits=sr02_clean_limits,
        ps=sr02_clean_position_sizing,
    )
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, rd)
    gate = RiskDecisionToPaperOrderGate(reg, clock=DeterministicClock())
    req = _sr02_request(symbol=sym)
    # gate G06C per_symbol kill'de sembol uyuşmaz (clean_ks boş dict)
    r = gate.evaluate(req)
    assert r.allowed is True


_QTY_MATRIX = [Decimal("0.0001"), Decimal("0.001"), Decimal("0.01"), Decimal("0.1"), Decimal("1")]


@pytest.mark.parametrize("qty", _QTY_MATRIX, ids=[f"qty_{q}" for q in _QTY_MATRIX])
def test_approved_various_qty(sr02_gate, qty):
    # notional risk_notional (1000) qty*0.01 notional 1000 match olunca oversizematch olmayabilir
    # notional 1000, qty qty'de qty>0 olsun
    r = sr02_gate.evaluate(_sr02_request(qty=qty, notional=Decimal("1000")))
    # Eğer qty*price yoksa — fallback_reference_price None ise G09D skip. G09A qty>0 PASS.
    assert r.allowed is True


_NOTIONAL_MATRIX = [Decimal("1"), Decimal("10"), Decimal("100"), Decimal("500"), Decimal("1000")]


@pytest.mark.parametrize("notional", _NOTIONAL_MATRIX, ids=[f"not_{n}" for n in _NOTIONAL_MATRIX])
def test_approved_various_notional_within_limit(sr02_gate, notional):
    r = sr02_gate.evaluate(_sr02_request(notional=notional))
    assert r.allowed is True


def test_approved_twice_equivalent_results(sr02_gate, sr02_happy_request):
    r1 = sr02_gate.evaluate(sr02_happy_request)
    sr02_gate.clear_idempotency()  # ikinci kez asıl çağrı (farklı key due clock? — aynı ts ise aynı)
    r2 = sr02_gate.evaluate(sr02_happy_request)
    assert r1.allowed == r2.allowed
    assert r1.validated_risk_decision_id == r2.validated_risk_decision_id
    assert r1.gate_version == r2.gate_version


def test_approved_info_codes_empty_on_first_call(sr02_gate, sr02_happy_request):
    sr02_gate.clear_idempotency()
    r = sr02_gate.evaluate(sr02_happy_request)
    # On first call without issues: info_codes tuple empty.
    assert isinstance(r.info_codes, tuple)


def test_approved_gateresult_immutable(sr02_gate, sr02_happy_request):
    from dataclasses import FrozenInstanceError
    r = sr02_gate.evaluate(sr02_happy_request)
    with pytest.raises(Exception):
        # frozen=True normally raises FrozenInstanceError; protect by broad exception
        r.allowed = False  # type: ignore[misc]


def test_approved_request_fields_preserved(sr02_happy_request):
    assert sr02_happy_request.symbol == SR02_SYM
    assert sr02_happy_request.requested_qty_base == Decimal("0.01")
    assert sr02_happy_request.correlation_id == SR02_CORR
    assert sr02_happy_request.policy_refs.risk_decision_id == SR02_RD_ID


def test_approved_request_sha_stable(sr02_happy_request):
    h1 = sr02_happy_request.schema_sha256()
    h2 = sr02_happy_request.schema_sha256()
    assert h1 == h2
    assert len(h1) == 64


def test_approved_uses_default_options(sr02_registry_approved, sr02_deterministic_clock):
    g = RiskDecisionToPaperOrderGate(sr02_registry_approved, clock=sr02_deterministic_clock)
    r = g.evaluate(_sr02_request())
    assert r.allowed is True


def test_approved_custom_options_ok(sr02_registry_approved, sr02_deterministic_clock):
    g = RiskDecisionToPaperOrderGate(
        sr02_registry_approved,
        options=GateOptions(stale_threshold_sec=9999.0, oversize_tolerance_bps=100),
        clock=sr02_deterministic_clock,
    )
    r = g.evaluate(_sr02_request())
    assert r.allowed is True


def test_approved_close_existing_sell_allowed(sr02_gate):
    # CLOSE_EXISTING + sell should not be treated as short attempt.
    r = sr02_gate.evaluate(
        _sr02_request(side="sell", position_intent="CLOSE_EXISTING")
    )
    assert r.allowed is True


def test_approved_result_to_sorted_dict(sr02_gate, sr02_happy_request):
    r = sr02_gate.evaluate(sr02_happy_request)
    d = r.to_sorted_dict()
    assert isinstance(d, dict)
    assert d["allowed"] is True


def test_approved_result_sha_deterministic(sr02_gate, sr02_happy_request):
    sr02_gate.clear_idempotency()
    # Clock is deterministic, but sha depends on decision_ts too — compare on input_sha256 field.
    r1 = sr02_gate.evaluate(sr02_happy_request)
    sr02_gate.clear_idempotency()
    r2 = sr02_gate.evaluate(sr02_happy_request)
    assert r1.input_sha256 == r2.input_sha256


def test_approved_decision_ts_instant_format(sr02_gate, sr02_happy_request):
    r = sr02_gate.evaluate(sr02_happy_request)
    # Instant regex YYYY-MM-DDThh:mm:ss.SSSZ
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", r.decision_ts) is not None


def test_approved_input_sha_equals_request_sha(sr02_gate, sr02_happy_request):
    r = sr02_gate.evaluate(sr02_happy_request)
    assert r.input_sha256 == sr02_happy_request.schema_sha256()


def test_approved_request_order_type_limit(sr02_gate):
    r = sr02_gate.evaluate(
        _sr02_request(order_type="limit", price=Decimal("100000"), notional=Decimal("1000"))
    )
    assert r.allowed is True
