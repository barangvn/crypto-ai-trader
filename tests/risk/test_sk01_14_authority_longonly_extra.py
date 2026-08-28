"""T14 — AD-11 Authority + Long-only enforcement + Leverage=1 + extra sizing boundary = 14 tests.

Goal: bring total tests/risk above 220 and cover remaining AC gaps.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.contracts.risk import (
    KillSwitchStateSpec,
    LimitsSnapshot,
    RiskDecision,
    RiskDecisionResult,
)
from app.risk import IndependentRiskEngine, evaluate_risk


def _build_lev_bypass(**overrides):
    """Build LimitsSnapshot bypassing __post_init__ (allows leverage!=1)."""
    raw = object.__new__(LimitsSnapshot)
    defaults = dict(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("100000"),
        max_daily_loss_notional=Decimal("1000"),
        max_drawdown_pct=0.20,
        max_consecutive_losses=10,
        max_leverage_allowed=1,
        max_default_order_notional=Decimal("5000"),
        current_exposure_notional=Decimal("0"),
        current_daily_pnl=Decimal("0"),
        current_drawdown_pct=0.0,
        current_consecutive_losses=0,
    )
    for k, v in {**defaults, **overrides}.items():
        object.__setattr__(raw, k, v)
    return raw


class TestT14Authority:
    """AD-11: Only app/risk produces APPROVED decisions."""

    def test_t14_rd_approved_requires_notional_gt_zero(self, happy_path_tuple):
        """Contract invariant: APPROVED ⇒ notional > 0."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        rd = evaluate_risk(opp, sig, reg, pv, lim, ctx)
        assert rd.decision == RiskDecisionResult.APPROVED
        assert rd.position_sizing.notional > Decimal("0")

    def test_t14_rd_rejected_has_notional_exactly_zero(self, happy_path_tuple, engine):
        """Contract invariant: REJECTED ⇒ notional == 0 (exact Decimal)."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        ctx2 = replace(ctx, emergency_stop_active=True)
        rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
        assert rd.decision == RiskDecisionResult.REJECTED
        assert rd.position_sizing.notional == Decimal("0")
        assert rd.position_sizing.base_qty == Decimal("0")
        assert rd.position_sizing.quote_qty == Decimal("0")

    def test_t14_rd_rejected_method_label(self, happy_path_tuple, engine):
        """REJECTED sizing method must indicate rejection source."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        ctx2 = replace(ctx, emergency_stop_active=True)
        rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
        assert rd.decision == RiskDecisionResult.REJECTED
        assert "reject" in rd.position_sizing.method.lower()

    @pytest.mark.parametrize("lev_val", [0.5, 1.5, 2, 3, 5, 10])
    def test_t14_leverage_ne_1_rejects(self, lev_val, happy_path_tuple, engine):
        """LimitsSnapshot.max_leverage_allowed != 1 → REJECTED (AD-08 / C10)."""
        opp, sig, reg, pv, _lim, ctx = happy_path_tuple
        bad_lim = _build_lev_bypass(max_leverage_allowed=lev_val)
        rd = engine.evaluate(opp, sig, reg, pv, bad_lim, ctx)
        assert rd.decision == RiskDecisionResult.REJECTED
        assert rd.position_sizing.notional == Decimal("0")
        reasons = set(rd.reason_codes)
        assert (
            "LIMITS_SNAPSHOT_INVALID" in reasons
            or "LEVERAGE_NOT_EQUAL_ONE" in reasons
            or "INTERNAL_CALCULATION_ERROR" in reasons
        ), reasons


class TestT14LongOnly:
    """C14 direction enforcement: long-only v1."""

    def test_t14_long_direction_approved(self, happy_path_tuple, engine):
        """SignalDirection.LONG still happy path APPROVED (ensure still unchanged)."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
        assert rd.decision == RiskDecisionResult.APPROVED

    @pytest.mark.parametrize("bad_dir", ["flat", "hold", "FLAT", "HOLD", "short", "SHORT"])
    def test_t14_nonlong_direction_rejects(self, bad_dir, happy_path_tuple, engine):
        """Any non-long direction → REJECTED (C14)."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        # bypass StrategySignal.__post_init__ if it validates directions
        from dataclasses import fields as _f
        raw_sig = object.__new__(type(sig))
        for f in _f(type(sig)):
            object.__setattr__(raw_sig, f.name, getattr(sig, f.name))
        object.__setattr__(raw_sig, "direction", bad_dir)
        rd = engine.evaluate(opp, raw_sig, reg, pv, lim, ctx)
        assert rd.decision == RiskDecisionResult.REJECTED


class TestT14SizingExtra:
    """Extra sizing boundary edge cases (epsilon / zero headroom / empty cash)."""

    def test_t14_no_cash_sizing_zero(self, happy_path_tuple, engine):
        """cash_quote=0 → sizing notional=0 (L4 headroom=0)."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        pv2 = replace(pv, cash_quote=Decimal("0"))
        rd = engine.evaluate(opp, sig, reg, pv2, lim, ctx)
        # sizing L4 min = 0, so notional = 0 regardless; per contract either path OK
        assert rd.position_sizing.notional == Decimal("0")

    def test_t14_exposure_at_max_sizing_zero(self, happy_path_tuple, engine):
        """current_exposure == max_exposure → headroom 0 → sizing notional=0."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        total_lim = lim.max_exposure_notional_total
        lim2 = replace(lim, current_exposure_notional=total_lim)
        rd = engine.evaluate(opp, sig, reg, pv, lim2, ctx)
        assert rd.position_sizing.notional == Decimal("0")

    def test_t14_dd_headroom_zero_sizing_zero(self, happy_path_tuple, engine):
        """cur_drawdown == max_drawdown → dd_headroom == 0 → sizing notional=0."""
        opp, sig, reg, pv, lim, ctx = happy_path_tuple
        max_dd = lim.max_drawdown_pct
        lim2 = replace(lim, current_drawdown_pct=max_dd)
        rd = engine.evaluate(opp, sig, reg, pv, lim2, ctx)
        assert rd.position_sizing.notional == Decimal("0")
