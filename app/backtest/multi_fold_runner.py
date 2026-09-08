"""S-BKT-02: Multi-Fold Walk-Forward Runner + Aggregate Artifact.

Yeni domain cost/position/portfolio ALGORITMASI YOK.
Sadece S-BKT-01 BacktestRunner'ı fold bazinda tekrar çağırır,
aggregate sonucu deterministik şekilde üretir.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

from .cost_injection import CostModelOverrides, cost_overrides_manifest
from .run_metadata import BacktestAssumptions, BacktestRun, BacktestWindowSplit
from .runner import (
    BacktestPerformanceSummary,
    BacktestRunCounts,
    BacktestRunResult,
    BacktestRunner,
    compute_result_sha256,
    load_backtest_artifact,
    save_backtest_artifact,
)
from .walk_forward import (
    WalkForwardConfig,
    WalkForwardFoldDefinition,
    _instant_from_event,
    generate_fold_splits,
)


@dataclass(frozen=True)
class MultiFoldManifest:
    config_sorted_dict: dict[str, Any]
    fold_definitions_sorted_dict: list[dict[str, Any]]
    per_fold_cost_manifest: list[dict[str, Any]]
    per_fold_sha256: list[str]
    overall_status: str
    failed_fold_ids: list[str]

    def to_sorted_dict(self) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    "walk_forward_config": self.config_sorted_dict,
                    "fold_definitions": self.fold_definitions_sorted_dict,
                    "per_fold_cost_manifest": self.per_fold_cost_manifest,
                    "per_fold_sha256": list(self.per_fold_sha256),
                    "overall_status": self.overall_status,
                    "failed_fold_ids": list(self.failed_fold_ids),
                }.items()
            )
        )


@dataclass(frozen=True)
class MultiFoldAggregateSummary:
    fold_count: int
    num_folds_attempted: int
    pass_count: int
    fail_count: int
    avg_total_return_pct: Decimal
    avg_max_drawdown_pct: Decimal
    avg_realized_pnl_quote: Decimal
    avg_fees_quote_total: Decimal
    per_fold_metrics_sorted: tuple[dict[str, Any], ...] = ()
    avg_sharpe_ratio_24h: float | None = None
    avg_sortino_ratio_24h: float | None = None
    avg_pfactor: float | None = None
    compound_total_return_pct: float = 0.0
    min_fold_total_return_pct: float = 0.0
    max_fold_total_return_pct: float = 0.0
    aggregate_info_codes: tuple[str, ...] = ()

    @property
    def apf(self) -> float | None:
        return self.avg_pfactor

    def to_sorted_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Decimal):
                raw[f.name] = format(v, "f")
            elif isinstance(v, tuple):
                raw[f.name] = list(v)
            else:
                raw[f.name] = v
        if "avg_pfactor" in raw:
            raw["avg_profit_factor"] = raw.pop("avg_pfactor")
        return dict(sorted(raw.items()))


setattr(MultiFoldAggregateSummary, "avg_profit_factor", MultiFoldAggregateSummary.apf)
setattr(MultiFoldAggregateSummary, "num_folds_ok", property(lambda self: self.pass_count))


@dataclass(frozen=True)
class MultiFoldBacktestResult:
    run_id: str
    manifest: MultiFoldManifest
    aggregate_summary: MultiFoldAggregateSummary
    per_fold_results: list[BacktestRunResult]

    def to_sorted_dict(self) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    "run_id": self.run_id,
                    "manifest": self.manifest.to_sorted_dict(),
                    "aggregate_summary": self.aggregate_summary.to_sorted_dict(),
                    "per_fold_results": [r.to_sorted_dict() for r in self.per_fold_results],
                }.items()
            )
        )


def _avg_or_zero(items: Sequence[Decimal]) -> Decimal:
    if not items:
        return Decimal("0")
    total = sum(items, Decimal("0"))
    n = Decimal(len(items))
    return (total / n).quantize(Decimal("0.00000001"))


def compute_multifold_sha256(result: MultiFoldBacktestResult) -> str:
    raw = json.dumps(result.to_sorted_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fold_subset_events(events: Iterable[Any], fold: WalkForwardFoldDefinition) -> list[Any]:
    ev_list = sorted(events, key=lambda e: _instant_from_event(e))
    return ev_list[fold.segment_start_idx : fold.segment_end_idx]


def run_multifold_walkforward(
    runner_factory: Any,
    bundle: Any,
    walk_forward: WalkForwardConfig | None = None,
    cost_overrides_global: CostModelOverrides | None = None,
    cost_overrides_per_fold: dict[str, CostModelOverrides] | None = None,
    *,
    run_id: str | None = None,
) -> MultiFoldBacktestResult:
    wf_cfg = walk_forward if walk_forward is not None else WalkForwardConfig()
    if wf_cfg.n_folds < 1:
        raise ValueError("BK_MF: n_folds >=1 olmali")
    events = list(bundle.iter_events())
    folds = generate_fold_splits(events, wf_cfg)
    base_fill = runner_factory()._defaults_fill_config if hasattr(runner_factory(), "_defaults_fill_config") else None

    per_fold_results: list[BacktestRunResult] = []
    failed_fold_ids: list[str] = []
    per_fold_sha: list[str] = []
    per_fold_cost: list[dict[str, Any]] = []

    base_run_id = run_id if run_id is not None else f"MF_{wf_cfg.n_folds}F_{len(events)}E"
    for fold in folds:
        fold_run_id = f"{base_run_id}_{fold.fold_id}"
        fold_override = (cost_overrides_per_fold or {}).get(fold.fold_id)
        fold_ws = fold.to_backtest_window_split()
        sub_events = _fold_subset_events(events, fold)

        if hasattr(bundle, "version") and hasattr(bundle, "bundle_id") and hasattr(bundle, "sha"):

            class _LocalBundle:
                bundle_id = bundle.bundle_id
                bundle_version = getattr(bundle, "bundle_version", bundle.version)
                version = bundle.version
                sha = bundle.sha
                symbol = getattr(bundle, "symbol", None)

                def iter_events(self):
                    return iter(sub_events)

                def compute_sha256(self):
                    return self.sha

            fold_bundle: Any = _LocalBundle()
        else:
            fold_bundle = bundle
        try:
            runner = runner_factory(
                cost_overrides=cost_overrides_global,
                cost_overrides_fold=fold_override,
                walk_forward_single_fold=fold_ws,
            )
            fold_result = runner.run(fold_bundle, run_id=fold_run_id, fold_backtest_window_split_override=fold_ws)
        except Exception as exc:  # noqa: BLE001 — fail-closed, no trade leak
            # --- BLOK-1: deterministic start/end from fold_ws splits (contract required) ---
            split_candidates = [s for s in (fold_ws.train, fold_ws.validation, fold_ws.test) if s is not None]
            if split_candidates:
                cands_start_sorted = sorted(split_candidates, key=lambda w: w.start_instant)
                cands_end_sorted = sorted(split_candidates, key=lambda w: w.end_instant)
                fail_start_instant = cands_start_sorted[0].start_instant
                fail_end_instant = cands_end_sorted[-1].end_instant
                fail_event_count = sum(getattr(s, "event_count", 0) for s in split_candidates)
            else:
                fail_start_instant = "1970-01-01T00:00:00.000Z"
                fail_end_instant = "1970-01-01T00:00:00.000Z"
                fail_event_count = 0
            meta_fail = BacktestRun(
                run_id=fold_run_id,
                bundle_id=getattr(bundle, "bundle_id", "unknown"),
                bundle_version=getattr(bundle, "version", "0"),
                bundle_sha=getattr(bundle, "sha", "0"),
                engine_version="1.0.0",
                contract_version="1.0.0",
                run_mode="replay",
                train_window=fold_ws.train,
                validation_window=fold_ws.validation,
                test_window=fold_ws.test,
                start_instant=fail_start_instant,
                end_instant=fail_end_instant,
                event_count=fail_event_count,
                walk_forward_mode="enabled_foundation",
                timeframe=getattr(bundle, "timeframe", "1m") or "1m",
            )
            asum_fail = BacktestAssumptions()
            cnt_fail = BacktestRunCounts()
            perf_fail = BacktestPerformanceSummary()
            # --- BLOK-2: deterministic fallback performance_v2 (contract required, fail closed) ---
            from .runner import upgrade_backtest_performance_v1_to_v2
            perf_fail_v2 = upgrade_backtest_performance_v1_to_v2(
                perf_fail,
                metrics_info_codes=("BK_MF_FOLD_FAIL_V2_FALLBACK",),
            )
            fail_code = f"BK_MF_FOLD_FAIL_{fold.fold_id}"
            fold_result = BacktestRunResult(
                metadata=meta_fail,
                assumptions=asum_fail,
                counts=cnt_fail,
                performance=perf_fail,
                performance_v2=perf_fail_v2,
                window_split=fold_ws,
                provenance={
                    "failure_exception_type": type(exc).__name__,
                    "failure_exception_code": fail_code,
                },
                failure_reason_codes=(fail_code,),
                engine_versions={"bkt_engine": "1.0.0"},
                run_notes=(f"fold_exception_{fold.fold_id}",),
            )
        per_fold_results.append(fold_result)
        per_fold_sha.append(compute_result_sha256(fold_result))
        if base_fill is not None:
            per_fold_cost.append(cost_overrides_manifest(base_fill, cost_overrides_global, fold_override))
        else:
            per_fold_cost.append({})
        if fold_result.failure_reason_codes:
            failed_fold_ids.append(fold.fold_id)

    overall_status = "PASS" if not failed_fold_ids else "FAILED"
    manifest = MultiFoldManifest(
        config_sorted_dict=wf_cfg.to_sorted_dict(),
        fold_definitions_sorted_dict=[f.to_sorted_dict() for f in folds],
        per_fold_cost_manifest=per_fold_cost,
        per_fold_sha256=per_fold_sha,
        overall_status=overall_status,
        failed_fold_ids=failed_fold_ids,
    )

    returns = [
        r.performance.total_return_pct
        for r in per_fold_results
        if not r.failure_reason_codes
    ]
    max_dds = [
        r.performance.max_drawdown_pct
        for r in per_fold_results
        if not r.failure_reason_codes
    ]
    rp = [
        r.performance.realized_pnl_quote
        for r in per_fold_results
        if not r.failure_reason_codes
    ]
    fees = [
        r.performance.total_fees_quote
        for r in per_fold_results
        if not r.failure_reason_codes
    ]
    # --- S-BKT-03 per-fold V2 metrics + aggregate canonical ---
    from .runner import BacktestPerformanceSummaryV2
    from .metrics_compute import aggregate_metrics_fold_level, _q8, _r8
    per_fold_dicts: list[dict[str, Any]] = []
    for r in per_fold_results:
        has_v2 = hasattr(r, "performance_v2") and isinstance(r.performance_v2, BacktestPerformanceSummaryV2)
        if has_v2:
            v2: Any = r.performance_v2
            d: dict[str, Any] = {
                "fold_run_id": r.metadata.run_id,
                "total_return_pct": float(v2.total_return_pct or 0.0),
                "net_return_pct": float(v2.net_return_pct or 0.0),
                "max_drawdown_pct": float(v2.max_drawdown_pct or 0.0),
                "total_trades": int(v2.total_trades or 0),
                "win_rate_pct": v2.win_rate_pct,
                "sharpe_ratio_24h": v2.sharpe_ratio_24h,
                "sortino_ratio_24h": v2.sortino_ratio_24h,
                "profit_factor": getattr(v2, "pfactor", None),
                "total_fees_quote": format(v2.total_fees_quote, "f"),
                "cost_overrides_sha256": str(v2.cost_overrides_sha256 or ""),
                "metrics_info_codes": list(v2.metrics_info_codes or ()),
                "failure_reason_codes": list(r.failure_reason_codes or ()),
            }
        else:
            v1 = r.performance
            d = {
                "fold_run_id": r.metadata.run_id,
                "total_return_pct": float(v1.total_return_pct or 0.0),
                "net_return_pct": float(v1.total_return_pct or 0.0),
                "max_drawdown_pct": float(v1.max_drawdown_pct or 0.0),
                "total_trades": int(getattr(v1, "total_trades", 0) or 0),
                "win_rate_pct": getattr(v1, "win_rate_pct", None),
                "sharpe_ratio_24h": getattr(v1, "sharpe_ratio_24h", None),
                "sortino_ratio_24h": None,
                "profit_factor": None,
                "total_fees_quote": format(v1.total_fees_quote, "f"),
                "cost_overrides_sha256": "",
                "metrics_info_codes": ["UPGRADED_FROM_V1_MFOLD"],
                "failure_reason_codes": list(r.failure_reason_codes or ()),
            }
        per_fold_dicts.append(d)
    per_fold_dicts.sort(key=lambda x: str(x.get("fold_run_id", "")))
    passed_only = [d for d, r in zip(per_fold_dicts, per_fold_results) if not r.failure_reason_codes]
    agg = aggregate_metrics_fold_level(passed_only, exclude_none_in_avg=True)
    n_folds_def = len(folds)
    summary = MultiFoldAggregateSummary(
        fold_count=n_folds_def,
        num_folds_attempted=n_folds_def,
        pass_count=n_folds_def - len(failed_fold_ids),
        fail_count=len(failed_fold_ids),
        avg_total_return_pct=_avg_or_zero(returns),
        avg_max_drawdown_pct=_avg_or_zero(max_dds),
        avg_realized_pnl_quote=_avg_or_zero(rp),
        avg_fees_quote_total=_avg_or_zero(fees),
        per_fold_metrics_sorted=tuple(
            {k: (format(v, "f") if isinstance(v, Decimal) else v) for k, v in d.items()} for d in per_fold_dicts
        ),
        avg_sharpe_ratio_24h=agg.get("avg_sharpe_ratio_24h"),
        avg_sortino_ratio_24h=agg.get("avg_sortino_ratio_24h"),
        avg_pfactor=agg.get("avg_profit_factor"),
        compound_total_return_pct=float(agg.get("compound_total_return_pct", 0.0) or 0.0),
        min_fold_total_return_pct=float(agg.get("min_fold_total_return_pct", 0.0) or 0.0),
        max_fold_total_return_pct=float(agg.get("max_fold_total_return_pct", 0.0) or 0.0),
        aggregate_info_codes=tuple(agg.get("info_codes", ())),
    )
    return MultiFoldBacktestResult(
        run_id=base_run_id,
        manifest=manifest,
        aggregate_summary=summary,
        per_fold_results=per_fold_results,
    )


def save_multi_fold_backtest_artifact(
    result: MultiFoldBacktestResult, path: str | Path
) -> str:
    sha = compute_multifold_sha256(result)
    data = dict(sorted({"sha256": sha, "result": result.to_sorted_dict()}.items()))
    Path(path).write_text(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return sha


def load_multi_fold_backtest_artifact(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def verify_multifold_deterministic(artifact_paths: Sequence[str | Path]) -> dict[str, Any]:
    shas: list[str] = []
    for p in artifact_paths:
        loaded = load_multi_fold_backtest_artifact(p)
        sha = loaded.get("sha256")
        if not isinstance(sha, str):
            raise ValueError("BK_MF_VERIFY: artifact sha256 yok")
        shas.append(sha)
    unique = sorted(set(shas))
    return dict(
        sorted(
            {
                "file_count": len(artifact_paths),
                "unique_sha_count": len(unique),
                "sha_list": shas,
                "is_deterministic": len(unique) == 1,
            }.items()
        )
    )
