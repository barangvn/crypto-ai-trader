from __future__ import annotations

from datetime import datetime
from typing import Any

from app.contracts.model import (
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    ModelRef,
    PromotionGateResult,
)
from app.evaluation.contract_payload import ChampionChallengerEvaluationPayload
from app.evaluation.delta import MetricDelta
from app.gate.exceptions import (
    ERR_GATE_EVAL_INCOMPARABLE,
    ERR_GATE_EVAL_STALE,
    ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT,
    ERR_GATE_EVIDENCE_INTEGRITY_FAIL,
    ERR_GATE_MIN_APPROVALS_FAIL,
    ERR_GATE_WINNER_HINT_INCONCLUSIVE_RERUN,
    GateInvariantError,
)


def _parse_ts(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if not isinstance(ts, str):
        return None
    s = ts.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def age_evaluation_check(
    eval_ts: Any,
    comparison_window_end_ts: Any,
    max_eval_age_days: int = 30,
) -> list[str]:
    reasons: list[str] = []
    eval_dt = _parse_ts(eval_ts)
    window_dt = _parse_ts(comparison_window_end_ts)
    if eval_dt is None or window_dt is None:
        reasons.append(ERR_GATE_EVAL_STALE)
        return reasons
    age = window_dt - eval_dt
    if age.days < 0:
        reasons.append(ERR_GATE_EVAL_STALE)
    elif age.days > max_eval_age_days:
        reasons.append(ERR_GATE_EVAL_STALE)
    return reasons


def comparable_flag_check(
    comparable_bool: bool,
    mismatch_codes: list[str] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if comparable_bool is not True:
        reasons.append(ERR_GATE_EVAL_INCOMPARABLE)
        if mismatch_codes:
            for code in mismatch_codes:
                if isinstance(code, str) and code:
                    reasons.append(code)
    return reasons


def evidence_integrity_check(
    evidence_refs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    metadata = metadata or {}
    integrity = metadata.get("evidence_integrity")
    if integrity is False:
        reasons.append(ERR_GATE_EVIDENCE_INTEGRITY_FAIL)
        return reasons
    if evidence_refs:
        for ref in evidence_refs:
            if isinstance(ref, dict):
                if ref.get("integrity_ok") is False:
                    reasons.append(ERR_GATE_EVIDENCE_INTEGRITY_FAIL)
                    break
    return reasons


def evidence_deltas_chain_check(
    metric_deltas: list[MetricDelta] | None = None,
    min_deltas_with_challenger_win: int = 2,
) -> list[str]:
    reasons: list[str] = []
    count = 0
    if metric_deltas:
        for md in metric_deltas:
            if not isinstance(md, MetricDelta):
                continue
            try:
                hint = getattr(md, "winner_hint", None)
                if hint is None:
                    continue
                s = str(hint)
                if s == "challenger":
                    count += 1
            except Exception:
                continue
    if count < int(min_deltas_with_challenger_win):
        reasons.append(ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT)
    return reasons


def approval_minimum_readonly(
    approval_refs: list[str] | None,
    min_count: int = 1,
) -> list[str]:
    reasons: list[str] = []
    count = 0
    if approval_refs:
        for ref in approval_refs:
            if isinstance(ref, str) and ref:
                count += 1
    if count < min_count:
        reasons.append(ERR_GATE_MIN_APPROVALS_FAIL)
    return reasons


def build_reason_codes(*args: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for bucket in args:
        if not bucket:
            continue
        for item in bucket:
            if not isinstance(item, str) or not item:
                continue
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    out.sort()
    return out


def build_promotion_gate_result(
    reasons: list[str],
    meta_cfg: dict[str, Any],
    gate_passed: bool,
    thresholds_version: str,
    weights_version: str,
) -> PromotionGateResult:
    if not isinstance(thresholds_version, str) or not thresholds_version:
        raise ValueError("thresholds_version must be a non-empty str")
    if not isinstance(weights_version, str) or not weights_version:
        raise ValueError("weights_version must be a non-empty str")
    merged = build_reason_codes(reasons)
    if gate_passed and merged:
        gate_passed_final = False
    else:
        gate_passed_final = bool(gate_passed) and not merged
    version_used = f"{thresholds_version}/{weights_version}"
    return PromotionGateResult(
        passed=gate_passed_final,
        reasons=list(merged),
        thresholds_used_version=version_used,
    )


def enforce_winner_gate_invariant(
    winner: CCWinnerEnum,
    gate: PromotionGateResult,
) -> None:
    if not isinstance(winner, CCWinnerEnum):
        raise GateInvariantError(
            "WINNER_TYPE_INVALID",
            f"winner must be CCWinnerEnum, got {type(winner).__name__}",
        )
    if not isinstance(gate, PromotionGateResult):
        raise GateInvariantError(
            "GATE_TYPE_INVALID",
            f"gate must be PromotionGateResult, got {type(gate).__name__}",
        )
    if winner is CCWinnerEnum.CHALLENGER_PROMOTED and gate.passed is not True:
        raise GateInvariantError(
            "C10_WINNER_CHALLENGER_WITHOUT_GATE_PASS",
            "winner=challenger_promoted requires promotion_gate_result.passed=True",
        )
    if gate.passed is True and winner is not CCWinnerEnum.CHALLENGER_PROMOTED:
        raise GateInvariantError(
            "C10_GATE_PASS_BUT_WINNER_NOT_CHALLENGER",
            "gate.passed=True requires winner=challenger_promoted",
        )


def inject_gate_into_champion_challenger(
    cce_payload: ChampionChallengerEvaluationPayload,
    gate: PromotionGateResult,
    final_winner: CCWinnerEnum,
    approval_refs: list[str] | None = None,
    evaluation_ts: str | None = None,
) -> ChampionChallengerEvaluation:
    if gate.passed is True:
        enforce_winner_gate_invariant(final_winner, gate)

    payload = cce_payload
    approval = list(approval_refs) if approval_refs else []
    approval = [a for a in approval if isinstance(a, str) and a]
    ts_str = evaluation_ts if (evaluation_ts and isinstance(evaluation_ts, str)) else payload.evaluation_ts
    try:
        if isinstance(ts_str, datetime):
            ts = ts_str.isoformat()
        else:
            _ = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            ts = str(ts_str)
    except Exception:
        ts = "2026-01-01T00:00:00.000Z"

    champ_ref = ModelRef(
        model_id=str(payload.champion_model_id),
        version=str(payload.champion_version),
    )
    chall_ref = ModelRef(
        model_id=str(payload.challenger_model_id),
        version=str(payload.challenger_version),
    )

    return ChampionChallengerEvaluation(
        cc_id="cce_eval_0000001",
        champion_ref=champ_ref,
        challenger_ref=chall_ref,
        winner=final_winner,
        comparison_metrics=dict(payload.comparison_metrics),
        evaluation_period_days=int(payload.evaluation_period_days or 0),
        promotion_gate_result=gate,
        rollback_strategy_ref=payload.rollback_strategy_ref,
        approval_refs=approval,
        evaluation_ts=ts,
        correlation_id="corr_eval_0000001",
        causation_id="caus_eval_0000001",
    )
