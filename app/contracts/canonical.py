from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.contracts.types import (
    ContractVersion,
    Instant,
    RunMode,
    SourceType,
    Symbol,
    ULID,
)


T = TypeVar("T")


@dataclass
class QualityFlags:
    stale: bool = False
    missing: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    reasons: list[dict[str, Any]] = field(default_factory=list)
    staleness_ms: int | None = None
    dedup_key: str | None = None
    expected_sequence: int | None = None
    actual_sequence: int | None = None

    def __post_init__(self) -> None:
        any_flag = (
            self.stale
            or self.missing
            or self.duplicate
            or self.out_of_order
            or self.invalid
            or self.quarantined
        )
        if any_flag and not self.degraded:
            self.degraded = True


@dataclass
class ClockRef:
    wall: Instant
    replay: Instant | None = None


@dataclass
class SchemaRef:
    contracts_md: str = "CONTRACTS.md@1.0.0"
    feature_version: str | None = None
    strategy_version: str | None = None
    model_id: str | None = None


@dataclass
class CanonicalEventEnvelope(Generic[T]):
    event_id: ULID
    event_type: str
    contract_version: ContractVersion
    symbol: Symbol | None
    source: str
    timestamp: Instant
    ingest_ts: Instant
    correlation_id: ULID
    causation_id: ULID
    run_mode: RunMode
    source_type: SourceType
    clock_ref: ClockRef
    quality_flags: QualityFlags
    schema_ref: SchemaRef = field(default_factory=SchemaRef)
    trace_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    payload: T | None = None
