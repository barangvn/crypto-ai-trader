from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from app.contracts.model import CCWinnerEnum
from app.evaluation.contract_payload import ChampionChallengerEvaluationPayload
from app.evaluation.delta import MetricDelta
from app.gate.builder import (
    age_evaluation_check,
    approval_minimum_readonly,
    build_promotion_gate_result,
    build_reason_codes,
    comparable_flag_check,
    enforce_winner_gate_invariant,
    evidence_deltas_chain_check,
    evidence_integrity_check,
    inject_gate_into_champion_challenger,
)
from app.gate.exceptions import (
    ERR_GATE_MIN_TOTAL_SCORE_UNMET,
    ERR_GATE_THRESHOLDS_VERSION_MISMATCH,
    ERR_GATE_WEIGHTS_VERSION_MISMATCH,
    ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN,
    THRESHOLD_FAIL_BY_METRIC_KEY,
)
from app.gate.thresholds import (
    THRESHOLDS_VERSION_V1,
    check_hard_constraints,
    check_soft_thresholds,
    compute_weighted_total_score,
    default_thresholds_v1,
)
from app.gate.weights import (
    WEIGHTS_VERSION_V1,
    default_weights_v1,
    renormalize_weights_if_needed,
    validate_weights_definition,
)


class WeightsConfig:
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        weights_version: str = WEIGHTS_VERSION_V1,
        auto_renormalize: bool = True,
    ) -> None:
        self.weights_version = weights_version
        raw = dict(weights) if weights else default_weights_v1()
        validated = validate_weights_definition(raw)
        if auto_renormalize:
            self.weights = renormalize_weights_if_needed(validated, weights_version)
        else:
            self.weights = validated
        validate_weights_definition(self.weights)


class ThresholdsConfig:
    def __init__(
        self,
        thresholds: dict[str, Any] | None = None,
        thresholds_version: str = THRESHOLDS_VERSION_V1,
    ) -> None:
        self.thresholds_version = thresholds_version
        cfg = thresholds if thresholds is not None else default_thresholds_v1()
        self.metric_bounds: dict[str, tuple[float, float]] = cfg["metric_bounds"]
        self.hard_thresholds: dict[str, Any] = cfg["hard_thresholds"]
        self.soft_thresholds: dict[str, Any] = cfg["soft_thresholds"]
        self.meta_thresholds: dict[str, Any] = cfg["meta_thresholds"]


def _delta_map_from_deltas(metric_deltas: list[MetricDelta]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for md in metric_deltas:
        try:
            key = md.metric_key
            delta = md.delta_value
            if isinstance(delta, Decimal):
                out[key] = float(delta)
            else:
                out[key] = delta
        except Exception:
            continue
    return out


def _canonical_sha256(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PromotionGate:
    def __init__(
        self,
        weights_cfg: WeightsConfig | None = None,
        thresholds_cfg: ThresholdsConfig | None = None,
        expected_thresholds_version: str | None = None,
        expected_weights_version: str | None = None,
    ) -> None:
        self.weights_cfg = weights_cfg or WeightsConfig()
        self.thresholds_cfg = thresholds_cfg or ThresholdsConfig()
        self.expected_thresholds_version = expected_thresholds_version
        self.expected_weights_version = expected_weights_version

    def evaluate(
        self,
        compare_result: Any,
        comparison_window_end_ts: str | None = None,
        approval_refs: list[str] | None = None,
        challenger_metrics_override: dict[str, Any] | None = None,
        champion_metrics_override: dict[str, Any] | None = None,
        min_approval_count_override: int | None = None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        payload: ChampionChallengerEvaluationPayload | None = getattr(
            compare_result, "payload", None
        )
        comparable = bool(getattr(compare_result, "comparable", False))
        metric_deltas_raw = getattr(compare_result, "metric_deltas", None) or []
        metric_deltas: list[MetricDelta] = [md for md in metric_deltas_raw if isinstance(md, MetricDelta)]

        if self.expected_thresholds_version and (
            self.expected_thresholds_version != self.thresholds_cfg.thresholds_version
        ):
            reasons.append(ERR_GATE_THRESHOLDS_VERSION_MISMATCH)
        if self.expected_weights_version and (
            self.expected_weights_version != self.weights_cfg.weights_version
        ):
            reasons.append(ERR_GATE_WEIGHTS_VERSION_MISMATCH)

        comparability_codes: list[str] = []
        cr_meta = getattr(compare_result, "metadata", None) or {}
        if isinstance(cr_meta, dict):
            inner = cr_meta.get("comparability_mismatch_codes")
            if isinstance(inner, list):
                comparability_codes.extend(str(x) for x in inner if x)

        reasons.extend(comparable_flag_check(comparable, comparability_codes))

        if payload is None:
            challenger_metrics = dict(challenger_metrics_override) if challenger_metrics_override else {}
            champion_metrics = dict(champion_metrics_override) if champion_metrics_override else {}
            winner_hint = CCWinnerEnum.INCONCLUSIVE_RERUN
            eval_ts = None
            evidence_refs = []
            payload_metadata: dict[str, Any] = {}
        else:
            challenger_metrics = dict(payload.comparison_metrics) if payload.comparison_metrics else {}
            champion_eval = getattr(compare_result, "champion_eval", None)
            champion_metrics = {}
            if champion_eval is not None:
                cm = getattr(champion_eval, "metrics", None)
                if isinstance(cm, dict):
                    champion_metrics = dict(cm)
            if champion_metrics_override:
                champion_metrics.update(champion_metrics_override)
            if challenger_metrics_override:
                challenger_metrics.update(challenger_metrics_override)
            winner_hint = payload.winner_hint
            eval_ts = payload.evaluation_ts
            evidence_refs = list(payload.evidence_refs or [])
            payload_metadata = dict(payload.metadata or {}) if hasattr(payload, "metadata") else {}

        window_end = comparison_window_end_ts or eval_ts

        reasons.extend(age_evaluation_check(eval_ts, window_end, int(self.thresholds_cfg.meta_thresholds.get("max_eval_age_days", 30))))

        reasons.extend(evidence_integrity_check(evidence_refs, payload_metadata))

        reasons.extend(evidence_deltas_chain_check(metric_deltas, 2))

        min_approvals = (
            int(min_approval_count_override)
            if min_approval_count_override is not None
            else int(self.thresholds_cfg.meta_thresholds.get("min_approval_count", 1))
        )
        reasons.extend(approval_minimum_readonly(approval_refs, min_approvals))

        if winner_hint is CCWinnerEnum.INCONCLUSIVE_RERUN:
            reasons.append(ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN)

        delta_map = _delta_map_from_deltas(metric_deltas)

        hard_reasons = check_hard_constraints(challenger_metrics, champion_metrics, delta_map)
        soft_reasons = check_soft_thresholds(
            challenger_metrics, champion_metrics, self.thresholds_cfg.soft_thresholds
        )

        weighted_total, norm_reasons = compute_weighted_total_score(
            challenger_metrics, self.weights_cfg.weights, self.thresholds_cfg.metric_bounds, champion_metrics
        )

        min_total_score = float(self.thresholds_cfg.meta_thresholds.get("min_total_score", 0.65))
        meta_reasons: list[str] = []
        if weighted_total < min_total_score:
            meta_reasons.append(ERR_GATE_MIN_TOTAL_SCORE_UNMET)

        all_reasons = build_reason_codes(
            reasons,
            norm_reasons,
            hard_reasons,
            soft_reasons,
            meta_reasons,
        )

        gate_passed = len(all_reasons) == 0

        gate = build_promotion_gate_result(
            reasons=all_reasons,
            meta_cfg=self.thresholds_cfg.meta_thresholds,
            gate_passed=gate_passed,
            thresholds_version=self.thresholds_cfg.thresholds_version,
            weights_version=self.weights_cfg.weights_version,
        )

        if gate_passed:
            final_winner = CCWinnerEnum.CHALLENGER_PROMOTED
        else:
            if winner_hint is CCWinnerEnum.CHAMPION_KEEPS:
                final_winner = CCWinnerEnum.CHAMPION_KEEPS
            elif winner_hint is CCWinnerEnum.CHALLENGER_PROMOTED and ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN not in all_reasons and not all_reasons:
                final_winner = CCWinnerEnum.CHALLENGER_PROMOTED
            else:
                final_winner = CCWinnerEnum.INCONCLUSIVE_RERUN

        try:
            enforce_winner_gate_invariant(final_winner, gate)
        except Exception:
            if gate.passed:
                final_winner = CCWinnerEnum.CHALLENGER_PROMOTED
            elif final_winner is CCWinnerEnum.CHALLENGER_PROMOTED:
                final_winner = CCWinnerEnum.CHAMPION_KEEPS
            enforce_winner_gate_invariant(final_winner, gate)

        cce_contract = None
        if payload is not None:
            try:
                cce_contract = inject_gate_into_champion_challenger(
                    cce_payload=payload,
                    gate=gate,
                    final_winner=final_winner,
                    approval_refs=approval_refs,
                    evaluation_ts=eval_ts,
                )
            except Exception:
                cce_contract = None

        soft_fail_set = {
            THRESHOLD_FAIL_BY_METRIC_KEY[k] for k in THRESHOLD_FAIL_BY_METRIC_KEY
        }
        hard_fail_set = {
            "HARD_RETURN_NOT_POSITIVE",
            "HARD_DRAWDOWN_WORSENED",
            "HARD_SHARPE_NEGATIVE",
            "HARD_PROFIT_FACTOR_SUBUNITY",
            "HARD_TRADE_COUNT_INSUFFICIENT",
            "HARD_OOS_FLAG_FALSE",
        }

        summary_obj = {
            "passed": bool(gate.passed),
            "reasons": list(gate.reasons),
            "weighted_total": weighted_total,
            "min_total_score": min_total_score,
            "weighted_total_vs_min": round(weighted_total - min_total_score, 8),
            "final_winner": final_winner.value,
            "winner_hint": winner_hint.value if hasattr(winner_hint, "value") else str(winner_hint),
            "thresholds_version": self.thresholds_cfg.thresholds_version,
            "weights_version": self.weights_cfg.weights_version,
            "thresholds_used_version": gate.thresholds_used_version,
            "hard_failed": sorted([r for r in gate.reasons if r in hard_fail_set]),
            "soft_failed": sorted([r for r in gate.reasons if r in soft_fail_set]),
            "norm_failed": sorted([r for r in gate.reasons if r.startswith("NORM_")]),
            "meta_failed": sorted([r for r in gate.reasons if r.startswith("EVAL_") or r.startswith("GATE_") or r.startswith("WINNER_") or r.startswith("THRESHOLDS_") or r.startswith("WEIGHTS_") or r == "EVIDENCE_INTEGRITY_FAIL"]),
            "deterministic": True,
        }
        schema_sha = _canonical_sha256(summary_obj)
        summary_obj["schema_sha256"] = schema_sha
        if cce_contract is not None:
            try:
                summary_obj["cce_contract_sha256"] = cce_contract.schema_sha256()
            except Exception:
                summary_obj["cce_contract_sha256"] = None
            try:
                summary_obj["cce_winner"] = cce_contract.winner.value
            except Exception:
                pass
        summary_obj["gate"] = {
            "passed": bool(gate.passed),
            "reasons": list(gate.reasons),
            "thresholds_used_version": gate.thresholds_used_version,
        }
        if cce_contract is not None:
            summary_obj["cce_contract"] = cce_contract
        return summary_obj
