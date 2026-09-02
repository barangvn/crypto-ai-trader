from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.contracts import (
    CONTRACT_VERSION,
    Candle,
    ClockRef,
    EligibilityContextView,
    FeatureVector,
    KillSwitchStateSpec,
    LimitsSnapshot,
    MarketTick,
    MarketRegime,
    MarketRegimeState,
    OpportunityScore,
    OpportunityScoreComponentPolicy,
    PaperFill,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PortfolioContextView,
    PortfolioSnapshot,
    Position,
    PositionSide,
    QualityFlags,
    RiskDecision,
    RiskDecisionResult,
    RunMode,
    SignalDirection,
    SourceType,
    StrategyContext,
    StrategySignal,
    Symbol,
    TimeInForce,
    ULID,
    format_instant,
    validate_instant,
)
from app.contracts.canonical import CanonicalEventEnvelope
from app.platform.event_bus import InMemoryTypedEventBus
from app.backtest.ordering import (
    ReplayClock,
    assert_no_look_ahead,
    stage_for_event,
)
from app.features import FeatureEngine
from app.regime import RegimeEngine
from app.strategies import (
    MomentumStrategy,
    PureStrategy,
    StrategyQualityHint,
    TrendFollowingStrategy,
    STRATEGY_VERSION_DEFAULT,
)
from app.opportunity import DeterministicOpportunityScorer
from app.risk import (
    DEFAULTS,
    DEFAULT_WEIGHTS,
    IndependentRiskEngine,
    RiskContext,
    RiskEngineDefaults,
    RiskScoreWeights,
    evaluate_risk,
)
from app.risk.gate import (
    GATE_VERSION_RSK02,
    GateOptions,
    GateResult,
    InMemoryDecisionRegistry,
    PaperOrderGateRequest,
    RiskDecisionToPaperOrderGate,
)
from app.simulation import (
    FILL_MODEL_VERSION,
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    PaperFillResult,
    PipelineReferenceData,
    build_pipeline_reference_data,
)
from app.simulation.portfolio import (
    PositionEngineResult,
    PortfolioSnapshotResult,
    Rolling24Result,
    apply_fill,
    build_portfolio_snapshot,
    build_rolling_24h,
)


FAIL_CLOSED_PREFIX = "BK-"


def _ulid_new(*, seed: str | None = None, counter: int | None = None) -> str:
    if seed is not None and counter is not None:
        h = hashlib.sha256(
            (f"bk-ulid|{seed}|{counter}|{__name__}").encode("utf-8")
        ).hexdigest()
    else:
        import os
        h = hashlib.sha256(
            (f"bk-ulid|{os.urandom(16).hex()}|{id(object())}|{__name__}").encode("utf-8")
        ).hexdigest()
    return "U" + h[:25]


@dataclass(slots=True)
class BacktestPipelineEngines:
    feature: FeatureEngine = field(default_factory=FeatureEngine)
    regime: RegimeEngine = field(default_factory=RegimeEngine)
    strategy_trend: TrendFollowingStrategy = field(default_factory=TrendFollowingStrategy)
    strategy_momentum: MomentumStrategy = field(default_factory=MomentumStrategy)
    opportunity: DeterministicOpportunityScorer = field(default_factory=DeterministicOpportunityScorer)
    risk: IndependentRiskEngine = field(default_factory=IndependentRiskEngine)
    gate: RiskDecisionToPaperOrderGate = field(
        default_factory=lambda: RiskDecisionToPaperOrderGate(InMemoryDecisionRegistry())
    )
    execution: PaperExecutionSimulator = field(default_factory=PaperExecutionSimulator)


@dataclass(slots=True)
class BacktestPipelineContext:
    run_id: str
    bus: InMemoryTypedEventBus
    clock: ReplayClock
    fill_config: FillAssumptionsConfig
    engines: BacktestPipelineEngines = field(default_factory=BacktestPipelineEngines)
    positions: dict[Symbol, Position | None] = field(default_factory=dict)
    last_snapshot: PortfolioSnapshot | None = None
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    fills: list[PaperFill] = field(default_factory=list)
    events_processed: int = 0
    events_emitted: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    initial_equity: Decimal = Decimal("10000")
    cash_quote: Decimal = Decimal("10000")
    quote_currency: str = "USDT"
    current_correlation_id: str = ""
    stage_timestamps: dict[str, str] = field(default_factory=dict)
    candle_history: dict[Symbol, list[Candle]] = field(default_factory=dict)
    last_mark_price: dict[Symbol, Decimal] = field(default_factory=dict)
    strategy_active: type[PureStrategy] = TrendFollowingStrategy
    prev_peak_equity: Decimal | None = None

    @dataclass(slots=True)
    class _Counts:
        feature_count: int = 0
        regime_count: int = 0
        strategy_count: int = 0
        opportunity_count: int = 0
        risk_count: int = 0
        gate_count: int = 0
        fill_count: int = 0
        position_count: int = 0
        portfolio_count: int = 0
        perf_count: int = 0

    counts: _Counts = field(default_factory=_Counts)

    def make_correlation_id(self) -> str:
        raw = _ulid_new()
        rid_no_dash = (self.run_id or "").replace("-", "")[:12]
        cid = "C" + rid_no_dash + raw[1:]
        self.current_correlation_id = cid
        return cid

    def next_position_for(self, symbol: Symbol) -> Position | None:
        return self.positions.get(symbol, None)

    def set_position(self, symbol: Symbol, pos: Position | None) -> None:
        self.positions[symbol] = pos

    def record_candle(self, candle: Candle) -> None:
        sym = Symbol(candle.symbol)
        self.candle_history.setdefault(sym, [])
        arr = self.candle_history[sym]
        if arr and arr[-1].close_time >= candle.close_time:
            return
        arr.append(candle)
        if candle.close is not None and candle.close > 0:
            self.last_mark_price[sym] = Decimal(candle.close)

    def record_tick(self, tick: MarketTick) -> None:
        sym = Symbol(tick.symbol)
        if tick.price is not None and tick.price > 0:
            self.last_mark_price[sym] = Decimal(tick.price)


@dataclass(slots=True)
class ReplayPipelineStepResult:
    stage_tick: MarketTick | None = None
    stage_candle: Candle | None = None
    feature: FeatureVector | None = None
    regime: MarketRegime | None = None
    strategy_signal: StrategySignal | None = None
    opportunity: OpportunityScore | None = None
    risk_decision: RiskDecision | None = None
    gate_result: GateResult | None = None
    paper_order: PaperOrder | None = None
    paper_fill: PaperFill | None = None
    position: Position | None = None
    portfolio_snapshot: PortfolioSnapshot | None = None
    rolling_perf: Rolling24Result | None = None
    failure_reasons: list[str] = field(default_factory=list)
    skipped_stages: list[str] = field(default_factory=list)
    correlation_id: str = ""
    causation_chain: list[tuple[str, str]] = field(default_factory=list)
    quality_violations: list[str] = field(default_factory=list)
    emitted_events: list[CanonicalEventEnvelope] = field(default_factory=list)
    market_candle: Candle | None = None
    market_tick: MarketTick | None = None
    emitted_stages: list[str] = field(default_factory=list)


def _extract_quality_block(qf: QualityFlags | None) -> str | None:
    if qf is None:
        return None
    if getattr(qf, "invalid", False):
        return "Q_INVALID"
    if getattr(qf, "quarantined", False):
        return "Q_QUARANTINED"
    if getattr(qf, "stale", False):
        return "Q_STALE"
    if getattr(qf, "duplicate", False):
        return "Q_DUP"
    if getattr(qf, "out_of_order", False):
        return "Q_OOO"
    if getattr(qf, "missing", False):
        return "Q_MISSING"
    return None


def _current_price(ctx: BacktestPipelineContext, symbol: Symbol, tick: MarketTick | None, candle: Candle | None) -> Decimal:
    if tick is not None and isinstance(tick.price, Decimal) and tick.price > 0:
        return tick.price
    if candle is not None and isinstance(candle.close, Decimal) and candle.close > 0:
        return candle.close
    return ctx.last_mark_price.get(symbol, Decimal("0"))


def _price_for_symbol(ctx: BacktestPipelineContext, symbol: Symbol) -> Decimal:
    return ctx.last_mark_price.get(symbol, Decimal("0"))


def _make_clock_ref(decision_ts: str, correlation_id: str) -> ClockRef:
    return ClockRef(
        wall=decision_ts,
        replay=decision_ts,
    )


def _make_risk_context(
    as_of: str,
    *,
    symbol_current_exposure_notional: Decimal | None = None,
    symbol_price_ref: Decimal | None = None,
) -> RiskContext:
    return RiskContext(
        kill_switch=KillSwitchStateSpec(active=False, reason="", triggered_at=None),
        as_of=as_of,
        symbol_current_exposure_notional=symbol_current_exposure_notional,
        symbol_price_ref=symbol_price_ref,
    )


def _make_limits_snapshot() -> LimitsSnapshot:
    return LimitsSnapshot(
        max_position_notional_quote=Decimal("100000"),
        max_single_order_notional_quote=Decimal("10000"),
        max_daily_notional_quote=Decimal("1000000"),
        max_holding_count=5,
        max_leverage=Decimal("1"),
        allow_short=False,
        allow_futures=False,
    )


def _append_causation(result: ReplayPipelineStepResult, stage: str) -> None:
    child = _ulid_new()
    result.causation_chain.append((stage, child))


def _compute_position_exposure_notional(pos: Position | None) -> Decimal:
    if pos is None:
        return Decimal("0")
    if getattr(pos, "base_qty", 0) <= 0:
        return Decimal("0")
    price = getattr(pos, "current_price", Decimal("0"))
    if not isinstance(price, Decimal) or price <= 0:
        return Decimal("0")
    qty = getattr(pos, "base_qty", Decimal("0"))
    if not isinstance(qty, Decimal) or qty <= 0:
        return Decimal("0")
    return qty * price


def run_replay_pipeline_step(
    ctx: BacktestPipelineContext,
    *,
    tick: MarketTick | None = None,
    candle: Candle | None = None,
) -> ReplayPipelineStepResult:
    result = ReplayPipelineStepResult()
    result.stage_tick = tick
    result.stage_candle = candle
    result.market_candle = candle
    result.market_tick = tick
    result.emitted_stages.append("MARKET")

    try:
        base_event = tick if tick is not None else candle
        if base_event is None:
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}NO_MARKET_EVENT")
            ctx.failures.append(("NO_MARKET_EVENT", "tick is None and candle is None"))
            return result

        quality = getattr(base_event, "quality_flags", None)
        quality_block = _extract_quality_block(quality)
        if quality_block is not None:
            result.quality_violations.append(quality_block)

        decision_ts = getattr(base_event, "event_ts", "")
        symbol = Symbol(getattr(base_event, "symbol", ""))

        if not decision_ts:
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}NO_DECISION_TS")
            ctx.failures.append(("NO_DECISION_TS", ""))
            return result
        if not validate_instant(decision_ts):
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}INVALID_DECISION_TS")
            ctx.failures.append(("INVALID_DECISION_TS", decision_ts))
            return result

        try:
            ctx.clock.advance(decision_ts)
        except BaseException as exc:  # noqa: BLE001 - fail-closed
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}CLOCK_{type(exc).__name__}")
            ctx.failures.append(("CLOCK_ADVANCE", str(exc)))
            return result

        if candle is not None:
            ctx.record_candle(candle)
        if tick is not None:
            ctx.record_tick(tick)

        ctx.stage_timestamps[stage_for_event(base_event)] = decision_ts

        correlation_id = ctx.make_correlation_id()
        result.correlation_id = correlation_id
        result.causation_chain.append(("MARKET", correlation_id))

        if quality_block is not None:
            result.skipped_stages.extend([
                "FEATURE", "REGIME", "STRATEGY", "OPPORTUNITY", "RISK", "GATE",
                "FILL", "POSITION",
            ])
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        assert_no_look_ahead(
            decision_ts=decision_ts,
            decision_input_max_ts=decision_ts,
            clock=ctx.clock,
        )

        prev_position = ctx.next_position_for(symbol)
        clock_ref = _make_clock_ref(decision_ts, correlation_id)
        current_price = _current_price(ctx, symbol, tick, candle)

        # ---------- STAGE 2: FEATURE ----------
        try:
            candles_for_feature = list(ctx.candle_history.get(symbol, []))
            if not candles_for_feature and candle is not None:
                candles_for_feature = [candle]
            if len(candles_for_feature) >= 20:
                feature = ctx.engines.feature.calculate(
                    symbol, candles_for_feature, timeframe=getattr(candle, "timeframe", "1m") if candle else "1m"
                )
            else:
                feature = None
            result.feature = feature
            if feature is not None:
                ctx.counts.feature_count += 1
                result.emitted_stages.append("FEATURE")
            else:
                result.skipped_stages.append("FEATURE")
            ctx.stage_timestamps["FEATURE"] = decision_ts
            _append_causation(result, "FEATURE")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}FEATURE_{type(exc).__name__}")
            ctx.failures.append(("FEATURE", str(exc)))
            result.skipped_stages.extend(["REGIME", "STRATEGY", "OPPORTUNITY", "RISK", "GATE", "FILL", "POSITION"])
            if "FEATURE" in result.emitted_stages:
                result.emitted_stages.remove("FEATURE")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        if feature is None:
            result.skipped_stages.extend(["REGIME", "STRATEGY", "OPPORTUNITY", "RISK", "GATE", "FILL", "POSITION"])
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 3: REGIME ----------
        try:
            regime, _aux_regime = ctx.engines.regime.detect(symbol, feature)
            result.regime = regime
            if regime is not None:
                ctx.counts.regime_count += 1
                result.emitted_stages.append("REGIME")
            else:
                result.skipped_stages.append("REGIME")
            ctx.stage_timestamps["REGIME"] = decision_ts
            _append_causation(result, "REGIME")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}REGIME_{type(exc).__name__}")
            ctx.failures.append(("REGIME", str(exc)))
            result.skipped_stages.extend(["STRATEGY", "OPPORTUNITY", "RISK", "GATE", "FILL", "POSITION"])
            if "REGIME" in result.emitted_stages:
                result.emitted_stages.remove("REGIME")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 4: STRATEGY ----------
        try:
            strategy_ctx = StrategyContext(
                symbol=symbol,
                as_of=decision_ts,
                clock_ref=clock_ref,
                features=feature,
                regime=regime,
                portfolio_ctx=PortfolioContextView(),
                eligibility_ctx=EligibilityContextView(eligible=True, reasons=[]),
                scoring_policy=OpportunityScoreComponentPolicy(
                    policy_version="policy_v1.0.0", component_keys=[]
                ),
                run_mode=RunMode.BACKTEST,
                source_type=SourceType.REPLAY,
                correlation_id=correlation_id,
                causation_id=correlation_id,
                strategy_params={},
            )
            if ctx.strategy_active is MomentumStrategy:
                sig = ctx.engines.strategy_momentum.evaluate(
                    strategy_ctx, quality_hint=StrategyQualityHint()
                )
            else:
                sig = ctx.engines.strategy_trend.evaluate(
                    strategy_ctx, quality_hint=StrategyQualityHint()
                )
            result.strategy_signal = sig
            if sig is not None:
                ctx.counts.strategy_count += 1
                result.emitted_stages.append("STRATEGY")
            else:
                result.skipped_stages.append("STRATEGY")
            ctx.stage_timestamps["STRATEGY"] = decision_ts
            _append_causation(result, "STRATEGY")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}STRATEGY_{type(exc).__name__}")
            ctx.failures.append(("STRATEGY", str(exc)))
            result.skipped_stages.extend(["OPPORTUNITY", "RISK", "GATE", "FILL", "POSITION"])
            if "STRATEGY" in result.emitted_stages:
                result.emitted_stages.remove("STRATEGY")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 5: OPPORTUNITY ----------
        try:
            opp = ctx.engines.opportunity.evaluate(
                sig, feature, regime, quality, decision_ts
            )
            result.opportunity = opp
            if opp is not None:
                ctx.counts.opportunity_count += 1
                result.emitted_stages.append("OPPORTUNITY")
            else:
                result.skipped_stages.append("OPPORTUNITY")
            ctx.stage_timestamps["OPPORTUNITY"] = decision_ts
            _append_causation(result, "OPPORTUNITY")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}OPPORTUNITY_{type(exc).__name__}")
            ctx.failures.append(("OPPORTUNITY", str(exc)))
            result.skipped_stages.extend(["RISK", "GATE", "FILL", "POSITION"])
            if "OPPORTUNITY" in result.emitted_stages:
                result.emitted_stages.remove("OPPORTUNITY")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 6: RISK ----------
        try:
            risk_ctx = _make_risk_context(
                as_of=decision_ts,
                symbol_current_exposure_notional=_compute_position_exposure_notional(prev_position),
                symbol_price_ref=current_price if current_price > 0 else None,
            )
            limits = _make_limits_snapshot()
            rdecision = ctx.engines.risk.evaluate(
                opp_score=opp,
                signal=sig,
                regime=regime,
                portfolio_view=ctx.last_snapshot,
                limits=limits,
                ctx=risk_ctx,
            )
            result.risk_decision = rdecision
            if rdecision is not None:
                ctx.counts.risk_count += 1
                result.emitted_stages.append("RISK")
            else:
                result.skipped_stages.append("RISK")
            ctx.stage_timestamps["RISK"] = decision_ts
            _append_causation(result, "RISK")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}RISK_{type(exc).__name__}")
            ctx.failures.append(("RISK", str(exc)))
            result.skipped_stages.extend(["GATE", "FILL", "POSITION"])
            if "RISK" in result.emitted_stages:
                result.emitted_stages.remove("RISK")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        verdict = getattr(rdecision, "decision", None)
        if verdict != RiskDecisionResult.APPROVED:
            result.skipped_stages.extend(["GATE", "FILL", "POSITION"])
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 7: PAPER ORDER GATE (S-RSK-02) ----------
        try:
            pos_sizing = getattr(rdecision, "position_sizing", None)
            requested_qty = getattr(pos_sizing, "base_qty", Decimal("0")) if pos_sizing else Decimal("0")
            requested_price = getattr(pos_sizing, "reference_price", None) if pos_sizing else None
            if requested_price is None and current_price > 0:
                requested_price = current_price
            requested_notional = (
                getattr(pos_sizing, "notional_quote", None) if pos_sizing else None
            )
            if requested_notional is None:
                requested_notional = (
                    requested_qty * requested_price
                    if isinstance(requested_qty, Decimal) and isinstance(requested_price, Decimal) and requested_price > 0
                    else Decimal("0")
                )
            signal_dir = getattr(sig, "direction", SignalDirection.HOLD)
            if signal_dir == SignalDirection.LONG:
                side = PaperOrderSide.BUY
            elif signal_dir == SignalDirection.SHORT:
                side = PaperOrderSide.SELL
            else:
                side = PaperOrderSide.BUY

            gate_req = PaperOrderGateRequest(
                symbol=symbol,
                side=side,
                order_type=PaperOrderType.MARKET,
                requested_qty_base=Decimal(requested_qty) if isinstance(requested_qty, Decimal) else Decimal("0"),
                requested_notional_quote=Decimal(requested_notional) if isinstance(requested_notional, Decimal) else Decimal("0"),
                requested_price=requested_price,
                policy_refs=PaperOrderPolicyRefs(
                    risk_decision_id=str(getattr(rdecision, "decision_id", "")),
                    opportunity_id=str(getattr(opp, "score_id", "")),
                    signal_id=str(getattr(sig, "signal_id", "")),
                ),
                correlation_id=ULID(correlation_id),
                causation_id=ULID(correlation_id),
                position_intent="OPEN_NEW" if prev_position is None or getattr(prev_position, "base_qty", Decimal("0")) == Decimal("0") else "INCREASE",
            )
            gate_result = ctx.engines.gate.evaluate(gate_req)
            result.gate_result = gate_result
            if gate_result is not None:
                ctx.counts.gate_count += 1
                result.emitted_stages.append("GATE")
            else:
                result.skipped_stages.append("GATE")
            ctx.stage_timestamps["GATE"] = decision_ts
            _append_causation(result, "GATE")
            if not getattr(gate_result, "allowed", False):
                result.skipped_stages.extend(["FILL", "POSITION"])
                ctx.events_processed += 1
                _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
                return result
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}GATE_{type(exc).__name__}")
            ctx.failures.append(("GATE", str(exc)))
            result.skipped_stages.extend(["FILL", "POSITION"])
            if "GATE" in result.emitted_stages:
                result.emitted_stages.remove("GATE")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- BUILD PaperOrder after gate allowed ----------
        try:
            porder = PaperOrder(
                paper_order_id=ULID(_ulid_new()),
                symbol=symbol,
                side=side,
                order_type=PaperOrderType.MARKET,
                status=PaperOrderStatus.NEW,
                qty_base=gate_req.requested_qty_base,
                notional_quote=gate_req.requested_notional_quote,
                price_limit=gate_req.requested_price,
                time_in_force=TimeInForce.GTC,
                created_at=decision_ts,
                policy_refs=gate_req.policy_refs,
                correlation_id=ULID(correlation_id),
                causation_id=ULID(correlation_id),
            )
            result.paper_order = porder
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}ORDER_BUILD_{type(exc).__name__}")
            ctx.failures.append(("ORDER_BUILD", str(exc)))
            result.skipped_stages.extend(["FILL", "POSITION"])
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 8: PAPER FILL (S-PTR-01) ----------
        try:
            ref = build_pipeline_reference_data(
                tick=tick,
                candle=candle,
                symbol=symbol,
                clock_ref=clock_ref,
            )
            fill_result = ctx.engines.execution.simulate(
                order=porder,
                reference=ref,
                quality_ctx=quality,
                clock_ref=clock_ref,
                publish_to_bus=False,
            )
            pf = fill_result.fill
            if pf is None or fill_result.rejected:
                if fill_result.reject_reasons:
                    result.failure_reasons.extend(
                        f"{FAIL_CLOSED_PREFIX}FILL_{r}" for r in fill_result.reject_reasons
                    )
                result.skipped_stages.append("POSITION")
                ctx.events_processed += 1
                _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
                return result
            result.paper_fill = pf
            ctx.fills.append(pf)
            ctx.counts.fill_count += 1
            result.emitted_stages.append("FILL")
            ctx.stage_timestamps["FILL"] = decision_ts
            _append_causation(result, "FILL")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}FILL_{type(exc).__name__}")
            ctx.failures.append(("FILL", str(exc)))
            result.skipped_stages.append("POSITION")
            if "FILL" in result.emitted_stages:
                result.emitted_stages.remove("FILL")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        # ---------- STAGE 9: POSITION (S-PTF-01) ----------
        try:
            pos_res: PositionEngineResult = apply_fill(
                prev_position,
                pf,
                symbol=symbol,
                current_price=current_price if current_price > 0 else Decimal("1"),
                quality_ctx=quality,
                clock_ref=clock_ref,
            )
            new_pos = pos_res.new_position
            result.position = new_pos
            ctx.set_position(symbol, new_pos)
            if new_pos is not None:
                ctx.counts.position_count += 1
                result.emitted_stages.append("POSITION")
                if getattr(pf, "side", None) == PaperOrderSide.BUY:
                    ctx.cash_quote = max(Decimal("0"), ctx.cash_quote - Decimal(getattr(pf, "notional_quote", Decimal("0"))) - Decimal(getattr(pf, "fees_quote", Decimal("0"))))
                elif getattr(pf, "side", None) == PaperOrderSide.SELL:
                    ctx.cash_quote = ctx.cash_quote + Decimal(getattr(pf, "notional_quote", Decimal("0"))) - Decimal(getattr(pf, "fees_quote", Decimal("0")))
            else:
                result.skipped_stages.append("POSITION")
            ctx.stage_timestamps["POSITION"] = decision_ts
            _append_causation(result, "POSITION")
        except BaseException as exc:  # noqa: BLE001
            result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}POSITION_{type(exc).__name__}")
            ctx.failures.append(("POSITION", str(exc)))
            if "POSITION" in result.emitted_stages:
                result.emitted_stages.remove("POSITION")
            ctx.events_processed += 1
            _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
            return result

        ctx.events_processed += 1
        _finalize_snapshot_and_perf(ctx, result, correlation_id, decision_ts, symbol, quality)
        return result
    except BaseException as exc:  # noqa: BLE001 - outer fail-closed
        result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}OUTER_{type(exc).__name__}")
        ctx.failures.append(("OUTER", str(exc)))
        return result


def _finalize_snapshot_and_perf(
    ctx: BacktestPipelineContext,
    result: ReplayPipelineStepResult,
    correlation_id: str,
    decision_ts: str,
    symbol: Symbol,
    quality: QualityFlags | None,
) -> None:
    try:
        positions_list: list[Position] = []
        current_price_map: dict[str, Decimal] = {}
        for s, p in ctx.positions.items():
            if p is not None and getattr(p, "base_qty", Decimal("0")) > 0:
                positions_list.append(p)
                mark_price = _price_for_symbol(ctx, s)
                if mark_price > 0:
                    current_price_map[str(s)] = mark_price
        mark_this = _price_for_symbol(ctx, symbol)
        if mark_this > 0:
            current_price_map[str(symbol)] = mark_this

        snap_res: PortfolioSnapshotResult = build_portfolio_snapshot(
            positions=positions_list,
            cash_quote=ctx.cash_quote,
            current_price_map=current_price_map,
            snapshot_ts=decision_ts,
            correlation_id=ULID(correlation_id),
            causation_id=ULID(correlation_id),
            prev_peak_equity_quote=ctx.prev_peak_equity,
            quality_ctx=quality,
        )
        snap = getattr(snap_res, "new_snapshot", None)
        if snap is None and getattr(snap_res, "rejected_reason", "").startswith("quality block"):
            snap_res = build_portfolio_snapshot(
                positions=positions_list,
                cash_quote=ctx.cash_quote,
                current_price_map=current_price_map,
                snapshot_ts=decision_ts,
                correlation_id=ULID(correlation_id),
                causation_id=ULID(correlation_id),
                prev_peak_equity_quote=ctx.prev_peak_equity,
                quality_ctx=None,
            )
            snap = getattr(snap_res, "new_snapshot", None)
        if snap is not None:
            ctx.snapshots.append(snap)
            ctx.last_snapshot = snap
            result.portfolio_snapshot = snap
            ctx.counts.portfolio_count += 1
            result.emitted_stages.append("PORTFOLIO")
            equity = getattr(snap, "equity_quote", None)
            if isinstance(equity, Decimal) and equity > 0:
                if ctx.prev_peak_equity is None or equity > ctx.prev_peak_equity:
                    ctx.prev_peak_equity = equity
            ctx.stage_timestamps["PORTFOLIO"] = decision_ts
            _append_causation(result, "PORTFOLIO")
            try:
                perf: Rolling24Result = build_rolling_24h(
                    snapshot_samples=list(ctx.snapshots),
                    end_ts=decision_ts,
                )
                result.rolling_perf = perf
                ctx.counts.perf_count += 1
                result.emitted_stages.append("PERFORMANCE")
                ctx.stage_timestamps["PERFORMANCE"] = decision_ts
                _append_causation(result, "PERFORMANCE")
            except BaseException as exc:  # noqa: BLE001
                result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}PERF_{type(exc).__name__}")
                ctx.failures.append(("PERF", str(exc)))
    except BaseException as exc:  # noqa: BLE001
        result.failure_reasons.append(f"{FAIL_CLOSED_PREFIX}PORTFOLIO_{type(exc).__name__}")
        ctx.failures.append(("PORTFOLIO", str(exc)))
