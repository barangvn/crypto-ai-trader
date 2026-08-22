"""S-CON-02B RiskDecision + nested helpers — 15+ contract tests.

Story coverage: C-06 → C-12 Acceptance Criteria.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    ContractSchemaError,
    KillSwitchStateSpec,
    LimitsSnapshot,
    PositionSizingSpec,
    RiskDecision,
    RiskDecisionResult,
    Symbol,
    format_instant,
)


# ---------------------------------------------------------------------------
# Test helper — valid RiskDecision factory with overrides
# ---------------------------------------------------------------------------


def _make_valid_limits() -> LimitsSnapshot:
    return LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("100000"),
        max_daily_loss_notional=Decimal("-500"),
        max_drawdown_pct=0.2,
        max_consecutive_losses=5,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("50000"),
        current_daily_pnl=Decimal("-120"),
        current_drawdown_pct=0.05,
        current_consecutive_losses=2,
    )


def _make_valid_kill() -> KillSwitchStateSpec:
    return KillSwitchStateSpec(
        global_kill=False,
        per_symbol=dict([(Symbol("BTC_USDT"), False)]),
        reason=None,
    )


def _make_valid_sizing(decision: str) -> PositionSizingSpec:
    if decision == "approved":
        return PositionSizingSpec(
            base_qty=Decimal("0.5"),
            quote_qty=Decimal("30000"),
            notional=Decimal("30000"),
            method="fixed_notional",
        )
    else:
        return PositionSizingSpec(
            base_qty=None,
            quote_qty=None,
            notional=Decimal("0"),
            method="rejected_block",
        )


def _make_valid_rd(decision: str = "approved", **overrides) -> RiskDecision:
    """Valid RiskDecision with ALL required fields; overrides applied last."""
    reason_codes: list[str] = [] if decision == "approved" else ["REJECT_REASON"]
    fields: dict = dict(
        decision_id="01J5XYZ1234567890ABCDEFGH",
        decision=decision,
        reason_codes=reason_codes,
        position_sizing=_make_valid_sizing(decision),
        limits_snapshot=_make_valid_limits(),
        kill_switch_state=_make_valid_kill(),
        valid_until=format_instant(),
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        stop_loss_ref=None,
        take_profit_ref=None,
        approval_chain=[],
    )
    fields.update(overrides)
    return RiskDecision(**fields)


# ---------------------------------------------------------------------------
# C-06: decision enum — approved=ok, rejected=ok; "partial" → ContractSchemaError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c06_decision_approved_is_valid() -> None:
    rd = _make_valid_rd(decision="approved")
    assert rd.decision == RiskDecisionResult.APPROVED
    assert rd.decision.value == "approved"


@pytest.mark.contract
def test_c06_decision_rejected_is_valid() -> None:
    rd = _make_valid_rd(decision="rejected")
    assert rd.decision == RiskDecisionResult.REJECTED
    assert rd.decision.value == "rejected"


@pytest.mark.contract
def test_c06_decision_partial_string_raises_contract_schema_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(decision="partial")
    assert "approved|rejected" in str(exc_info.value)
    assert not isinstance(exc_info.value, ValueError) or type(exc_info.value) is ContractSchemaError


# ---------------------------------------------------------------------------
# C-07: LimitsSnapshot.max_leverage_allowed=2 → ERROR (v1 hard boundary)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c07_limits_max_leverage_2_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("100000"),
            max_daily_loss_notional=Decimal("-500"),
            max_drawdown_pct=0.2,
            max_consecutive_losses=5,
            max_leverage_allowed=2,
            current_exposure_notional=Decimal("50000"),
            current_daily_pnl=Decimal("-120"),
            current_drawdown_pct=0.05,
            current_consecutive_losses=2,
        )
    assert "max_leverage_allowed MUST be 1" in str(exc_info.value)


@pytest.mark.contract
def test_c07b_limits_max_leverage_1_ok() -> None:
    ls = LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("100000"),
        max_daily_loss_notional=Decimal("-500"),
        max_drawdown_pct=0.2,
        max_consecutive_losses=5,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("50000"),
        current_daily_pnl=Decimal("-120"),
        current_drawdown_pct=0.05,
        current_consecutive_losses=2,
    )
    assert ls.max_leverage_allowed == 1


# ---------------------------------------------------------------------------
# C-08: global_kill=True + approved → ContractSchemaError (AD-11 fail-closed)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c08_global_kill_true_plus_approved_raises_error() -> None:
    bad_kill = KillSwitchStateSpec(
        global_kill=True,
        per_symbol=dict([(Symbol("BTC_USDT"), False)]),
        reason="TEST_GLOBAL_KILL",
    )
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(decision="approved", kill_switch_state=bad_kill)
    assert "global_kill=True iken decision='approved' OLAMAZ" in str(exc_info.value)


@pytest.mark.contract
def test_c08b_global_kill_true_plus_rejected_ok() -> None:
    bad_kill = KillSwitchStateSpec(
        global_kill=True,
        per_symbol=dict([(Symbol("BTC_USDT"), False)]),
        reason="TEST_GLOBAL_KILL",
    )
    rd = _make_valid_rd(decision="rejected", kill_switch_state=bad_kill)
    assert rd.decision == RiskDecisionResult.REJECTED
    assert rd.kill_switch_state.global_kill is True


# ---------------------------------------------------------------------------
# C-09: approved + notional=0 → ERROR; rejected + notional>0 → ERROR
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c09_approved_with_zero_notional_raises_error() -> None:
    bad_sizing = PositionSizingSpec(
        base_qty=None,
        quote_qty=None,
        notional=Decimal("0"),
        method="fixed_notional",
    )
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(decision="approved", position_sizing=bad_sizing)
    assert "approved: position_sizing.notional must be > 0" in str(exc_info.value)


@pytest.mark.contract
def test_c09b_rejected_with_nonzero_notional_raises_error() -> None:
    bad_sizing = PositionSizingSpec(
        base_qty=Decimal("0.1"),
        quote_qty=Decimal("5000"),
        notional=Decimal("5000"),
        method="rejected_block",
    )
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(decision="rejected", position_sizing=bad_sizing)
    assert "rejected: position_sizing.notional must be exactly Decimal('0')" in str(exc_info.value)


# ---------------------------------------------------------------------------
# C-10: limits_snapshot missing field (no max_drawdown_pct) → TypeError/ContractSchemaError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c10_limits_missing_field_raises_error() -> None:
    with pytest.raises((TypeError, ContractSchemaError)):
        LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("100000"),
            max_daily_loss_notional=Decimal("-500"),
            # max_drawdown_pct EKSİK
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("50000"),
            current_daily_pnl=Decimal("-120"),
            current_drawdown_pct=0.05,
            current_consecutive_losses=2,
        )


# ---------------------------------------------------------------------------
# C-11: valid_until = "bad-instant-format" → ContractSchemaError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c11_valid_until_bad_format_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(valid_until="bad-instant-format")
    assert "valid_until invalid Instant format" in str(exc_info.value)


# ---------------------------------------------------------------------------
# C-12: LimitsSnapshot.max_drawdown_pct=1.5 → ERROR ([0,1] range)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_c12_limits_max_drawdown_1_5_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("100000"),
            max_daily_loss_notional=Decimal("-500"),
            max_drawdown_pct=1.5,
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("50000"),
            current_daily_pnl=Decimal("-120"),
            current_drawdown_pct=0.05,
            current_consecutive_losses=2,
        )
    assert "out of [0.0, 1.0] range" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 11: 10x determinism — same input → 10x schema_sha256() identical
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_risk_decision_10x_determinism_schema_sha256() -> None:
    fixed_instant = "2026-08-15T12:00:00.000Z"
    rd = _make_valid_rd(
        decision="approved",
        valid_until=fixed_instant,
        decision_id="01J5XYZ1234567890ABCDEFGH",
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        position_sizing=PositionSizingSpec(
            base_qty=Decimal("0.5"),
            quote_qty=Decimal("30000"),
            notional=Decimal("30000"),
            method="fixed_notional",
        ),
        limits_snapshot=LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("100000"),
            max_daily_loss_notional=Decimal("-500"),
            max_drawdown_pct=0.2,
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("50000"),
            current_daily_pnl=Decimal("-120"),
            current_drawdown_pct=0.05,
            current_consecutive_losses=2,
        ),
        kill_switch_state=KillSwitchStateSpec(
            global_kill=False,
            per_symbol=dict([(Symbol("BTC_USDT"), False)]),
            reason=None,
        ),
        reason_codes=[],
        stop_loss_ref=None,
        take_profit_ref=None,
        approval_chain=[],
    )
    digests = [rd.schema_sha256() for _ in range(10)]
    first = digests[0]
    assert all(d == first for d in digests)
    assert len(first) == 64


# ---------------------------------------------------------------------------
# 12: to_sorted_dict() — SORTED top-level keys
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_risk_decision_to_sorted_dict_keys_sorted() -> None:
    rd = _make_valid_rd(decision="approved")
    d = rd.to_sorted_dict()
    keys = list(d.keys())
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# 13: correlation/causation — correlation_id="" (too short) → ContractSchemaError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_13_correlation_id_empty_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_rd(correlation_id="")
    assert "correlation_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 14: Nested PositionSizingSpec — base_qty/quote_qty both=None OK; one set OK
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_14_sizing_both_base_and_quote_none_ok() -> None:
    ps = PositionSizingSpec(
        base_qty=None,
        quote_qty=None,
        notional=Decimal("1000"),
        method="notional_only",
    )
    assert ps.base_qty is None
    assert ps.quote_qty is None
    assert ps.notional == Decimal("1000")


@pytest.mark.contract
def test_14_sizing_only_base_set_ok() -> None:
    ps = PositionSizingSpec(
        base_qty=Decimal("0.1"),
        quote_qty=None,
        notional=Decimal("5000"),
        method="base_qty_only",
    )
    assert ps.base_qty == Decimal("0.1")
    assert ps.quote_qty is None


@pytest.mark.contract
def test_14_sizing_only_quote_set_ok() -> None:
    ps = PositionSizingSpec(
        base_qty=None,
        quote_qty=Decimal("5000"),
        notional=Decimal("5000"),
        method="quote_qty_only",
    )
    assert ps.base_qty is None
    assert ps.quote_qty == Decimal("5000")


# ---------------------------------------------------------------------------
# 15: KillSwitchStateSpec.per_symbol invalid symbol (lowercase) → ContractSchemaError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_15_kill_per_symbol_lowercase_invalid_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        KillSwitchStateSpec(
            global_kill=False,
            per_symbol=dict([("btc_usdt", False)]),
            reason=None,
        )
    assert "invalid symbol" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Bonus: CONTRACT_VERSION importable and usable
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_contract_version_importable() -> None:
    assert isinstance(CONTRACT_VERSION, str)
    parts = CONTRACT_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
