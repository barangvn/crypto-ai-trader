"""S-RSK-01 Independent Risk Engine — fail-closed, side-effect free, stdlib only.

Public exports:
  - IndependentRiskEngine          (single typed evaluator)
  - RiskEngineDefaults             (frozen fixture/production defaults)
  - RiskScoreWeights               (frozen R01..R20 20-component weights total=1.0)
  - RiskContext                    (frozen evaluation ctx: killswitch, thresholds, windows)
  - RiskEngineResult               (internal intermediary; not a contract)
  - evaluate_risk                  (function shortcut — pure)

Hard invariants (read-only / fail-closed):
  - AD-11: ONLY this module produces approved RiskDecision.
  - AD-19: Every exception / malformed input -> RiskDecisionResult.REJECTED.
  - AD-20: same inputs (typed, comparable) -> same sha256 over 10 runs.
  - CAP-1: no `if run_mode` / `if source_type` branches anywhere.
  - CAP-2: QualityFlags consumed READ-ONLY; no validator import/call.
  - CAP-4 setup: produces the typed RiskDecision that downstream PaperOrder
    gate will accept/reject. PaperOrder itself is OOS for this story.
  - NO network, NO db, NO exchange, NO credentials. stdlib-only.
  - v1: long only; max_leverage_allowed MUST equal 1 (checked via LimitsSnapshot).
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_DOWN
from typing import Any, Iterable

from app.contracts.canonical import QualityFlags
from app.contracts.exceptions import ContractSchemaError
from app.contracts.opportunity import OpportunityScore
from app.contracts.portfolio import PortfolioSnapshot
from app.contracts.regime import MarketRegime, MarketRegimeState, REGIME_KEYS
from app.contracts.risk import (
    KillSwitchStateSpec,
    LimitsSnapshot,
    PositionSizingSpec,
    RiskDecision,
    RiskDecisionResult,
)
from app.contracts.strategy import SignalDirection, StrategySignal
from app.contracts.types import Instant, Symbol, format_instant, validate_symbol_canonical

# ---------------------------------------------------------------------------
# Internal helpers — simple, stdlib-only
# ---------------------------------------------------------------------------

def _ulidish_new() -> str:
    """128-bit random id encoded as 32 hex chars (>= 8 alnum, regex compatible)."""
    return uuid.uuid4().hex


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _instant_now() -> Instant:
    """UTC ISO-8601 Instant with ms precision and Z suffix."""
    from datetime import datetime, timezone
    return format_instant(datetime.now(timezone.utc))


def _instant_add_ms(ts: str, ms: int) -> Instant:
    from datetime import datetime, timezone
    base = ts[:-1]
    if "." in base:
        main, frac = base.split(".", 1)
    else:
        main = base
        frac = "000"
    try:
        dt = datetime.strptime(main, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        frac_ms = int((frac + "000")[:3])
        epoch_s = dt.timestamp() + frac_ms / 1000.0
        epoch_s += ms / 1000.0
        return format_instant(datetime.fromtimestamp(epoch_s, tz=timezone.utc))
    except Exception:
        return ts


def _instant_diff_ms(a: str, b: str) -> float:
    """Return (a - b) in milliseconds. ISO Z format is ms-precision."""
    from datetime import datetime, timezone

    def _parse(x: str) -> float:
        base = x[:-1]
        if "." in base:
            main, frac = base.split(".", 1)
        else:
            main = base
            frac = "000"
        dt = datetime.strptime(main, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.timestamp() + int((frac + "000")[:3]) / 1000.0

    try:
        return (_parse(a) - _parse(b)) * 1000.0
    except Exception:
        return float("inf")


# ---------------------------------------------------------------------------
# 20 Risk component weights — sum = 1.0000 (fixture defaults; ADN open)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskScoreWeights:
    """Sum = 1.000 exactly (within float repr). Fixture defaults only."""

    w_quality:           float = 0.110  # R01
    w_spread:            float = 0.070  # R02
    w_expected_edge:     float = 0.080  # R03
    w_cost_ratio:        float = 0.060  # R04
    w_opp_conf:          float = 0.070  # R05
    w_sig_strength:      float = 0.030  # R06
    w_sig_conf:          float = 0.060  # R07
    w_strat_regime:      float = 0.080  # R08
    w_regime_conf:       float = 0.040  # R09
    w_regime_type:       float = 0.050  # R10
    w_drawdown:          float = 0.050  # R11
    w_daily_loss:        float = 0.050  # R12
    w_consec_losses:     float = 0.030  # R13
    w_exposure_util:     float = 0.040  # R14
    w_concentration:     float = 0.040  # R15
    w_cash_util:         float = 0.030  # R16
    w_budget_headroom:   float = 0.030  # R17
    w_dup_cooldown:      float = 0.030  # R18
    w_slip_lat_model:    float = 0.020  # R19
    w_sig_score_div:     float = 0.030  # R20

    def as_tuple_ordered(self) -> tuple[tuple[str, float], ...]:
        return tuple(vars(self).items())


DEFAULT_WEIGHTS = RiskScoreWeights()


# ---------------------------------------------------------------------------
# Regime x Strategy penalty matrix (R08) — fixture defaults only (ADN open)
# ---------------------------------------------------------------------------

STRATEGY_REGIME_PENALTY: dict[str, dict[str, float]] = {
    "trend": {
        "bull": 0.05,
        "bear": 0.65,
        "sideways": 0.60,
        "high_volatility": 0.75,
        "low_volatility": 0.30,
        "transition_uncertain": 0.55,
    },
    "momentum": {
        "bull": 0.15,
        "bear": 0.65,
        "sideways": 0.50,
        "high_volatility": 0.70,
        "low_volatility": 0.40,
        "transition_uncertain": 0.55,
    },
    # fallback for unknown strategies
    "_default_": {
        r: 0.60 for r in REGIME_KEYS
    },
}
for _fallback_key in STRATEGY_REGIME_PENALTY:
    for _rk in REGIME_KEYS:
        STRATEGY_REGIME_PENALTY[_fallback_key].setdefault(_rk, 0.60)


REGIME_TYPE_RISK: dict[str, float] = {
    "bull": 0.30,
    "bear": 0.55,
    "sideways": 0.35,
    "high_volatility": 0.90,
    "low_volatility": 0.10,
    "transition_uncertain": 0.70,
}
for _rk in REGIME_KEYS:
    REGIME_TYPE_RISK.setdefault(_rk, 0.70)


# ---------------------------------------------------------------------------
# RiskContext — frozen evaluation context (fixture override via replace())
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskEngineDefaults:
    stale_portfolio_view_threshold_ms: int = 300_000  # 5 minutes
    stale_data_reject_closed: bool = True            # C08 default reject
    min_positive_net_edge_bps: float = 0.0
    score_valid_until_ms: int = 300_000               # 5 minutes
    signal_valid_until_ms: int = 300_000              # 5 minutes
    duplicate_decision_window_ms: int = 60_000        # 1 minute
    cooldown_window_ms: int = 120_000                 # 2 minutes
    decision_valid_until_ms: int = 30_000             # 30 seconds
    max_default_order_notional_quote: Decimal = Decimal("5000")
    drawdown_risk_budget_fraction: float = 0.80       # L5 multiplier
    concentration_diversifier_n: float = 3.0          # R15 multiplier
    spread_bps_model_default: float = 25.0            # for R02 denominator
    slippage_bps_default: float = 10.0                # R19
    latency_bps_default: float = 10.0                 # R19
    spread_abnormal_threshold_bps: float = 100.0      # fallback for abnormal_spread


DEFAULTS = RiskEngineDefaults()


@dataclass(frozen=True)
class RiskContext:
    kill_switch: KillSwitchStateSpec
    emergency_stop_active: bool = False
    as_of: Instant | None = None           # None → _instant_now()
    symbol_current_exposure_notional: Decimal | None = None  # for R15 concentration
    duplicate_tracker: dict[tuple[str, Symbol, str], Instant] = field(default_factory=dict)
    cooldown_tracker: dict[tuple[Symbol, str], Instant] = field(default_factory=dict)
    risk_score_threshold_approval: float = 0.40
    risk_score_threshold_observation: float = 0.70
    weights: RiskScoreWeights = DEFAULT_WEIGHTS
    defaults: RiskEngineDefaults = DEFAULTS
    symbol_price_ref: Decimal | None = None  # for base_qty calc (entry price)
    feature_spread_bps_probe: float | None = None  # for R02 fallback quality spread


# ---------------------------------------------------------------------------
# Internal intermediary
# ---------------------------------------------------------------------------

@dataclass
class RiskEngineResult:
    decision: RiskDecisionResult
    reason_codes: list[str]
    position_sizing: PositionSizingSpec
    approval_chain: list[str]
    risk_weighted_sum: float
    risk_quality_adjusted: float


# ---------------------------------------------------------------------------
# Independent Risk Engine (pure, side-effect free; no bus publish inside)
# ---------------------------------------------------------------------------

class IndependentRiskEngine:
    """Deterministic fail-closed pure evaluator.

    Signature:
      evaluate(opp, sig, regime, portfolio_view, limits, ctx) -> RiskDecision

    Guarantees (no exceptions propagate to caller; fail-closed outer):
      - If anything raises inside evaluation -> rejected with INTERNAL_CALCULATION_ERROR.
      - Output always a valid RiskDecision.
    """

    def __init__(
        self,
        weights: RiskScoreWeights | None = None,
        defaults: RiskEngineDefaults | None = None,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS
        self._defaults = defaults or DEFAULTS

    # --------------------------------------------------------------
    # Public API — outer fail-closed safety
    # --------------------------------------------------------------
    def evaluate(
        self,
        opp_score: OpportunityScore,
        signal: StrategySignal,
        regime: MarketRegime,
        portfolio_view: PortfolioSnapshot | None,
        limits: LimitsSnapshot,
        ctx: RiskContext,
    ) -> RiskDecision:
        try:
            return self._evaluate_inner(opp_score, signal, regime, portfolio_view, limits, ctx)
        except (ContractSchemaError, TypeError, ValueError, AttributeError, KeyError, IndexError, ZeroDivisionError, OverflowError):
            return self._build_rejected_safe(
                opp_score=opp_score,
                signal=signal,
                regime=regime,
                portfolio_view=portfolio_view,
                limits=limits,
                ctx=ctx,
                reason_codes=["INTERNAL_CALCULATION_ERROR"],
                as_of=None,
            )
        except Exception:
            return self._build_rejected_safe(
                opp_score=opp_score,
                signal=signal,
                regime=regime,
                portfolio_view=portfolio_view,
                limits=limits,
                ctx=ctx,
                reason_codes=["INTERNAL_CALCULATION_ERROR"],
                as_of=None,
            )

    # --------------------------------------------------------------
    # Inner evaluation (may raise; outer catches -> fail closed)
    # --------------------------------------------------------------
    def _evaluate_inner(
        self,
        opp_score: OpportunityScore,
        signal: StrategySignal,
        regime: MarketRegime,
        portfolio_view: PortfolioSnapshot | None,
        limits: LimitsSnapshot,
        ctx: RiskContext,
    ) -> RiskDecision:
        # Inputs: basic typed / invariant checks (limits validity re-verified)
        if not isinstance(opp_score, OpportunityScore):
            raise ContractSchemaError("opp_score must be OpportunityScore")
        if not isinstance(signal, StrategySignal):
            raise ContractSchemaError("signal must be StrategySignal")
        if not isinstance(regime, MarketRegime):
            raise ContractSchemaError("regime must be MarketRegime")
        if not isinstance(limits, LimitsSnapshot):
            raise ContractSchemaError("limits must be LimitsSnapshot")
        if not isinstance(ctx, RiskContext):
            raise ContractSchemaError("ctx must be RiskContext")

        as_of = ctx.as_of or _instant_now()

        # LimitsSnapshot.__post_init__ already enforces invariants; call explicitly to ensure
        # LimitsSnapshot(...) was already validated. This is effectively a double-check,
        # not a new validator — but LimitsSnapshot.__post_init__ already runs on construction.
        # For safety, attempt to round-trip -> if __post_init__ raised, caller's limits object
        # would already have been invalid. Skip re-construction; just check max_leverage_allowed==1.
        if limits.max_leverage_allowed != 1:
            # Should not be possible because LimitsSnapshot raises ContractSchemaError at construction.
            return self._build_rejected_safe(
                opp_score=opp_score, signal=signal, regime=regime,
                portfolio_view=portfolio_view, limits=limits, ctx=ctx,
                reason_codes=["LIMITS_SNAPSHOT_INVALID"],
                as_of=as_of,
            )

        # Symbol match (deterministic): symbol consistency required
        sym = opp_score.symbol_ref
        if not validate_symbol_canonical(sym):
            return self._build_rejected_safe(
                opp_score=opp_score, signal=signal, regime=regime,
                portfolio_view=portfolio_view, limits=limits, ctx=ctx,
                reason_codes=["SYMBOL_INVALID"],
                as_of=as_of,
            )

        # QualityFlags reference (immutable upstream — not mutated, not re-validated)
        qf: QualityFlags | None = opp_score.quality_flags
        q = qf if qf is not None else QualityFlags()

        # --------------------------------------------------------------
        # 20 Checks (C01..C20 + few extra quality sub-flags)
        # --------------------------------------------------------------
        reasons: list[str] = []
        chain: list[str] = []

        # C01 global kill switch
        if ctx.kill_switch.global_kill:
            reasons.append("KILL_SWITCH_GLOBAL_ACTIVE")
            chain.append("C01_REJECT")
        else:
            chain.append("C01_PASS")

        # C02 emergency stop
        if ctx.emergency_stop_active:
            reasons.append("EMERGENCY_STOP_ACTIVE")
            chain.append("C02_REJECT")
        else:
            chain.append("C02_PASS")

        # C03 per-symbol kill
        if sym in ctx.kill_switch.per_symbol and ctx.kill_switch.per_symbol[sym]:
            reasons.append("KILL_SWITCH_SYMBOL_ACTIVE")
            chain.append("C03_REJECT")
        else:
            chain.append("C03_PASS")

        # C04 limits validity (already 100% covered by LimitsSnapshot __post_init__ except re-check)
        # Just mark chain pass
        chain.append("C04_PASS")

        # C05 portfolio missing / stale
        if portfolio_view is None:
            reasons.append("PORTFOLIO_VIEW_MISSING")
            chain.append("C05_REJECT")
        else:
            if not isinstance(portfolio_view, PortfolioSnapshot):
                reasons.append("PORTFOLIO_VIEW_MISSING")
                chain.append("C05_REJECT")
            else:
                delta = _instant_diff_ms(as_of, portfolio_view.ts)
                if delta > ctx.defaults.stale_portfolio_view_threshold_ms:
                    reasons.append("PORTFOLIO_VIEW_STALE")
                    chain.append("C05_REJECT")
                else:
                    chain.append("C05_PASS")

        # C06 quality invalid
        if getattr(q, "invalid", False):
            reasons.append("QUALITY_INVALID")
            chain.append("C06_REJECT")
        else:
            chain.append("C06_PASS")

        # C07 quality quarantined
        if getattr(q, "quarantined", False):
            reasons.append("QUALITY_QUARANTINED")
            chain.append("C07_REJECT")
        else:
            chain.append("C07_PASS")

        # C08 quality stale (fail-closed default stale_data_reject_closed=True)
        if getattr(q, "stale", False):
            if ctx.defaults.stale_data_reject_closed:
                reasons.append("QUALITY_STALE")
                chain.append("C08_REJECT")
            else:
                chain.append("C08_PASS_PENALTIED")
        else:
            chain.append("C08_PASS")

        # C09 quality degraded (NOT a direct reject — scoring penalty only; but note reason)
        # Append informational reason only if degraded AND no prior hard fail: always append as code
        # (informational; decision still continues). We'll mark chain but no REJECT.
        if getattr(q, "degraded", False):
            reasons.append("QUALITY_DEGRADED_PENALTY")
            chain.append("C09_PENALTY")
        else:
            chain.append("C09_PASS")

        # C10 quality missing / duplicate / out_of_order (informational penalty — not hard fail
        # by default — but append penalty reason if any)
        has_seq_issue = bool(
            getattr(q, "missing", False)
            or getattr(q, "duplicate", False)
            or getattr(q, "out_of_order", False)
        )
        if has_seq_issue:
            reasons.append("QUALITY_SEQUENCE_ISSUES")
            chain.append("C10_PENALTY")
        else:
            chain.append("C10_PASS")

        # C11 invalid opportunity score (range, actionable, expected_edge present)
        if not (0.0 <= opp_score.score_total <= 1.0):
            reasons.append("OPPORTUNITY_INVALID")
            chain.append("C11_REJECT")
        elif not opp_score.actionable:
            reasons.append("OPPORTUNITY_NOT_ACTIONABLE")
            chain.append("C11_REJECT")
        elif opp_score.expected_edge_bps is None:
            reasons.append("OPPORTUNITY_EXPECTED_EDGE_MISSING")
            chain.append("C11_REJECT")
        else:
            chain.append("C11_PASS")

        # C12 net-of-cost edge positive
        if opp_score.expected_edge_bps is None or opp_score.expected_edge_bps <= ctx.defaults.min_positive_net_edge_bps:
            reasons.append("EXPECTED_NET_EDGE_NON_POSITIVE")
            chain.append("C12_REJECT")
        else:
            chain.append("C12_PASS")

        # C13 invalid strategy signal (direction enum, strength/confidence bounds -> covered by
        # StrategySignal.__post_init__. Just check type + direction LONG-ONLY base check)
        # We additionally check direction as a soft C13 chain pass.
        if signal.direction not in (SignalDirection.LONG, SignalDirection.FLAT, SignalDirection.HOLD):
            # Impossible via enum; defensive
            reasons.append("SIGNAL_INVALID")
            chain.append("C13_REJECT")
        else:
            chain.append("C13_PASS")

        # C14 direction long-only (FLAT / HOLD -> decision cannot be approved)
        if signal.direction == SignalDirection.FLAT:
            reasons.append("SIGNAL_DIRECTION_FLAT")
            chain.append("C14_REJECT")
        elif signal.direction == SignalDirection.HOLD:
            reasons.append("SIGNAL_DIRECTION_HOLD")
            chain.append("C14_REJECT")
        elif signal.direction == SignalDirection.LONG:
            chain.append("C14_PASS")
        else:
            # SHORT is not a value in SignalDirection (v1) but defensive here
            reasons.append("SIGNAL_DIRECTION_NOT_LONG")
            chain.append("C14_REJECT")

        # C15 score / signal expiry
        opp_age_ms = _instant_diff_ms(as_of, opp_score.created_ts)
        if opp_age_ms > ctx.defaults.score_valid_until_ms:
            reasons.append("OPPORTUNITY_SCORE_EXPIRED")
            chain.append("C15_REJECT")
        sig_created_ts = None
        for _probe in ("created_ts", "generated_ts"):
            v = getattr(signal, _probe, None)
            if isinstance(v, str) and v.endswith("Z"):
                sig_created_ts = v
                break
        sig_age_ms = _instant_diff_ms(as_of, sig_created_ts) if sig_created_ts else 0.0
        if sig_created_ts and sig_age_ms > ctx.defaults.signal_valid_until_ms:
            reasons.append("SIGNAL_EXPIRED")
            chain.append("C15_REJECT")
        else:
            if "C15_REJECT" not in chain:
                chain.append("C15_PASS")

        # C16 duplicate decision window
        dup_key = (opp_score.correlation_id, sym, as_of[:-7])  # round to seconds
        last = ctx.duplicate_tracker.get(dup_key)
        if last is not None and _instant_diff_ms(as_of, last) <= ctx.defaults.duplicate_decision_window_ms:
            reasons.append("DUPLICATE_DECISION_WINDOW")
            chain.append("C16_REJECT")
        else:
            chain.append("C16_PASS")

        # C17 cooldown
        strategy_id = signal.strategy_id
        cool_key = (sym, strategy_id)
        last_cool = ctx.cooldown_tracker.get(cool_key)
        if last_cool is not None and _instant_diff_ms(as_of, last_cool) <= ctx.defaults.cooldown_window_ms:
            reasons.append("COOLDOWN_ACTIVE")
            chain.append("C17_REJECT")
        else:
            chain.append("C17_PASS")

        # C18/C19/C20 notional / exposure / limits-based: those rely on proposed sizing.
        # We'll compute proposed notional FIRST (min-of-5 using portfolio), then re-verify limits
        # against proposed and append REJECT if breach.

        # --------------------------------------------------------------
        # Preliminary sizing (L1..L5 min-of-5) — will adjust later if hard reject
        # --------------------------------------------------------------
        sizing = self._compute_sizing(opp_score, signal, portfolio_view, limits, ctx)
        proposed_notional = sizing.notional

        # C18 max position notional (inclusive boundary: limit breach at equality)
        if proposed_notional >= limits.max_position_notional_per_symbol and proposed_notional > Decimal("0"):
            reasons.append("LIMIT_MAX_POSITION_NOTIONAL")
            chain.append("C18_REJECT")
        else:
            chain.append("C18_PASS")

        # C19 max exposure total (inclusive boundary: exposure exactly at limit treated as breach)
        post_exposure = limits.current_exposure_notional + proposed_notional
        if post_exposure >= limits.max_exposure_notional_total and proposed_notional > Decimal("0"):
            reasons.append("LIMIT_MAX_EXPOSURE")
            chain.append("C19_REJECT")
        else:
            chain.append("C19_PASS")

        # C20 daily loss / drawdown / consecutive losses
        if limits.current_daily_pnl + (-limits.max_daily_loss_notional) < Decimal("0"):
            # current daily loss (negative) exceeds max allowed loss magnitude
            if limits.current_daily_pnl < Decimal("0") and (
                -limits.current_daily_pnl > limits.max_daily_loss_notional
            ):
                reasons.append("LIMIT_DAILY_LOSS_BREACH")
                chain.append("C20_REJECT_DAILY_LOSS")
        if limits.current_drawdown_pct > limits.max_drawdown_pct:
            reasons.append("LIMIT_MAX_DRAWDOWN_BREACH")
            chain.append("C20_REJECT_DRAWDOWN")
        if limits.current_consecutive_losses > limits.max_consecutive_losses:
            reasons.append("LIMIT_CONSECUTIVE_LOSSES_BREACH")
            chain.append("C20_REJECT_CONSEC")
        if not any(x.startswith("C20_REJECT") for x in chain):
            chain.append("C20_PASS")

        # --------------------------------------------------------------
        # Any hard reject reason? decision = REJECTED with zero sizing
        # --------------------------------------------------------------
        hard_reject = any(x.endswith("_REJECT") or x.startswith("C20_REJECT") for x in chain)

        risk_components: dict[str, float] = {}
        quality_mult = self._quality_multiplier(q)
        if not hard_reject:
            # 20 risk components (R01..R20) and weighted score (deterministic)
            risk_components = self._compute_risk_components(
                opp=opp_score,
                sig=signal,
                regime=regime,
                pv=portfolio_view,
                limits=limits,
                ctx=ctx,
                proposed_notional=proposed_notional,
                q=q,
            )
            weighted_sum = 0.0
            for (_, w_val), rk in zip(self._weights.as_tuple_ordered(), [
                "R01_quality","R02_spread","R03_edge","R04_cost","R05_opp_conf",
                "R06_sig_strength","R07_sig_conf","R08_strat_regime","R09_regime_conf",
                "R10_regime_type","R11_drawdown","R12_daily_loss","R13_consec_losses",
                "R14_exposure_util","R15_concentration","R16_cash_util",
                "R17_budget_headroom","R18_dup_cooldown","R19_slip_lat_model","R20_sig_score_div"
            ]):
                weighted_sum += risk_components.get(rk, 0.0) * w_val
            weighted_sum = _clip01(weighted_sum)
            adjusted = _clip01(weighted_sum * (1.0 / max(0.40, quality_mult)))
            # Threshold decision
            if adjusted < ctx.risk_score_threshold_approval:
                decision = RiskDecisionResult.APPROVED
            elif adjusted < ctx.risk_score_threshold_observation:
                decision = RiskDecisionResult.REJECTED
                reasons.append("RISK_SCORE_OBSERVATION_BAND")
            else:
                decision = RiskDecisionResult.REJECTED
                reasons.append("RISK_SCORE_TOO_HIGH")
        else:
            weighted_sum = 1.0
            adjusted = 1.0
            decision = RiskDecisionResult.REJECTED

        # If decision approved but proposed_notional <= 0: reject (L5 or cash/exposure empty)
        if decision == RiskDecisionResult.APPROVED and proposed_notional <= Decimal("0"):
            decision = RiskDecisionResult.REJECTED
            reasons.append("SIZING_PROPOSED_NOTIONAL_ZERO")
            hard_reject = True

        # --------------------------------------------------------------
        # Assemble PositionSizingSpec (zero if rejected)
        # --------------------------------------------------------------
        if decision == RiskDecisionResult.REJECTED:
            sizing = PositionSizingSpec(
                base_qty=Decimal("0"), quote_qty=Decimal("0"),
                notional=Decimal("0"), method="rejected_no_sizing",
            )
        else:
            sizing = self._compute_sizing(opp_score, signal, portfolio_view, limits, ctx)

        # --------------------------------------------------------------
        # Build RiskDecision (final)
        # --------------------------------------------------------------
        valid_until = _instant_add_ms(as_of, ctx.defaults.decision_valid_until_ms)
        return RiskDecision(
            decision_id=_ulidish_new(),
            decision=decision,
            reason_codes=sorted(set(reasons)),
            position_sizing=sizing,
            limits_snapshot=limits,
            kill_switch_state=ctx.kill_switch,
            valid_until=valid_until,
            correlation_id=opp_score.correlation_id,
            causation_id=opp_score.score_id,
            approval_chain=chain,
        )

    # --------------------------------------------------------------
    # Sizing (min-of-5) — deterministic, bounded, long-only, non-negative
    # --------------------------------------------------------------
    def _compute_sizing(
        self,
        opp: OpportunityScore,
        sig: StrategySignal,
        pv: PortfolioSnapshot | None,
        limits: LimitsSnapshot,
        ctx: RiskContext,
    ) -> PositionSizingSpec:
        eps = Decimal("1e-18")

        # L1 max position notional per symbol
        L1 = limits.max_position_notional_per_symbol
        # L2 exposure headroom
        head = limits.max_exposure_notional_total - limits.current_exposure_notional
        if head < Decimal("0"):
            head = Decimal("0")
        L2 = head
        # L3 default max order notional
        L3 = ctx.defaults.max_default_order_notional_quote
        # L4 available cash
        L4 = pv.cash_quote if isinstance(pv, PortfolioSnapshot) else Decimal("0")
        # L5 drawdown headroom notional
        try:
            dd_headroom = max(0.0, limits.max_drawdown_pct - limits.current_drawdown_pct)
            frac = float(dd_headroom) * float(ctx.defaults.drawdown_risk_budget_fraction)
            equity = pv.equity_quote if isinstance(pv, PortfolioSnapshot) else Decimal("0")
            L5 = (Decimal(str(max(0.0, frac))) * equity).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        except Exception:
            L5 = Decimal("0")

        notional = min(L1, L2, L3, L4, L5)
        if notional < Decimal("0"):
            notional = Decimal("0")

        price_ref = ctx.symbol_price_ref
        if price_ref is None and isinstance(sig.entry_price_ref, Decimal):
            price_ref = sig.entry_price_ref
        if price_ref is None:
            # fallback 1.0 — conservative
            price_ref = Decimal("1")
        if not isinstance(price_ref, Decimal) or isinstance(price_ref, bool):
            price_ref = Decimal("1")
        if price_ref <= eps:
            price_ref = Decimal("1")

        base_qty = (notional / price_ref).quantize(Decimal("1e-12"), rounding=ROUND_DOWN)
        if base_qty < Decimal("0"):
            base_qty = Decimal("0")
        quote_qty = notional
        if quote_qty < Decimal("0"):
            quote_qty = Decimal("0")
        method = "sizing_min_of_five_rules_v1"
        return PositionSizingSpec(
            base_qty=base_qty, quote_qty=quote_qty,
            notional=notional, method=method,
        )

    # --------------------------------------------------------------
    # Quality multiplier (UPSTREAM values; no mutation / no validation call)
    # --------------------------------------------------------------
    def _quality_multiplier(self, q: QualityFlags) -> float:
        invalid = getattr(q, "invalid", False)
        quar = getattr(q, "quarantined", False)
        if invalid or quar:
            return 0.15
        stale = getattr(q, "stale", False)
        deg = getattr(q, "degraded", False)
        if stale or deg:
            return 0.60
        missing = getattr(q, "missing", False)
        dup = getattr(q, "duplicate", False)
        ooo = getattr(q, "out_of_order", False)
        if missing or dup or ooo:
            return 0.85
        return 1.00

    # --------------------------------------------------------------
    # 20 Risk components
    # --------------------------------------------------------------
    def _compute_risk_components(
        self,
        opp: OpportunityScore,
        sig: StrategySignal,
        regime: MarketRegime,
        pv: PortfolioSnapshot | None,
        limits: LimitsSnapshot,
        ctx: RiskContext,
        proposed_notional: Decimal,
        q: QualityFlags,
    ) -> dict[str, float]:
        comp: dict[str, float] = {}

        # R01 quality flags (higher = riskier)
        comp["R01_quality"] = _clip01(
            0.10 * float(getattr(q, "stale", False))
            + 0.15 * float(getattr(q, "missing", False))
            + 0.10 * float(getattr(q, "duplicate", False))
            + 0.10 * float(getattr(q, "out_of_order", False))
            + 0.25 * float(getattr(q, "degraded", False))
            + 1.00 * (1.0 if (getattr(q, "invalid", False) or getattr(q, "quarantined", False)) else 0.0)
        )

        # R02 spread risk (abnormal fallback; use probe bps if provided)
        spread_bps = float(ctx.feature_spread_bps_probe if ctx.feature_spread_bps_probe is not None else ctx.defaults.spread_bps_model_default)
        abnormal = bool(getattr(q, "abnormal_spread", False)) if hasattr(q, "abnormal_spread") else bool(
            spread_bps >= ctx.defaults.spread_abnormal_threshold_bps
        )
        if abnormal:
            comp["R02_spread"] = _clip01(spread_bps / 500.0)
        else:
            comp["R02_spread"] = _clip01(spread_bps / 500.0)

        # R03 expected edge risk (higher if expected edge very low)
        min_target = max(1.0, ctx.defaults.min_positive_net_edge_bps + 1.0)
        edge = opp.expected_edge_bps if opp.expected_edge_bps is not None else -1e9
        comp["R03_edge"] = _clip01(1.0 - (edge / min_target))

        # R04 cost ratio = expected_cost / expected_edge
        eps_edge = 1e-9
        edge_for_ratio = max(eps_edge, abs(edge) if edge > 0 else eps_edge)
        cost = opp.expected_cost_bps if isinstance(opp.expected_cost_bps, float) else 0.0
        comp["R04_cost"] = _clip01(cost / edge_for_ratio)

        # R05 opp confidence
        comp["R05_opp_conf"] = _clip01(1.0 - float(opp.confidence))

        # R06 signal strength extremity (0.5 → low risk, extremes → high risk)
        comp["R06_sig_strength"] = _clip01(abs(float(sig.signal_strength) - 0.5) * 2.0)

        # R07 signal confidence
        sc = sig.confidence if isinstance(sig.confidence, float) else 0.5
        comp["R07_sig_conf"] = _clip01(1.0 - sc)

        # R08 strategy regime penalty
        strat = sig.strategy_id
        regime_name = str(regime.regime.value) if isinstance(regime.regime, MarketRegimeState) else str(regime.regime)
        matrix = STRATEGY_REGIME_PENALTY.get(strat) or STRATEGY_REGIME_PENALTY["_default_"]
        comp["R08_strat_regime"] = _clip01(matrix.get(regime_name, 0.60))

        # R09 regime confidence
        comp["R09_regime_conf"] = _clip01(1.0 - float(regime.confidence))

        # R10 regime type
        comp["R10_regime_type"] = _clip01(REGIME_TYPE_RISK.get(regime_name, 0.70))

        # R11 drawdown vs limit
        eps = 1e-9
        comp["R11_drawdown"] = _clip01(float(limits.current_drawdown_pct) / max(eps, float(limits.max_drawdown_pct)))

        # R12 daily loss vs limit
        max_loss_mag = float(max(Decimal("0"), -limits.max_daily_loss_notional if limits.max_daily_loss_notional < Decimal("0") else limits.max_daily_loss_notional))
        curr_loss_mag = float(max(Decimal("0"), -limits.current_daily_pnl if limits.current_daily_pnl < Decimal("0") else Decimal("0")))
        comp["R12_daily_loss"] = _clip01(curr_loss_mag / max(eps, max_loss_mag))

        # R13 consecutive losses vs limit
        denom = max(1, int(limits.max_consecutive_losses))
        comp["R13_consec_losses"] = _clip01(float(int(limits.current_consecutive_losses)) / float(denom))

        # R14 exposure utilization
        cur_exp = float(limits.current_exposure_notional)
        max_exp = max(eps, float(limits.max_exposure_notional_total))
        comp["R14_exposure_util"] = _clip01(cur_exp / max_exp)

        # R15 per-symbol concentration (post-order)
        sym_cur = float(ctx.symbol_current_exposure_notional or Decimal("0"))
        proposed_flt = float(proposed_notional)
        total = max(eps, float(limits.max_exposure_notional_total))
        comp["R15_concentration"] = _clip01(
            ((sym_cur + proposed_flt) / total) * float(ctx.defaults.concentration_diversifier_n)
        )

        # R16 cash utilization
        cash = float(pv.cash_quote if isinstance(pv, PortfolioSnapshot) else Decimal("0"))
        comp["R16_cash_util"] = _clip01(proposed_flt / max(eps, cash))

        # R17 budget headroom drawdown
        budget = max(eps, float(limits.max_drawdown_pct) * float(ctx.defaults.drawdown_risk_budget_fraction))
        comp["R17_budget_headroom"] = _clip01(float(limits.current_drawdown_pct) / budget)

        # R18 duplicate / cooldown
        dup_reject = False
        cool_reject = False
        # best effort — in inner call we can't access chain; use probe via context attributes
        dup_key = (opp.correlation_id, opp.symbol_ref, (ctx.as_of or _instant_now())[:-7])
        if ctx.duplicate_tracker.get(dup_key) is not None:
            dup_reject = True
        cool_key = (opp.symbol_ref, sig.strategy_id)
        if ctx.cooldown_tracker.get(cool_key) is not None:
            cool_reject = True
        if dup_reject or cool_reject:
            comp["R18_dup_cooldown"] = 0.90
        else:
            comp["R18_dup_cooldown"] = 0.05

        # R19 slippage + latency model risk (cost vs edge)
        slip_lat = float(ctx.defaults.slippage_bps_default) + float(ctx.defaults.latency_bps_default)
        comp["R19_slip_lat_model"] = _clip01(slip_lat / max(eps_edge, edge if edge > 0 else eps_edge))

        # R20 signal-score divergence
        regime_comp = float(regime.confidence) * 0.3
        sig_comp = (sc if isinstance(sc, float) else 0.5) * 0.3
        strength_comp = float(sig.signal_strength) * 0.4
        signal_based = regime_comp + sig_comp + strength_comp
        diff = abs(float(opp.score_total) - signal_based)
        comp["R20_sig_score_div"] = _clip01(diff / 0.50)

        return comp

    # --------------------------------------------------------------
    # Helper: build REJECTED in any fail-closed path
    # --------------------------------------------------------------
    def _build_rejected_safe(
        self,
        opp_score: Any,
        signal: Any,
        regime: Any,
        portfolio_view: Any,
        limits: Any,
        ctx: Any,
        reason_codes: list[str],
        as_of: Instant | None,
    ) -> RiskDecision:
        try:
            if not isinstance(limits, LimitsSnapshot):
                limits = LimitsSnapshot(
                    max_position_notional_per_symbol=Decimal("0"),
                    max_exposure_notional_total=Decimal("0"),
                    max_daily_loss_notional=Decimal("0"),
                    max_drawdown_pct=0.0,
                    max_consecutive_losses=0,
                    max_leverage_allowed=1,
                    current_exposure_notional=Decimal("0"),
                    current_daily_pnl=Decimal("0"),
                    current_drawdown_pct=0.0,
                    current_consecutive_losses=0,
                )
        except Exception:
            # Last-ditch attempt to construct fallback limits via raw values
            limits = object.__new__(LimitsSnapshot)
            limits.max_position_notional_per_symbol = Decimal("0")
            limits.max_exposure_notional_total = Decimal("0")
            limits.max_daily_loss_notional = Decimal("0")
            limits.max_drawdown_pct = 0.0
            limits.max_consecutive_losses = 0
            limits.max_leverage_allowed = 1
            limits.current_exposure_notional = Decimal("0")
            limits.current_daily_pnl = Decimal("0")
            limits.current_drawdown_pct = 0.0
            limits.current_consecutive_losses = 0

        try:
            kill = ctx.kill_switch if isinstance(ctx, RiskContext) else KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None)
            if not isinstance(kill, KillSwitchStateSpec):
                kill = KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None)
        except Exception:
            kill = KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None)

        try:
            corr = opp_score.correlation_id if isinstance(opp_score, OpportunityScore) else _ulidish_new()
            caus = opp_score.score_id if isinstance(opp_score, OpportunityScore) else _ulidish_new()
        except Exception:
            corr = _ulidish_new()
            caus = _ulidish_new()

        ts = as_of or _instant_now()
        try:
            valid_until = _instant_add_ms(ts, int(ctx.defaults.decision_valid_until_ms) if isinstance(ctx, RiskContext) else 30_000)
        except Exception:
            valid_until = ts

        # Construct rejected zero sizing
        try:
            sizing = PositionSizingSpec(base_qty=Decimal("0"), quote_qty=Decimal("0"), notional=Decimal("0"), method="rejected_no_sizing")
        except ContractSchemaError:
            sizing = PositionSizingSpec(
                base_qty=Decimal("0"),
                quote_qty=Decimal("0"),
                notional=Decimal("0"),
                method="rejected_no_sizing",
            )

        return RiskDecision(
            decision_id=_ulidish_new(),
            decision=RiskDecisionResult.REJECTED,
            reason_codes=sorted(set(reason_codes)) if reason_codes else ["INTERNAL_CALCULATION_ERROR"],
            position_sizing=sizing,
            limits_snapshot=limits,
            kill_switch_state=kill,
            valid_until=valid_until,
            correlation_id=corr,
            causation_id=caus,
            approval_chain=[],
        )


# Shortcut function (pure)
def evaluate_risk(
    opp_score: OpportunityScore,
    signal: StrategySignal,
    regime: MarketRegime,
    portfolio_view: PortfolioSnapshot | None,
    limits: LimitsSnapshot,
    ctx: RiskContext,
    engine: IndependentRiskEngine | None = None,
) -> RiskDecision:
    return (engine or IndependentRiskEngine()).evaluate(
        opp_score=opp_score,
        signal=signal,
        regime=regime,
        portfolio_view=portfolio_view,
        limits=limits,
        ctx=ctx,
    )


__all__ = [
    "IndependentRiskEngine",
    "RiskEngineDefaults",
    "RiskScoreWeights",
    "RiskContext",
    "evaluate_risk",
    "DEFAULT_WEIGHTS",
    "DEFAULTS",
]
