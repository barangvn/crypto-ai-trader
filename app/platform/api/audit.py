"""Audit event writer for 2 permissioned POST routes (S-API-02 + AD-16).

Audit events are published to the EventBus as CanonicalEventEnvelope.

N1 audit payload (9 REQUIRED fields + extra optional fields:
  - ts (Instant), operator (str|None), reason (str|None),
  - correlation_id (ULID), idempotency_key (ULID),
  - double_confirm_token (ULID — NOT hashed NOT stored),
  - route (str literal path), auth_scope (literal), final_result (str).

Idempotency duplicate publishes an additional "idempotency_duplicate" INFO row
audit row in addition to the main row that is the first successful call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import uuid
from datetime import datetime, timezone

from app.contracts import CanonicalEventEnvelope
from app.contracts.canonical import (
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.types import (
    ContractVersion,
    Instant,
    RunMode,
    SourceType,
    ULID,
    format_instant,
)
from app.platform.event_bus import InMemoryTypedEventBus


EVENT_TYPE_AUDIT_POST_MAIN = "eapi.audit.post_main.v1"
EVENT_TYPE_AUDIT_POST_DUPLICATE = "eapi.audit.idempotency_duplicate.v1"


@dataclass
class AuditEventPayload:
    ts: Instant
    operator: str | None
    reason: str | None
    correlation_id: ULID
    idempotency_key: str
    double_confirm_token: str
    route: str
    auth_scope: str
    final_result: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_sorted_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "operator": self.operator,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "double_confirm_token": self.double_confirm_token,
            "route": self.route,
            "auth_scope": self.auth_scope,
            "final_result": self.final_result,
            "details": self.details,
        }


def _publish(bus: InMemoryTypedEventBus, event_type: str, payload: AuditEventPayload) -> None:
    now = format_instant(datetime.now(timezone.utc))
    envelope = CanonicalEventEnvelope(
        event_id=ULID(uuid.uuid4().hex),
        event_type=event_type,
        contract_version=ContractVersion("1.0.0"),
        symbol=None,
        source="eapi-audit",
        timestamp=payload.ts,
        ingest_ts=now,
        correlation_id=payload.correlation_id,
        causation_id=ULID(uuid.uuid4().hex),
        run_mode=RunMode.PAPER,
        source_type=SourceType.SIMULATED,
        clock_ref=ClockRef(wall=now),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        trace_id=None,
        extra={
            "idempotency_key": payload.idempotency_key,
            "double_confirm_token": payload.double_confirm_token,
            "route": payload.route,
            "auth_scope": payload.auth_scope,
            "final_result": payload.final_result,
        },
        payload=payload.to_sorted_dict(),
    )
    bus.publish(envelope)


def publish_main_audit(
    bus: InMemoryTypedEventBus,
    *,
    correlation_id: ULID,
    idempotency_key: str,
    double_confirm_token: str,
    route: str,
    auth_scope: str,
    final_result: str,
    operator: str | None,
    reason: str | None,
    details: dict[str, Any] | None = None,
) -> AuditEventPayload:
    """Publish the main audit row (successful or failed_attempt)."""
    ts = format_instant(datetime.now(timezone.utc))
    payload = AuditEventPayload(
        ts=ts,
        operator=operator,
        reason=reason,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        double_confirm_token=double_confirm_token,
        route=route,
        auth_scope=auth_scope,
        final_result=final_result,
        details=details or {},
    )
    _publish(bus, EVENT_TYPE_AUDIT_POST_MAIN, payload)
    return payload


def publish_duplicate_audit(
    bus: InMemoryTypedEventBus,
    *,
    correlation_id: ULID,
    idempotency_key: str,
    double_confirm_token: str,
    route: str,
    auth_scope: str,
    original_correlation_id: ULID,
) -> AuditEventPayload:
    """Publish idempotency_duplicate info audit row (AC-05)."""
    ts = format_instant(datetime.now(timezone.utc))
    payload = AuditEventPayload(
        ts=ts,
        operator=None,
        reason=None,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        double_confirm_token=double_confirm_token,
        route=route,
        auth_scope=auth_scope,
        final_result="idempotency_duplicate",
        details={"original_correlation_id": original_correlation_id},
    )
    _publish(bus, EVENT_TYPE_AUDIT_POST_DUPLICATE, payload)
    return payload
