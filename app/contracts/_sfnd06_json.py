"""S-FND-06 canonical JSON serialization (CAP-SER-01 / CAP-SER-08).

Internal helper module. stdlib only (`json`, `dataclasses`, `decimal`, `typing`).
No 3rd party. No I/O. No network. No wall-clock source.

Determinism contract:
  - `canonical_json` always emits `sort_keys=True` (top-level AND every nested
    dict), compact separators `(",", ":")`, no indent, no NaN/Inf.
  - Decimal -> `str(decimal)` (OD-06-02 DEFAULT: preserve original string, no
    normalisation).
  - Unknown types (datetime, set, custom class, bytes, ...) -> FAIL CLOSED
    (`CanonicalSerializationError`), never a silent `default(o)` fallback.
  - Circular references -> FAIL CLOSED (never silently truncated).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any


class CanonicalSerializationError(ValueError):
    """Fail-closed helper exception; catchable as ValueError."""


def _fail(message: str) -> "CanonicalSerializationError":
    return CanonicalSerializationError(message)


def _walk(obj: Any, active: set[int]) -> Any:
    """Return a JSON-native mirror of obj with deep-sorted dict keys.

    Raises CanonicalSerializationError for any value that cannot be represented
    deterministically (FC-09 unknown type, FC-10 circular reference).
    """
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)

    if is_dataclass(obj) and not isinstance(obj, type):
        oid = id(obj)
        if oid in active:
            raise _fail(
                "circular reference detected while serializing dataclass "
                f"{type(obj).__name__!r}"
            )
        active.add(oid)
        try:
            as_dict = asdict(obj)
        finally:
            active.discard(oid)
        return _walk(as_dict, active)

    if isinstance(obj, dict):
        oid = id(obj)
        if oid in active:
            raise _fail("circular reference detected while serializing dict")
        active.add(oid)
        try:
            out: dict[str, Any] = {}
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise _fail(
                        "canonical JSON requires str object keys; got "
                        f"{type(key).__name__}"
                    )
                out[key] = _walk(value, active)
        finally:
            active.discard(oid)
        return out

    if isinstance(obj, (list, tuple)):
        oid = id(obj)
        if oid in active:
            raise _fail("circular reference detected while serializing sequence")
        active.add(oid)
        try:
            return [_walk(item, active) for item in obj]
        finally:
            active.discard(oid)

    raise _fail(
        "unsupported type for canonical JSON: "
        f"{type(obj).__module__}.{type(obj).__qualname__} (fail-closed FC-09)"
    )


def canonical_json(obj: Any, /) -> bytes:
    """Return deterministic, canonical JSON bytes for obj.

    Rules: sort_keys=True (deep), separators=(",", ":"), no indent,
    Decimal -> str (no exponent handling beyond str()), datetime disallowed
    (must be an Instant string), None -> null, bool lowercase,
    dataclass -> asdict, circular reference -> raise,
    unknown type -> raise.
    """
    normalized = _walk(obj, set())
    try:
        text = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise _fail(f"canonical_json serialization failed: {exc}") from exc
    return text.encode("utf-8")


def canonical_loads(raw: bytes | bytearray | str, /) -> Any:
    """Inverse of :func:`canonical_json`; stdlib `json.loads` (strict=True)."""
    if not isinstance(raw, (bytes, bytearray, str)):
        raise _fail(
            "canonical_loads expects bytes, bytearray or str; got "
            f"{type(raw).__name__}"
        )
    if isinstance(raw, bytearray):
        raw = bytes(raw)
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _fail(f"canonical_loads parse failed: {exc}") from exc


def canonical_json_equal(a: Any, b: Any, /) -> bool:
    """CAP-SER-08: deterministic JSON equality — `canonical_json(a) == canonical_json(b)`."""
    return canonical_json(a) == canonical_json(b)


__all__ = [
    "CanonicalSerializationError",
    "canonical_json",
    "canonical_loads",
    "canonical_json_equal",
]
