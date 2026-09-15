from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from app.contracts.model import _REQUIRED_METRIC_KEYS

from app.rollback.exceptions import (
    ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY,
    ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN,
    ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE,
    ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH,
    ERR_ROLLBACK_INCOMPLETE_EVIDENCE,
    ERR_ROLLBACK_INVALID_TRIGGER_TYPE,
    ERR_ROLLBACK_PRIOR_STATE_REF_NULL,
    ERR_ROLLBACK_RATIONALE_EMPTY,
    ERR_ROLLBACK_STALE_DEGRADATION_WINDOW,
    ERR_ROLLBACK_STRATEGY_REF_ARTIFACT_NOT_FOUND,
)
from app.rollback.thresholds import ThresholdsConfig


VALID_TRIGGER_TYPES: frozenset[str] = frozenset(
    {"degradation_breach", "manual_governance", "kill_switch_emergency"}
)

VALID_TARGET_MODES: frozenset[str] = frozenset(
    {"restore_prior_champion", "observe_only_disabled"}
)

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def _parse_ts(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if not isinstance(ts, str):
        return None
    s = ts.strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _canonical_sha256(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_trigger_type(trigger_type: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(trigger_type, str) or not trigger_type:
        reasons.append(ERR_ROLLBACK_INVALID_TRIGGER_TYPE)
        return reasons
    if trigger_type not in VALID_TRIGGER_TYPES:
        reasons.append(ERR_ROLLBACK_INVALID_TRIGGER_TYPE)
    return reasons


def validate_target_mode(mode: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(mode, str) or not mode:
        return reasons
    if mode not in VALID_TARGET_MODES:
        return reasons
    return reasons


def validate_delta_metrics_keys(delta_metrics: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(delta_metrics, dict):
        reasons.append(ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE)
        return reasons
    present = set(delta_metrics.keys())
    required = set(_REQUIRED_METRIC_KEYS)
    missing = required - present
    if missing:
        reasons.append(ERR_ROLLBACK_DELTA_METRICS_INCOMPLETE)
    return reasons


def validate_evidence_integrity(
    evidence_integrity_ok_flag: Any,
    evidence_integrity_sha: Any,
    evidence_canonical_bundle: Any = None,
) -> list[str]:
    reasons: list[str] = []
    if evidence_integrity_ok_flag is False:
        reasons.append(ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH)
        return reasons
    if isinstance(evidence_integrity_sha, str) and evidence_integrity_sha:
        if not _SHA256_HEX_RE.match(evidence_integrity_sha.lower()):
            reasons.append(ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH)
            return reasons
        if evidence_canonical_bundle is not None:
            computed = _canonical_sha256(evidence_canonical_bundle)
            if computed.lower() != evidence_integrity_sha.lower():
                reasons.append(ERR_ROLLBACK_EVIDENCE_INTEGRITY_MISMATCH)
    return reasons


def validate_staleness_window(
    evidence_ts: Any,
    comparison_window_end_ts: Any,
    cfg: ThresholdsConfig,
) -> list[str]:
    reasons: list[str] = []
    ev_dt = _parse_ts(evidence_ts)
    win_dt = _parse_ts(comparison_window_end_ts)
    if ev_dt is None or win_dt is None:
        reasons.append(ERR_ROLLBACK_STALE_DEGRADATION_WINDOW)
        return reasons
    age = win_dt - ev_dt
    if age.days < 0:
        reasons.append(ERR_ROLLBACK_STALE_DEGRADATION_WINDOW)
    elif age.days > cfg.max_degradation_window_days:
        reasons.append(ERR_ROLLBACK_STALE_DEGRADATION_WINDOW)
    return reasons


def validate_approval_fields(
    approver_identity: Any,
    rationale_text: Any,
    prior_state_snapshot_ref: Any,
) -> list[str]:
    reasons: list[str] = []
    if not isinstance(approver_identity, str) or not approver_identity.strip():
        reasons.append(ERR_ROLLBACK_APPROVER_IDENTITY_EMPTY)
    if not isinstance(rationale_text, str) or not rationale_text.strip():
        reasons.append(ERR_ROLLBACK_RATIONALE_EMPTY)
    if prior_state_snapshot_ref is None or (
        isinstance(prior_state_snapshot_ref, str) and not prior_state_snapshot_ref.strip()
    ):
        reasons.append(ERR_ROLLBACK_PRIOR_STATE_REF_NULL)
    return reasons


def validate_min_evidence_count(
    degradation_evidence_count: Any,
    cfg: ThresholdsConfig,
) -> list[str]:
    reasons: list[str] = []
    if not isinstance(degradation_evidence_count, int) or isinstance(degradation_evidence_count, bool):
        reasons.append(ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN)
        return reasons
    if degradation_evidence_count < cfg.min_degradation_evidence_count:
        reasons.append(ERR_ROLLBACK_DEGRADATION_EVIDENCE_COUNT_BELOW_MIN)
    return reasons


def validate_strategy_ref_artifact_exists_flag(
    strategy_ref_artifact_exists: Any,
    rollback_strategy_ref: Any,
) -> list[str]:
    reasons: list[str] = []
    if isinstance(rollback_strategy_ref, str) and rollback_strategy_ref.strip():
        if strategy_ref_artifact_exists is False:
            reasons.append(ERR_ROLLBACK_STRATEGY_REF_ARTIFACT_NOT_FOUND)
    return reasons


def validate_evidence_bundle(
    trigger_type: Any,
    delta_metrics: Any,
    approver_identity: Any,
    rationale_text: Any,
    prior_state_snapshot_ref: Any,
    degradation_evidence_count: Any,
    evidence_ts: Any,
    comparison_window_end_ts: Any,
    evidence_integrity_ok_flag: Any,
    evidence_integrity_sha: Any,
    rollback_strategy_ref: Any,
    strategy_ref_artifact_exists: Any,
    thresholds_cfg: ThresholdsConfig,
    evidence_canonical_bundle: Any = None,
) -> list[str]:
    reasons: list[str] = []

    t_reasons = validate_trigger_type(trigger_type)
    dm_reasons = validate_delta_metrics_keys(delta_metrics)
    ap_reasons = validate_approval_fields(
        approver_identity, rationale_text, prior_state_snapshot_ref
    )
    ec_reasons = validate_min_evidence_count(degradation_evidence_count, thresholds_cfg)
    st_reasons = validate_staleness_window(
        evidence_ts, comparison_window_end_ts, thresholds_cfg
    )
    ig_reasons = validate_evidence_integrity(
        evidence_integrity_ok_flag, evidence_integrity_sha, evidence_canonical_bundle
    )
    sr_reasons = validate_strategy_ref_artifact_exists_flag(
        strategy_ref_artifact_exists, rollback_strategy_ref
    )

    has_structural_missing = (
        t_reasons
        or dm_reasons
        or ap_reasons
        or ec_reasons
    )
    if has_structural_missing:
        reasons.append(ERR_ROLLBACK_INCOMPLETE_EVIDENCE)

    reasons.extend(t_reasons)
    reasons.extend(dm_reasons)
    reasons.extend(ap_reasons)
    reasons.extend(ec_reasons)
    reasons.extend(st_reasons)
    reasons.extend(ig_reasons)
    reasons.extend(sr_reasons)

    return reasons
