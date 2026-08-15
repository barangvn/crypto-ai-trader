from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class ContractSchemaError(ValueError):
    """Raised when a canonical contract fails schema/type/value validation.

    All contract validation errors in this module (FeatureVector, MarketRegime,
    StrategyContext, StrategySignal, and their nested helpers) use this single
    exception type so tests can catch them uniformly.
    """


def _recursive_sorted(obj: Any) -> Any:
    """Produce a deterministically ordered, JSON-serialisable object.

    Rules:
    - Dataclasses => dict (recurse)
    - Dicts      => new dict with keys SORTED, values recursed
    - Lists      => list with each value recursed (order preserved — sequence IS data)
    - Tuples     => list (tuples treated as list for deterministic serialisation)
    - Sets/frozensets => sorted(list(...)) list for stable order
    - Enum       => .value (StrEnum => str, IntEnum => int, etc.)
    - Decimal    => str(decimal) — floats lose precision, so decimals are stringified
    - bytes      => hex() — raw bytes not stable in JSON default serialisation
    - Primitives => self (str/int/float/bool/None)
    """
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _recursive_sorted(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, (list, tuple)):
        return [_recursive_sorted(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted([_recursive_sorted(x) for x in obj], key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    if is_dataclass(obj):
        d = asdict(obj)
        return {k: _recursive_sorted(d[k]) for k in sorted(d.keys())}
    # Fallback: unknown type — repr() for determinism. Shouldn't trigger for contracts.
    return repr(obj)


def to_sorted_dict(obj: Any) -> dict[str, Any]:
    """Return the deterministic sorted dict representation of a contract instance."""
    if not is_dataclass(obj):
        raise ContractSchemaError("to_sorted_dict only supports dataclass contracts")
    return _recursive_sorted(obj)  # type: ignore[return-value]


def schema_sha256(obj: Any) -> str:
    """Return the lowercase hex SHA-256 digest of the deterministic JSON encoding.

    The digest is stable across calls for the same logical input (field order,
    enum names, decimal stringifications are all normalised before hashing).
    """
    sorted_repr = to_sorted_dict(obj)
    payload = json.dumps(sorted_repr, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deep_copy(obj: Any) -> Any:
    """Pure helper — wraps copy.deepcopy. Shared by contracts that need safe copies."""
    return copy.deepcopy(obj)
