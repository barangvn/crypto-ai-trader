from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Literal

from app.contracts import (
    CONTRACT_VERSION,
    Candle,
    MarketTick,
    Symbol,
    ULID,
    to_sorted_dict,
)
from app.contracts.types import Instant, validate_instant
from app.platform.event_bus import InMemoryTypedEventBus
from app.backtest.ordering import (
    ReplayClock,
    deterministic_sort_events,
    verify_event_ordering_strict,
)
from app.backtest.run_metadata import (
    BACKTEST_ASSUMPTIONS_VERSION,
    BACKTEST_RUN_VERSION,
    BacktestAssumptions,
    BacktestRun,
    BacktestWindowSplit,
    SplitDataset,
    WindowSplit,
)
from app.backtest.pipeline import (
    BacktestPipelineContext,
    BacktestPipelineEngines,
    ReplayPipelineStepResult,
    run_replay_pipeline_step,
)
from app.simulation import FillAssumptionsConfig


BACKTEST_ENGINE_VERSION: Literal["1.0.0"] = "1.0.0"


def _runner_ulid_new(seed: str = "", *, counter: int | None = None) -> str:
    if counter is not None:
        h = hashlib.sha256(
            (f"bkt-run|{seed}|{counter}|{__name__}").encode("utf-8")
        ).hexdigest()
    else:
        h = hashlib.sha256(
            (f"bkt-run|{seed}|{os.urandom(16).hex()}|{__name__}").encode("utf-8")
        ).hexdigest()
    return "U" + h[:25]


def _dc_to_sorted_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        out: dict[str, Any] = {}
        for f in fields(obj):
            out[f.name] = _dc_to_sorted_dict(getattr(obj, f.name))
        return dict(sorted(out.items()))
    if isinstance(obj, (list, tuple)):
        return [_dc_to_sorted_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _dc_to_sorted_dict(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


@dataclass(slots=True, frozen=True)
class BacktestRunCounts:
    market_events: int = 0
    feature_events: int = 0
    regime_events: int = 0
    strategy_events: int = 0
    opportunity_events: int = 0
    risk_decisions: int = 0
    risk_approved: int = 0
    risk_rejected: int = 0
    gate_allowed: int = 0
    gate_blocked: int = 0
    paper_orders_created: int = 0
    paper_fills: int = 0
    paper_fill_rejections: int = 0
    position_transitions: int = 0
    portfolio_snapshots: int = 0
    performance_calculations: int = 0
    failures: int = 0
    quality_blocked: int = 0
    skipped: int = 0

    @property
    def market_count(self) -> int:
        return self.market_events

    @property
    def feature_count(self) -> int:
        return self.feature_events

    @property
    def regime_count(self) -> int:
        return self.regime_events

    @property
    def strategy_count(self) -> int:
        return self.strategy_events

    @property
    def opportunity_count(self) -> int:
        return self.opportunity_events

    @property
    def risk_count(self) -> int:
        return self.risk_decisions

    @property
    def gate_count(self) -> int:
        return self.gate_allowed + self.gate_blocked

    @property
    def order_count(self) -> int:
        return self.paper_orders_created

    @property
    def fill_count(self) -> int:
        return self.paper_fills

    @property
    def position_count(self) -> int:
        return self.position_transitions

    @property
    def portfolio_count(self) -> int:
        return self.portfolio_snapshots

    @property
    def perf_count(self) -> int:
        return self.performance_calculations

    def to_sorted_dict(self) -> dict[str, Any]:
        return _dc_to_sorted_dict(self)


@dataclass(slots=True, frozen=True)
class BacktestPerformanceSummary:
    total_return_pct: float = 0.0
    realized_pnl_quote: Decimal = Decimal("0")
    unrealized_pnl_quote: Decimal = Decimal("0")
    total_fees_quote: Decimal = Decimal("0")
    gross_exposure_quote: Decimal = Decimal("0")
    net_exposure_quote: Decimal = Decimal("0")
    max_drawdown_pct: float = 0.0
    sharpe_ratio_24h: float | None = None
    rolling_24h_return_pct: float | None = None
    win_rate_pct: float | None = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    fill_count: int = 0
    order_count: int = 0
    avg_fill_qty_base: Decimal = Decimal("0")
    avg_notional_per_trade: Decimal = Decimal("0")
    final_equity_quote: Decimal = Decimal("0")
    initial_equity_quote: Decimal = Decimal("0")

    @property
    def total_return(self) -> float:
        return self.total_return_pct

    @property
    def realized_pnl(self) -> Decimal:
        return self.realized_pnl_quote

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.unrealized_pnl_quote

    @property
    def fees(self) -> Decimal:
        return self.total_fees_quote

    @property
    def exposure(self) -> Decimal:
        return self.gross_exposure_quote

    @property
    def max_drawdown(self) -> float:
        return self.max_drawdown_pct

    @property
    def rolling_24h(self) -> float | None:
        return self.rolling_24h_return_pct

    def to_sorted_dict(self) -> dict[str, Any]:
        return _dc_to_sorted_dict(self)


@dataclass(slots=True, frozen=True)
class BacktestRunResult:
    metadata: BacktestRun
    assumptions: BacktestAssumptions
    counts: BacktestRunCounts
    performance: BacktestPerformanceSummary
    window_split: BacktestWindowSplit | None
    provenance: dict[str, Any]
    failure_reason_codes: tuple[str, ...]
    engine_versions: dict[str, str]
    run_notes: tuple[str, ...]

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema_version": "bkt_result_v1",
            "engine_version": BACKTEST_ENGINE_VERSION,
            "contract_version": CONTRACT_VERSION,
            "metadata": self.metadata.to_sorted_dict(),
            "assumptions": self.assumptions.to_sorted_dict(),
            "counts": self.counts.to_sorted_dict(),
            "performance": self.performance.to_sorted_dict(),
            "window_split": self.window_split.to_sorted_dict() if self.window_split else None,
            "provenance": _dc_to_sorted_dict(self.provenance),
            "failure_reason_codes": list(self.failure_reason_codes),
            "engine_versions": dict(self.engine_versions),
            "run_notes": list(self.run_notes),
        }


def compute_result_sha256(result: BacktestRunResult | dict[str, Any]) -> str:
    if isinstance(result, BacktestRunResult):
        obj = result.to_sorted_dict()
    else:
        obj = result
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_backtest_artifact(result: BacktestRunResult, path: str | Path) -> str:
    p = Path(path)
    d = result.to_sorted_dict()
    sha = compute_result_sha256(d)
    d["result_sha256"] = sha
    payload = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload, encoding="utf-8")
    return sha


def load_backtest_artifact(path: str | Path) -> tuple[dict[str, Any], str]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if "result_sha256" in raw:
        verify_dict = {k: v for k, v in raw.items() if k != "result_sha256"}
        actual_sha = compute_result_sha256(verify_dict)
    else:
        actual_sha = compute_result_sha256(raw)
    return raw, actual_sha


def verify_deterministic_artifact(
    artifact_paths: list[str | Path],
) -> dict[str, Any]:
    shas: set[str] = set()
    for p in artifact_paths:
        _, sha = load_backtest_artifact(p)
        shas.add(sha)
    return {
        "file_count": len(artifact_paths),
        "unique_sha_count": len(shas),
        "sha_list": sorted(shas),
        "is_deterministic": len(shas) == 1,
    }


def _split_events_for_windows(
    events: list[Any],
    *,
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
) -> tuple[list[Any], list[Any], list[Any]]:
    if not events:
        return [], [], []
    total = len(events)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * validation_ratio)
    return events[:train_end], events[train_end:val_end], events[val_end:]


@dataclass(slots=True)
class BacktestRunner:
    assumptions: BacktestAssumptions
    fill_config: FillAssumptionsConfig = field(default_factory=FillAssumptionsConfig)
    enforce_order_strict: bool = True
    use_walk_forward: bool = False
    train_ratio: float = 0.6
    validation_ratio: float = 0.2
    strategy_engine: str = "trend"
    run_notes: list[str] = field(default_factory=list)

    def _iter_bundle_events(
        self,
        bundle: Any,
    ) -> Iterable[MarketTick | Candle]:
        for event in bundle.iter_events():
            if isinstance(event, (MarketTick, Candle)):
                yield event

    def _build_window_split(
        self,
        sorted_events: list[Any],
        train_events: list[Any],
        val_events: list[Any],
        test_events: list[Any],
    ) -> BacktestWindowSplit:
        train_split = None
        val_split = None
        test_split = None
        if train_events:
            first_ts = getattr(train_events[0], "event_ts", "")
            last_ts = getattr(train_events[-1], "event_ts", "")
            train_split = WindowSplit(
                dataset=SplitDataset.TRAIN,
                start_instant=first_ts,
                end_instant=last_ts,
                event_count=len(train_events),
            )
        if val_events:
            first_ts = getattr(val_events[0], "event_ts", "")
            last_ts = getattr(val_events[-1], "event_ts", "")
            val_split = WindowSplit(
                dataset=SplitDataset.VALIDATION,
                start_instant=first_ts,
                end_instant=last_ts,
                event_count=len(val_events),
            )
        if test_events:
            first_ts = getattr(test_events[0], "event_ts", "")
            last_ts = getattr(test_events[-1], "event_ts", "")
            test_split = WindowSplit(
                dataset=SplitDataset.TEST,
                start_instant=first_ts,
                end_instant=last_ts,
                event_count=len(test_events),
            )
        return BacktestWindowSplit(
            train=train_split,
            validation=val_split,
            test=test_split,
            overlap_free=True,
        )

    def _init_pipeline_ctx(
        self,
        run_id: str,
        bus: InMemoryTypedEventBus,
    ) -> BacktestPipelineContext:
        from app.strategies import MomentumStrategy, TrendFollowingStrategy
        ctx = BacktestPipelineContext(
            run_id=run_id,
            bus=bus,
            clock=ReplayClock(),
            fill_config=self.fill_config,
            engines=BacktestPipelineEngines(),
            initial_equity=Decimal(self.assumptions.initial_equity_quote),
            cash_quote=Decimal(self.assumptions.initial_equity_quote),
            quote_currency=self.assumptions.quote_currency,
        )
        if self.strategy_engine == "momentum":
            ctx.strategy_active = MomentumStrategy
        else:
            ctx.strategy_active = TrendFollowingStrategy
        return ctx

    def run(
        self,
        bundle: Any,
        *,
        run_id: str | None = None,
    ) -> BacktestRunResult:
        det_seed = f"{getattr(bundle, 'bundle_id', 'sbkt')}|{getattr(bundle, 'bundle_version', 'x')}|{getattr(bundle, 'compute_sha256', lambda: '0')()}"
        actual_run_id = run_id or _runner_ulid_new(det_seed, counter=0)
        bus = InMemoryTypedEventBus()
        ctx = self._init_pipeline_ctx(actual_run_id, bus)

        raw_events = list(self._iter_bundle_events(bundle))
        sorted_events = deterministic_sort_events(raw_events)
        if self.enforce_order_strict:
            verify_event_ordering_strict(sorted_events)

        train_events, val_events, test_events = _split_events_for_windows(
            sorted_events,
            train_ratio=self.train_ratio,
            validation_ratio=self.validation_ratio,
        )
        window_split = self._build_window_split(
            sorted_events, train_events, val_events, test_events
        )

        market_count = 0
        feature_count = 0
        regime_count = 0
        strategy_count = 0
        opportunity_count = 0
        risk_total = 0
        risk_approved = 0
        risk_rejected = 0
        gate_allowed = 0
        gate_blocked = 0
        porder_created = 0
        fills = 0
        fill_rejections = 0
        pos_transitions = 0
        snaps = 0
        perfs = 0
        quality_blocked = 0
        skipped_total = 0
        all_failures: list[str] = []
        step_results: list[ReplayPipelineStepResult] = []

        for event in sorted_events:
            tick = event if isinstance(event, MarketTick) else None
            candle = event if isinstance(event, Candle) else None
            res = run_replay_pipeline_step(ctx, tick=tick, candle=candle)
            step_results.append(res)
            market_count += 1
            if res.feature is not None:
                feature_count += 1
            if res.regime is not None:
                regime_count += 1
            if res.strategy_signal is not None:
                strategy_count += 1
            if res.opportunity is not None:
                opportunity_count += 1
            if res.risk_decision is not None:
                risk_total += 1
                v = getattr(res.risk_decision, "decision", None)
                try:
                    from app.contracts.risk import RiskDecisionResult
                    if v == RiskDecisionResult.APPROVED:
                        risk_approved += 1
                    else:
                        risk_rejected += 1
                except BaseException:
                    if v is not None and str(v) in {"APPROVED", "RiskDecisionResult.APPROVED"}:
                        risk_approved += 1
                    else:
                        risk_rejected += 1
            gr = res.gate_result
            if gr is not None:
                if getattr(gr, "allowed", False):
                    gate_allowed += 1
                else:
                    gate_blocked += 1
            if res.paper_order is not None:
                porder_created += 1
            if res.paper_fill is not None:
                fills += 1
            if res.paper_order is not None and res.paper_fill is None:
                fill_rejections += 1
            if res.position is not None:
                pos_transitions += 1
            if res.portfolio_snapshot is not None:
                snaps += 1
            if res.rolling_perf is not None:
                perfs += 1
            if res.quality_violations:
                quality_blocked += 1
            if res.skipped_stages:
                skipped_total += 1
            for fr in res.failure_reasons:
                all_failures.append(fr)

        counts = BacktestRunCounts(
            market_events=market_count,
            feature_events=feature_count,
            regime_events=regime_count,
            strategy_events=strategy_count,
            opportunity_events=opportunity_count,
            risk_decisions=risk_total,
            risk_approved=risk_approved,
            risk_rejected=risk_rejected,
            gate_allowed=gate_allowed,
            gate_blocked=gate_blocked,
            paper_orders_created=porder_created,
            paper_fills=fills,
            paper_fill_rejections=fill_rejections,
            position_transitions=pos_transitions,
            portfolio_snapshots=snaps,
            performance_calculations=perfs,
            failures=len(ctx.failures),
            quality_blocked=quality_blocked,
            skipped=skipped_total,
        )

        performance = self._compute_performance_summary(ctx)
        assumptions_hash = self.assumptions.compute_hash()
        provenance_sha = hashlib.sha256(
            "|".join([
                str(bundle.bundle_id),
                str(bundle.bundle_version),
                str(bundle.compute_sha256()),
                BACKTEST_ENGINE_VERSION,
                CONTRACT_VERSION,
                assumptions_hash,
            ]).encode("utf-8")
        ).hexdigest()

        metadata = BacktestRun(
            run_id=actual_run_id,
            bundle_id=str(bundle.bundle_id),
            bundle_version=str(bundle.bundle_version),
            bundle_sha=str(bundle.compute_sha256()),
            assumptions_hash=assumptions_hash,
            timeframe=getattr(bundle, "timeframe", "1m") or "1m",
            start_instant=getattr(sorted_events[0], "event_ts", "") if sorted_events else "",
            end_instant=getattr(sorted_events[-1], "event_ts", "") if sorted_events else "",
            train_window=window_split,
            validation_window=window_split,
            test_window=window_split,
            walk_forward_mode="disabled" if not self.use_walk_forward else "enabled_foundation",
            event_count=market_count,
            fill_count=fills,
            portfolio_snapshot_count=snaps,
            result_hash="",
            engine_version=BACKTEST_ENGINE_VERSION,
            run_mode="backtest",
            source_type="replay",
        )

        engine_versions: dict[str, str] = {
            "backtest": BACKTEST_ENGINE_VERSION,
            "contract": CONTRACT_VERSION,
            "fill_model": getattr(self.fill_config, "__version__", "1.0.0") if hasattr(self.fill_config, "__version__") else "1.0.0",
            "assumptions": BACKTEST_ASSUMPTIONS_VERSION,
            "run_metadata": BACKTEST_RUN_VERSION,
        }
        try:
            from app.features import SFEA01_FEATURE_VERSION
            engine_versions["feature"] = SFEA01_FEATURE_VERSION
        except BaseException:
            pass
        try:
            from app.regime import SREG01_DETECTOR_VERSION
            engine_versions["regime"] = SREG01_DETECTOR_VERSION
        except BaseException:
            pass
        try:
            from app.strategies import STRATEGY_VERSION_DEFAULT
            engine_versions["strategy"] = STRATEGY_VERSION_DEFAULT
        except BaseException:
            pass
        try:
            from app.opportunity import SCORER_VERSION_STORY_DEFAULT
            engine_versions["opportunity"] = SCORER_VERSION_STORY_DEFAULT
        except BaseException:
            pass
        try:
            from app.simulation import FILL_MODEL_VERSION
            engine_versions["fill_model"] = FILL_MODEL_VERSION
        except BaseException:
            pass
        try:
            from app.risk.gate import GATE_VERSION_RSK02
            engine_versions["gate"] = GATE_VERSION_RSK02
        except BaseException:
            pass

        provenance: dict[str, Any] = {
            "bundle_provenance_sha256": provenance_sha,
            "bundle_sha256": str(bundle.compute_sha256()),
            "assumptions_sha256": assumptions_hash,
            "bundle_symbol_count": len(getattr(bundle, "symbols", []) or []),
            "bundle_event_count": len(sorted_events),
            "symbols": sorted([str(s) for s in (getattr(bundle, "symbols", []) or [])]),
            "deterministic_ordered": True,
            "look_ahead_guards": True,
            "overlap_free_splits": window_split.overlap_free if window_split else True,
            "fail_closed_enabled": True,
        }

        result = BacktestRunResult(
            metadata=metadata,
            assumptions=self.assumptions,
            counts=counts,
            performance=performance,
            window_split=window_split,
            provenance=provenance,
            failure_reason_codes=tuple(sorted(set(all_failures))),
            engine_versions=engine_versions,
            run_notes=tuple(self.run_notes),
        )

        sha = compute_result_sha256(result)
        object.__setattr__(result.metadata, "result_hash", sha)

        return result

    def _compute_performance_summary(
        self,
        ctx: BacktestPipelineContext,
    ) -> BacktestPerformanceSummary:
        last_snap = ctx.last_snapshot
        initial = Decimal(self.assumptions.initial_equity_quote)
        if last_snap is not None:
            final_eq = getattr(last_snap, "equity_quote", Decimal("0"))
            realized = getattr(last_snap, "realized_pnl_quote", Decimal("0"))
            unrealized = getattr(last_snap, "unrealized_pnl_quote", Decimal("0"))
            fees = getattr(last_snap, "fees_quote", Decimal("0"))
            gross_exp = getattr(last_snap, "gross_exposure_quote", Decimal("0"))
            net_exp = getattr(last_snap, "net_exposure_quote", Decimal("0"))
            max_dd_pct = float(getattr(last_snap, "max_drawdown_pct", 0.0) or 0.0)
        else:
            final_eq = initial
            realized = Decimal("0")
            unrealized = Decimal("0")
            fees = Decimal("0")
            gross_exp = Decimal("0")
            net_exp = Decimal("0")
            max_dd_pct = 0.0

        initial_f = float(initial) if initial > 0 else 1.0
        total_return = (float(final_eq) - initial_f) / initial_f * 100.0

        total_fills = len(ctx.fills)
        total_orders = total_fills
        sum_notional = Decimal("0")
        sum_qty = Decimal("0")
        for f in ctx.fills:
            n = getattr(f, "notional_quote", Decimal("0"))
            if isinstance(n, Decimal):
                sum_notional += n
            q = getattr(f, "fill_qty_base", Decimal("0"))
            if isinstance(q, Decimal):
                sum_qty += q

        rolling_24h_return = None
        if ctx.snapshots:
            latest = ctx.snapshots[-1]
            last_24h_start = None
            end_ms = 0
            try:
                dt_end = getattr(latest, "ts", "")
                for s in reversed(ctx.snapshots):
                    s_ms = 0
                    try:
                        ts_val = getattr(s, "ts", "")
                        if isinstance(ts_val, str):
                            from datetime import datetime as _dt, timezone as _tz
                            t = _dt.strptime(ts_val.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z")
                            s_ms = t.timestamp() * 1000
                    except BaseException:
                        pass
                    if end_ms == 0:
                        end_ms = s_ms
                    if end_ms - s_ms <= 86400 * 1000:
                        last_24h_start = s
                    else:
                        break
            except BaseException:
                pass
            if last_24h_start is not None and last_24h_start is not latest:
                start_eq = float(getattr(last_24h_start, "equity_quote", Decimal("0")) or 1.0)
                end_eq = float(getattr(latest, "equity_quote", Decimal("0")) or 0.0)
                if start_eq > 0:
                    rolling_24h_return = (end_eq - start_eq) / start_eq * 100.0

        perf = BacktestPerformanceSummary(
            total_return_pct=total_return,
            realized_pnl_quote=realized,
            unrealized_pnl_quote=unrealized,
            total_fees_quote=fees,
            gross_exposure_quote=gross_exp,
            net_exposure_quote=net_exp,
            max_drawdown_pct=max_dd_pct,
            rolling_24h_return_pct=rolling_24h_return,
            final_equity_quote=final_eq,
            initial_equity_quote=initial,
            fill_count=total_fills,
            order_count=total_orders,
            avg_fill_qty_base=sum_qty / Decimal(max(1, total_fills)),
            avg_notional_per_trade=sum_notional / Decimal(max(1, total_fills)),
        )
        return perf


def run_deterministic_check_n_times(
    runner_factory: Any,
    bundle: Any,
    n: int = 10,
) -> dict[str, Any]:
    shas: set[str] = set()
    results: list[BacktestRunResult] = []
    for _ in range(n):
        r = runner_factory().run(bundle)
        shas.add(compute_result_sha256(r))
        results.append(r)
    return {
        "unique_sha_count": len(shas),
        "sha_list": sorted(shas),
        "n_runs": n,
        "is_deterministic": len(shas) == 1,
    }
