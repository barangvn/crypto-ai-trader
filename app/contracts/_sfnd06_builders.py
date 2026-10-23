"""S-FND-06 canonical envelope & quality builders (CAP-SER-05 / CAP-SER-06).

Internal helper module. stdlib only (`dataclasses`, `typing`) plus internal app
imports through the S-FND-05 public API (`app.contracts.sfnd05_api`). No I/O.
No network. No wall-clock source (defaults are fixed, deterministic fixtures).

All construction goes through the S-FND-05 frozen dataclass constructors, so
every S-FND-05 post-init invariant is enforced here automatically (zero drift).

Fail-closed:
  - FC-11: empty/invalid `event_type` -> ValueError (via S-FND-05 validation).
  - FC-12: empty / too-long quality reason `code` -> ValueError.
  - FC-16 / HR-12: manual `degraded=True` -> ValueError (default safety; a
    non-binding optional future safety choice, see open-decisions OD-06-07/HR-12).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.contracts._sfnd06_constants import QUALITY_CODE_MAX
from app.contracts.sfnd05_api import (
    CanonicalEventEnvelope,
    ClockRefT,
    ContractValidationError,
    QualityFlags,
    QualityReason,
    SchemaRefT,
)

# Deterministic fixture defaults (never random, never wall-clock). Chosen so the
# builder is fully reproducible: same inputs -> byte-identical output (D-01/D-02).
DEFAULT_EVENT_ID = "01J5KX7YQJABCDEF0123456789"
DEFAULT_CORRELATION_ID = "01926bfb-4f4b-78a9-8f3b-0a2c3d4e5f6a"
DEFAULT_CAUSATION_ID = "01J5KX7YQJABCDEF0123456789"
DEFAULT_TIMESTAMP = "2026-08-10T18:30:00Z"
DEFAULT_INGEST_TS = "2026-08-10T18:30:01.100Z"

_SETTABLE_QUALITY_FLAGS: tuple[str, ...] = (
    "stale",
    "missing",
    "duplicate",
    "out_of_order",
    "invalid",
    "quarantined",
)


def _coerce_quality_flags(value: Any) -> QualityFlags:
    if value is None:
        return QualityFlags()
    if isinstance(value, QualityFlags):
        return value
    if isinstance(value, dict):
        return QualityFlags(**value)
    raise ContractValidationError(
        "[quality_flags] must be a QualityFlags instance, a dict or None"
    )


def _coerce_clock_ref(value: Any, wall: str) -> ClockRefT:
    if value is None:
        return ClockRefT(wall=wall, replay=None)
    if isinstance(value, ClockRefT):
        return value
    if isinstance(value, dict):
        return ClockRefT(**value)
    raise ContractValidationError(
        "[clock_ref] must be a ClockRefT instance, a dict or None"
    )


def _coerce_schema_ref(value: Any) -> SchemaRefT:
    if value is None:
        return SchemaRefT()
    if isinstance(value, SchemaRefT):
        return value
    if isinstance(value, dict):
        return SchemaRefT(**value)
    raise ContractValidationError(
        "[schema_ref] must be a SchemaRefT instance, a dict or None"
    )


def _coerce_reasons(value: Any) -> tuple[QualityReason, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ContractValidationError(
            "[quality_flags.reasons] must be a list or tuple of QualityReason or None"
        )
    reasons: list[QualityReason] = []
    for item in value:
        if isinstance(item, QualityReason):
            reasons.append(item)
        elif isinstance(item, dict):
            reasons.append(QualityReason(**item))
        else:
            raise ContractValidationError(
                "[quality_flags.reasons] entries must be QualityReason or dict"
            )
    return tuple(reasons)


def build_valid_envelope(
    *,
    event_type: str,
    payload: Any,
    event_id: str | None = None,
    contract_version: str = "1.0.0",
    symbol: str | None = None,
    source: str = "fixture.unknown",
    timestamp: str | None = None,
    ingest_ts: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    run_mode: str = "backtest",
    source_type: str = "static_fixture",
    clock_ref: dict | None = None,
    quality_flags: object | None = None,
    schema_ref: dict | None = None,
    trace_id: str | None = None,
    extra: dict | None = None,
) -> "CanonicalEventEnvelope":
    """Construct a valid envelope with deterministic fixture defaults.

    Missing required fields fall back to fixed fixture values; the resulting
    envelope MUST pass every S-FND-05 post-init invariant, otherwise the S-FND-05
    constructor raises (fail-closed). `quality_flags`/`clock_ref`/`schema_ref`
    accept either the real S-FND-05 instance or an equivalent dict (GAP-06-04).
    """
    resolved_timestamp = DEFAULT_TIMESTAMP if timestamp is None else timestamp
    resolved_ingest_ts = DEFAULT_INGEST_TS if ingest_ts is None else ingest_ts

    return CanonicalEventEnvelope(
        event_id=DEFAULT_EVENT_ID if event_id is None else event_id,
        event_type=event_type,
        contract_version=contract_version,
        symbol=symbol,
        source=source,
        timestamp=resolved_timestamp,
        ingest_ts=resolved_ingest_ts,
        correlation_id=DEFAULT_CORRELATION_ID if correlation_id is None else correlation_id,
        causation_id=DEFAULT_CAUSATION_ID if causation_id is None else causation_id,
        run_mode=run_mode,
        source_type=source_type,
        clock_ref=_coerce_clock_ref(clock_ref, resolved_timestamp),
        quality_flags=_coerce_quality_flags(quality_flags),
        schema_ref=_coerce_schema_ref(schema_ref),
        trace_id=trace_id,
        extra=extra,
        payload=payload,
    )


def build_quality(
    *,
    stale: bool = False,
    missing: bool = False,
    duplicate: bool = False,
    out_of_order: bool = False,
    invalid: bool = False,
    quarantined: bool = False,
    reasons: list | None = None,
    degraded: bool = False,
) -> "QualityFlags":
    """Build QualityFlags; `degraded` is auto-set by the S-FND-05 invariant.

    Passing `degraded=True` manually is rejected (fail-closed FC-16/HR-12):
    `degraded` must only ever be derived from the six other quality flags. This
    is a non-binding default safety choice (optional future explicit expansion).
    """
    if degraded:
        raise ContractValidationError(
            "[quality_flags.degraded] manual degraded=True override rejected; "
            "degraded is auto-derived from the other quality flags (FC-16/HR-12, "
            "default safety / non-binding optional future choice)"
        )
    return QualityFlags(
        stale=stale,
        missing=missing,
        duplicate=duplicate,
        out_of_order=out_of_order,
        invalid=invalid,
        quarantined=quarantined,
        reasons=_coerce_reasons(reasons),
    )


def append_quality_reason(
    qf: "QualityFlags", /, code: str, message: str, context: dict | None = None
) -> "QualityFlags":
    """Return a NEW QualityFlags with `QualityReason(code, message, context)` appended.

    Frozen dataclass workaround: never mutates; always returns a new instance.
    Duplicate `code` -> NOOP idempotent (first message wins, GAP-06-05).
    Invalid code (empty or > QUALITY_CODE_MAX) -> ValueError (FC-12).
    """
    if not isinstance(qf, QualityFlags):
        raise ContractValidationError("[qf] must be a QualityFlags instance")
    if not isinstance(code, str) or len(code) < 1 or len(code) > QUALITY_CODE_MAX:
        raise ContractValidationError(
            f"[QualityReason.code] must be a non-empty str of length <= {QUALITY_CODE_MAX} "
            "(fail-closed FC-12)"
        )
    existing = qf.reasons
    if any(reason.code == code for reason in existing):
        return qf
    appended = existing + (QualityReason(code=code, message=message, context=context),)
    return dataclasses.replace(qf, reasons=appended)


def set_quality_flag(
    qf: "QualityFlags", /, flag_name: str, value: bool = True
) -> "QualityFlags":
    """Return a NEW QualityFlags with a single flag toggled.

    `degraded` cannot be set manually (FC-16/HR-12). Unknown flag names raise
    (GAP-06-08). The S-FND-05 degraded invariant is re-checked on construction.
    """
    if not isinstance(qf, QualityFlags):
        raise ContractValidationError("[qf] must be a QualityFlags instance")
    if not isinstance(flag_name, str):
        raise ContractValidationError("[flag_name] must be str")
    if flag_name == "degraded":
        raise ContractValidationError(
            "[quality_flags.degraded] cannot be set manually; it is auto-derived "
            "(FC-16/HR-12)"
        )
    if flag_name not in _SETTABLE_QUALITY_FLAGS:
        raise ContractValidationError(
            f"[quality_flags.{flag_name}] unknown flag name (fail-closed GAP-06-08)"
        )
    return dataclasses.replace(qf, **{flag_name: bool(value)})


__all__ = [
    "build_valid_envelope",
    "build_quality",
    "append_quality_reason",
    "set_quality_flag",
]
