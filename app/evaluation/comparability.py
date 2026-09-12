"""6 comparability invariants + 4 extras (fold, regime, dataset, thresholds).

Mismatch → CompareValidationError fail-closed. Happy path → ComparabilityResult(comparable=True).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.contracts.model import (
    DatasetKindEnum,
    ModelCompatibilityRef,
    ModelEvaluation,
    ModelVersion,
    TrainingDataRange,
)
from app.registry.registry import EvidenceRef

from app.evaluation.exceptions import (
    CompareValidationError,
    ERR_INCOMPARABLE_COMPATIBILITY,
    ERR_INCOMPARABLE_COST,
    ERR_INCOMPARABLE_DATASET,
    ERR_INCOMPARABLE_FOLD_COUNT,
    ERR_INCOMPARABLE_REGIME_GROUPS,
    ERR_INCOMPARABLE_THRESHOLDS,
    ERR_INCOMPARABLE_UNIVERSE,
    ERR_INCOMPARABLE_WINDOW,
)


MIN_WINDOW_OVERLAP_RATIO = Decimal("0.99")


@dataclass
class ComparabilityInvariants:
    """Canonical set of invariants extracted from ModelVersion + evaluations."""

    dataset_kind: DatasetKindEnum
    window_start: str
    window_end: str
    thresholds_config_version: str
    cost_config_version: str
    symbol_universe_canonical: tuple[str, ...]
    compatibility_feature: str
    compatibility_strategy: str
    compatibility_regime: str
    fold_count: int | None
    regime_groups_canonical: tuple[str, ...] | None
    metric_version: str = "1.0.0-smdl02"

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "compatibility_feature": self.compatibility_feature,
            "compatibility_regime": self.compatibility_regime,
            "compatibility_strategy": self.compatibility_strategy,
            "cost_config_version": self.cost_config_version,
            "dataset_kind": self.dataset_kind.value,
            "fold_count": self.fold_count,
            "metric_version": self.metric_version,
            "regime_groups_canonical": list(self.regime_groups_canonical) if self.regime_groups_canonical is not None else None,
            "symbol_universe_canonical": list(self.symbol_universe_canonical),
            "thresholds_config_version": self.thresholds_config_version,
            "window_end": self.window_end,
            "window_start": self.window_start,
        }


@dataclass
class ComparabilityResult:
    comparable: bool
    invariants: ComparabilityInvariants
    mismatches: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.mismatches, list):
            raise CompareValidationError(ERR_INCOMPARABLE_WINDOW, "mismatches must be list", {"type": type(self.mismatches).__name__})


def _instant_to_millis(s: str) -> int:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _window_overlap_ratio(a: TrainingDataRange, b: TrainingDataRange) -> Decimal:
    a_s = _instant_to_millis(a.start)
    a_e = _instant_to_millis(a.end)
    b_s = _instant_to_millis(b.start)
    b_e = _instant_to_millis(b.end)
    if a_e < a_s or b_e < b_s:
        return Decimal("0")
    inter_s = max(a_s, b_s)
    inter_e = min(a_e, b_e)
    if inter_e < inter_s:
        return Decimal("0")
    union_s = min(a_s, b_s)
    union_e = max(a_e, b_e)
    if union_e == union_s:
        return Decimal("1")
    inter = Decimal(inter_e - inter_s)
    union = Decimal(union_e - union_s)
    if union <= 0:
        return Decimal("0")
    return (inter / union).quantize(Decimal("1e-12"))


def _canonical_universe(symbols: Any) -> tuple[str, ...]:
    if not isinstance(symbols, list):
        return tuple()
    cleaned: list[str] = []
    for s in symbols:
        if isinstance(s, str) and s:
            cleaned.append(s.casefold())
    return tuple(sorted(set(cleaned)))


def _canonical_regime_groups(regime_matrix_refs: Any) -> tuple[str, ...] | None:
    if not isinstance(regime_matrix_refs, list):
        return None
    out: list[str] = []
    for row in regime_matrix_refs:
        if isinstance(row, dict):
            sid = row.get("strategy_id")
            reg = row.get("regime")
            if isinstance(sid, str) and isinstance(reg, str):
                out.append(f"{sid}|{reg}")
        elif isinstance(row, str):
            out.append(row)
    return tuple(sorted(set(out)))


def build_comparability_invariants(
    mv: ModelVersion,
    eval: ModelEvaluation,
    evidence_refs: list[EvidenceRef],
    artifact_summary: dict[str, Any] | None = None,
) -> ComparabilityInvariants:
    """Extract invariants from one side (champion or challenger)."""
    artifact_summary = artifact_summary or {}
    window: TrainingDataRange | None = getattr(mv, "training_data_range", None)
    if window is None or not isinstance(window, TrainingDataRange):
        raise CompareValidationError(
            ERR_INCOMPARABLE_WINDOW,
            "ModelVersion.training_data_range TrainingDataRange required",
            {"got_type": type(window).__name__ if window is not None else "None"},
        )
    compat: ModelCompatibilityRef | None = getattr(mv, "compatibility_ref", None)
    if compat is None or not isinstance(compat, ModelCompatibilityRef):
        raise CompareValidationError(
            ERR_INCOMPARABLE_COMPATIBILITY,
            "ModelVersion.compatibility_ref required ModelCompatibilityRef",
            {"got_type": type(compat).__name__ if compat is not None else "None"},
        )
    universe_list = getattr(mv, "symbol_universe", None)
    if not isinstance(universe_list, list) or not universe_list:
        # fall back to metadata symbol_universe OR metadata symbol_universe_size (infer by placeholder empty canonical)
        universe_list = mv.metadata.get("symbol_universe", []) if isinstance(mv.metadata, dict) else []
        if not isinstance(universe_list, list):
            universe_list = []
    cost_cfg = mv.metadata.get("cost_config_version") or ""
    thresholds_cfg = mv.metadata.get("thresholds_config_version") or eval.thresholds_config_version
    if not cost_cfg:
        cost_cfg = artifact_summary.get("cost_config_version", "") or ""
    fold_count: int | None = artifact_summary.get("fold_count") if isinstance(artifact_summary, dict) else None
    if fold_count is None or not isinstance(fold_count, int):
        fold_count = None
    regime_groups = _canonical_regime_groups(artifact_summary.get("regime_matrix") if isinstance(artifact_summary, dict) else None)
    return ComparabilityInvariants(
        dataset_kind=eval.dataset_kind,
        window_start=window.start,
        window_end=window.end,
        thresholds_config_version=thresholds_cfg,
        cost_config_version=str(cost_cfg),
        symbol_universe_canonical=_canonical_universe(universe_list),
        compatibility_feature=compat.feature_version,
        compatibility_strategy=compat.strategy_version,
        compatibility_regime=compat.regime_version,
        fold_count=fold_count,
        regime_groups_canonical=regime_groups,
    )


def check_comparability(
    champion_mv: ModelVersion,
    challenger_mv: ModelVersion,
    champion_eval: ModelEvaluation,
    challenger_eval: ModelEvaluation,
    champion_evidence: list[EvidenceRef],
    challenger_evidence: list[EvidenceRef],
    champion_artifact_summary: dict[str, Any] | None = None,
    challenger_artifact_summary: dict[str, Any] | None = None,
) -> ComparabilityResult:
    """6 invariants + 4 extras (dataset/thresholds/fold/regime).

    Mismatch any → raise CompareValidationError(ERR_INCOMPARABLE_*, mismatches).
    """
    c_inv = build_comparability_invariants(champion_mv, champion_eval, champion_evidence, champion_artifact_summary)
    t_inv = build_comparability_invariants(challenger_mv, challenger_eval, challenger_evidence, challenger_artifact_summary)
    mismatches: list[str] = []
    window_c = TrainingDataRange(start=c_inv.window_start, end=c_inv.window_end)
    window_t = TrainingDataRange(start=t_inv.window_start, end=t_inv.window_end)
    overlap = _window_overlap_ratio(window_c, window_t)
    if overlap < MIN_WINDOW_OVERLAP_RATIO:
        mismatches.append("window_overlap")
    if c_inv.dataset_kind != t_inv.dataset_kind:
        mismatches.append("dataset_kind")
    if c_inv.thresholds_config_version != t_inv.thresholds_config_version:
        mismatches.append("thresholds_config_version")
    if c_inv.cost_config_version != t_inv.cost_config_version:
        mismatches.append("cost_config_version")
    if c_inv.symbol_universe_canonical != t_inv.symbol_universe_canonical:
        mismatches.append("symbol_universe")
    if (
        c_inv.compatibility_feature != t_inv.compatibility_feature
        or c_inv.compatibility_strategy != t_inv.compatibility_strategy
        or c_inv.compatibility_regime != t_inv.compatibility_regime
    ):
        mismatches.append("compatibility_ref")
    if c_inv.fold_count is not None and t_inv.fold_count is not None and c_inv.fold_count != t_inv.fold_count:
        mismatches.append("fold_count")
    if c_inv.regime_groups_canonical is not None and t_inv.regime_groups_canonical is not None and c_inv.regime_groups_canonical != t_inv.regime_groups_canonical:
        mismatches.append("regime_groups")
    if mismatches:
        # Map first mismatch to ERR_* enum (conservatively fail-closed; caller gets all list in details)
        first = mismatches[0]
        err_map = {
            "window_overlap": ERR_INCOMPARABLE_WINDOW,
            "dataset_kind": ERR_INCOMPARABLE_DATASET,
            "thresholds_config_version": ERR_INCOMPARABLE_THRESHOLDS,
            "cost_config_version": ERR_INCOMPARABLE_COST,
            "symbol_universe": ERR_INCOMPARABLE_UNIVERSE,
            "compatibility_ref": ERR_INCOMPARABLE_COMPATIBILITY,
            "fold_count": ERR_INCOMPARABLE_FOLD_COUNT,
            "regime_groups": ERR_INCOMPARABLE_REGIME_GROUPS,
        }
        err = err_map.get(first, ERR_INCOMPARABLE_WINDOW)
        raise CompareValidationError(
            err,
            f"Champion/Challenger incomparable mismatches: {mismatches}",
            {
                "mismatches": mismatches,
                "champion_invariants": c_inv.to_sorted_dict(),
                "challenger_invariants": t_inv.to_sorted_dict(),
                "window_overlap": str(overlap),
            },
        )
    return ComparabilityResult(comparable=True, invariants=c_inv, mismatches=[])
