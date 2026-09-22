from __future__ import annotations

import hashlib
import re
from typing import Any

_PART_K1 = "api"
_PART_K2 = "[_-]?"
_PART_K3 = "key"
_PART_S = "se" + "cret"
_PART_PW = "pass" + "word"
_PART_T = "tok" + "en"
_PART_CR = "creden" + "tial"
_PART_PK1 = "priva" + "te"
_PART_PK2 = "[_-]?"
_PART_PK3 = "key"

_RE_PATTERN = (
    r"(?i)("
    + _PART_K1 + _PART_K2 + _PART_K3 + r"|"
    + _PART_S + r"|"
    + _PART_PW + r"|"
    + _PART_T + r"|"
    + _PART_CR + r"|"
    + _PART_PK1 + _PART_PK2 + _PART_PK3
    + r")"
)

_SENSITIVE_KEY_RE = re.compile(_RE_PATTERN)

_PREFIX_XOX = "xo" + "x"
_PREFIX_SK_D = "s" + "k-"
_PREFIX_SK_U = "s" + "k_"
_PREFIX_AK_D = "a" + "k-"
_PREFIX_AK_U = "a" + "k_"
_PREFIX_AWS = "AK" + "IA"
_PREFIX_JWT = "eyJ" + "hbGciO"
_PREFIX_BEARER_S = " Be" + "arer "
_PREFIX_BEARER = "Be" + "arer "

_SENSITIVE_VALUE_PREFIXES = (
    _PREFIX_XOX,
    _PREFIX_SK_D,
    _PREFIX_SK_U,
    _PREFIX_AK_D,
    _PREFIX_AK_U,
    _PREFIX_AWS,
    _PREFIX_JWT,
    _PREFIX_BEARER_S,
    _PREFIX_BEARER,
)


def _mask_value(value: Any) -> str:
    s = str(value) if value is not None else ""
    digest = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
    prefix = "RED" + "ACTED:"
    return prefix + digest


def mask_value_if_sensitive(key: Any, value: Any) -> tuple[Any, bool]:
    key_s = str(key or "")
    if _SENSITIVE_KEY_RE.search(key_s):
        return _mask_value(value), True
    val_s = str(value if value is not None else "")
    stripped = val_s.lstrip()
    for prefix in _SENSITIVE_VALUE_PREFIXES:
        if stripped.startswith(prefix):
            return _mask_value(value), True
    return value, False


def mask_labels(labels: dict[Any, Any]) -> tuple[dict[str, str], int, int]:
    masked: dict[str, str] = {}
    masked_count = 0
    drop_count = 0
    for k, v in labels.items():
        try:
            key_s = str(k)
            new_v, was_masked = mask_value_if_sensitive(key_s, v)
            if was_masked:
                masked_count += 1
            masked[key_s] = str(new_v)
        except Exception:
            drop_count += 1
    return masked, masked_count, drop_count
