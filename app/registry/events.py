from __future__ import annotations

from typing import Any

from app.contracts import (
    CanonicalEventEnvelope,
    ClockRef,
    ContractVersion,
    Instant,
    QualityFlags,
    RunMode,
    SchemaRef,
    SourceType,
    Symbol,
    ULID,
    now_instant,
    to_sorted_dict,
)
from app.contracts.model import ModelLifecycleTransition, ModelVersion


def build_status_transition_event(
    *,
    envelope_event_id: str,
    mv: ModelVersion,
    tx: ModelLifecycleTransition,
    previous_mv_sha: str,
    new_mv_sha: str,
    symbol: Symbol | None = None,
    source: str = "model_registry.v1",
    contract_version: tuple[int, int, int] = (1, 0, 0),
    quality_flags: QualityFlags | None = None,
    run_mode: RunMode = RunMode.BACKTEST,
    source_type: SourceType = SourceType.REPLAY,
) -> CanonicalEventEnvelope[dict[str, Any]]:
    timestamp: Instant = tx.requested_ts
    ingest_ts: Instant = now_instant()

    meta_approvals = tx.metadata.get("approval_refs")
    if isinstance(meta_approvals, list):
        approval_count = len(meta_approvals)
    else:
        approval_count = 1 if (isinstance(tx.approved_by, str) and tx.approved_by) else 0
    payload_raw: dict[str, Any] = {
        "approval_count": approval_count,
        "from_status": tx.from_status.value,
        "gate_decision_id": tx.metadata.get("gate_decision_id"),
        "model_id": mv.model_id,
        "mv_schema_sha256": new_mv_sha,
        "occurred_at": tx.requested_ts,
        "previous_mv_sha": previous_mv_sha,
        "to_status": tx.to_status.value,
        "transition_command": tx.reason,
        "transition_id": tx.transition_id,
        "version": mv.version,
    }
    payload: dict[str, Any] = dict(sorted(payload_raw.items()))

    contract_ver_str = ContractVersion(
        f"{contract_version[0]}.{contract_version[1]}.{contract_version[2]}"
    )

    if quality_flags is None:
        quality_flags = QualityFlags()

    envelope = CanonicalEventEnvelope(
        event_id=ULID(envelope_event_id),
        event_type="model_version_status_transitioned.v1",
        contract_version=contract_ver_str,
        symbol=symbol,
        source=source,
        timestamp=timestamp,
        ingest_ts=ingest_ts,
        correlation_id=ULID(mv.correlation_id),
        causation_id=ULID(tx.transition_id),
        run_mode=run_mode,
        source_type=source_type,
        clock_ref=ClockRef(wall=timestamp, replay=timestamp),
        quality_flags=quality_flags,
        schema_ref=SchemaRef(
            model_id=mv.model_id,
            feature_version=mv.feature_version,
        ),
        payload=payload,
    )
    return envelope
