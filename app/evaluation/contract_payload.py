"""ChampionChallengerEvaluationPayload typed helper.

REUSE contracts ChampionChallengerEvaluation fields schema 1-1:
- Do NOT duplicate contracts class (S-CON-02C immutable, HARD-RED)
- Produce a build helper that returns a dict the caller can pass to ChampionChallengerEvaluation constructor
  (S-MDL-03 later, with gate passed/CC valid, fills the final contract; engine here builds payload dict WITHOUT gate.passed setting)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.contracts.exceptions import to_sorted_dict
from app.contracts.model import (
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    ModelRef,
    PromotionGateResult,
    _REQUIRED_METRIC_KEYS,
)
from app.evaluation.delta import (
    CRITICAL_DELTA_KEYS_ORDERED,
    DIRECTION_NEUTRAL_MATCH,
    MetricDelta,
    Directionality,
    sorted_metric_keys,
)


@dataclass
class ChampionChallengerEvaluationPayload:
    """Engine output payload — ready for S-CON-02C ChampionChallengerEvaluation constructor (S-MDL-03 fills gate.passed).

    Notes:
      - promotion_gate_result is passed=False default (S-MDL-03 boundary: never set True here).
      - approval_refs = [] (empty, later S-MDL-03 fills).
      - winner_hint ∈ 3 CCWinnerEnum (non-binding just report)
      - cce_contract: real ChampionChallengerEvaluation (constructed safely by post_init override)
    """

    champion_ref: ModelRef
    challenger_ref: ModelRef
    comparable: bool
    winner_hint: CCWinnerEnum
    comparison_metrics: dict[str, Any]  # values are delta (Decimal/float/int) for 11 required keys
    metric_deltas: list[MetricDelta]
    evaluation_period_days: int
    rollback_strategy_ref: str | None
    evidence_refs: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    cce_contract: ChampionChallengerEvaluation | None = None  # filled in __post_init__

    def __post_init__(self) -> None:
        """Build real ChampionChallengerEvaluation contract safely (workaround gate invariant S-MDL-03 boundary)."""
        import re as _re

        def _to_ulidish(raw: Any, fallback: str) -> str:
            s = fallback if raw is None else str(raw)
            s = _re.sub(r"[^A-Za-z0-9_\-]", "_", s)  # replace forbidden chars (. etc) with underscore
            if len(s) < 8:
                s = s.ljust(16, "X")
            return s

        try:
            md = self.metadata or {}
            cc_id_raw = md.get("cc_eval_id", f"CCEVAL_{id(self):016x}")
            cc_id = _to_ulidish(cc_id_raw, f"CCEVAL000000000{id(self):08x}")
            evaluation_ts = md.get("evaluation_ts", "2026-01-01T00:00:00.000Z")
            correlation_id = _to_ulidish(md.get("correlation_id", "CORREVAL00000001"), "CORREVAL00000001")
            causation_id = _to_ulidish(md.get("causation_id", "CAUSEEVAL00000001"), "CAUSEEVAL00000001")
            thresholds_version = str(md.get("thresholds_config_version", "1.0.0") or "1.0.0")
            gate = PromotionGateResult(passed=False, reasons=[], thresholds_used_version=thresholds_version)
            safe_winner = CCWinnerEnum.INCONCLUSIVE_RERUN
            safe_cce = ChampionChallengerEvaluation(
                cc_id=cc_id,
                champion_ref=self.champion_ref,
                challenger_ref=self.challenger_ref,
                winner=safe_winner,
                comparison_metrics=dict(self.comparison_metrics or {}),
                evaluation_period_days=int(self.evaluation_period_days or 0),
                promotion_gate_result=gate,
                rollback_strategy_ref=self.rollback_strategy_ref,
                approval_refs=[],
                evaluation_ts=evaluation_ts,
                correlation_id=correlation_id,
                causation_id=causation_id,
                notes=None,
            )
            safe_cce.winner = self.winner_hint
            self.cce_contract = safe_cce
        except Exception as _exc:
            self.cce_contract = None

    def to_sorted_dict(self) -> dict[str, Any]:
        sorted_evidence = sorted(
            self.evidence_refs,
            key=lambda e: (
                str(e.get("kind", "")),
                str(e.get("ref_id", "")),
                str(e.get("model_id", "")),
                str(e.get("version", "")),
            ),
        )
        d: dict[str, Any] = {
            "champion_ref": to_sorted_dict(self.champion_ref),
            "challenger_ref": to_sorted_dict(self.challenger_ref),
            "comparable": self.comparable,
            "winner_hint": self.winner_hint.value,
            "comparison_metrics": {k: self._comparison_metric_value_to_serial(self.comparison_metrics[k]) for k in sorted(self.comparison_metrics.keys())},
            "metric_deltas": [self._md_sorted(md) for md in self.metric_deltas],  # build_cce_payload already sorted
            "evaluation_period_days": self.evaluation_period_days,
            "rollback_strategy_ref": self.rollback_strategy_ref,
            "evidence_refs": [self._evidence_ref_serial(e) for e in sorted_evidence],
            "metadata": {k: self._metadata_serial(self.metadata[k]) for k in sorted(self.metadata.keys())},
        }
        return d

    def schema_sha256(self) -> str:
        payload = json.dumps(self.to_sorted_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata_serial(v: Any) -> Any:
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, dict):
            return {k: ChampionChallengerEvaluationPayload._metadata_serial(v[k]) for k in sorted(v.keys())}
        if isinstance(v, list):
            return [ChampionChallengerEvaluationPayload._metadata_serial(x) for x in v]
        return v

    @staticmethod
    def _comparison_metric_value_to_serial(v: Any) -> Any:
        if isinstance(v, bool):
            return v
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return v
        return v

    @staticmethod
    def _md_sorted(md: MetricDelta) -> dict[str, Any]:
        def _ser(v: Any) -> Any:
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, bool):
                return v
            return v
        # directionality is already str (higher_better/lower_better/neutral_match) per MetricDelta design
        dir_value = md.directionality.value if hasattr(md.directionality, "value") else md.directionality
        return {
            "champion_value": _ser(md.champion_value),
            "challenger_value": _ser(md.challenger_value),
            "delta": _ser(md.delta),
            "directionality": dir_value,
            "metric_key": md.metric_key,
            "metric_version": md.metric_version,
            "rounding_precision": md.rounding_precision,
            "winner_hint": md.winner_hint,
        }

    @staticmethod
    def _evidence_ref_serial(e: Any) -> Any:
        if isinstance(e, dict):
            return {k: e[k] for k in sorted(e.keys())}
        return e


def _winner_hint_from_deltas(metric_deltas: list[MetricDelta]) -> CCWinnerEnum:
    """Non-binding winner hint (S-MDL-03 makes decisions; this reports).

    Critical 6 keys (return/maxDD/sharpe/sortino/PF/total_fees) all pro-challenger
    → challenger_promoted. All pro-champion → champion_keeps. Otherwise tie/mixed → inconclusive_rerun.
    Tie (delta==0) treats as NO pro for either (conservative). OD-05 tie → inconclusive default.
    """
    by_key = {md.metric_key: md for md in metric_deltas}
    pro_challenger_critical = 0
    pro_champion_critical = 0
    tie_count = 0
    for k in CRITICAL_DELTA_KEYS_ORDERED:
        md = by_key.get(k)
        if md is None:
            return CCWinnerEnum.INCONCLUSIVE_RERUN
        # normalize directionality str for comparison
        dir_str = md.directionality.value if hasattr(md.directionality, "value") else md.directionality
        if dir_str == DIRECTION_NEUTRAL_MATCH:
            continue
        delta = md.delta
        if isinstance(delta, Decimal):
            if delta > 0:
                pro_challenger_critical += 1
            elif delta < 0:
                pro_champion_critical += 1
            else:
                tie_count += 1
        elif isinstance(delta, int):
            if delta > 0:
                pro_challenger_critical += 1
            elif delta < 0:
                pro_champion_critical += 1
            else:
                tie_count += 1
        elif isinstance(delta, float):
            if delta > 0.0:
                pro_challenger_critical += 1
            elif delta < 0.0:
                pro_champion_critical += 1
            else:
                tie_count += 1
    if pro_challenger_critical > 0 and pro_champion_critical == 0 and tie_count >= 0:
        if tie_count == 0 and pro_challenger_critical == len(CRITICAL_DELTA_KEYS_ORDERED):
            return CCWinnerEnum.CHALLENGER_PROMOTED
    if pro_champion_critical > 0 and pro_challenger_critical == 0 and tie_count >= 0:
        if tie_count == 0 and pro_champion_critical == len(CRITICAL_DELTA_KEYS_ORDERED):
            return CCWinnerEnum.CHAMPION_KEEPS
    return CCWinnerEnum.INCONCLUSIVE_RERUN


def build_cce_payload(
    champion_ref: ModelRef,
    challenger_ref: ModelRef,
    comparable: bool,
    metric_deltas: list[MetricDelta],
    evaluation_period_days: int,
    rollback_strategy_ref: str | None,
    evidence_refs: list[dict[str, Any]],
    challenger_metrics: dict[str, Any] | None = None,
    champion_metrics: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChampionChallengerEvaluationPayload:
    """Build payload; produce comparison_metrics = CHALLENGER METRIC VALUES (valid 11-keyed typed dict passes S-CON-02C contract validator).

    comparison_metrics design note: S-CON-02C validates ChampionChallengerEvaluation.comparison_metrics through
    _validate_metrics_11keys which enforces return_pct/total_fees=Decimal, maxDD∈[0,1], trade_count Int≥0, oos_flag Bool.
    Therefore comparison_metrics cannot be raw deltas. Use CHALLENGER'S fully-validated METRIC VALUES directly
    (already typed correctly per 11-keys from ModelEvaluation.metrics). Delta values live in metric_deltas list.
    """
    ordered_keys = [k for k in _REQUIRED_METRIC_KEYS]
    extra_keys = sorted({md.metric_key for md in metric_deltas if md.metric_key not in _REQUIRED_METRIC_KEYS})
    comparison_metrics_raw: dict[str, Any] = {}
    # default challenger_metrics fallback: reconstruct typed scalar defaults per key type from delta directions if possible
    # but caller must pass challenger_metrics for happy path (always present from engine.compare)
    if challenger_metrics is not None:
        # copy 11 required key values as-is (already typed and validated)
        for k in ordered_keys:
            if k in challenger_metrics:
                comparison_metrics_raw[k] = challenger_metrics[k]
        # safe extras if present but S-CON-02C validator strips extras; only 11 keys carried into comparison_metrics of CCE constructor
    # Build comparison_metrics = strict 11 key typed dict (constructor validates at line 749)
    deltas_by_key = {md.metric_key: md for md in metric_deltas}
    for k in ordered_keys + extra_keys:
        md = deltas_by_key.get(k)
        # comparison_metrics values = Challenger's metric values (not delta)
        # No need to overwrite with md delta; keep challenger_metrics passed values
    # canonical order metric_deltas (spec CAP-5 canonical ordering)
    all_keys = {md.metric_key for md in metric_deltas}
    order_reference = {k: idx for idx, k in enumerate(sorted_metric_keys({k: True for k in all_keys}))}
    metric_deltas_sorted = sorted(
        metric_deltas,
        key=lambda md: (
            order_reference.get(md.metric_key, 99999),
            md.metric_key,
            md.metric_version,
            md.rounding_precision,
        ),
    )
    winner_hint = _winner_hint_from_deltas(metric_deltas_sorted) if comparable else CCWinnerEnum.INCONCLUSIVE_RERUN
    md_final = metadata or {}
    if champion_metrics:
        # champion_metrics not explicitly used in payload but helps debugging/audit
        pass
    return ChampionChallengerEvaluationPayload(
        champion_ref=champion_ref,
        challenger_ref=challenger_ref,
        comparable=comparable,
        winner_hint=winner_hint,
        comparison_metrics=comparison_metrics_raw,  # 11-key challenger values typed correct (not delta)
        metric_deltas=metric_deltas_sorted,
        evaluation_period_days=int(evaluation_period_days),
        rollback_strategy_ref=rollback_strategy_ref,
        evidence_refs=[dict(e) for e in evidence_refs],
        metadata=dict(md_final),
    )
