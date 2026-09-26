from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


INSTANT_RGX_STR = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"
INSTANT_RGX = re.compile(INSTANT_RGX_STR)

SYMBOL_RGX_STR = r"^[A-Z0-9]{2,20}_[A-Z0-9]{2,12}$"
SYMBOL_RGX = re.compile(SYMBOL_RGX_STR)

EVENT_TYPE_RGX_STR = r"^[a-z_]+\.v[0-9]+$"
EVENT_TYPE_RGX = re.compile(EVENT_TYPE_RGX_STR)

ULID_CROCKFORD_RGX_STR = r"^[0-9A-HJKMNP-TV-Z]{26}$"
ULID_CROCKFORD_RGX = re.compile(ULID_CROCKFORD_RGX_STR)

UUID7_RGX_STR = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
UUID7_RGX = re.compile(UUID7_RGX_STR)

CONTRACT_VERSION_STR = "1.0.0"
SCHEMA_REF_CONTRACTS_MD = "CONTRACTS.md@1.0.0"
RUN_MODE_VALUES = ("paper", "backtest", "live")
SOURCE_TYPE_VALUES = (
    "live_ws",
    "historical_rest",
    "replay",
    "simulated",
    "synthetic",
    "static_fixture",
)
EXTRA_KEY_RGX_STR = r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$"
EXTRA_KEY_RGX = re.compile(EXTRA_KEY_RGX_STR)
QUALITY_CODE_MAX = 64
QUALITY_MESSAGE_MAX = 512


class ContractValidationError(ValueError):
    pass


def _require(condition: bool, field: str, reason: str) -> None:
    if not condition:
        raise ContractValidationError(f"[{field}] {reason}")


def validate_instant(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    _require(INSTANT_RGX.match(value) is not None, field, (
        "must match ISO-8601 UTC (Z suffix, optional 1-6 fractional digits), e.g. 2026-08-10T18:30:00Z or "
        "2026-08-10T18:30:00.123Z"
    ))
    return value


def validate_ulid_sortable(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    m_ulid = ULID_CROCKFORD_RGX.match(value)
    m_uuid7 = UUID7_RGX.match(value)
    _require((m_ulid is not None) or (m_uuid7 is not None), field, (
        "must be ULID (Crockford Base32 26 char uppercase) OR UUIDv7 string, e.g. "
        "01J5KX7YQJABCDEF0123456789 or 01926bfb-4f4b-78a9-8f3b-0a2c3d4e5f6a"
    ))
    return value


def validate_symbol_canonical(value: Any, field: str) -> str | None:
    if value is None:
        return None
    _require(isinstance(value, str), field, "must be str or None")
    _require(SYMBOL_RGX.match(value) is not None, field, (
        "must match BASE_QUOTE canonical form uppercase, e.g. BTC_USDT. "
        "BASE max 20 alnum uppercase, QUOTE max 12 alnum uppercase."
    ))
    return value


def validate_event_type(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    _require(EVENT_TYPE_RGX.match(value) is not None, field, (
        "must match snake_case noun with MAJOR version suffix, e.g. market_tick.v1"
    ))
    return value


def validate_contract_version(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    _require(value == CONTRACT_VERSION_STR, field, (
        f"must be literal '{CONTRACT_VERSION_STR}' (fail-closed: contract_version mismatch)"
    ))
    return value


def validate_run_mode(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    _require(value in RUN_MODE_VALUES, field, (
        f"must be one of {RUN_MODE_VALUES}"
    ))
    return value


def validate_source_type(value: Any, field: str) -> str:
    _require(isinstance(value, str), field, "must be str")
    _require(value in SOURCE_TYPE_VALUES, field, (
        f"must be one of {SOURCE_TYPE_VALUES}"
    ))
    return value


def validate_nonempty_str(value: Any, field: str, max_len: int = 256) -> str:
    _require(isinstance(value, str), field, "must be str")
    stripped = value
    _require(len(stripped) >= 1, field, "must be non-empty string")
    _require(len(stripped) <= max_len, field, f"max length {max_len}")
    return stripped


@dataclass(frozen=True)
class QualityReason:
    code: str
    message: str = ""
    context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        validate_nonempty_str(object.__getattribute__(self, "code"), "QualityReason.code", QUALITY_CODE_MAX)
        msg = object.__getattribute__(self, "message")
        if not isinstance(msg, str):
            raise ContractValidationError("[QualityReason.message] must be str")
        if len(msg) > QUALITY_MESSAGE_MAX:
            raise ContractValidationError(
                f"[QualityReason.message] max length {QUALITY_MESSAGE_MAX}"
            )
        ctx = object.__getattribute__(self, "context")
        if ctx is not None and not isinstance(ctx, dict):
            raise ContractValidationError("[QualityReason.context] must be dict or None")
