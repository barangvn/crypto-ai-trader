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
    pass_count: int
    fail_count: int
    avg_total_return_pct: Decimal
    avg_max_drawdown_pct: Decimal
    avg_realized_pnl_quote: Decimal
    avg_fees_quote_total: Decimal

    def to_sorted_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Decimal):
                raw[f.name] = format(v, "f")
            else:
                raw[f.name] = v
        return dict(sorted(raw.items()))


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
            )
            asum_fail = BacktestAssumptions()
            cnt_fail = BacktestRunCounts()
            perf_fail = BacktestPerformanceSummary()
            fail_code = f"BK_MF_FOLD_FAIL_{fold.fold_id}"
            fold_result = BacktestRunResult(
                metadata=meta_fail,
                assumptions=asum_fail,
                counts=cnt_fail,
                performance=perf_fail,
                window_split=fold_ws,
                provenance={"failure_exception": f"{type(exc).__name__}: {exc}"},
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
    summary = MultiFoldAggregateSummary(
        fold_count=len(folds),
        pass_count=len(folds) - len(failed_fold_ids),
        fail_count=len(failed_fold_ids),
        avg_total_return_pct=_avg_or_zero(returns),
        avg_max_drawdown_pct=_avg_or_zero(max_dds),
        avg_realized_pnl_quote=_avg_or_zero(rp),
        avg_fees_quote_total=_avg_or_zero(fees),
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
