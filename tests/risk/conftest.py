"""conftest.py — S-RSK-01 fixtures for 20+ check pipeline + 20 risk score + min-of-5 sizing.

Not: Story T01..T13 test ailesi için ZORUNLU common fixtures.
Stdlib-only, no external deps.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

import pytest

from app.contracts.canonical import CanonicalEventEnvelope, QualityFlags
from app.contracts.opportunity import OpportunityScore
from app.contracts.portfolio import PortfolioSnapshot, Position, PositionSide
from app.contracts.regime import (
    MarketRegime,
    MarketRegimeState,
    REGIME_KEYS,
    TimeRangeSpec,
)
from app.contracts.risk import KillSwitchStateSpec, LimitsSnapshot, RiskDecisionResult
from app.contracts.strategy import SignalDirection, StrategySignal
from app.contracts.types import Instant, Symbol, format_instant
from app.platform.event_bus import InMemoryTypedEventBus
from app.risk import (
    DEFAULT_WEIGHTS,
    DEFAULTS,
    IndependentRiskEngine,
    RiskContext,
    RiskEngineDefaults,
    RiskScoreWeights,
    evaluate_risk,
)


# ---------------------------------------------------------------------------
# Core: timestamp + id helpers
# ---------------------------------------------------------------------------
_UUID_CNTR: list[int] = [0]


def _uid(prefix: str = "") -> str:
    """ULID-ish (A-Za-z0-9_-) + short counter; regex _ULIDISH_RE = ^[A-Za-z0-9_-]{8,}$"""
    import uuid as _uuid
    _UUID_CNTR[0] += 1
    return f"{prefix}{_uuid.uuid4().hex[:16]}{_UUID_CNTR[0]:02d}"


def ts_now() -> Instant:
    from datetime import datetime, timezone
    return format_instant(datetime.now(timezone.utc))


def ts_add_ms(ts: str, ms: int) -> Instant:
    try:
        from datetime import datetime, timezone
        base = ts[:-1]
        if "." in base:
            main, frac = base.split(".", 1)
        else:
            main = base
            frac = "000"
        dt = datetime.strptime(main, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        epoch_s = dt.timestamp() + int((frac + "000")[:3]) / 1000.0 + ms / 1000.0
        return format_instant(datetime.fromtimestamp(epoch_s, tz=timezone.utc))
    except Exception:
        return ts


# ---------------------------------------------------------------------------
# Default fixtures (deterministic; happy path baseline)
# ---------------------------------------------------------------------------

SYM: Symbol = "BTC_USDT"
REGIME6_SCORES_BASE: dict[str, float] = {k: 0.20 for k in sorted(REGIME_KEYS)}

@pytest.fixture()
def clean_quality() -> QualityFlags:
    return QualityFlags(stale=False, missing=False, duplicate=False, out_of_order=False, invalid=False, quarantined=False, degraded=False)


@pytest.fixture(params=[True, False], ids=["degraded_on", "degraded_off"])
def quality_with_degraded(request: Any) -> QualityFlags:
    if request.param:
        return QualityFlags(stale=False, missing=False, duplicate=False, out_of_order=False, invalid=False, quarantined=False, degraded=True)
    return QualityFlags(degraded=False)


@pytest.fixture()
def clean_limits() -> LimitsSnapshot:
    return LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("50000"),
        max_daily_loss_notional=Decimal("1000"),
        max_drawdown_pct=0.20,
        max_consecutive_losses=5,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("8000"),
        current_daily_pnl=Decimal("-200"),
        current_drawdown_pct=0.05,
        current_consecutive_losses=1,
    )


@pytest.fixture()
def clean_portfolio() -> PortfolioSnapshot:
    ts = ts_now()
    pos = Position(
        position_id=_uid("pos_"),
        symbol=SYM,
        side=PositionSide.LONG,
        base_qty=Decimal("0.08"),
        avg_entry_price=Decimal("50000"),
        current_price=Decimal("100000"),
        unrealized_pnl_quote=Decimal("4000"),
        realized_pnl_quote=Decimal("200"),
        fees_quote=Decimal("10"),
        opened_ts=ts_add_ms(ts, -3_600_000),
        last_updated_ts=ts,
        open_refs=[],
        correlation_id=_uid("pcr_"),
        causation_id=_uid("cau_"),
    )
    return PortfolioSnapshot(
        snapshot_id=_uid("snap_"),
        account_ref="paper.main",
        ts=ts,
        cash_quote=Decimal("42000"),
        equity_quote=Decimal("50000"),
        realized_pnl_quote_24h=Decimal("200"),
        unrealized_pnl_quote=Decimal("4000"),
        fees_quote_total=Decimal("10"),
        exposure_notional=Decimal("8000"),
        drawdown_pct=0.05,
        peak_equity_quote=Decimal("52631"),
        correlation_id=_uid("pc_"),
        causation_id=_uid("pccau_"),
        positions_snapshot=[pos],
    )


@pytest.fixture()
def clean_regime() -> MarketRegime:
    ts = ts_now()
    return MarketRegime(
        timeframe="5m",
        regime=MarketRegimeState.BULL,
        confidence=0.85,
        scores=dict(REGIME6_SCORES_BASE),
        detector_version="reg_01_v1",
        feature_version="fea_01_v1",
        lookback_ts=TimeRangeSpec(start=ts_add_ms(ts, -3_600_000), end=ts),
    )


@pytest.fixture()
def clean_signal() -> StrategySignal:
    return StrategySignal(
        strategy_id="trend",
        strategy_version="str_01_v1",
        direction=SignalDirection.LONG,
        signal_strength=0.75,
        correlation_id=_uid("crsig_"),
        causation_id=_uid("stratctx_"),
        supporting_feature_keys=["rsi_14", "ema_50_cross_200", "vwap_bias"],
        supporting_regime_evidence={"bull": 0.70, "high_volatility": 0.15},
        entry_thesis="trend_follow_ema_cross",
        entry_price_ref=Decimal("100000"),
        stop_policy=None,
        take_profit_policy=None,
        confidence=0.80,
        expected_edge_bps=35.0,
    )


@pytest.fixture()
def clean_opp_score(clean_quality: QualityFlags, clean_signal: StrategySignal, clean_regime: MarketRegime) -> OpportunityScore:
    created = ts_now()
    components = {
        "raw_signal": 0.75,
        "confidence_penalty": 0.85,
        "gross_edge": 60.0 / 100.0,
        "fee_penalty": 1.0 - (1.5 / max(1e-9, 60.0)),
        "slippage_penalty": 1.0 - (5.0 / 60.0),
        "spread_penalty": 1.0 - (10.0 / 60.0),
        "latency_penalty": 1.0 - (1.5 / 60.0),
        "net_edge": (60.0 - 1.5 - 5.0 - 10.0 - 1.5) / 100.0,
        "cost_multiplier": 1.0,
        "regime_adjustment": 0.95,
        "strategy_adjustment": 0.98,
        "final_score": 0.66,
    }
    return OpportunityScore(
        score_id=_uid("opp_"),
        score_total=0.66,
        confidence=0.82,
        actionable=True,
        reject_reasons=[],
        score_components=components,
        expected_edge_bps=35.0,
        expected_cost_bps=15.0,
        symbol_ref=SYM,
        regime_ref=str(clean_regime.regime.value),
        strategy_ref=clean_signal.strategy_id + "@" + clean_signal.strategy_version,
        policy_version="opp_policy_v1.0.0",
        correlation_id=clean_signal.correlation_id,
        causation_id=clean_signal.causation_id,
        created_ts=created,
        model_version_ref="opp_01_v1",
        quality_flags=clean_quality,
        expected_hold_bars=12,
        explainability_note=None,
    )


@pytest.fixture()
def clean_ctx() -> RiskContext:
    ts = ts_now()
    return RiskContext(
        kill_switch=KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None),
        emergency_stop_active=False,
        as_of=ts,
        symbol_current_exposure_notional=Decimal("8000"),
        duplicate_tracker={},
        cooldown_tracker={},
        weights=DEFAULT_WEIGHTS,
        defaults=DEFAULTS,
        symbol_price_ref=Decimal("100000"),
        feature_spread_bps_probe=20.0,
    )


@pytest.fixture()
def happy_path_tuple(clean_opp_score, clean_signal, clean_regime, clean_portfolio, clean_limits, clean_ctx) -> Any:
    return (clean_opp_score, clean_signal, clean_regime, clean_portfolio, clean_limits, clean_ctx)


@pytest.fixture()
def engine() -> IndependentRiskEngine:
    return IndependentRiskEngine()


@pytest.fixture()
def typed_bus() -> InMemoryTypedEventBus:
    return InMemoryTypedEventBus()


# ================================================================
# S-RSK-02 (CAP-4 Gate Enforcement) — fixtures SONUNA — DOKUNMA
# ================================================================

from app.contracts.paper import PaperOrderPolicyRefs, PaperOrderSide, PaperOrderType
from app.contracts.risk import PositionSizingSpec, RiskDecision
from app.risk import (
    ClockRef,
    DecisionRegistry,
    DeterministicClock,
    GateOptions,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
)


SR02_BASE_TS: Instant = "2026-03-18T12:00:00.000Z"
SR02_CORR: str = "sr02_corr_base_0001"
SR02_RD_ID: str = "sr02_rd_base_rdid_0099"
SR02_CAUS_PREV: str = "sr02_prev_oppscore_88"
SR02_SYM: Symbol = "BTC_USDT"

ONE_MS_BEFORE = "2026-03-18T12:04:29.999Z"
EXACT_VALID_UNTIL = "2026-03-18T12:04:30.000Z"
ONE_MS_AFTER = "2026-03-18T12:04:30.001Z"
AT_299s = "2026-03-18T12:04:59.000Z"
AT_300s = "2026-03-18T12:05:00.000Z"
AT_301s = "2026-03-18T12:05:01.000Z"


@pytest.fixture()
def sr02_deterministic_clock() -> DeterministicClock:
    return DeterministicClock(SR02_BASE_TS)


@pytest.fixture()
def sr02_clean_limits() -> LimitsSnapshot:
    return LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("50000"),
        max_daily_loss_notional=Decimal("-1000"),
        max_drawdown_pct=0.20,
        max_consecutive_losses=5,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("8000"),
        current_daily_pnl=Decimal("-200"),
        current_drawdown_pct=0.05,
        current_consecutive_losses=1,
    )


@pytest.fixture()
def sr02_clean_ks_no_kill() -> KillSwitchStateSpec:
    return KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None)


@pytest.fixture()
def sr02_clean_position_sizing() -> PositionSizingSpec:
    return PositionSizingSpec(
        base_qty=Decimal("0.01"),
        quote_qty=Decimal("1000"),
        notional=Decimal("1000"),
        method="min_of_five",
    )


def _bypass_rd(
    *,
    decision=RiskDecisionResult.APPROVED,
    decision_id: str = SR02_RD_ID,
    correlation_id: str = SR02_CORR,
    causation_id: str = SR02_CAUS_PREV,
    valid_until: str = "2026-03-18T12:04:30.000Z",
    ks: KillSwitchStateSpec | None = None,
    limits: LimitsSnapshot | None = None,
    ps: PositionSizingSpec | None = None,
    reason_codes: list[str] | None = None,
) -> RiskDecision:
    """Create RiskDecision, bypassing AD-11 __post_init__ invariants for G06A test scenarios.

    We construct RiskDecision using object.__new__ to skip ContractSchemaError raised
    by __post_init__ for combinations that the gate explicitly re-checks via G06 for
    defense-in-depth coverage (e.g. global_kill=True + approved).
    """
    if ks is None:
        ks = KillSwitchStateSpec(global_kill=False, per_symbol={}, reason=None)
    if limits is None:
        limits = LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("50000"),
            max_daily_loss_notional=Decimal("-1000"),
            max_drawdown_pct=0.20,
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("8000"),
            current_daily_pnl=Decimal("-200"),
            current_drawdown_pct=0.05,
            current_consecutive_losses=1,
        )
    if ps is None:
        ps = PositionSizingSpec(
            base_qty=Decimal("0.01"),
            quote_qty=Decimal("1000"),
            notional=(Decimal("1000") if decision == RiskDecisionResult.APPROVED else Decimal("0")),
            method="min_of_five",
        )
    if reason_codes is None:
        reason_codes = []
    # Force-decimal invariant by-pass:
    obj = object.__new__(RiskDecision)
    obj.decision_id = decision_id
    obj.decision = decision
    obj.reason_codes = list(reason_codes)
    obj.position_sizing = ps
    obj.limits_snapshot = limits
    obj.kill_switch_state = ks
    obj.valid_until = valid_until
    obj.correlation_id = correlation_id
    obj.causation_id = causation_id
    obj.stop_loss_ref = None
    obj.take_profit_ref = None
    obj.approval_chain = []
    # created_ts (not a field on contract; we attach for gate G08A age-ability
    try:
        obj.created_ts = SR02_BASE_TS  # type: ignore[attr-defined]
    except Exception:
        pass
    return obj


@pytest.fixture()
def sr02_approved_rd(sr02_clean_ks_no_kill, sr02_clean_limits, sr02_clean_position_sizing):
    return _bypass_rd(
        decision=RiskDecisionResult.APPROVED,
        ks=sr02_clean_ks_no_kill,
        limits=sr02_clean_limits,
        ps=sr02_clean_position_sizing,
        reason_codes=[],
    )


@pytest.fixture()
def sr02_rejected_rd(sr02_clean_ks_no_kill, sr02_clean_limits):
    ps = PositionSizingSpec(base_qty=None, quote_qty=None, notional=Decimal("0"), method="reject_fallback")
    return _bypass_rd(
        decision=RiskDecisionResult.REJECTED,
        decision_id=SR02_RD_ID + "_rej",
        ks=sr02_clean_ks_no_kill,
        limits=sr02_clean_limits,
        ps=ps,
        reason_codes=["R03_LIMIT_EXCEEDED", "R12_POSITION_LIMIT"],
    )


def _sr02_request(
    *,
    symbol: str = SR02_SYM,
    side=PaperOrderSide.BUY,
    order_type=PaperOrderType.MARKET,
    qty: Decimal = Decimal("0.01"),
    notional: Decimal = Decimal("1000"),
    price: Decimal | None = None,
    risk_decision_id: str = SR02_RD_ID,
    correlation_id: str = SR02_CORR,
    causation_id: str = SR02_CAUS_PREV,
    position_intent: str = "OPEN_NEW",
) -> PaperOrderGateRequest:
    refs = PaperOrderPolicyRefs(
        risk_decision_id=risk_decision_id,
        strategy_id="trend",
        strategy_version="str_01_v1",
    )
    # request.causation_id by default caller-provided; gate expects request.causation_id
    # (to be kept as caller side; GateResult.causation_id will = rd.decision_id
    return PaperOrderGateRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        requested_qty_base=qty,
        requested_notional_quote=notional,
        requested_price=price,
        policy_refs=refs,
        correlation_id=correlation_id,
        causation_id=causation_id,
        position_intent=position_intent,
    )


@pytest.fixture()
def sr02_happy_request() -> PaperOrderGateRequest:
    return _sr02_request()


@pytest.fixture()
def sr02_registry_approved(sr02_approved_rd) -> InMemoryDecisionRegistry:
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID, sr02_approved_rd)
    return reg


@pytest.fixture()
def sr02_registry_rejected(sr02_rejected_rd) -> InMemoryDecisionRegistry:
    reg = InMemoryDecisionRegistry()
    reg.register(SR02_CORR, SR02_RD_ID + "_rej", sr02_rejected_rd)
    return reg


@pytest.fixture()
def sr02_gate(sr02_registry_approved, sr02_deterministic_clock) -> RiskDecisionToPaperOrderGate:
    return RiskDecisionToPaperOrderGate(
        sr02_registry_approved,
        clock=sr02_deterministic_clock,
    )


@pytest.fixture()
def sr02_gate_rejected(sr02_registry_rejected, sr02_deterministic_clock) -> RiskDecisionToPaperOrderGate:
    return RiskDecisionToPaperOrderGate(
        sr02_registry_rejected,
        clock=sr02_deterministic_clock,
    )


@pytest.fixture()
def sr02_gate_empty(sr02_deterministic_clock) -> RiskDecisionToPaperOrderGate:
    return RiskDecisionToPaperOrderGate(
        InMemoryDecisionRegistry(),
        clock=sr02_deterministic_clock,
    )


@pytest.fixture()
def sr02_gate_opts() -> GateOptions:
    return GateOptions(
        stale_threshold_sec=60.0,
        oversize_tolerance_bps=20,
    )

