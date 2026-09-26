from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from ._validation import (
    EXTRA_KEY_RGX,
    ContractValidationError,
    _require,
    validate_contract_version,
    validate_event_type,
    validate_instant,
    validate_nonempty_str,
    validate_run_mode,
    validate_source_type,
    validate_symbol_canonical,
    validate_ulid_sortable,
)
from .nested_refs import ClockRefT, SchemaRefT
from .quality_flags import QualityFlags


T = TypeVar("T")


@dataclass(frozen=True)
class CanonicalEventEnvelope(Generic[T]):
    event_id: str
    event_type: str
    contract_version: str
    symbol: str | None
    source: str
    timestamp: str
    ingest_ts: str
    correlation_id: str
    causation_id: str
    run_mode: str
    source_type: str
    clock_ref: ClockRefT
    quality_flags: QualityFlags
    schema_ref: SchemaRefT
    trace_id: str | None = None
    extra: dict[str, Any] | None = None
    payload: T | None = None

    def __post_init__(self) -> None:
        validate_ulid_sortable(object.__getattribute__(self, "event_id"), "event_id")
        validate_event_type(object.__getattribute__(self, "event_type"), "event_type")
        validate_contract_version(
            object.__getattribute__(self, "contract_version"), "contract_version"
        )
        validate_symbol_canonical(
            object.__getattribute__(self, "symbol"), "symbol"
        )
        validate_nonempty_str(
            object.__getattribute__(self, "source"), "source", max_len=256
        )
        validate_instant(object.__getattribute__(self, "timestamp"), "timestamp")
        validate_instant(object.__getattribute__(self, "ingest_ts"), "ingest_ts")
        validate_ulid_sortable(
            object.__getattribute__(self, "correlation_id"), "correlation_id"
        )
        validate_ulid_sortable(
            object.__getattribute__(self, "causation_id"), "causation_id"
        )
        validate_run_mode(object.__getattribute__(self, "run_mode"), "run_mode")
        source_type = validate_source_type(
            object.__getattribute__(self, "source_type"), "source_type"
        )
        clock_ref = object.__getattribute__(self, "clock_ref")
        _require(
            isinstance(clock_ref, ClockRefT),
            "clock_ref",
            "must be ClockRefT frozen dataclass",
        )
        qf = object.__getattribute__(self, "quality_flags")
        _require(
            isinstance(qf, QualityFlags),
            "quality_flags",
            "must be QualityFlags frozen dataclass",
        )
        schema_ref = object.__getattribute__(self, "schema_ref")
        _require(
            isinstance(schema_ref, SchemaRefT),
            "schema_ref",
            "must be SchemaRefT frozen dataclass",
        )
        trace_id = object.__getattribute__(self, "trace_id")
        if trace_id is not None:
            _require(
                isinstance(trace_id, str) and 0 < len(trace_id) <= 256,
                "trace_id",
                "must be non-empty str max 256 or None",
            )
        extra = object.__getattribute__(self, "extra")
        if extra is not None:
            _require(isinstance(extra, dict), "extra", "must be dict[str, Any] or None")
            _require(len(extra) <= 64, "extra", "max 64 keys")
            for k, v in extra.items():
                _require(
                    isinstance(k, str) and EXTRA_KEY_RGX.match(k) is not None,
                    "extra keys",
                    (
                        "keys must match ^[a-zA-Z][a-zA-Z0-9_]{0,63}$ (no unicode/no dots)"
                    ),
                )
                _require(
                    not isinstance(v, dict),
                    f"extra[{k}]",
                    "nested dict forbidden (max nesting depth 1 flat only)",
                )
                if isinstance(v, list):
                    for item in v:
                        _require(
                            not isinstance(item, dict) and not isinstance(item, list),
                            f"extra[{k}]",
                            "nested containers forbidden (flat values only)",
                        )

        if source_type == "replay":
            replay_clock = object.__getattribute__(clock_ref, "replay")
            if replay_clock is None:
                raise ContractValidationError(
                    "[clock_ref.replay] invariant violation: source_type='replay' requires "
                    "clock_ref.replay is not None (Fail-closed FC-04)."
                )
            ts = object.__getattribute__(self, "timestamp")
            its = object.__getattribute__(self, "ingest_ts")
            if ts == its:
                raise ContractValidationError(
                    "[timestamp == ingest_ts] parity invariant violation: replay source "
                    "requires timestamp != ingest_ts (Fail-closed FC-05)."
                )


__all__ = ["CanonicalEventEnvelope"]
